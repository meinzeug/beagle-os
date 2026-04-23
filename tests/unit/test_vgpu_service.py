"""Unit tests for VgpuService, SriovService and VgpuSurfaceService.

All tests run without real hardware by injecting mock callables.
"""
import sys
import os
import uuid
from http import HTTPStatus

import pytest

# Ensure the services directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../beagle-host/services"))

from vgpu_service import VgpuService, SriovService  # noqa: E402
from vgpu_surface import VgpuSurfaceService  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _noop_virsh(cmd):
    return ""


def _noop_define(xml):
    pass


def _domain_name(vmid):
    return f"beagle-{vmid}"


def _make_vgpu(
    mdev_bus_root="/sys/class/mdev_bus",
    bus_mdev_root="/sys/bus/mdev/devices",
    reads=None,
    writes=None,
    dirs=None,
    exists=None,
    virsh=None,
    define=None,
):
    written = writes if writes is not None else {}
    read_map = reads or {}

    def _read(path):
        if path in read_map:
            return read_map[path]
        raise FileNotFoundError(path)

    def _write(path, value):
        written[path] = value

    def _listdir(path):
        return (dirs or {}).get(path, [])

    def _exists(path):
        if exists is not None:
            return exists(path)
        return path in read_map or path in (dirs or {})

    return VgpuService(
        run_virsh=virsh or _noop_virsh,
        define_domain_xml=define or _noop_define,
        libvirt_domain_name=_domain_name,
        sysfs_read=_read,
        sysfs_write=_write,
        listdir=_listdir,
        exists=_exists,
        sys_class_mdev_bus=mdev_bus_root,
        sys_bus_mdev=bus_mdev_root,
    ), written


def _make_sriov(reads=None, writes=None, dirs=None, exists=None, pci_root="/sys/bus/pci/devices"):
    written = writes if writes is not None else {}
    read_map = reads or {}

    def _read(path):
        if path in read_map:
            return read_map[path]
        raise FileNotFoundError(path)

    def _write(path, value):
        written[path] = value

    def _listdir(path):
        return (dirs or {}).get(path, [])

    def _exists(path):
        if exists is not None:
            return exists(path)
        return path in read_map

    return SriovService(
        sysfs_read=_read,
        sysfs_write=_write,
        listdir=_listdir,
        exists=_exists,
        sys_bus_pci_devices=pci_root,
    ), written


def _make_surface(vgpu_svc=None, sriov_svc=None):
    vgpu = vgpu_svc
    sriov = sriov_svc
    if vgpu is None:
        vgpu, _ = _make_vgpu()
    if sriov is None:
        sriov, _ = _make_sriov()

    return VgpuSurfaceService(
        list_mdev_types=lambda pci: vgpu.list_mdev_types(pci),
        list_mdev_instances=lambda: vgpu.list_mdev_instances(),
        create_mdev_instance=lambda pci, tid: vgpu.create_mdev_instance(pci, tid),
        delete_mdev_instance=lambda uid: vgpu.delete_mdev_instance(uid),
        assign_mdev_to_vm=lambda uid, vmid: vgpu.assign_mdev_to_vm(uid, vmid),
        release_mdev_from_vm=lambda uid, vmid: vgpu.release_mdev_from_vm(uid, vmid),
        list_sriov_devices=lambda: sriov.list_sriov_devices(),
        set_vf_count=lambda pci, count: sriov.set_vf_count(pci, count),
        list_vfs=lambda pci: sriov.list_vfs(pci),
        service_name="test",
        utcnow=lambda: "2025-01-01T00:00:00Z",
        version="0.0.1",
    )


# ---------------------------------------------------------------------------
# VgpuService — list_mdev_types
# ---------------------------------------------------------------------------

