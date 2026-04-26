"""Tests for gpu_assignment_modes.py — GoEnterprise Plan 10 Schritt 2."""
from __future__ import annotations

import xml.etree.ElementTree as ET
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../beagle-host/services"))

from gpu_assignment_modes import GpuAssignmentModeService, MAX_TIMESLICE_VMS


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_MINIMAL_VM_XML = """<domain type='kvm'>
  <name>beagle-100</name>
  <devices>
    <disk type='file'><driver name='qemu' type='qcow2'/></disk>
  </devices>
</domain>"""

_VM_XML_WITH_PASSTHROUGH = """<domain type='kvm'>
  <name>beagle-101</name>
  <devices>
    <hostdev mode='subsystem' type='pci' managed='yes'>
      <source>
        <address domain='0x0000' bus='0x01' slot='0x00' function='0x0'/>
      </source>
    </hostdev>
  </devices>
</domain>"""

_VM_XML_WITH_VGPU = """<domain type='kvm'>
  <name>beagle-102</name>
  <devices>
    <hostdev mode='subsystem' type='mdev' model='vfio-pci' managed='no'>
      <source>
        <address uuid='87654321-4321-4321-4321-ba0987654321'/>
      </source>
    </hostdev>
  </devices>
</domain>"""


def _make_service(
    vm_xml: str = _MINIMAL_VM_XML,
    vm_state: str = "shut off",
    timeslice_assignments: list[dict] | None = None,
) -> tuple[GpuAssignmentModeService, list[str], list[str], list[tuple]]:
    """Returns (service, sysfs_calls, defined_xmls, timeslice_saved)."""
    sysfs_calls: list[str] = []
    defined_xmls: list[str] = []
    saved: list[tuple] = []
    removed: list[tuple] = []
    ts_store: list[dict] = list(timeslice_assignments or [])

    svc = GpuAssignmentModeService(
        run_virsh=lambda args: (
            vm_xml if args[0] == "dumpxml" else vm_state
        ),
        define_domain_xml=lambda xml: defined_xmls.append(xml),
        libvirt_domain_name=lambda vmid: f"beagle-{vmid}",
        sysfs_write=lambda path, val: sysfs_calls.append(f"{path}={val}"),
        sys_bus_pci_root="/sys/bus/pci",
        list_timeslice_assignments=lambda: list(ts_store),
        save_timeslice_assignment=lambda g, v: (ts_store.append({"gpu_id": g, "vmid": v}), saved.append((g, v))),
        remove_timeslice_assignment=lambda g, v: removed.append((g, v)),
    )
    return svc, sysfs_calls, defined_xmls, saved


# ---------------------------------------------------------------------------
# Passthrough Tests
# ---------------------------------------------------------------------------

class TestPassthrough:
    def test_assign_passthrough_happy_path(self):
        svc, sysfs, xmls, _ = _make_service()
        result = svc.assign_passthrough("0000:01:00.0", 100)
        assert result["ok"] is True
        assert result["mode"] == "passthrough"
        assert result["pci_address"] == "0000:01:00.0"
        assert result["vmid"] == 100
        assert len(xmls) == 1
        root = ET.fromstring(xmls[0])
        hostdev = root.find(".//hostdev[@type='pci']")
        assert hostdev is not None

    def test_assign_passthrough_binds_vfio(self):
        svc, sysfs, _, _ = _make_service()
        svc.assign_passthrough("0000:01:00.0", 100)
        joined = "\n".join(sysfs)
        assert "driver_override=vfio-pci" in joined
        assert "vfio-pci/bind=0000:01:00.0" in joined

    def test_assign_passthrough_invalid_pci(self):
        svc, _, _, _ = _make_service()
        result = svc.assign_passthrough("invalid", 100)
        assert result["ok"] is False
        assert "invalid PCI address" in result["error"]

    def test_assign_passthrough_invalid_vmid(self):
        svc, _, _, _ = _make_service()
        result = svc.assign_passthrough("0000:01:00.0", "abc")
        assert result["ok"] is False

    def test_assign_passthrough_negative_vmid(self):
        svc, _, _, _ = _make_service()
        result = svc.assign_passthrough("0000:01:00.0", -1)
        assert result["ok"] is False
        assert "vmid" in result["error"]

    def test_assign_passthrough_vm_running(self):
        svc, _, _, _ = _make_service(vm_state="running")
        result = svc.assign_passthrough("0000:01:00.0", 100)
        assert result["ok"] is False
        assert "shut off" in result["error"]

    def test_assign_passthrough_already_assigned(self):
        svc, _, _, _ = _make_service(vm_xml=_VM_XML_WITH_PASSTHROUGH)
        result = svc.assign_passthrough("0000:01:00.0", 101)
        assert result["ok"] is False
        assert "already assigned" in result["error"]

    def test_release_passthrough_happy_path(self):
        svc, sysfs, xmls, _ = _make_service(vm_xml=_VM_XML_WITH_PASSTHROUGH)
        result = svc.release_passthrough("0000:01:00.0", 101)
        assert result["ok"] is True
        assert result["mode"] == "passthrough"
        root = ET.fromstring(xmls[0])
        assert root.find(".//hostdev[@type='pci']") is None

    def test_release_passthrough_unbinds_vfio(self):
        svc, sysfs, _, _ = _make_service(vm_xml=_VM_XML_WITH_PASSTHROUGH)
        svc.release_passthrough("0000:01:00.0", 101)
        joined = "\n".join(sysfs)
        assert "drivers_probe" in joined

    def test_release_passthrough_not_assigned(self):
        svc, _, _, _ = _make_service()
        result = svc.release_passthrough("0000:01:00.0", 100)
        assert result["ok"] is False
        assert "not assigned" in result["error"]

    def test_release_passthrough_vm_running(self):
        svc, _, _, _ = _make_service(vm_state="running")
        result = svc.release_passthrough("0000:01:00.0", 100)
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Time-Slicing Tests
# ---------------------------------------------------------------------------

