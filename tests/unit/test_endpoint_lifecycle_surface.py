from __future__ import annotations

import sys
from http import HTTPStatus
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from endpoint_lifecycle_surface import EndpointLifecycleSurfaceService


def _service() -> EndpointLifecycleSurfaceService:
    return EndpointLifecycleSurfaceService(
        enroll_endpoint=lambda payload: {"ok": True, "config": payload},
        register_wireguard_peer=lambda identity, payload: {
            "ok": True,
            "device_id": identity.get("endpoint_id", ""),
            "server_endpoint": "srv1.beagle-os.com:51820",
            "client_ip": "10.88.1.10/32",
            "allowed_ips": "0.0.0.0/0",
        },
        service_name="beagle-control-plane",
        store_endpoint_report=lambda _node, _vmid, _payload: Path("/tmp/report.json"),
        summarize_endpoint_report=lambda payload: payload,
        utcnow=lambda: "2026-04-29T05:00:00Z",
        version="test",
    )


def test_handles_vpn_register_path() -> None:
    assert EndpointLifecycleSurfaceService.handles_post("/api/v1/vpn/register") is True
    assert EndpointLifecycleSurfaceService.requires_endpoint_auth("/api/v1/vpn/register") is True


def test_vpn_register_returns_mesh_payload() -> None:
    response = _service().route_post(
        "/api/v1/vpn/register",
        endpoint_identity={"endpoint_id": "thin-01", "vmid": 100, "node": "beagle-0"},
        json_payload={"device_id": "thin-01", "public_key": "PUBKEY=="},
        remote_addr="127.0.0.1",
    )

    assert int(response["status"]) == int(HTTPStatus.OK)
    assert response["payload"]["ok"] is True
    assert response["payload"]["device_id"] == "thin-01"
    assert response["payload"]["allowed_ips"] == "0.0.0.0/0"
