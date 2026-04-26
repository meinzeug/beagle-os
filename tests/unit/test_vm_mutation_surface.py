from __future__ import annotations

import sys
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from vm_mutation_surface import VmMutationSurfaceService


class _Vm:
    def __init__(self, vmid: int, node: str) -> None:
        self.vmid = vmid
        self.node = node


def _service() -> tuple[VmMutationSurfaceService, list[tuple[int, str, bool, bool, str]]]:
    vm = _Vm(100, "node-a")
    calls: list[tuple[int, str, bool, bool, str]] = []
    service = VmMutationSurfaceService(
        attach_usb_to_guest=lambda vm, busid: {},
        build_vm_usb_state=lambda vm: {},
        find_vm=lambda vmid: vm if int(vmid) == 100 else None,
        invalidate_vm_cache=lambda vmid, node: None,
        issue_sunshine_access_token=lambda vm: ("", {}),
        migrate_vm=lambda vmid, target_node, live, copy_storage, requester_identity: calls.append((vmid, target_node, live, copy_storage, requester_identity)) or {
            "service": "beagle-control-plane",
            "version": "test",
            "generated_at": "2026-04-23T10:00:00Z",
            "migration": {"vmid": vmid, "target_node": target_node},
        },
        queue_vm_action=lambda vm, action, requester_identity, params=None: {},
        reboot_vm=lambda vmid: "",
        service_name="beagle-control-plane",
        start_vm=lambda vmid: "",
        start_installer_prep=lambda vm: {},
        stop_vm=lambda vmid: "",
        summarize_action_result=lambda payload: payload or {},
        sunshine_proxy_ticket_url=lambda token: token,
        usb_action_wait_seconds=0,
        utcnow=lambda: "2026-04-23T10:00:00Z",
        version="test",
        wait_for_action_result=lambda node, vmid, action_id: None,
        detach_usb_from_guest=lambda vm, port, busid: {},
    )
    return service, calls


def test_handles_migrate_path() -> None:
    assert VmMutationSurfaceService.handles_path("/api/v1/vms/100/migrate") is True
    assert VmMutationSurfaceService.requires_json_body("/api/v1/vms/100/migrate") is True


def test_handles_snapshot_path() -> None:
    assert VmMutationSurfaceService.handles_path("/api/v1/vms/100/snapshot") is True
    assert VmMutationSurfaceService.handles_path("/api/v1/vms/999/snapshot") is True
    assert VmMutationSurfaceService.handles_path("/api/v1/vms/100/migrate") is True


def _service_with_enqueue() -> tuple[VmMutationSurfaceService, list[tuple], list[tuple]]:
    vm = _Vm(100, "node-a")
    migrate_calls: list[tuple] = []
    enqueue_calls: list[tuple] = []

    def _enqueue(name, payload, *, idempotency_key="", owner=""):
        enqueue_calls.append((name, payload, idempotency_key, owner))

        class _Job:
            job_id = "deadbeef1234"
        return _Job()

    service = VmMutationSurfaceService(
        attach_usb_to_guest=lambda vm, busid: {},
        build_vm_usb_state=lambda vm: {},
        find_vm=lambda vmid: vm if int(vmid) == 100 else None,
        invalidate_vm_cache=lambda vmid, node: None,
        issue_sunshine_access_token=lambda vm: ("", {}),
        migrate_vm=lambda vmid, target_node, live, copy_storage, requester_identity: migrate_calls.append((vmid, target_node)) or {
            "migration": {"vmid": vmid}
        },
        queue_vm_action=lambda vm, action, requester_identity, params=None: {},
        reboot_vm=lambda vmid: "",
        service_name="beagle-control-plane",
        start_vm=lambda vmid: "",
        start_installer_prep=lambda vm: {},
        stop_vm=lambda vmid: "",
        summarize_action_result=lambda payload: payload or {},
        sunshine_proxy_ticket_url=lambda token: token,
        usb_action_wait_seconds=0,
        utcnow=lambda: "2026-04-23T10:00:00Z",
        version="test",
        wait_for_action_result=lambda node, vmid, action_id: None,
        detach_usb_from_guest=lambda vm, port, busid: {},
        enqueue_job=_enqueue,
    )
    return service, migrate_calls, enqueue_calls


def test_snapshot_enqueues_job_and_returns_202() -> None:
    service, _, enqueue_calls = _service_with_enqueue()

    response = service.route_post(
        "/api/v1/vms/100/snapshot",
        json_payload={"name": "mysnap"},
        requester_identity="admin",
    )

    assert int(response["status"]) == 202
    assert response["payload"]["ok"] is True
    assert response["payload"]["job_id"] == "deadbeef1234"
    assert response["payload"]["vmid"] == 100
    assert response["payload"]["name"] == "mysnap"
    assert len(enqueue_calls) == 1
    name, payload, ikey, owner = enqueue_calls[0]
    assert name == "vm.snapshot"
    assert payload["vmid"] == 100
    assert payload["node"] == "node-a"
    assert payload["name"] == "mysnap"
    assert ikey == "vm.snapshot.100.mysnap"
    assert owner == "admin"


