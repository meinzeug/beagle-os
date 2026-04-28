from __future__ import annotations

import sys
from http import HTTPStatus
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from device_registry import DeviceRegistryService
from fleet_http_surface import FleetHttpSurfaceService
from mdm_policy_service import MDMPolicy, MDMPolicyService


HW = {
    "cpu_model": "Intel Core i5-8500T",
    "cpu_cores": 6,
    "ram_gb": 16,
    "gpu_model": "Intel UHD 630",
    "network_interfaces": ["eth0"],
    "disk_gb": 256,
}


def make_services(tmp_path: Path) -> tuple[DeviceRegistryService, MDMPolicyService, FleetHttpSurfaceService]:
    audit_events: list[tuple[str, str, dict[str, object]]] = []
    registry = DeviceRegistryService(
        state_file=tmp_path / "device-registry.json",
        utcnow=lambda: "2026-04-28T06:00:00Z",
    )
    mdm = MDMPolicyService(state_file=tmp_path / "mdm.json")
    service = FleetHttpSurfaceService(
        device_registry_service=registry,
        mdm_policy_service=mdm,
        audit_event=lambda event_type, outcome, **details: audit_events.append((event_type, outcome, details)),
        requester_identity=lambda: "admin",
        utcnow=lambda: "2026-04-28T06:00:00Z",
        version="test",
    )
    return registry, mdm, service


def test_register_device_and_fetch_detail(tmp_path: Path) -> None:
    _, _, service = make_services(tmp_path)

    created = service.route_post(
        "/api/v1/fleet/devices/register",
        json_payload={
            "device_id": "dev-001",
            "hostname": "tc-001",
            "hardware": HW,
            "os_version": "8.0.0",
            "wg_public_key": "pubkey",
            "wg_assigned_ip": "10.99.0.10/32",
        },
    )

    assert created is not None
    assert created["status"] == HTTPStatus.CREATED
    assert created["payload"]["device"]["device_id"] == "dev-001"

    detail = service.route_get("/api/v1/fleet/devices/dev-001")
    assert detail is not None
    assert detail["status"] == HTTPStatus.OK
    assert detail["payload"]["device"]["hostname"] == "tc-001"
    assert detail["payload"]["device"]["hardware"]["gpu_model"] == "Intel UHD 630"
    assert detail["payload"]["device"]["last_wipe_report"] == {}


def test_list_devices_returns_groups_and_filters(tmp_path: Path) -> None:
    registry, _, service = make_services(tmp_path)
    registry.register_device("dev-001", "tc-001", HW)
    registry.register_device("dev-002", "tc-002", HW)
    registry.set_group("dev-001", "berlin")
    registry.set_group("dev-002", "munich")
    registry.update_heartbeat("dev-001")

    listing = service.route_get(
        "/api/v1/fleet/devices",
        query={"group": ["berlin"], "status": ["online"]},
    )

    assert listing is not None
    assert listing["status"] == HTTPStatus.OK
    assert listing["payload"]["count"] == 1
    assert listing["payload"]["devices"][0]["device_id"] == "dev-001"
    assert "berlin" in listing["payload"]["groups"]
    assert "munich" in listing["payload"]["groups"]


def test_put_updates_location_group_and_notes(tmp_path: Path) -> None:
    registry, _, service = make_services(tmp_path)
    registry.register_device("dev-001", "tc-001", HW)

    response = service.route_put(
        "/api/v1/fleet/devices/dev-001",
        json_payload={
            "location": "Berlin-Office-1",
            "group": "reception",
            "notes": "Kiosk am Empfang",
        },
    )

    assert response is not None
    assert response["status"] == HTTPStatus.OK
    device = response["payload"]["device"]
    assert device["location"] == "Berlin-Office-1"
    assert device["group"] == "reception"
    assert device["notes"] == "Kiosk am Empfang"


def test_post_actions_change_state(tmp_path: Path) -> None:
    registry, _, service = make_services(tmp_path)
    registry.register_device("dev-001", "tc-001", HW)

    heartbeat = service.route_post(
        "/api/v1/fleet/devices/dev-001/heartbeat",
        json_payload={"metrics": {"temp_c": 41}},
    )
    assert heartbeat is not None
    assert heartbeat["status"] == HTTPStatus.OK
    assert heartbeat["payload"]["action"] == "heartbeat"
    assert heartbeat["payload"]["device"]["status"] == "online"

    locked = service.route_post("/api/v1/fleet/devices/dev-001/lock", json_payload={})
    assert locked is not None
    assert locked["payload"]["device"]["status"] == "locked"

    wipe = service.route_post("/api/v1/fleet/devices/dev-001/wipe", json_payload={})
    assert wipe is not None
    assert wipe["payload"]["device"]["status"] == "wipe_pending"

    wiped = service.route_post("/api/v1/fleet/devices/dev-001/confirm-wiped", json_payload={})
    assert wiped is not None
    assert wiped["payload"]["device"]["status"] == "wiped"


