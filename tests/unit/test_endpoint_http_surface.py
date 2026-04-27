from __future__ import annotations

import sys
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from endpoint_http_surface import EndpointHttpSurfaceService


class _Vm:
    def __init__(self, vmid: int, node: str) -> None:
        self.vmid = vmid
        self.node = node


def _service(*, prepare_ok: bool = True) -> EndpointHttpSurfaceService:
    vm = _Vm(100, "beagle-0")
    profiles = {100: {"stream_host": "srv2.beagle-os.com", "moonlight_port": "47984"}}
    sessions = {
        "pool-a:100": {
            "session_id": "pool-a:100",
            "pool_id": "pool-a",
            "vm_id": 100,
            "current_node": "beagle-2",
            "status": "active",
        }
    }

    def _find(vmid: int):
        return vm if int(vmid) == vm.vmid else None

    def _prepare(_vm, resolution: str):
        return {
            "ok": bool(prepare_ok),
            "resolution": resolution,
            "exitcode": 0 if prepare_ok else 4,
            "stdout": "APPLIED" if prepare_ok else "",
            "stderr": "" if prepare_ok else "failed",
        }

    return EndpointHttpSurfaceService(
        build_vm_profile=lambda found_vm: profiles.get(int(found_vm.vmid), {}),
        dequeue_vm_actions=lambda node, vmid: [],
        exchange_moonlight_pairing_token=lambda vm, endpoint_identity, pairing_token: {"ok": pairing_token == "valid-token"},
        fetch_sunshine_server_identity=lambda vm, guest_user: {},
        find_vm=_find,
        issue_moonlight_pairing_token=lambda vm, endpoint_identity, device_name: {
            "ok": True,
            "token": "valid-token",
            "pin": "1234",
            "expires_at": "2026-04-22T00:10:00Z",
        },
        prepare_virtual_display_on_vm=_prepare,
        register_moonlight_certificate_on_vm=lambda vm, cert, device_name: {"ok": True},
        service_name="beagle-control-plane",
        session_manager_service=type(
            "SessionManagerStub",
            (),
            {
                "find_active_session": staticmethod(
                    lambda **kwargs: sessions.get(str(kwargs.get("session_id") or "").strip())
                    or next(
                        (
                            value
                            for value in sessions.values()
                            if int(value.get("vm_id") or 0) == int(kwargs.get("vm_id") or 0)
                            and str(value.get("status") or "") == "active"
                        ),
                        None,
                    )
                )
            },
        )(),
        store_action_result=lambda node, vmid, payload: None,
        store_support_bundle=lambda node, vmid, action_id, filename, payload: {},
        summarize_action_result=lambda payload: payload or {},
        utcnow=lambda: "2026-04-22T00:00:00Z",
        version="test",
    )


def test_handles_prepare_stream_path() -> None:
    assert EndpointHttpSurfaceService.handles_path("/api/v1/endpoints/moonlight/prepare-stream") is True
    assert EndpointHttpSurfaceService.requires_json_body("/api/v1/endpoints/moonlight/prepare-stream") is True
    assert EndpointHttpSurfaceService.handles_path("/api/v1/endpoints/moonlight/pair-token") is True
    assert EndpointHttpSurfaceService.handles_path("/api/v1/endpoints/moonlight/pair-exchange") is True
    assert EndpointHttpSurfaceService.handles_path("/api/v1/session/current") is True


def test_prepare_stream_route_success() -> None:
    service = _service(prepare_ok=True)
    response = service.route_post(
        "/api/v1/endpoints/moonlight/prepare-stream",
        endpoint_identity={"vmid": 100, "node": "beagle-0"},
        query={},
        json_payload={"resolution": "1920x1080"},
    )

    assert int(response["status"]) == 200
    assert response["payload"]["ok"] is True
    assert response["payload"]["resolution"] == "1920x1080"


def test_prepare_stream_route_failure_propagates_gateway_status() -> None:
    service = _service(prepare_ok=False)
    response = service.route_post(
        "/api/v1/endpoints/moonlight/prepare-stream",
        endpoint_identity={"vmid": 100, "node": "beagle-0"},
        query={},
        json_payload={"resolution": "3840x2160"},
    )

    assert int(response["status"]) == 502
    assert response["payload"]["ok"] is False


def test_prepare_stream_route_requires_resolution() -> None:
    service = _service(prepare_ok=True)
    response = service.route_post(
        "/api/v1/endpoints/moonlight/prepare-stream",
        endpoint_identity={"vmid": 100, "node": "beagle-0"},
        query={},
        json_payload={},
    )

    assert int(response["status"]) == 400
    assert "missing resolution" in response["payload"]["error"]


def test_pair_token_route_success() -> None:
    service = _service()
    response = service.route_post(
        "/api/v1/endpoints/moonlight/pair-token",
        endpoint_identity={"vmid": 100, "node": "beagle-0", "hostname": "endpoint-a"},
        query={},
        json_payload={"device_name": "endpoint-a"},
    )

    assert int(response["status"]) == 201
    assert response["payload"]["ok"] is True
    assert response["payload"]["pairing"]["token"] == "valid-token"
    assert response["payload"]["pairing"]["pin"] == "1234"


def test_pair_exchange_requires_token() -> None:
    service = _service()
    response = service.route_post(
        "/api/v1/endpoints/moonlight/pair-exchange",
        endpoint_identity={"vmid": 100, "node": "beagle-0", "hostname": "endpoint-a"},
        query={},
        json_payload={},
    )

    assert int(response["status"]) == 400
    assert "missing pairing_token" in response["payload"]["error"]


def test_pair_exchange_success() -> None:
    service = _service()
    response = service.route_post(
        "/api/v1/endpoints/moonlight/pair-exchange",
        endpoint_identity={"vmid": 100, "node": "beagle-0", "hostname": "endpoint-a"},
        query={},
        json_payload={"pairing_token": "valid-token"},
    )

    assert int(response["status"]) == 200
    assert response["payload"]["ok"] is True


def test_session_current_route_uses_vmid_from_endpoint_identity() -> None:
    service = _service()
    response = service.route_get(
        "/api/v1/session/current",
        endpoint_identity={"vmid": 100, "node": "beagle-0", "hostname": "endpoint-a"},
        query={},
    )

    assert int(response["status"]) == 200
    assert response["payload"]["ok"] is True
    assert response["payload"]["current_node"] == "beagle-2"
    assert response["payload"]["stream_host"] == "srv2.beagle-os.com"
    assert response["payload"]["moonlight_port"] == "47984"
    assert response["payload"]["reconnect_required"] is True