class TestListMdevTypes:
    def test_empty_when_no_mdev_bus(self):
        svc, _ = _make_vgpu(dirs={"/sys/class/mdev_bus": []})
        assert svc.list_mdev_types() == []

    def test_returns_types_for_gpu(self):
        bus = "/mbus"
        pci = "0000:01:00.0"
        tid = "nvidia-123"
        types_path = f"{bus}/{pci}/mdev_supported_types"
        type_path = f"{types_path}/{tid}"
        svc, _ = _make_vgpu(
            mdev_bus_root=bus,
            dirs={
                bus: [pci],
                types_path: [tid],
                type_path: [],
            },
            reads={
                f"{type_path}/name": "GRID T4-4Q",
                f"{type_path}/description": "4GB slice",
                f"{type_path}/available_instances": "4",
                f"{type_path}/max_instances": "4",
            },
        )
        result = svc.list_mdev_types()
        assert len(result) == 1
        assert result[0]["gpu_pci"] == pci
        assert result[0]["type_id"] == tid
        assert result[0]["name"] == "GRID T4-4Q"
        assert result[0]["available_instances"] == 4

    def test_filter_by_gpu_pci(self):
        bus = "/mbus"
        pci_a = "0000:01:00.0"
        pci_b = "0000:02:00.0"
        tid = "nvidia-123"
        types_a = f"{bus}/{pci_a}/mdev_supported_types"
        types_b = f"{bus}/{pci_b}/mdev_supported_types"
        type_a_path = f"{types_a}/{tid}"
        type_b_path = f"{types_b}/{tid}"
        svc, _ = _make_vgpu(
            mdev_bus_root=bus,
            dirs={
                bus: [pci_a, pci_b],
                types_a: [tid],
                types_b: [tid],
                type_a_path: [],
                type_b_path: [],
            },
            reads={
                f"{type_a_path}/name": "T4-4Q",
                f"{type_a_path}/available_instances": "4",
                f"{type_b_path}/name": "A16-4Q",
                f"{type_b_path}/available_instances": "2",
            },
        )
        result = svc.list_mdev_types(gpu_pci=pci_a)
        assert len(result) == 1
        assert result[0]["gpu_pci"] == pci_a


# ---------------------------------------------------------------------------
# VgpuService — list_mdev_instances
# ---------------------------------------------------------------------------

class TestListMdevInstances:
    def test_empty(self):
        svc, _ = _make_vgpu(dirs={"/sys/bus/mdev/devices": []})
        assert svc.list_mdev_instances() == []

    def test_returns_instance(self):
        uid = str(uuid.uuid4())
        bus_mdev = "/sys/bus/mdev/devices"
        inst_path = f"{bus_mdev}/{uid}"
        type_link = f"{inst_path}/mdev_type"
        svc, _ = _make_vgpu(
            dirs={bus_mdev: [uid]},
            exists=lambda p: p == type_link,
        )
        # list_mdev_instances uses os.readlink which we can't easily inject;
        # it falls back to empty strings on OSError — test the graceful path
        result = svc.list_mdev_instances()
        assert len(result) == 1
        assert result[0]["uuid"] == uid


# ---------------------------------------------------------------------------
# VgpuService — create_mdev_instance
# ---------------------------------------------------------------------------

class TestCreateMdevInstance:
    def test_create_success(self):
        bus = "/mbus"
        pci = "0000:01:00.0"
        tid = "nvidia-123"
        create_path = f"{bus}/{pci}/mdev_supported_types/{tid}/create"
        written = {}
        svc, written = _make_vgpu(
            mdev_bus_root=bus,
            writes=written,
            exists=lambda p: p == create_path,
        )
        result = svc.create_mdev_instance(pci, tid)
        assert result["ok"] is True
        assert "uuid" in result
        assert create_path in written

    def test_invalid_pci(self):
        svc, _ = _make_vgpu()
        result = svc.create_mdev_instance("not-a-pci", "nvidia-123")
        assert result["ok"] is False
        assert "invalid PCI" in result["error"]

    def test_type_not_found(self):
        bus = "/mbus"
        pci = "0000:01:00.0"
        tid = "nvidia-999"
        svc, _ = _make_vgpu(mdev_bus_root=bus, exists=lambda p: False)
        result = svc.create_mdev_instance(pci, tid)
        assert result["ok"] is False
        assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# VgpuService — delete_mdev_instance