def test_put_and_actions_emit_audit_events(tmp_path: Path) -> None:
    audit_events: list[tuple[str, str, dict[str, object]]] = []
    registry = DeviceRegistryService(
        state_file=tmp_path / "device-registry.json",
        utcnow=lambda: "2026-04-28T06:00:00Z",
    )
    service = FleetHttpSurfaceService(
        device_registry_service=registry,
        audit_event=lambda event_type, outcome, **details: audit_events.append((event_type, outcome, details)),
        requester_identity=lambda: "admin",
        utcnow=lambda: "2026-04-28T06:00:00Z",
        version="test",
    )
    registry.register_device("dev-001", "tc-001", HW)

    service.route_put(
        "/api/v1/fleet/devices/dev-001",
        json_payload={"location": "Berlin", "notes": "Frontdesk"},
    )
    service.route_post("/api/v1/fleet/devices/dev-001/lock", json_payload={})

    assert audit_events[0][0] == "fleet.device.update"
    assert audit_events[0][1] == "success"
    assert audit_events[0][2]["username"] == "admin"
    assert audit_events[1][0] == "fleet.device.lock"
    assert audit_events[1][2]["device_id"] == "dev-001"


def test_register_requires_device_payload(tmp_path: Path) -> None:
    _, _, service = make_services(tmp_path)

    response = service.route_post(
        "/api/v1/fleet/devices/register",
        json_payload={"device_id": "dev-001"},
    )

    assert response is not None
    assert response["status"] == HTTPStatus.BAD_REQUEST


def test_missing_device_returns_not_found(tmp_path: Path) -> None:
    _, _, service = make_services(tmp_path)

    detail = service.route_get("/api/v1/fleet/devices/missing")
    assert detail is not None
    assert detail["status"] == HTTPStatus.NOT_FOUND

    action = service.route_post("/api/v1/fleet/devices/missing/lock", json_payload={})
    assert action is not None
    assert action["status"] == HTTPStatus.NOT_FOUND


def test_effective_policy_route_returns_group_resolved_policy(tmp_path: Path) -> None:
    registry, mdm, service = make_services(tmp_path)
    registry.register_device("dev-001", "tc-001", HW)
    registry.set_group("dev-001", "berlin")
    mdm.create_policy(MDMPolicy(policy_id="corp", name="Corporate", allowed_pools=["pool-a"]))
    mdm.assign_to_group("berlin", "corp")

    response = service.route_get("/api/v1/fleet/devices/dev-001/effective-policy")

    assert response is not None
    assert response["status"] == HTTPStatus.OK
    assert response["payload"]["source_type"] == "group"
    assert response["payload"]["source_id"] == "berlin"
    assert response["payload"]["policy"]["policy_id"] == "corp"


def test_effective_policy_route_reports_assignment_conflicts(tmp_path: Path) -> None:
    registry, mdm, service = make_services(tmp_path)
    registry.register_device("dev-001", "tc-001", HW)
    registry.set_group("dev-001", "berlin")
    mdm.create_policy(MDMPolicy(policy_id="group-policy", name="Group", allowed_pools=["pool-a"]))
    mdm.create_policy(MDMPolicy(policy_id="device-policy", name="Device", allowed_pools=["pool-b"]))
    mdm.assign_to_group("berlin", "group-policy")
    mdm.assign_to_device("dev-001", "device-policy")

    response = service.route_get("/api/v1/fleet/devices/dev-001/effective-policy")

    assert response is not None
    assert response["status"] == HTTPStatus.OK
    assert response["payload"]["policy"]["policy_id"] == "device-policy"
    assert response["payload"]["conflicts"] == ["device assignment overrides group policy group-policy"]
    assert response["payload"]["policy"]["validation"]["ok"] is True
    assert response["payload"]["diagnostics"]["effective_source_type"] == "device"
    assert response["payload"]["diagnostics"]["group_policy"]["policy_id"] == "group-policy"
    assert response["payload"]["diagnostics"]["device_policy"]["policy_id"] == "device-policy"
    assert any(entry["field"] == "allowed_pools" for entry in response["payload"]["diagnostics"]["diffs"]["device_vs_group"])
    assert response["payload"]["remediation_hints"]
    assert response["payload"]["remediation_actions"]


def test_bulk_device_action_route_updates_multiple_devices(tmp_path: Path) -> None:
    registry, _, service = make_services(tmp_path)
    registry.register_device("dev-001", "tc-001", HW)
    registry.register_device("dev-002", "tc-002", HW)

    response = service.route_post(
        "/api/v1/fleet/devices/actions/bulk",
        json_payload={"action": "set-group", "target_ids": ["dev-001", "dev-002"], "value": "berlin"},
    )

    assert response is not None
    assert response["status"] == HTTPStatus.OK
    assert len(response["payload"]["affected"]) == 2
    assert registry.get_device("dev-001").group == "berlin"
    assert registry.get_device("dev-002").group == "berlin"


def test_bulk_device_action_route_reports_missing_devices(tmp_path: Path) -> None:
    registry, _, service = make_services(tmp_path)
    registry.register_device("dev-001", "tc-001", HW)

    response = service.route_post(
        "/api/v1/fleet/devices/actions/bulk",
        json_payload={"action": "lock", "target_ids": ["dev-001", "missing"]},
    )

    assert response is not None
    assert response["status"] == HTTPStatus.OK
    assert len(response["payload"]["affected"]) == 1
    assert response["payload"]["failed"] == [{"device_id": "missing", "error": "device not found"}]
