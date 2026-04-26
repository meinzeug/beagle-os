"""GPU assignment mode service — GoEnterprise Plan 10.

Implements three GPU assignment modes for libvirt/KVM VMs:

  - passthrough: Exclusive PCI passthrough (highest performance, one VM)
  - timeslice:   Shared GPU via CUDA time-slicing (multiple VMs, one physical GPU)
  - vgpu:        NVIDIA vGPU via mdev (hardware-isolated per-VM GPU partition)

All privileged sysfs/virsh calls are injected for testability.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Callable

_PCI_ADDR_RE = re.compile(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Maximum number of VMs allowed to share one GPU in timeslice mode.
MAX_TIMESLICE_VMS = 8


def _validate_pci_addr(pci_address: str) -> str:
    addr = str(pci_address or "").strip().lower()
    if not _PCI_ADDR_RE.match(addr):
        raise ValueError(f"invalid PCI address: {pci_address!r}")
    return addr


def _validate_uuid(value: str) -> str:
    val = str(value or "").strip().lower()
    if not _UUID_RE.match(val):
        raise ValueError(f"invalid UUID: {value!r}")
    return val


def _validate_gpu_id(gpu_id: str) -> str:
    val = str(gpu_id or "").strip()
    if not val or "/" in val or ".." in val:
        raise ValueError(f"invalid gpu_id: {gpu_id!r}")
    return val


def _validate_vmid(vmid: Any) -> int:
    try:
        val = int(vmid)
    except (TypeError, ValueError):
        raise ValueError(f"invalid vmid: {vmid!r}")
    if val <= 0:
        raise ValueError(f"vmid must be positive, got {vmid!r}")
    return val


class GpuAssignmentModeService:
    """Unified service for all three GPU assignment modes.

    Parameters
    ----------
    run_virsh:
        Callable(args) → stdout string.  Used for domstate / dumpxml.
    define_domain_xml:
        Callable(xml_str) → None.  Calls ``virsh define``.
    libvirt_domain_name:
        Callable(vmid) → domain name string.
    sysfs_write:
        Callable(path, value) → None.  Writes to sysfs for vfio binding.
        Defaults to ``Path(path).write_text(value)``.
    sys_bus_pci_root:
        Override for ``/sys/bus/pci`` (test injection).
    list_timeslice_assignments:
        Callable() → list[dict].  Returns existing time-slice assignments so
        the service can enforce the MAX_TIMESLICE_VMS limit.  Optional.
    save_timeslice_assignment:
        Callable(gpu_id, vmid) → None.  Persists a time-slice assignment.
    remove_timeslice_assignment:
        Callable(gpu_id, vmid) → None.  Removes a time-slice assignment.
    """

    def __init__(
        self,
        *,
        run_virsh: Callable[[list[str]], str],
        define_domain_xml: Callable[[str], None],
        libvirt_domain_name: Callable[[int], str],
        sysfs_write: Callable[[str, str], None] | None = None,
        sys_bus_pci_root: str | None = None,
        list_timeslice_assignments: Callable[[], list[dict[str, Any]]] | None = None,
        save_timeslice_assignment: Callable[[str, int], None] | None = None,
        remove_timeslice_assignment: Callable[[str, int], None] | None = None,
    ) -> None:
        from pathlib import Path

        self._run_virsh = run_virsh
        self._define_domain_xml = define_domain_xml
        self._libvirt_domain_name = libvirt_domain_name
        self._sysfs_write: Callable[[str, str], None] = sysfs_write or (
            lambda p, v: Path(p).write_text(v)
        )
        self._sys_bus_pci_root = str(sys_bus_pci_root or "/sys/bus/pci")
        self._list_timeslice_assignments = list_timeslice_assignments or (lambda: [])
        self._save_timeslice_assignment = save_timeslice_assignment or (lambda g, v: None)
        self._remove_timeslice_assignment = remove_timeslice_assignment or (lambda g, v: None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _vm_state(self, vmid: int) -> str:
        try:
            return self._run_virsh(["domstate", self._libvirt_domain_name(vmid)]).strip().lower()
        except Exception:
            return "unknown"

    def _dump_xml(self, vmid: int) -> str:
        return self._run_virsh(["dumpxml", self._libvirt_domain_name(vmid)])

    @staticmethod
    def _hostdev_pci(domain_hex: int, bus_hex: int, slot_hex: int, func_hex: int) -> ET.Element:
        hostdev = ET.Element("hostdev", {"mode": "subsystem", "type": "pci", "managed": "yes"})
        source = ET.SubElement(hostdev, "source")
        ET.SubElement(
            source,
            "address",
            {
                "domain": f"0x{domain_hex:04x}",
                "bus": f"0x{bus_hex:02x}",
                "slot": f"0x{slot_hex:02x}",
                "function": f"0x{func_hex:x}",
            },
        )
        return hostdev

    @staticmethod
    def _hostdev_mdev(mdev_uuid: str) -> ET.Element:
        """Return a <hostdev> element for an NVIDIA vGPU (mdev device)."""
        hostdev = ET.Element(
            "hostdev",
            {
                "mode": "subsystem",
                "type": "mdev",
                "model": "vfio-pci",
                "managed": "no",
            },
        )
        source = ET.SubElement(hostdev, "source")
        ET.SubElement(source, "address", {"uuid": mdev_uuid})
        return hostdev

    def _parse_pci(self, addr: str) -> tuple[int, int, int, int]:
        parts = addr.split(":")
        domain = int(parts[0], 16)
        bus = int(parts[1], 16)
        slot_func = parts[2].split(".")
        return domain, bus, int(slot_func[0], 16), int(slot_func[1])

    def _bind_vfio(self, addr: str) -> list[str]:
        """Bind a PCI device to vfio-pci.  Returns any non-fatal warnings."""
        warnings: list[str] = []
        pci_dev = f"{self._sys_bus_pci_root}/devices/{addr}"
        try:
            self._sysfs_write(f"{pci_dev}/driver/unbind", addr)
        except OSError:
            pass  # no driver bound — expected
        except Exception as exc:
            warnings.append(f"driver unbind: {exc}")
        try:
            self._sysfs_write(f"{pci_dev}/driver_override", "vfio-pci")
        except Exception as exc:
            warnings.append(f"driver_override: {exc}")
        try:
            self._sysfs_write(f"{self._sys_bus_pci_root}/drivers/vfio-pci/bind", addr)
        except Exception as exc:
            warnings.append(f"vfio-pci bind: {exc}")
        return warnings

    def _unbind_vfio(self, addr: str) -> list[str]:
        """Unbind vfio-pci and reprobes original driver.  Returns warnings."""
        warnings: list[str] = []
        pci_dev = f"{self._sys_bus_pci_root}/devices/{addr}"
        try:
            self._sysfs_write(f"{pci_dev}/driver/unbind", addr)
        except OSError:
            pass
        except Exception as exc:
            warnings.append(f"vfio-pci unbind: {exc}")
        try:
            self._sysfs_write(f"{pci_dev}/driver_override", "\n")
        except Exception as exc:
            warnings.append(f"driver_override reset: {exc}")
        try:
            self._sysfs_write(f"{self._sys_bus_pci_root}/drivers_probe", addr)
        except Exception as exc:
            warnings.append(f"drivers_probe: {exc}")
        return warnings

    # ------------------------------------------------------------------
    # Mode 1: Passthrough  (exclusive PCI device assignment)
    # ------------------------------------------------------------------

    def assign_passthrough(self, pci_address: str, vmid: Any) -> dict[str, Any]:
        """Assign an entire GPU to a stopped VM via PCI passthrough.

        The GPU is bound to vfio-pci on the host, then added as a <hostdev>
        in the libvirt domain XML.  The VM must be shut off.

        Returns ``{"ok": True, "mode": "passthrough", ...}`` on success.
        """
        try:
            addr = _validate_pci_addr(pci_address)
            vid = _validate_vmid(vmid)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        state = self._vm_state(vid)
        if state not in ("shut off", "shutoff", "unknown"):
            return {
                "ok": False,
                "error": f"VM {vid} must be shut off (state: {state!r})",
            }

        try:
            xml_text = self._dump_xml(vid)
            root = ET.fromstring(xml_text)
        except Exception as exc:
            return {"ok": False, "error": f"failed to read VM XML: {exc}"}

        d, b, s, f = self._parse_pci(addr)

        # Idempotency: already assigned?
        for hd in root.iter("hostdev"):
            if hd.get("type") != "pci":
                continue
            src = hd.find("source/address")
            if src is not None:
                if (
                    int(src.get("domain", "0"), 16) == d
                    and int(src.get("bus", "0"), 16) == b
                    and int(src.get("slot", "0"), 16) == s
                    and int(src.get("function", "0"), 16) == f
                ):
                    return {"ok": False, "error": f"GPU {addr} already assigned to VM {vid}"}

        devices = root.find("devices")
        if devices is None:
            return {"ok": False, "error": "VM XML has no <devices> element"}

        warnings = self._bind_vfio(addr)
        devices.append(self._hostdev_pci(d, b, s, f))

        try:
            self._define_domain_xml(ET.tostring(root, encoding="unicode"))
        except Exception as exc:
            return {"ok": False, "error": f"failed to update VM XML: {exc}"}

        result: dict[str, Any] = {"ok": True, "mode": "passthrough", "pci_address": addr, "vmid": vid}
        if warnings:
            result["sysfs_warnings"] = warnings
        return result

    def release_passthrough(self, pci_address: str, vmid: Any) -> dict[str, Any]:
        """Remove a passthrough GPU assignment from a stopped VM."""
        try:
            addr = _validate_pci_addr(pci_address)
            vid = _validate_vmid(vmid)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        state = self._vm_state(vid)
        if state not in ("shut off", "shutoff", "unknown"):
            return {"ok": False, "error": f"VM {vid} must be shut off (state: {state!r})"}

        try:
            xml_text = self._dump_xml(vid)
            root = ET.fromstring(xml_text)
        except Exception as exc:
            return {"ok": False, "error": f"failed to read VM XML: {exc}"}

        d, b, s, f = self._parse_pci(addr)
        devices = root.find("devices")
        if devices is None:
            return {"ok": False, "error": "VM XML has no <devices> element"}

        to_remove: ET.Element | None = None
        for hd in devices.findall("hostdev"):
            if hd.get("type") != "pci":
                continue
            src = hd.find("source/address")
            if src is not None and (
                int(src.get("domain", "0"), 16) == d
                and int(src.get("bus", "0"), 16) == b
                and int(src.get("slot", "0"), 16) == s
                and int(src.get("function", "0"), 16) == f
            ):
                to_remove = hd
                break

        if to_remove is None:
            return {"ok": False, "error": f"GPU {addr} not assigned to VM {vid}"}

        devices.remove(to_remove)
        try:
            self._define_domain_xml(ET.tostring(root, encoding="unicode"))
        except Exception as exc:
            return {"ok": False, "error": f"failed to update VM XML: {exc}"}

        warnings = self._unbind_vfio(addr)
        result: dict[str, Any] = {"ok": True, "mode": "passthrough", "pci_address": addr, "vmid": vid}
        if warnings:
            result["sysfs_warnings"] = warnings
        return result

    # ------------------------------------------------------------------
    # Mode 2: Time-Slicing  (shared GPU, software-level sharing)
    # ------------------------------------------------------------------

    def assign_timeslice(self, gpu_id: str, vmid: Any) -> dict[str, Any]:
        """Register a VM for shared GPU access via CUDA time-slicing.

        Time-slicing does *not* require vfio-pci binding on the host.  Instead,
        the same passthrough device is made available to multiple VMs through
        NVIDIA's time-slicing feature (configured via ``/etc/nvidia/...`` or the
        device-plugin on the host).

        This service layer:
        1. Validates arguments.
        2. Enforces the MAX_TIMESLICE_VMS cap.
        3. Persists the assignment (injected ``save_timeslice_assignment``).

        Actual driver configuration (nvidia-smi timeslicing or
        ``/etc/nvidia/container-runtime/config.toml``) is performed by a
        separate host-level provisioning step outside libvirt XML.

        Returns ``{"ok": True, "mode": "timeslice", ...}``.
        """
        try:
            gid = _validate_gpu_id(gpu_id)
            vid = _validate_vmid(vmid)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        existing = self._list_timeslice_assignments()
        gpu_vms = [a for a in existing if str(a.get("gpu_id")) == gid]

        if any(str(a.get("vmid")) == str(vid) for a in gpu_vms):
            return {"ok": False, "error": f"VM {vid} is already in timeslice pool for GPU {gid!r}"}

        if len(gpu_vms) >= MAX_TIMESLICE_VMS:
            return {
                "ok": False,
                "error": (
                    f"GPU {gid!r} already has {len(gpu_vms)} VMs assigned"
                    f" (max {MAX_TIMESLICE_VMS})"
                ),
            }

        try:
            self._save_timeslice_assignment(gid, vid)
        except Exception as exc:
            return {"ok": False, "error": f"failed to save timeslice assignment: {exc}"}

        return {
            "ok": True,
            "mode": "timeslice",
            "gpu_id": gid,
            "vmid": vid,
            "slot": len(gpu_vms) + 1,
            "total_slots": len(gpu_vms) + 1,
        }

    def release_timeslice(self, gpu_id: str, vmid: Any) -> dict[str, Any]:
        """Remove a VM from the time-slicing pool for a given GPU."""
        try:
            gid = _validate_gpu_id(gpu_id)
            vid = _validate_vmid(vmid)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        existing = self._list_timeslice_assignments()
        if not any(str(a.get("gpu_id")) == gid and str(a.get("vmid")) == str(vid) for a in existing):
            return {"ok": False, "error": f"VM {vid} not in timeslice pool for GPU {gid!r}"}

        try:
            self._remove_timeslice_assignment(gid, vid)
        except Exception as exc:
            return {"ok": False, "error": f"failed to remove timeslice assignment: {exc}"}

        return {"ok": True, "mode": "timeslice", "gpu_id": gid, "vmid": vid}

    # ------------------------------------------------------------------
    # Mode 3: vGPU  (NVIDIA mdev — hardware-isolated GPU partition)
    # ------------------------------------------------------------------

    def assign_vgpu(self, mdev_uuid: str, vmid: Any) -> dict[str, Any]:
        """Assign an NVIDIA vGPU mdev device to a VM.

        The mdev device must be pre-created on the host via:
            ``mdevctl start -u <uuid> -p <parent_pci> -t <vgpu_type>``

        This method adds the <hostdev type="mdev"> element to the libvirt
        domain XML so the VM sees an isolated GPU partition.  The VM may be
        in any non-running state for a persistent config change.

        Returns ``{"ok": True, "mode": "vgpu", ...}``.
        """
        try:
            uuid = _validate_uuid(mdev_uuid)
            vid = _validate_vmid(vmid)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        state = self._vm_state(vid)
        if state not in ("shut off", "shutoff", "unknown"):
            return {"ok": False, "error": f"VM {vid} must be shut off (state: {state!r})"}

        try:
            xml_text = self._dump_xml(vid)
            root = ET.fromstring(xml_text)
        except Exception as exc:
            return {"ok": False, "error": f"failed to read VM XML: {exc}"}

        # Idempotency: already assigned?
        for hd in root.iter("hostdev"):
            if hd.get("type") != "mdev":
                continue
            src = hd.find("source/address")
            if src is not None and src.get("uuid", "").lower() == uuid:
                return {"ok": False, "error": f"vGPU {uuid} already assigned to VM {vid}"}

        devices = root.find("devices")
        if devices is None:
            return {"ok": False, "error": "VM XML has no <devices> element"}

        devices.append(self._hostdev_mdev(uuid))

        try:
            self._define_domain_xml(ET.tostring(root, encoding="unicode"))
        except Exception as exc:
            return {"ok": False, "error": f"failed to update VM XML: {exc}"}

        return {"ok": True, "mode": "vgpu", "mdev_uuid": uuid, "vmid": vid}

    def release_vgpu(self, mdev_uuid: str, vmid: Any) -> dict[str, Any]:
        """Remove an NVIDIA vGPU assignment from a VM."""
        try:
            uuid = _validate_uuid(mdev_uuid)
            vid = _validate_vmid(vmid)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        state = self._vm_state(vid)
        if state not in ("shut off", "shutoff", "unknown"):
            return {"ok": False, "error": f"VM {vid} must be shut off (state: {state!r})"}

        try:
            xml_text = self._dump_xml(vid)
            root = ET.fromstring(xml_text)
        except Exception as exc:
            return {"ok": False, "error": f"failed to read VM XML: {exc}"}

        devices = root.find("devices")
        if devices is None:
            return {"ok": False, "error": "VM XML has no <devices> element"}

        to_remove: ET.Element | None = None
        for hd in devices.findall("hostdev"):
            if hd.get("type") != "mdev":
                continue
            src = hd.find("source/address")
            if src is not None and src.get("uuid", "").lower() == uuid:
                to_remove = hd
                break

        if to_remove is None:
            return {"ok": False, "error": f"vGPU {uuid} not assigned to VM {vid}"}

        devices.remove(to_remove)
        try:
            self._define_domain_xml(ET.tostring(root, encoding="unicode"))
        except Exception as exc:
            return {"ok": False, "error": f"failed to update VM XML: {exc}"}

        return {"ok": True, "mode": "vgpu", "mdev_uuid": uuid, "vmid": vid}
