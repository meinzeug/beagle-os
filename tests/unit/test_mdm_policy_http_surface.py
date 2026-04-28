from __future__ import annotations

import sys
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from mdm_policy_http_surface import MDMPolicyHttpSurfaceService
from mdm_policy_service import MDMPolicyService


def _service(tmp_path: Path) -> MDMPolicyHttpSurfaceService:
    return MDMPolicyHttpSurfaceService(
        mdm_policy_service=MDMPolicyService(state_file=tmp_path / "mdm.json"),
        requester_identity=lambda: "admin",
        audit_event=lambda *args, **kwargs: None,
        service_name="beagle-control-plane",
        utcnow=lambda: "2026-04-28T00:00:00Z",
        version="test",
    )


def test_policy_create_list_assign_update_delete_flow(tmp_path: Path) -> None:
    service = _service(tmp_path)

    created = service.route_post(
        "/api/v1/fleet/policies",
        json_payload={
            "policy_id": "corp",
            "name": "Corporate",
            "allowed_pools": ["pool-a"],
            "screen_lock_timeout_seconds": 300,
        },
        requester="admin",
    )
    assert int(created["status"]) == 201
    assert created["payload"]["policy"]["policy_id"] == "corp"

    listing = service.route_get("/api/v1/fleet/policies")
    assert int(listing["status"]) == 200
    assert listing["payload"]["policies"][0]["policy_id"] == "corp"

    updated = service.route_put(
        "/api/v1/fleet/policies/corp",
        json_payload={"name": "Corporate Updated", "allowed_pools": "pool-a,pool-b"},
        requester="admin",
    )
    assert int(updated["status"]) == 200
    assert updated["payload"]["policy"]["name"] == "Corporate Updated"
    assert updated["payload"]["policy"]["allowed_pools"] == ["pool-a", "pool-b"]

    deleted = service.route_delete("/api/v1/fleet/policies/corp", requester="admin")
    assert int(deleted["status"]) == 200
    assert deleted["payload"]["deleted"] is True


def test_assignment_flow_and_clear(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.route_post(
        "/api/v1/fleet/policies",
        json_payload={"policy_id": "corp", "name": "Corporate"},
        requester="admin",
    )

    assigned = service.route_post(
        "/api/v1/fleet/policies/assignments",
        json_payload={"target_type": "device", "target_id": "dev-001", "policy_id": "corp"},
        requester="admin",
    )
    assert int(assigned["status"]) == 200
    assert assigned["payload"]["device_assignments"]["dev-001"] == "corp"

    cleared = service.route_post(
        "/api/v1/fleet/policies/assignments",
        json_payload={"target_type": "device", "target_id": "dev-001", "policy_id": ""},
        requester="admin",
    )
    assert int(cleared["status"]) == 200
    assert cleared["payload"]["device_assignments"] == {}


def test_bulk_assignment_flow(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.route_post(
        "/api/v1/fleet/policies",
        json_payload={"policy_id": "corp", "name": "Corporate"},
        requester="admin",
    )

    assigned = service.route_post(
        "/api/v1/fleet/policies/assignments/bulk",
        json_payload={"target_type": "device", "target_ids": ["dev-001", "dev-002"], "policy_id": "corp"},
        requester="admin",
    )
    assert int(assigned["status"]) == 200
    assert assigned["payload"]["affected_ids"] == ["dev-001", "dev-002"]

    cleared = service.route_post(
        "/api/v1/fleet/policies/assignments/bulk",
        json_payload={"target_type": "device", "target_ids": ["dev-001", "dev-002"], "policy_id": ""},
        requester="admin",
    )
    assert int(cleared["status"]) == 200
    assert cleared["payload"]["assignment_status"] == "cleared"


def test_policy_create_rejects_invalid_payload(tmp_path: Path) -> None:
    service = _service(tmp_path)
    response = service.route_post(
        "/api/v1/fleet/policies",
        json_payload={
            "policy_id": "corp",
            "name": "Corporate",
            "allowed_codecs": ["badcodec"],
            "update_window_start_hour": 2,
            "update_window_end_hour": 2,
        },
        requester="admin",
    )
    assert int(response["status"]) == 400
    assert "invalid codecs" in response["payload"]["error"]


def test_policy_list_includes_validation_metadata(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.route_post(
        "/api/v1/fleet/policies",
        json_payload={"policy_id": "corp", "name": "Corporate", "screen_lock_timeout_seconds": 600},
        requester="admin",
    )
    listing = service.route_get("/api/v1/fleet/policies")
    assert int(listing["status"]) == 200
    validation = listing["payload"]["policies"][0]["validation"]
    assert validation["ok"] is True
    assert "policy allows all pools" in validation["warnings"]
