from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from stream_http_surface import StreamHttpSurfaceService
from stream_policy_service import StreamPolicy, StreamPolicyService


class _Vm:
    def __init__(self, vmid: int, node: str = "beagle-2") -> None:
        self.vmid = vmid
        self.node = node


class _Pool:
    def __init__(self, pool_id: str) -> None:
        self.pool_id = pool_id


class _PoolManager:
    def __init__(self) -> None:
        self._sessions = [
            {
                "session_id": "design-1:501",
                "pool_id": "design-1",
                "vmid": 501,
                "current_node": "beagle-2",
                "status": "active",
            }
        ]

    def list_active_sessions(self):
        return list(self._sessions)

    def list_pools(self):
        return [_Pool("design-1")]

    def list_desktops(self, pool_id: str):
        if pool_id != "design-1":
            return []
        return [{"vmid": 501, "node": "beagle-2"}]


def _service(tmp_path: Path) -> tuple[StreamHttpSurfaceService, list[tuple[str, str, dict]]]:
    vm = _Vm(501)
    audit_events: list[tuple[str, str, dict]] = []

    policy_service = StreamPolicyService(state_file=tmp_path / "stream-policies.json")
    policy_service.create_policy(
        StreamPolicy(
            policy_id="design-secure",
            name="Design Secure",
            max_fps=60,
            max_bitrate_mbps=28,
            resolution="2560x1440",
            codec="h265",
            network_mode="vpn_required",
        )
    )
    policy_service.assign_policy("design-1", "design-secure")

    service = StreamHttpSurfaceService(
        state_file=tmp_path / "streams" / "servers.json",
        build_vm_profile=lambda found_vm: {"stream_host": "srv2.beagle-os.com", "moonlight_port": 47984},
        find_vm=lambda vmid: vm if int(vmid) == vm.vmid else None,
        pool_manager_service=_PoolManager(),
        stream_policy_service=policy_service,
        requester_identity=lambda: "streamd",
        audit_event=lambda event_type, outcome, **details: audit_events.append((event_type, outcome, details)),
        utcnow=lambda: "2026-04-28T19:30:00Z",
        version="test",
    )
    return service, audit_events


def test_stream_server_register_and_config_contract(tmp_path: Path) -> None:
    service, _audit_events = _service(tmp_path)

    register = service.route_post(
        "/api/v1/streams/register",
        json_payload={
            "vm_id": 501,
            "stream_server_id": "beagle-streamd-501",
            "host": "10.20.0.45",
            "port": 48010,
            "wireguard_active": True,
            "capabilities": {"encoders": ["h264", "h265"], "protocol": "gamestream"},
        },
    )

    assert register is not None
    assert register["status"] == 201
    registration = register["payload"]["registration"]
    assert registration["stream_server_id"] == "beagle-streamd-501"
    assert registration["links"]["register"] == "/api/v1/streams/register"
    assert registration["links"]["config"] == "/api/v1/streams/501/config"
    assert registration["links"]["events"] == "/api/v1/streams/501/events"

    config = service.route_get("/api/v1/streams/501/config", query={})

    assert config is not None
    assert config["status"] == 200
    payload = config["payload"]["config"]
    assert payload["pool_id"] == "design-1"
    assert payload["stream_host"] == "srv2.beagle-os.com"
    assert payload["policy"]["network_mode"] == "vpn_required"
    assert payload["connection_allowed"] is True


def test_stream_server_config_denies_direct_when_vpn_required(tmp_path: Path) -> None:
    service, _audit_events = _service(tmp_path)
    service.route_post(
        "/api/v1/streams/register",
        json_payload={"vm_id": 501, "wireguard_active": True},
    )

    config = service.route_get("/api/v1/streams/501/config", query={"wireguard_active": ["false"]})

    assert config is not None
    assert config["status"] == 403
    assert "vpn_required" in config["payload"]["error"]
    assert config["payload"]["config"]["connection_allowed"] is False


def test_stream_server_events_are_audited(tmp_path: Path) -> None:
    service, audit_events = _service(tmp_path)
    service.route_post(
        "/api/v1/streams/register",
        json_payload={"vm_id": 501, "wireguard_active": True},
    )

    event = service.route_post(
        "/api/v1/streams/501/events",
        json_payload={
            "event_type": "session.stop",
            "details": {"reason": "user_disconnect", "duration_seconds": 1934},
        },
    )

    assert event is not None
    assert event["status"] == 200
    assert event["payload"]["event"]["event_type"] == "session.stop"
    assert audit_events[-1][0] == "stream.session.stop"
    assert audit_events[-1][1] == "success"
    assert audit_events[-1][2]["vm_id"] == 501
