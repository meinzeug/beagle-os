"""Unit tests for GpuPassthroughService."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../beagle-host/services'))

from gpu_passthrough_service import GpuPassthroughService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_XML = """
<domain type='kvm'>
  <name>beagle-101</name>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>
  </devices>
</domain>
""".strip()

_XML_WITH_HOSTDEV = """
<domain type='kvm'>
  <name>beagle-101</name>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>
    <hostdev mode='subsystem' type='pci' managed='yes'>
      <source>
        <address domain='0x0000' bus='0x01' slot='0x00' function='0x0'/>
      </source>
    </hostdev>
  </devices>
</domain>
""".strip()


def _make_service(
    virsh_responses: dict[tuple, str] | None = None,
    vm_state: str = "shut off",
    defined_xmls: list[str] | None = None,
    sysfs_written: list[tuple[str, str]] | None = None,
    domain_xml: str = _MINIMAL_XML,
) -> GpuPassthroughService:
    """Build a GpuPassthroughService with all side-effects captured."""
    if defined_xmls is None:
        defined_xmls = []
    if sysfs_written is None:
        sysfs_written = []

    def run_virsh(command: list[str]) -> str:
        verb = command[0] if command else ""
        if verb == "domstate":
            return vm_state
        if verb == "dumpxml":
            return domain_xml
        return ""

    def define_domain_xml(xml_text: str) -> None:
        defined_xmls.append(xml_text)

    def sysfs_write(path: str, value: str) -> None:
        sysfs_written.append((path, value))

    return GpuPassthroughService(
        run_virsh=run_virsh,
        define_domain_xml=define_domain_xml,
        libvirt_domain_name=lambda vmid: f"beagle-{vmid}",
        sysfs_write=sysfs_write,
        sys_bus_pci_root="/sys/bus/pci",
    )


# ---------------------------------------------------------------------------
# assign_gpu
# ---------------------------------------------------------------------------


def test_assign_gpu_success():
    defined = []
    sysfs = []
    svc = _make_service(defined_xmls=defined, sysfs_written=sysfs)

    result = svc.assign_gpu("0000:01:00.0", 101)

    assert result["ok"] is True
    assert result["pci_address"] == "0000:01:00.0"
    assert result["vmid"] == 101

    # XML should have been updated
    assert len(defined) == 1
    root = ET.fromstring(defined[0])
    hostdevs = [hd for hd in root.iter("hostdev") if hd.get("type") == "pci"]
    assert len(hostdevs) == 1
    addr = hostdevs[0].find("source/address")
    assert addr is not None
    assert int(addr.get("domain"), 16) == 0
    assert int(addr.get("bus"), 16) == 1
    assert int(addr.get("slot"), 16) == 0
    assert int(addr.get("function"), 16) == 0


def test_assign_gpu_sysfs_calls():
    sysfs = []
    svc = _make_service(sysfs_written=sysfs)
    svc.assign_gpu("0000:01:00.0", 101)

    paths = [p for p, _ in sysfs]
    assert "/sys/bus/pci/devices/0000:01:00.0/driver_override" in paths
    assert "/sys/bus/pci/drivers/vfio-pci/bind" in paths

    # driver_override must be set to "vfio-pci"
    override_val = next(v for p, v in sysfs if "driver_override" in p)
    assert override_val == "vfio-pci"

    # bind must send the PCI address
    bind_val = next(v for p, v in sysfs if "vfio-pci/bind" in p)
    assert bind_val == "0000:01:00.0"


def test_assign_gpu_invalid_pci_address():
    svc = _make_service()
    result = svc.assign_gpu("not-a-pci-addr", 101)
    assert result["ok"] is False
    assert "invalid PCI address" in result["error"]


def test_assign_gpu_vm_running():
    svc = _make_service(vm_state="running")
    result = svc.assign_gpu("0000:01:00.0", 101)
    assert result["ok"] is False
    assert "shut off" in result["error"]


def test_assign_gpu_already_assigned():
    svc = _make_service(domain_xml=_XML_WITH_HOSTDEV)
    result = svc.assign_gpu("0000:01:00.0", 101)
    assert result["ok"] is False
    assert "already assigned" in result["error"]


# ---------------------------------------------------------------------------
# release_gpu
# ---------------------------------------------------------------------------


def test_release_gpu_success():
    defined = []
    sysfs = []
    svc = _make_service(defined_xmls=defined, sysfs_written=sysfs, domain_xml=_XML_WITH_HOSTDEV)

    result = svc.release_gpu("0000:01:00.0", 101)

    assert result["ok"] is True
    assert result["pci_address"] == "0000:01:00.0"

    # hostdev should be gone from the updated XML
    assert len(defined) == 1
    root = ET.fromstring(defined[0])
    hostdevs = [hd for hd in root.iter("hostdev") if hd.get("type") == "pci"]
    assert len(hostdevs) == 0


def test_release_gpu_sysfs_calls():
    sysfs = []
    svc = _make_service(sysfs_written=sysfs, domain_xml=_XML_WITH_HOSTDEV)
    svc.release_gpu("0000:01:00.0", 101)

    paths = [p for p, _ in sysfs]
    assert "/sys/bus/pci/devices/0000:01:00.0/driver/unbind" in paths
    assert "/sys/bus/pci/devices/0000:01:00.0/driver_override" in paths
    assert "/sys/bus/pci/drivers_probe" in paths


def test_release_gpu_not_assigned():
    svc = _make_service(domain_xml=_MINIMAL_XML)
    result = svc.release_gpu("0000:01:00.0", 101)
    assert result["ok"] is False
    assert "not assigned" in result["error"]


def test_release_gpu_vm_running():
    svc = _make_service(vm_state="running", domain_xml=_XML_WITH_HOSTDEV)
    result = svc.release_gpu("0000:01:00.0", 101)
    assert result["ok"] is False
    assert "shut off" in result["error"]


def test_release_gpu_invalid_pci():
    svc = _make_service()
    result = svc.release_gpu("ZZZZ:ZZ:ZZ.Z", 101)
    assert result["ok"] is False
    assert "invalid PCI address" in result["error"]


# ---------------------------------------------------------------------------
# GpuPassthroughSurfaceService
# ---------------------------------------------------------------------------


def test_surface_handles_path():
    from gpu_passthrough_surface import GpuPassthroughSurfaceService

    svc = GpuPassthroughSurfaceService(
        assign_gpu=lambda pci, vmid: {"ok": True},
        release_gpu=lambda pci, vmid: {"ok": True},
        service_name="test",
        utcnow=lambda: "2026-04-23T00:00:00Z",
        version="test",
    )

    assert svc.handles_path("/api/v1/virtualization/gpus/0000:01:00.0/assign") is True
    assert svc.handles_path("/api/v1/virtualization/gpus/0000:01:00.0/release") is True
    assert svc.handles_path("/api/v1/virtualization/gpus/0000:01:00.0/unknown") is False
    assert svc.handles_path("/api/v1/virtualization/overview") is False


def test_surface_assign_success():
    from gpu_passthrough_surface import GpuPassthroughSurfaceService
    from http import HTTPStatus

    calls = []

    def assign_gpu(pci, vmid):
        calls.append(("assign", pci, vmid))
        return {"ok": True, "pci_address": pci, "vmid": vmid, "note": "ok"}

    svc = GpuPassthroughSurfaceService(
        assign_gpu=assign_gpu,
        release_gpu=lambda pci, vmid: {"ok": True},
        service_name="test",
        utcnow=lambda: "2026-04-23T00:00:00Z",
        version="test",
    )

    resp = svc.route_post(
        "/api/v1/virtualization/gpus/0000:01:00.0/assign",
        {"vmid": 101},
    )
    assert resp["status"] == HTTPStatus.OK
    assert len(calls) == 1
    assert calls[0] == ("assign", "0000:01:00.0", 101)


def test_surface_missing_vmid():
    from gpu_passthrough_surface import GpuPassthroughSurfaceService
    from http import HTTPStatus

    svc = GpuPassthroughSurfaceService(
        assign_gpu=lambda pci, vmid: {"ok": True},
        release_gpu=lambda pci, vmid: {"ok": True},
        service_name="test",
        utcnow=lambda: "2026-04-23T00:00:00Z",
        version="test",
    )

    resp = svc.route_post("/api/v1/virtualization/gpus/0000:01:00.0/assign", {})
    assert resp["status"] == HTTPStatus.BAD_REQUEST
    assert "vmid" in resp["payload"]["error"]


def test_surface_service_error_returns_422():
    from gpu_passthrough_surface import GpuPassthroughSurfaceService
    from http import HTTPStatus

    svc = GpuPassthroughSurfaceService(
        assign_gpu=lambda pci, vmid: {"ok": False, "error": "VM is running"},
        release_gpu=lambda pci, vmid: {"ok": True},
        service_name="test",
        utcnow=lambda: "2026-04-23T00:00:00Z",
        version="test",
    )

    resp = svc.route_post("/api/v1/virtualization/gpus/0000:01:00.0/assign", {"vmid": 101})
    assert resp["status"] == HTTPStatus.UNPROCESSABLE_ENTITY
    assert resp["payload"]["ok"] is False