# ---------------------------------------------------------------------------

class TestDeleteMdevInstance:
    def test_delete_success(self):
        uid = "12345678-1234-1234-1234-123456789abc"
        bus_mdev = "/sys/bus/mdev/devices"
        remove_path = f"{bus_mdev}/{uid}/remove"
        written = {}
        svc, written = _make_vgpu(
            writes=written,
            exists=lambda p: p == remove_path,
        )
        result = svc.delete_mdev_instance(uid)
        assert result["ok"] is True
        assert written[remove_path] == "1"

    def test_invalid_uuid(self):
        svc, _ = _make_vgpu()
        result = svc.delete_mdev_instance("not-a-uuid")
        assert result["ok"] is False
        assert "invalid UUID" in result["error"]

    def test_instance_not_found(self):
        uid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        svc, _ = _make_vgpu(exists=lambda p: False)
        result = svc.delete_mdev_instance(uid)
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# VgpuService — assign_mdev_to_vm
# ---------------------------------------------------------------------------

_MINIMAL_XML = """<domain type='kvm'>
  <name>beagle-101</name>
  <devices></devices>
</domain>"""

_XML_WITH_MDEV = lambda uid: f"""<domain type='kvm'>
  <name>beagle-101</name>
  <devices>
    <hostdev mode='subsystem' type='mdev' managed='no' model='vfio-pci'>
      <source><address uuid='{uid}'/></source>
    </hostdev>
  </devices>
</domain>"""


class TestAssignMdevToVm:
    def test_assign_adds_hostdev(self):
        uid = "12345678-1234-1234-1234-123456789abc"
        defined_xmls = []
        svc, _ = _make_vgpu(
            virsh=lambda cmd: "shut off" if cmd[0] == "domstate" else _MINIMAL_XML,
            define=lambda xml: defined_xmls.append(xml),
        )
        result = svc.assign_mdev_to_vm(uid, 101)
        assert result["ok"] is True
        assert defined_xmls
        assert uid in defined_xmls[0]

    def test_reject_running_vm(self):
        uid = "12345678-1234-1234-1234-123456789abc"
        svc, _ = _make_vgpu(
            virsh=lambda cmd: "running" if cmd[0] == "domstate" else _MINIMAL_XML,
        )
        result = svc.assign_mdev_to_vm(uid, 101)
        assert result["ok"] is False
        assert "shut off" in result["error"]

    def test_reject_duplicate_assignment(self):
        uid = "12345678-1234-1234-1234-123456789abc"
        xml_with_mdev = _XML_WITH_MDEV(uid)
        svc, _ = _make_vgpu(
            virsh=lambda cmd: "shut off" if cmd[0] == "domstate" else xml_with_mdev,
        )
        result = svc.assign_mdev_to_vm(uid, 101)
        assert result["ok"] is False
        assert "already assigned" in result["error"]

    def test_invalid_uuid(self):
        svc, _ = _make_vgpu()
        result = svc.assign_mdev_to_vm("bad-uuid", 101)
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# VgpuService — release_mdev_from_vm
# ---------------------------------------------------------------------------

class TestReleaseMdevFromVm:
    def test_release_removes_hostdev(self):
        uid = "12345678-1234-1234-1234-123456789abc"
        xml_with_mdev = _XML_WITH_MDEV(uid)
        defined_xmls = []
        svc, _ = _make_vgpu(
            virsh=lambda cmd: "shut off" if cmd[0] == "domstate" else xml_with_mdev,
            define=lambda xml: defined_xmls.append(xml),
        )
        result = svc.release_mdev_from_vm(uid, 101)
        assert result["ok"] is True
        assert defined_xmls
        assert uid not in defined_xmls[0]

    def test_not_assigned(self):
        uid = "12345678-1234-1234-1234-123456789abc"
        svc, _ = _make_vgpu(
            virsh=lambda cmd: "shut off" if cmd[0] == "domstate" else _MINIMAL_XML,
        )
        result = svc.release_mdev_from_vm(uid, 101)
        assert result["ok"] is False
        assert "not assigned" in result["error"]