def test_snapshot_uses_default_name_when_not_supplied() -> None:
    service, _, enqueue_calls = _service_with_enqueue()

    response = service.route_post(
        "/api/v1/vms/100/snapshot",
        json_payload={},
        requester_identity="ops",
    )

    assert int(response["status"]) == 202
    assert response["payload"]["name"].startswith("snap-")
    _, payload, ikey, _ = enqueue_calls[0]
    assert payload["name"].startswith("snap-")
    assert ikey.startswith("vm.snapshot.100.snap-")


def test_snapshot_vm_not_found_returns_404() -> None:
    service, _, enqueue_calls = _service_with_enqueue()

    response = service.route_post(
        "/api/v1/vms/999/snapshot",
        json_payload={"name": "s1"},
        requester_identity="admin",
    )

    assert int(response["status"]) == 404
    assert response["payload"]["ok"] is False
    assert len(enqueue_calls) == 0


def test_snapshot_invalid_vmid_returns_400() -> None:
    service, _, enqueue_calls = _service_with_enqueue()

    response = service.route_post(
        "/api/v1/vms/notanid/snapshot",
        json_payload={"name": "s1"},
        requester_identity="admin",
    )

    assert int(response["status"]) == 400
    assert response["payload"]["ok"] is False
    assert len(enqueue_calls) == 0


def test_snapshot_enqueue_failure_returns_500() -> None:
    vm = _Vm(100, "node-a")

    def _enqueue_fail(name, payload, *, idempotency_key="", owner=""):
        raise RuntimeError("queue unavailable")

    service = VmMutationSurfaceService(
        attach_usb_to_guest=lambda vm, busid: {},
        build_vm_usb_state=lambda vm: {},
        find_vm=lambda vmid: vm if int(vmid) == 100 else None,
        invalidate_vm_cache=lambda vmid, node: None,
        issue_sunshine_access_token=lambda vm: ("", {}),
        migrate_vm=lambda vmid, target_node, live, copy_storage, requester_identity: {},
        queue_vm_action=lambda vm, action, requester_identity, params=None: {},
        reboot_vm=lambda vmid: "",
        service_name="beagle-control-plane",
        start_vm=lambda vmid: "",
        start_installer_prep=lambda vm: {},
        stop_vm=lambda vmid: "",
        summarize_action_result=lambda payload: payload or {},
        sunshine_proxy_ticket_url=lambda token: token,
        usb_action_wait_seconds=0,
        utcnow=lambda: "2026-04-23T10:00:00Z",
        version="test",
        wait_for_action_result=lambda node, vmid, action_id: None,
        detach_usb_from_guest=lambda vm, port, busid: {},
        enqueue_job=_enqueue_fail,
    )

    response = service.route_post(
        "/api/v1/vms/100/snapshot",
        json_payload={"name": "s1"},
        requester_identity="admin",
    )

    assert int(response["status"]) == 500
    assert response["payload"]["ok"] is False
    assert "queue unavailable" in response["payload"]["error"]


def test_snapshot_no_enqueue_job_returns_503() -> None:
    service, _ = _service()  # no enqueue_job

    response = service.route_post(
        "/api/v1/vms/100/snapshot",
        json_payload={"name": "s1"},
        requester_identity="admin",
    )

    assert int(response["status"]) == 503
    assert response["payload"]["ok"] is False
    assert "job queue not available" in response["payload"]["error"]


def test_migrate_route_dispatches_to_service() -> None:
    service, calls = _service()
    response = service.route_post(
        "/api/v1/vms/100/migrate",
        json_payload={"target_node": "node-b"},
        requester_identity="admin",
    )

    assert int(response["status"]) == 202
    assert response["payload"]["ok"] is True
    assert calls == [(100, "node-b", True, False, "admin")]


def test_power_route_includes_vm_power_for_not_found() -> None:
    service, _ = _service()
    response = service.route_post(
        "/api/v1/virtualization/vms/999999/power",
        json_payload={"action": "start"},
        requester_identity="admin",
    )

    assert int(response["status"]) == 404
    assert response["payload"]["ok"] is False
    vm_power = response["payload"]["vm_power"]
    assert vm_power["vmid"] == 999999
    assert vm_power["action"] == "start"


def test_power_route_rejects_invalid_action() -> None:
    service, _ = _service()
    response = service.route_post(
        "/api/v1/virtualization/vms/100/power",
        json_payload={"action": "hibernate"},
        requester_identity="admin",
    )

    assert int(response["status"]) == 400
    assert response["payload"]["ok"] is False