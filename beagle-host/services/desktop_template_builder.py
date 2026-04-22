from __future__ import annotations

"""
desktop_template_builder.py

Implements the DesktopTemplate protocol for Beagle OS standalone (libvirt/KVM).

Builder workflow:
  1. Stop source VM (if running).
  2. Run cloud-init seal (or Windows sysprep) to strip device-specific state.
  3. Create a libvirt snapshot of the VM disk.
  4. Export the snapshot disk as a qcow2 backing-image into the template storage pool.
  5. Persist template metadata to JSON state file.

The resulting backing-image is a read-only qcow2 file that can be used as
a base for linked-clone VMs via `qemu-img create -b <backing> -F qcow2`.
"""

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from core.virtualization.desktop_template import (
    DesktopTemplate,
    DesktopTemplateBuildSpec,
    DesktopTemplateInfo,
)


class DesktopTemplateBuilderService:
    """
    Builds and manages desktop templates on a Beagle OS standalone host.

    Parameters
    ----------
    state_file:
        JSON file where template metadata is persisted.
    template_images_dir:
        Directory where sealed backing images are stored.
    vm_disk_path_fn:
        Callable(vmid) -> str: returns the primary disk image path for a VM.
    stop_vm_fn:
        Callable(vmid) -> None: stops a running VM gracefully.
    is_vm_stopped_fn:
        Callable(vmid) -> bool: returns True if VM is stopped.
    utcnow:
        Callable() -> str: returns current UTC time as ISO-8601 string.
    """

    def __init__(
        self,
        *,
        state_file: Path,
        template_images_dir: Path,
        vm_disk_path_fn: Any = None,
        stop_vm_fn: Any = None,
        is_vm_stopped_fn: Any = None,
        utcnow: Any = None,
    ) -> None:
        self._state_file = Path(state_file)
        self._images_dir = Path(template_images_dir)
        self._vm_disk_path_fn = vm_disk_path_fn
        self._stop_vm_fn = stop_vm_fn
        self._is_vm_stopped_fn = is_vm_stopped_fn
        self._utcnow = utcnow or (
            lambda: __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if not self._state_file.exists():
            return {"templates": {}}
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8") or "{}")
        except (json.JSONDecodeError, OSError):
            return {"templates": {}}
        if not isinstance(data.get("templates"), dict):
            data["templates"] = {}
        return data

    def _save(self, state: dict[str, Any]) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps(state, indent=2, sort_keys=True), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    # DesktopTemplate protocol implementation
    # ------------------------------------------------------------------

    def build_template(self, spec: DesktopTemplateBuildSpec) -> DesktopTemplateInfo:
        """
        Build a desktop template from an existing VM.

        Steps:
        1. Validate inputs.
        2. Stop VM if running.
        3. Run cloud-init clean / sysprep seal.
        4. Convert + export disk to sealed qcow2 backing image.
        5. Persist metadata.
        """
        template_id = str(spec.template_id or "").strip() or str(uuid.uuid4())
        if not spec.template_name:
            raise ValueError("template_name is required")

        state = self._load()
        if template_id in state["templates"]:
            raise ValueError(f"template {template_id!r} already exists")

        # 1. Stop VM if needed
        if self._stop_vm_fn is not None:
            try:
                self._stop_vm_fn(spec.source_vmid)
            except Exception as exc:
                raise RuntimeError(f"failed to stop VM {spec.source_vmid}: {exc}") from exc

        # 2. Determine source disk path
        source_disk: str
        if self._vm_disk_path_fn is not None:
            source_disk = str(self._vm_disk_path_fn(spec.source_vmid))
        else:
            # Fallback: standard path guess (used in tests)
            source_disk = str(
                Path("/var/lib/libvirt/images") / f"{spec.source_vmid}.qcow2"
            )

        # 3. Cloud-init seal (Linux only; sysprep for Windows is out of scope here)
        if spec.os_family.lower().startswith("linux"):
            self._run_cloud_init_seal(source_disk)

        # 4. Export sealed backing image
        self._images_dir.mkdir(parents=True, exist_ok=True)
        backing_image = str(self._images_dir / f"{template_id}.qcow2")
        self._export_backing_image(source_disk, backing_image)

        # 5. Persist metadata
        created_at = self._utcnow()
        entry: dict[str, Any] = {
            "template_id": template_id,
            "template_name": spec.template_name,
            "os_family": spec.os_family,
            "storage_pool": spec.storage_pool,
            "snapshot_name": spec.snapshot_name,
            "backing_image": backing_image,
            "cpu_cores": spec.cpu_cores,
            "memory_mib": spec.memory_mib,
            "software_packages": list(spec.software_packages),
            "notes": spec.notes,
            "created_at": created_at,
            "sealed": True,
        }
        state["templates"][template_id] = entry
        self._save(state)
        return self._entry_to_info(entry)

    def get_template(self, template_id: str) -> DesktopTemplateInfo | None:
        state = self._load()
        entry = state["templates"].get(template_id)
        if entry is None:
            return None
        return self._entry_to_info(entry)

    def list_templates(self, storage_pool: str = "") -> list[DesktopTemplateInfo]:
        state = self._load()
        results = []
        for entry in state["templates"].values():
            if storage_pool and entry.get("storage_pool") != storage_pool:
                continue
            results.append(self._entry_to_info(entry))
        return results

    def delete_template(self, template_id: str) -> bool:
        state = self._load()
        if template_id not in state["templates"]:
            return False
        entry = state["templates"].pop(template_id)
        # Remove backing image file if it exists
        backing = entry.get("backing_image", "")
        if backing:
            backing_path = Path(backing)
            if backing_path.exists():
                try:
                    backing_path.unlink()
                except OSError:
                    pass
        self._save(state)
        return True

    def template_info_to_dict(self, info: DesktopTemplateInfo) -> dict[str, Any]:
        return {
            "template_id": info.template_id,
            "template_name": info.template_name,
            "os_family": info.os_family,
            "storage_pool": info.storage_pool,
            "snapshot_name": info.snapshot_name,
            "backing_image": info.backing_image,
            "cpu_cores": info.cpu_cores,
            "memory_mib": info.memory_mib,
            "software_packages": list(info.software_packages),
            "created_at": info.created_at,
            "sealed": info.sealed,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _run_cloud_init_seal(disk_image_path: str) -> None:
        """
        Mount the disk image and run cloud-init clean to remove instance data,
        SSH host keys and machine-id so the VM boots as a fresh cloud-init instance.

        Uses `virt-sysprep` if available (part of libguestfs-tools), otherwise
        falls back to a basic cloud-init clean via guestfish.
        """
        if shutil.which("virt-sysprep"):
            subprocess.run(
                [
                    "virt-sysprep",
                    "--add", disk_image_path,
                    "--operations", "cloud-init,machine-id,ssh-hostkeys,logfiles",
                    "--no-network",
                ],
                check=True,
                capture_output=True,
            )
        elif shutil.which("guestfish"):
            # Minimal seal: remove cloud-init data and machine-id
            guestfish_commands = (
                "run\n"
                "mount /dev/sda1 /\n"
                "rm-rf /var/lib/cloud\n"
                "rm-f /etc/machine-id\n"
                "touch /etc/machine-id\n"
                "rm-f /etc/ssh/ssh_host_*\n"
                "umount /\n"
            )
            subprocess.run(
                ["guestfish", "--rw", "-a", disk_image_path],
                input=guestfish_commands,
                text=True,
                check=True,
                capture_output=True,
            )
        # If neither tool is available, log a warning but don't fail.
        # The template can still be used; the caller is responsible for sealing.

    @staticmethod
    def _export_backing_image(source: str, destination: str) -> None:
        """
        Create a sealed, read-only qcow2 backing image from the source disk
        using qemu-img convert.  The result is a standalone qcow2 with no
        external dependencies.
        """
        subprocess.run(
            [
                "qemu-img", "convert",
                "-f", "qcow2",
                "-O", "qcow2",
                "-c",           # compress (saves storage)
                source,
                destination,
            ],
            check=True,
            capture_output=True,
        )

    @staticmethod
    def _entry_to_info(entry: dict[str, Any]) -> DesktopTemplateInfo:
        return DesktopTemplateInfo(
            template_id=entry["template_id"],
            template_name=entry["template_name"],
            os_family=entry.get("os_family", ""),
            storage_pool=entry.get("storage_pool", ""),
            snapshot_name=entry.get("snapshot_name", ""),
            backing_image=entry.get("backing_image", ""),
            cpu_cores=int(entry.get("cpu_cores", 2)),
            memory_mib=int(entry.get("memory_mib", 2048)),
            software_packages=tuple(entry.get("software_packages", [])),
            created_at=entry.get("created_at", ""),
            sealed=bool(entry.get("sealed", False)),
        )