# ---------------------------------------------------------------------------
# SriovService — list_sriov_devices
# ---------------------------------------------------------------------------

class TestListSriovDevices:
    def test_empty_when_no_pci_devices(self):
        svc, _ = _make_sriov(dirs={"/sys/bus/pci/devices": []})
        assert svc.list_sriov_devices() == []

    def test_returns_sriov_device(self):
        root = "/sys/bus/pci/devices"
        pci = "0000:03:00.0"
        total_path = f"{root}/{pci}/sriov_totalvfs"
        numvfs_path = f"{root}/{pci}/sriov_numvfs"
        svc, _ = _make_sriov(
            pci_root=root,
            dirs={root: [pci]},
            reads={
                total_path: "7",
                numvfs_path: "0",
            },
            exists=lambda p: p in (total_path, numvfs_path),
        )
        result = svc.list_sriov_devices()
        assert len(result) == 1
        assert result[0]["pci"] == pci
        assert result[0]["total_vfs"] == 7
        assert result[0]["current_vfs"] == 0

    def test_skips_devices_without_sriov(self):
        root = "/sys/bus/pci/devices"
        pci_no_sriov = "0000:04:00.0"
        svc, _ = _make_sriov(
            pci_root=root,
            dirs={root: [pci_no_sriov]},
            exists=lambda p: False,
        )
        assert svc.list_sriov_devices() == []


# ---------------------------------------------------------------------------
# SriovService — set_vf_count
# ---------------------------------------------------------------------------

class TestSetVfCount:
    def test_set_vf_count_success(self):
        root = "/sys/bus/pci/devices"
        pci = "0000:03:00.0"
        total_path = f"{root}/{pci}/sriov_totalvfs"
        numvfs_path = f"{root}/{pci}/sriov_numvfs"
        written = {}
        svc, written = _make_sriov(
            pci_root=root,
            writes=written,
            reads={total_path: "7", numvfs_path: "3"},
            exists=lambda p: p in (total_path, numvfs_path),
        )
        result = svc.set_vf_count(pci, 3)
        assert result["ok"] is True
        assert written[numvfs_path] == "3"

    def test_set_vf_count_over_limit(self):
        root = "/sys/bus/pci/devices"
        pci = "0000:03:00.0"
        total_path = f"{root}/{pci}/sriov_totalvfs"
        svc, _ = _make_sriov(
            pci_root=root,
            reads={total_path: "7"},
            exists=lambda p: p == total_path,
        )
        result = svc.set_vf_count(pci, 99)
        assert result["ok"] is False
        assert "at most" in result["error"]

    def test_invalid_pci(self):
        svc, _ = _make_sriov()
        result = svc.set_vf_count("bad-addr", 2)
        assert result["ok"] is False
        assert "invalid PCI" in result["error"]

    def test_device_without_sriov(self):
        root = "/sys/bus/pci/devices"
        pci = "0000:03:00.0"
        svc, _ = _make_sriov(pci_root=root, exists=lambda p: False)
        result = svc.set_vf_count(pci, 1)
        assert result["ok"] is False
        assert "does not support SR-IOV" in result["error"]


# ---------------------------------------------------------------------------
# VgpuSurfaceService — handles_path_get / handles_path_post
# ---------------------------------------------------------------------------

