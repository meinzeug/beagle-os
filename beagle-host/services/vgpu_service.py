"""NVIDIA Mediated Devices (vGPU / mdev) and Intel SR-IOV service.

Hardware requirements for NVIDIA vGPU (mdev):
  - NVIDIA GPU with vGPU support (e.g. A-series, T4, L4, RTX 4000+)
  - NVIDIA vGPU host driver (proprietary, requires NVIDIA license for enterprise)
  - kernel modules: nvidia, nvidia_vgpu_vfio
  - IOMMU enabled in BIOS and kernel (intel_iommu=on or amd_iommu=on)

Hardware requirements for Intel SR-IOV vGPU:
  - Intel Arc / Xe-LP / Xe-HPG discrete GPU or integrated Xe-LP (e.g. Tiger Lake+)
  - kernel 6.2+ with i915 SR-IOV patches, or linux-oem-22.04 / Ubuntu HWE
  - module parameters: i915.enable_guc=3 i915.max_vfs=<n>
  - IOMMU enabled

Both features are detected automatically at runtime via sysfs.
If neither mdev bus nor sriov_totalvfs is present the service returns
empty lists, which is the expected state on any non-GPU or GPU-only host.
"""
from __future__ import annotations

import uuid as _uuid_mod
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

_UUID_RE_STR = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
import re as _re
_UUID_RE = _re.compile(r"^" + _UUID_RE_STR + r"$", _re.IGNORECASE)
_PCI_ADDR_RE = _re.compile(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$")


class VgpuService:
    """NVIDIA mdev instance lifecycle manager.

    All sysfs I/O is injected so the service is fully testable without
    real hardware.  The live defaults read/write the real sysfs paths.
    """

    def __init__(
        self,
        *,
        run_virsh: Callable[[list[str]], str],
        define_domain_xml: Callable[[str], None],
        libvirt_domain_name: Callable[[int], str],
        sysfs_read: Callable[[str], str] | None = None,
        sysfs_write: Callable[[str, str], None] | None = None,
        listdir: Callable[[str], list[str]] | None = None,
        exists: Callable[[str], bool] | None = None,
        sys_class_mdev_bus: str | None = None,
        sys_bus_mdev: str | None = None,
    ) -> None:
        self._run_virsh = run_virsh
        self._define_domain_xml = define_domain_xml
        self._libvirt_domain_name = libvirt_domain_name
        self._sysfs_read = sysfs_read or self._default_read
        self._sysfs_write = sysfs_write or self._default_write
        self._listdir = listdir or self._default_listdir
        self._exists = exists or (lambda p: Path(p).exists())
        self._mdev_bus_root = str(sys_class_mdev_bus or "/sys/class/mdev_bus")
        self._bus_mdev_root = str(sys_bus_mdev or "/sys/bus/mdev/devices")

    @staticmethod
    def _default_read(path: str) -> str:
        return Path(path).read_text().strip()

    @staticmethod
    def _default_write(path: str, value: str) -> None:
        Path(path).write_text(value)

    @staticmethod
    def _default_listdir(path: str) -> list[str]:
        p = Path(path)
        if not p.exists():
            return []
        return [child.name for child in p.iterdir()]

    # ------------------------------------------------------------------
    # mdev type discovery
    # ------------------------------------------------------------------

    def list_mdev_types(self, gpu_pci: str | None = None) -> list[dict[str, Any]]:
        """Return available mdev types for all (or one) GPU.

        Each entry has: gpu_pci, type_id, name, description,
        available_instances, max_instances.
        """
        result: list[dict[str, Any]] = []
        for bus_dev in self._listdir(self._mdev_bus_root):
            # bus_dev is the PCI address
            if gpu_pci and str(bus_dev).lower() != str(gpu_pci).lower():
                continue
            types_path = f"{self._mdev_bus_root}/{bus_dev}/mdev_supported_types"
            for type_id in self._listdir(types_path):
                type_path = f"{types_path}/{type_id}"
                name = self._safe_read(f"{type_path}/name")
                description = self._safe_read(f"{type_path}/description")
                available = self._safe_read_int(f"{type_path}/available_instances")
                max_inst = self._safe_read_int(f"{type_path}/max_instances", available)
                result.append(
                    {
                        "gpu_pci": str(bus_dev),
                        "type_id": str(type_id),
                        "name": name,
                        "description": description,
                        "available_instances": available,
                        "max_instances": max_inst,
                    }
                )
        return result

    # ------------------------------------------------------------------
    # mdev instance discovery
    # ------------------------------------------------------------------

    def list_mdev_instances(self) -> list[dict[str, Any]]:
        """Return currently active mdev device instances."""
        result: list[dict[str, Any]] = []
        for dev_name in self._listdir(self._bus_mdev_root):
            instance_path = f"{self._bus_mdev_root}/{dev_name}"
            type_link = f"{instance_path}/mdev_type"
            type_id = ""
            gpu_pci = ""
            if self._exists(type_link):
                # type_link is a symlink → .../mdev_supported_types/<type_id>
                try:
                    import os
                    target = os.readlink(type_link)
                    type_id = Path(target).name
                    gpu_pci = Path(target).parent.parent.name
                except OSError:
                    pass
            result.append(
                {
                    "uuid": str(dev_name),
                    "type_id": type_id,
                    "gpu_pci": gpu_pci,
                }
            )
        return result

    # ------------------------------------------------------------------
    # mdev instance lifecycle
    # ------------------------------------------------------------------

    def create_mdev_instance(self, gpu_pci: str, type_id: str) -> dict[str, Any]:
        """Create a new mdev instance on the given GPU."""
        pci = str(gpu_pci or "").strip().lower()
        tid = str(type_id or "").strip()
        if not pci or not _PCI_ADDR_RE.match(pci):
            return {"ok": False, "error": f"invalid PCI address: {gpu_pci!r}"}
        if not tid:
            return {"ok": False, "error": "type_id is required"}

        create_path = f"{self._mdev_bus_root}/{pci}/mdev_supported_types/{tid}/create"
        if not self._exists(create_path):
            return {
                "ok": False,
                "error": f"mdev type {tid!r} not found on {pci}",
            }
        new_uuid = str(_uuid_mod.uuid4())
        try:
            self._sysfs_write(create_path, new_uuid)
        except Exception as exc:
            return {"ok": False, "error": f"failed to create mdev instance: {exc}"}
        return {"ok": True, "uuid": new_uuid, "type_id": tid, "gpu_pci": pci}

    def delete_mdev_instance(self, mdev_uuid: str) -> dict[str, Any]:
        """Remove an existing mdev instance."""
        uid = str(mdev_uuid or "").strip().lower()
        if not _UUID_RE.match(uid):
            return {"ok": False, "error": f"invalid UUID: {mdev_uuid!r}"}

        remove_path = f"{self._bus_mdev_root}/{uid}/remove"
        if not self._exists(remove_path):
            return {"ok": False, "error": f"mdev instance {uid!r} not found"}
        try:
            self._sysfs_write(remove_path, "1")
        except Exception as exc:
            return {"ok": False, "error": f"failed to delete mdev instance: {exc}"}
        return {"ok": True, "uuid": uid}

    # ------------------------------------------------------------------
    # mdev → VM assignment (libvirt XML patch)
    # ------------------------------------------------------------------

    def assign_mdev_to_vm(self, mdev_uuid: str, vmid: int) -> dict[str, Any]:
        """Add a vfio-pci mdev hostdev entry to the VM's libvirt XML."""
        uid = str(mdev_uuid or "").strip().lower()
        if not _UUID_RE.match(uid):
            return {"ok": False, "error": f"invalid UUID: {mdev_uuid!r}"}
        vmid = int(vmid)
        vm_state = self._vm_state(vmid)
        if vm_state not in ("shut off", "shutoff", "unknown"):
            return {
                "ok": False,
                "error": f"VM {vmid} must be shut off (current: {vm_state!r})",
            }
        try:
            xml_text = self._dump_xml(vmid)
        except Exception as exc:
            return {"ok": False, "error": f"failed to read VM XML: {exc}"}
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            return {"ok": False, "error": f"failed to parse VM XML: {exc}"}

        if self._xml_has_mdev(root, uid):
            return {"ok": False, "error": f"mdev {uid} is already assigned to VM {vmid}"}

        devices = root.find("devices")
        if devices is None:
            return {"ok": False, "error": "VM XML has no <devices> element"}

        devices.append(self._mdev_hostdev_element(uid))
        new_xml = ET.tostring(root, encoding="unicode")
        try:
            self._define_domain_xml(new_xml)
        except Exception as exc:
            return {"ok": False, "error": f"failed to update VM XML: {exc}"}
        return {"ok": True, "uuid": uid, "vmid": vmid}

    def release_mdev_from_vm(self, mdev_uuid: str, vmid: int) -> dict[str, Any]:
        """Remove a vfio-pci mdev hostdev entry from the VM's libvirt XML."""
        uid = str(mdev_uuid or "").strip().lower()
        if not _UUID_RE.match(uid):
            return {"ok": False, "error": f"invalid UUID: {mdev_uuid!r}"}
        vmid = int(vmid)
        vm_state = self._vm_state(vmid)
        if vm_state not in ("shut off", "shutoff", "unknown"):
            return {
                "ok": False,
                "error": f"VM {vmid} must be shut off (current: {vm_state!r})",
            }
        try:
            xml_text = self._dump_xml(vmid)
        except Exception as exc:
            return {"ok": False, "error": f"failed to read VM XML: {exc}"}
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            return {"ok": False, "error": f"failed to parse VM XML: {exc}"}

        removed = self._xml_remove_mdev(root, uid)
        if not removed:
            return {"ok": False, "error": f"mdev {uid} is not assigned to VM {vmid}"}

        new_xml = ET.tostring(root, encoding="unicode")
        try:
            self._define_domain_xml(new_xml)
        except Exception as exc:
            return {"ok": False, "error": f"failed to update VM XML: {exc}"}
        return {"ok": True, "uuid": uid, "vmid": vmid}

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _vm_state(self, vmid: int) -> str:
        domain = self._libvirt_domain_name(vmid)
        try:
            return self._run_virsh(["domstate", domain]).strip().lower()
        except Exception:
            return "unknown"

    def _dump_xml(self, vmid: int) -> str:
        return self._run_virsh(["dumpxml", self._libvirt_domain_name(vmid)])

    def _safe_read(self, path: str) -> str:
        try:
            return self._sysfs_read(path)
        except Exception:
            return ""

    def _safe_read_int(self, path: str, default: int = 0) -> int:
        try:
            return int(self._sysfs_read(path))
        except Exception:
            return default

    @staticmethod
    def _mdev_hostdev_element(uid: str) -> ET.Element:
        hostdev = ET.Element(
            "hostdev",
            {"mode": "subsystem", "type": "mdev", "managed": "no", "model": "vfio-pci"},
        )
        source = ET.SubElement(hostdev, "source")
        ET.SubElement(source, "address", {"uuid": uid})
        return hostdev

    @staticmethod
    def _xml_has_mdev(root: ET.Element, uid: str) -> bool:
        for hd in root.iter("hostdev"):
            if hd.get("type") != "mdev":
                continue
            addr = hd.find("source/address")
            if addr is not None and str(addr.get("uuid") or "").lower() == uid.lower():
                return True
        return False

    @staticmethod
    def _xml_remove_mdev(root: ET.Element, uid: str) -> bool:
        devices = root.find("devices")
        if devices is None:
            return False
        for hd in list(devices.findall("hostdev")):
            if hd.get("type") != "mdev":
                continue
            addr = hd.find("source/address")
            if addr is not None and str(addr.get("uuid") or "").lower() == uid.lower():
                devices.remove(hd)
                return True
        return False


class SriovService:
    """Intel SR-IOV VF management (Arc/Xe-LP and compatible GPUs).

    Hardware requirements:
      - Intel Arc / Xe-LP discrete GPU or Iris Xe integrated (Tiger Lake+)
      - Linux kernel 6.2+ or Ubuntu HWE with i915 SR-IOV patches
      - Kernel parameters: i915.enable_guc=3 i915.max_vfs=<n>
      - IOMMU enabled (intel_iommu=on)

    The service reads from /sys/bus/pci/devices/<pci>/sriov_totalvfs to
    detect SR-IOV capable devices and writes sriov_numvfs to create VFs.
    Each VF appears as a new PCI function and can be assigned to VMs via
    the GpuPassthroughService (same vfio-pci + libvirt XML path).
    """

    def __init__(
        self,
        *,
        sysfs_read: Callable[[str], str] | None = None,
        sysfs_write: Callable[[str, str], None] | None = None,
        listdir: Callable[[str], list[str]] | None = None,
        exists: Callable[[str], bool] | None = None,
        sys_bus_pci_devices: str | None = None,
    ) -> None:
        self._sysfs_read = sysfs_read or (lambda p: Path(p).read_text().strip())
        self._sysfs_write = sysfs_write or (lambda p, v: Path(p).write_text(v))
        self._listdir = listdir or (lambda p: [x.name for x in Path(p).iterdir()] if Path(p).exists() else [])
        self._exists = exists or (lambda p: Path(p).exists())
        self._pci_devices = str(sys_bus_pci_devices or "/sys/bus/pci/devices")

    def _safe_read_int(self, path: str, default: int = 0) -> int:
        try:
            return int(self._sysfs_read(path))
        except Exception:
            return default

    def list_sriov_devices(self) -> list[dict[str, Any]]:
        """Return PCI devices that support SR-IOV (have sriov_totalvfs)."""
        result: list[dict[str, Any]] = []
        for dev in self._listdir(self._pci_devices):
            total_path = f"{self._pci_devices}/{dev}/sriov_totalvfs"
            if not self._exists(total_path):
                continue
            total = self._safe_read_int(total_path)
            if total <= 0:
                continue
            current = self._safe_read_int(f"{self._pci_devices}/{dev}/sriov_numvfs")
            driver = ""
            driver_link = f"{self._pci_devices}/{dev}/driver"
            if self._exists(driver_link):
                try:
                    import os
                    driver = Path(os.readlink(driver_link)).name
                except OSError:
                    pass
            result.append(
                {
                    "pci": str(dev),
                    "total_vfs": total,
                    "current_vfs": current,
                    "driver": driver,
                }
            )
        return result

    def set_vf_count(self, pci: str, count: int) -> dict[str, Any]:
        """Create or destroy VFs for a SR-IOV capable PCI device."""
        dev = str(pci or "").strip().lower()
        if not _PCI_ADDR_RE.match(dev):
            return {"ok": False, "error": f"invalid PCI address: {pci!r}"}
        count = int(count)
        if count < 0:
            return {"ok": False, "error": "count must be >= 0"}
        total_path = f"{self._pci_devices}/{dev}/sriov_totalvfs"
        if not self._exists(total_path):
            return {"ok": False, "error": f"{dev} does not support SR-IOV"}
        total = self._safe_read_int(total_path)
        if count > total:
            return {
                "ok": False,
                "error": f"requested {count} VFs but device supports at most {total}",
            }
        numvfs_path = f"{self._pci_devices}/{dev}/sriov_numvfs"
        try:
            self._sysfs_write(numvfs_path, str(count))
        except Exception as exc:
            return {"ok": False, "error": f"failed to set VF count: {exc}"}
        current = self._safe_read_int(numvfs_path, count)
        return {"ok": True, "pci": dev, "current_vfs": current, "total_vfs": total}

    def list_vfs(self, pci: str) -> list[dict[str, Any]]:
        """Return VFs (virtfnN symlinks) for a physical function."""
        dev = str(pci or "").strip().lower()
        result: list[dict[str, Any]] = []
        dev_path = f"{self._pci_devices}/{dev}"
        for entry in self._listdir(dev_path):
            if not str(entry).startswith("virtfn"):
                continue
            try:
                index = int(str(entry)[len("virtfn"):])
            except ValueError:
                continue
            import os
            vf_link = f"{dev_path}/{entry}"
            vf_pci = ""
            try:
                vf_pci = Path(os.readlink(vf_link)).name
            except OSError:
                pass
            vf_driver = ""
            vf_driver_link = f"{self._pci_devices}/{vf_pci}/driver"
            if vf_pci and self._exists(vf_driver_link):
                try:
                    vf_driver = Path(os.readlink(vf_driver_link)).name
                except OSError:
                    pass
            result.append({"index": index, "pci": vf_pci, "driver": vf_driver})
        result.sort(key=lambda x: x["index"])
        return result