class TestTimeslice:
    def test_assign_timeslice_happy_path(self):
        svc, _, _, saved = _make_service()
        result = svc.assign_timeslice("gpu-0", 200)
        assert result["ok"] is True
        assert result["mode"] == "timeslice"
        assert result["gpu_id"] == "gpu-0"
        assert result["vmid"] == 200
        assert saved == [("gpu-0", 200)]

    def test_assign_timeslice_slot_count(self):
        existing = [{"gpu_id": "gpu-0", "vmid": i} for i in range(3)]
        svc, _, _, _ = _make_service(timeslice_assignments=existing)
        result = svc.assign_timeslice("gpu-0", 300)
        assert result["ok"] is True
        assert result["slot"] == 4
        assert result["total_slots"] == 4

    def test_assign_timeslice_max_exceeded(self):
        existing = [{"gpu_id": "gpu-0", "vmid": i + 1} for i in range(MAX_TIMESLICE_VMS)]
        svc, _, _, _ = _make_service(timeslice_assignments=existing)
        result = svc.assign_timeslice("gpu-0", 999)
        assert result["ok"] is False
        assert str(MAX_TIMESLICE_VMS) in result["error"]

    def test_assign_timeslice_duplicate(self):
        existing = [{"gpu_id": "gpu-0", "vmid": 200}]
        svc, _, _, _ = _make_service(timeslice_assignments=existing)
        result = svc.assign_timeslice("gpu-0", 200)
        assert result["ok"] is False
        assert "already in timeslice pool" in result["error"]

    def test_assign_timeslice_invalid_gpu_id(self):
        svc, _, _, _ = _make_service()
        result = svc.assign_timeslice("", 100)
        assert result["ok"] is False
        assert "invalid gpu_id" in result["error"]

    def test_assign_timeslice_invalid_gpu_id_traversal(self):
        svc, _, _, _ = _make_service()
        result = svc.assign_timeslice("../../etc/passwd", 100)
        assert result["ok"] is False

    def test_release_timeslice_happy_path(self):
        existing = [{"gpu_id": "gpu-0", "vmid": 200}]
        svc, _, _, _ = _make_service(timeslice_assignments=existing)
        result = svc.release_timeslice("gpu-0", 200)
        assert result["ok"] is True
        assert result["mode"] == "timeslice"

    def test_release_timeslice_not_found(self):
        svc, _, _, _ = _make_service()
        result = svc.release_timeslice("gpu-0", 999)
        assert result["ok"] is False
        assert "not in timeslice pool" in result["error"]

    def test_multiple_gpus_independent(self):
        """Two different GPUs can have independent timeslice assignments."""
        svc, _, _, saved = _make_service()
        r1 = svc.assign_timeslice("gpu-0", 10)
        r2 = svc.assign_timeslice("gpu-1", 10)
        assert r1["ok"] is True
        assert r2["ok"] is True


# ---------------------------------------------------------------------------
# vGPU Tests
# ---------------------------------------------------------------------------

_MDEV_UUID = "12345678-1234-1234-1234-ab1234567890"
_MDEV_UUID2 = "87654321-4321-4321-4321-ba0987654321"


class TestVgpu:
    def test_assign_vgpu_happy_path(self):
        svc, _, xmls, _ = _make_service()
        result = svc.assign_vgpu(_MDEV_UUID, 102)
        assert result["ok"] is True
        assert result["mode"] == "vgpu"
        assert result["mdev_uuid"] == _MDEV_UUID
        root = ET.fromstring(xmls[0])
        hostdev = root.find(".//hostdev[@type='mdev']")
        assert hostdev is not None
        addr = hostdev.find("source/address")
        assert addr is not None
        assert addr.get("uuid") == _MDEV_UUID

    def test_assign_vgpu_invalid_uuid(self):
        svc, _, _, _ = _make_service()
        result = svc.assign_vgpu("not-a-uuid", 100)
        assert result["ok"] is False
        assert "invalid UUID" in result["error"]

    def test_assign_vgpu_vm_running(self):
        svc, _, _, _ = _make_service(vm_state="running")
        result = svc.assign_vgpu(_MDEV_UUID, 100)
        assert result["ok"] is False

    def test_assign_vgpu_already_assigned(self):
        svc, _, _, _ = _make_service(vm_xml=_VM_XML_WITH_VGPU)
        result = svc.assign_vgpu(_MDEV_UUID2, 102)
        assert result["ok"] is False
        assert "already assigned" in result["error"]

    def test_release_vgpu_happy_path(self):
        svc, _, xmls, _ = _make_service(vm_xml=_VM_XML_WITH_VGPU)
        result = svc.release_vgpu(_MDEV_UUID2, 102)
        assert result["ok"] is True
        root = ET.fromstring(xmls[0])
        assert root.find(".//hostdev[@type='mdev']") is None

    def test_release_vgpu_not_assigned(self):
        svc, _, _, _ = _make_service()
        result = svc.release_vgpu(_MDEV_UUID, 100)
        assert result["ok"] is False
        assert "not assigned" in result["error"]

    def test_release_vgpu_vm_running(self):
        svc, _, _, _ = _make_service(vm_state="running")
        result = svc.release_vgpu(_MDEV_UUID, 100)
        assert result["ok"] is False

    def test_vgpu_no_passthrough_sysfs_calls(self):
        """vGPU mode must not touch vfio-pci sysfs (mdev manages binding itself)."""
        svc, sysfs, _, _ = _make_service()
        svc.assign_vgpu(_MDEV_UUID, 102)
        assert sysfs == []