class TestVgpuSurfaceHandles:
    def test_get_paths(self):
        svc = _make_surface()
        assert svc.handles_path_get("/api/v1/virtualization/mdev/types")
        assert svc.handles_path_get("/api/v1/virtualization/mdev/instances")
        assert svc.handles_path_get("/api/v1/virtualization/sriov")
        uid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        assert svc.handles_path_get(f"/api/v1/virtualization/sriov/0000:01:00.0/vfs")

    def test_post_paths(self):
        svc = _make_surface()
        uid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        assert svc.handles_path_post("/api/v1/virtualization/mdev/create")
        assert svc.handles_path_post(f"/api/v1/virtualization/mdev/{uid}/assign")
        assert svc.handles_path_post(f"/api/v1/virtualization/mdev/{uid}/release")
        assert svc.handles_path_post(f"/api/v1/virtualization/mdev/{uid}/delete")
        assert svc.handles_path_post("/api/v1/virtualization/sriov/0000:01:00.0/set-vfs")

    def test_unknown_paths(self):
        svc = _make_surface()
        assert not svc.handles_path_get("/api/v1/other")
        assert not svc.handles_path_post("/api/v1/other")


# ---------------------------------------------------------------------------
# VgpuSurfaceService — GET routes
# ---------------------------------------------------------------------------

class TestVgpuSurfaceGetRoutes:
    def test_mdev_types_empty(self):
        svc = _make_surface()
        response = svc.route_get("/api/v1/virtualization/mdev/types")
        assert response is not None
        assert response["status"] == HTTPStatus.OK
        assert response["payload"]["ok"] is True
        assert isinstance(response["payload"]["mdev_types"], list)

    def test_sriov_empty(self):
        svc = _make_surface()
        response = svc.route_get("/api/v1/virtualization/sriov")
        assert response is not None
        assert response["status"] == HTTPStatus.OK
        assert response["payload"]["ok"] is True
        assert isinstance(response["payload"]["sriov_devices"], list)

    def test_mdev_instances_empty(self):
        svc = _make_surface()
        response = svc.route_get("/api/v1/virtualization/mdev/instances")
        assert response is not None
        assert response["status"] == HTTPStatus.OK
        assert response["payload"]["ok"] is True


# ---------------------------------------------------------------------------
# VgpuSurfaceService — POST validation
# ---------------------------------------------------------------------------

class TestVgpuSurfacePostValidation:
    def test_mdev_create_missing_gpu_pci(self):
        svc = _make_surface()
        resp = svc.route_post("/api/v1/virtualization/mdev/create", {"type_id": "nvidia-123"})
        assert resp["status"] == HTTPStatus.BAD_REQUEST
        assert resp["payload"]["ok"] is False

    def test_mdev_create_missing_type_id(self):
        svc = _make_surface()
        resp = svc.route_post("/api/v1/virtualization/mdev/create", {"gpu_pci": "0000:01:00.0"})
        assert resp["status"] == HTTPStatus.BAD_REQUEST

    def test_mdev_assign_missing_vmid(self):
        svc = _make_surface()
        uid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        resp = svc.route_post(f"/api/v1/virtualization/mdev/{uid}/assign", {})
        assert resp["status"] == HTTPStatus.BAD_REQUEST

    def test_sriov_set_vfs_missing_count(self):
        svc = _make_surface()
        resp = svc.route_post("/api/v1/virtualization/sriov/0000:01:00.0/set-vfs", {})
        assert resp["status"] == HTTPStatus.BAD_REQUEST

    def test_mdev_create_forwards_service_error(self):
        # VgpuService will return ok=False because create_path doesn't exist
        bus = "/mbus"
        pci = "0000:01:00.0"
        tid = "nvidia-123"
        vgpu, _ = _make_vgpu(mdev_bus_root=bus, exists=lambda p: False)
        svc = _make_surface(vgpu_svc=vgpu)
        resp = svc.route_post(
            "/api/v1/virtualization/mdev/create",
            {"gpu_pci": pci, "type_id": tid},
        )
        assert resp["status"] == HTTPStatus.UNPROCESSABLE_ENTITY
        assert resp["payload"]["ok"] is False
