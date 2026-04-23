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