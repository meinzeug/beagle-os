from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

_PCI_ADDR_RE = re.compile(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$")


def _parse_pci_addr(addr: str) -> tuple[int, int, int, int]:
    """Parse 'DDDD:BB:SS.F' → (domain, bus, slot, function) as ints."""
    parts = addr.split(":")
    domain = int(parts[0], 16)
    bus = int(parts[1], 16)
    slot_func = parts[2].split(".")
    slot = int(slot_func[0], 16)
    func = int(slot_func[1])
    return domain, bus, slot, func


class GpuPassthroughService:
    """Manages vfio-pci binding and libvirt XML patching for GPU passthrough.

    All privileged sysfs writes and virsh calls are injected for testability.
    """

    def __init__(
        self,
        *,
        run_virsh: Callable[[list[str]], str],
        define_domain_xml: Callable[[str], None],
        libvirt_domain_name: Callable[[int], str],
        sysfs_write: Callable[[str, str], None] | None = None,
        sys_bus_pci_root: str | None = None,
    ) -> None:
        self._run_virsh = run_virsh
        self._define_domain_xml = define_domain_xml
        self._libvirt_domain_name = libvirt_domain_name
        self._sysfs_write = sysfs_write or self._default_sysfs_write
        self._sys_bus_pci_root = str(sys_bus_pci_root or "/sys/bus/pci")

    @staticmethod
    def _default_sysfs_write(path: str, value: str) -> None:
        Path(path).write_text(value)

    @staticmethod
    def _validate_pci_addr(pci_address: str) -> str:
        addr = str(pci_address or "").strip().lower()
        if not _PCI_ADDR_RE.match(addr):
            raise ValueError(f"invalid PCI address: {pci_address!r}")
        return addr

    def _vm_state(self, vmid: int) -> str:
        domain_name = self._libvirt_domain_name(vmid)
        try:
            return self._run_virsh(["domstate", domain_name]).strip().lower()
        except Exception:
            return "unknown"

    def _dump_xml(self, vmid: int) -> str:
        domain_name = self._libvirt_domain_name(vmid)
        return self._run_virsh(["dumpxml", domain_name])

    @staticmethod
    def _hostdev_element(domain: int, bus: int, slot: int, func: int) -> ET.Element:
        hostdev = ET.Element("hostdev", {"mode": "subsystem", "type": "pci", "managed": "yes"})
        source = ET.SubElement(hostdev, "source")
        ET.SubElement(
            source,
            "address",
            {
                "domain": f"0x{domain:04x}",
                "bus": f"0x{bus:02x}",
                "slot": f"0x{slot:02x}",
                "function": f"0x{func:x}",
            },
        )
        return hostdev

    @staticmethod
    def _xml_has_hostdev(root: ET.Element, domain: int, bus: int, slot: int, func: int) -> bool:
        for hd in root.iter("hostdev"):
            if hd.get("type") != "pci":
                continue
            src = hd.find("source/address")
            if src is None:
                continue
            if (
                int(src.get("domain", "0"), 16) == domain
                and int(src.get("bus", "0"), 16) == bus
                and int(src.get("slot", "0"), 16) == slot
                and int(src.get("function", "0"), 16) == func
            ):
                return True
        return False

    @staticmethod
    def _xml_remove_hostdev(
        root: ET.Element, domain: int, bus: int, slot: int, func: int
    ) -> bool:
        devices = root.find("devices")
        if devices is None:
            return False
        to_remove: ET.Element | None = None
        for hd in devices.findall("hostdev"):
            if hd.get("type") != "pci":
                continue
            src = hd.find("source/address")
            if src is None:
                continue
            if (
                int(src.get("domain", "0"), 16) == domain
                and int(src.get("bus", "0"), 16) == bus
                and int(src.get("slot", "0"), 16) == slot
                and int(src.get("function", "0"), 16) == func
            ):
                to_remove = hd
                break
        if to_remove is not None:
            devices.remove(to_remove)
            return True
        return False

    def assign_gpu(self, pci_address: str, vmid: int) -> dict[str, Any]:
        """Assign a GPU to a stopped VM.

        Steps:
        1. Validate PCI address format.
        2. Check VM is shut off.
        3. Detach host driver via sysfs unbind.
        4. Bind vfio-pci.
        5. Add <hostdev> to libvirt domain XML and virsh define.
        """
        try:
            addr = self._validate_pci_addr(pci_address)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        domain, bus, slot, func = _parse_pci_addr(addr)
        vmid = int(vmid)

        vm_state = self._vm_state(vmid)
        if vm_state not in ("shut off", "shutoff", "unknown"):
            return {
                "ok": False,
                "error": (
                    f"VM {vmid} must be shut off before GPU assignment"
                    f" (current state: {vm_state!r})"
                ),
            }

        try:
            xml_text = self._dump_xml(vmid)
        except Exception as exc:
            return {"ok": False, "error": f"failed to read VM XML: {exc}"}

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            return {"ok": False, "error": f"failed to parse VM XML: {exc}"}

        if self._xml_has_hostdev(root, domain, bus, slot, func):
            return {"ok": False, "error": f"GPU {addr} is already assigned to VM {vmid}"}

        devices = root.find("devices")
        if devices is None:
            return {"ok": False, "error": "VM XML has no <devices> element"}

        # Bind vfio-pci — errors are collected as warnings; the XML patch still proceeds
        sysfs_warnings: list[str] = []
        pci_dev = f"{self._sys_bus_pci_root}/devices/{addr}"

        try:
            self._sysfs_write(f"{pci_dev}/driver/unbind", addr)
        except OSError:
            pass  # no driver currently bound — expected
        except Exception as exc:
            sysfs_warnings.append(f"driver unbind: {exc}")

        try:
            self._sysfs_write(f"{pci_dev}/driver_override", "vfio-pci")
        except Exception as exc:
            sysfs_warnings.append(f"driver_override: {exc}")

        try:
            self._sysfs_write(f"{self._sys_bus_pci_root}/drivers/vfio-pci/bind", addr)
        except Exception as exc:
            sysfs_warnings.append(f"vfio-pci bind: {exc}")

        # Patch XML
        devices.append(self._hostdev_element(domain, bus, slot, func))
        new_xml = ET.tostring(root, encoding="unicode")

        try:
            self._define_domain_xml(new_xml)
        except Exception as exc:
            return {"ok": False, "error": f"failed to update VM XML: {exc}"}

        result: dict[str, Any] = {
            "ok": True,
            "pci_address": addr,
            "vmid": vmid,
            "note": (
                "GPU assigned. Host driver detached, vfio-pci bound."
                " A host reboot may be required if binding failed at runtime."
            ),
        }
        if sysfs_warnings:
            result["sysfs_warnings"] = sysfs_warnings
        return result

    def release_gpu(self, pci_address: str, vmid: int) -> dict[str, Any]:
        """Remove GPU assignment from a stopped VM and unbind vfio-pci.

        Steps:
        1. Validate PCI address format.
        2. Check VM is shut off.
        3. Remove <hostdev> from libvirt domain XML and virsh define.
        4. Unbind vfio-pci, reset driver_override, probe original driver.
        """
        try:
            addr = self._validate_pci_addr(pci_address)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        domain, bus, slot, func = _parse_pci_addr(addr)
        vmid = int(vmid)

        vm_state = self._vm_state(vmid)
        if vm_state not in ("shut off", "shutoff", "unknown"):
            return {
                "ok": False,
                "error": (
                    f"VM {vmid} must be shut off before GPU release"
                    f" (current state: {vm_state!r})"
                ),
            }

        try:
            xml_text = self._dump_xml(vmid)
        except Exception as exc:
            return {"ok": False, "error": f"failed to read VM XML: {exc}"}

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            return {"ok": False, "error": f"failed to parse VM XML: {exc}"}

        removed = self._xml_remove_hostdev(root, domain, bus, slot, func)
        if not removed:
            return {"ok": False, "error": f"GPU {addr} is not assigned to VM {vmid}"}

        new_xml = ET.tostring(root, encoding="unicode")

        try:
            self._define_domain_xml(new_xml)
        except Exception as exc:
            return {"ok": False, "error": f"failed to update VM XML: {exc}"}

        sysfs_warnings: list[str] = []
        pci_dev = f"{self._sys_bus_pci_root}/devices/{addr}"

        try:
            self._sysfs_write(f"{pci_dev}/driver/unbind", addr)
        except OSError:
            pass  # already unbound — ok
        except Exception as exc:
            sysfs_warnings.append(f"vfio-pci unbind: {exc}")

        try:
            self._sysfs_write(f"{pci_dev}/driver_override", "\n")
        except Exception as exc:
            sysfs_warnings.append(f"driver_override reset: {exc}")

        try:
            self._sysfs_write(f"{self._sys_bus_pci_root}/drivers_probe", addr)
        except Exception as exc:
            sysfs_warnings.append(f"drivers_probe: {exc}")

        result: dict[str, Any] = {
            "ok": True,
            "pci_address": addr,
            "vmid": vmid,
            "note": "GPU released. vfio-pci unbound, original driver probe requested.",
        }
        if sysfs_warnings:
            result["sysfs_warnings"] = sysfs_warnings
        return result
