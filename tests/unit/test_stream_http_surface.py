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
    def __init__(self, vmid: int, node: str = "srv2") -> None:
        self.vmid = vmid
        self.node = node


class _Pool:
    def __init__(self, pool_id: str) -> None:
        self.pool_id = pool_id


class _PoolManager:
    def __init__(self) -> None:
        self._sessions = [
            {
                "session_id": "gaming-1:303",
                "pool_id": "gaming-1",
                "vmid": 303,
                "current_node": "srv2",
                "status": "active",
            }
        ]

    def list_active_sessions(self):
        return list(self._sessions)

    def list_pools(self):
        return [_Pool("gaming-1")]

    def list_desktops(self, pool_id: str):
        if pool_id != "gaming-1":
            return []
        return [{"vmid": 303, "node": "srv2"}]


def _service(
    tmp_path: Path,
    *,
    network_mode: str = "vpn_required",
) -> tuple[StreamHttpSurfaceService, list[tuple[str, str, dict]]]:
    vm = _Vm(303)
    audit_events: list[tuple[str, str, dict]] = []
    policy_service = StreamPolicyService(state_file=tmp_path / "stream-policies.json")
    policy_service.create_policy(
        StreamPolicy(
            policy_id="gaming-tight",
            name="Gaming Tight",
            max_fps=120,
            max_bitrate_mbps=35,
            resolution="2560x1440",
            codec="h265",
            network_mode=network_mode,
            usb_redirect=True,
        )
    )
    policy_service.assign_policy("gaming-1", "gaming-tight")

    service = StreamHttpSurfaceService(
        state_file=tmp_path / "streams" / "servers.json",
        build_vm_profile=lambda found_vm: {"stream_host": "srv2.beagle-os.com", "beagle_stream_client_port": 47984},
        find_vm=lambda vmid: vm if int(vmid) == 303 else None,
        pool_manager_service=_PoolManager(),
        stream_policy_service=policy_service,
        requester_identity=lambda: "alice",
        audit_event=lambda event_type, outcome, **details: audit_events.append((event_type, outcome, details)),
        utcnow=lambda: "2026-04-28T12:00:00Z",
        version="test",
    )
    return service, audit_events


def test_handles_stream_routes() -> None:
    assert StreamHttpSurfaceService.handles_post("/api/v1/streams/register") is True
    assert StreamHttpSurfaceService.handles_post("/api/v1/streams/allocate") is True
    assert StreamHttpSurfaceService.handles_post("/api/v1/streams/303/events") is True
    assert StreamHttpSurfaceService.handles_get("/api/v1/streams/303/config") is True
    assert StreamHttpSurfaceService.requires_json_body("/api/v1/streams/303/events") is True
    assert StreamHttpSurfaceService.handles_get("/api/v1/vms/303") is False


def test_register_returns_links_and_persists_state(tmp_path: Path) -> None:
    service, audit_events = _service(tmp_path)

    response = service.route_post(
        "/api/v1/streams/register",
        json_payload={
            "vm_id": 303,
            "stream_server_id": "streamd-303",
            "host": "10.0.0.44",
            "port": 47990,
            "wireguard_active": True,
            "capabilities": {"encoders": ["h264", "h265"]},
        },
    )

    assert response is not None
    assert response["status"] == 201
    payload = response["payload"]
    assert payload["registration"]["stream_server_id"] == "streamd-303"
    assert payload["registration"]["links"]["config"] == "/api/v1/streams/303/config"
    assert payload["registration"]["pool_id"] == "gaming-1"
    assert audit_events[0][0] == "stream.server.register"


def test_register_rejects_when_vpn_required_without_wireguard(tmp_path: Path) -> None:
    service, audit_events = _service(tmp_path, network_mode="vpn_required")

    response = service.route_post(
        "/api/v1/streams/register",
        json_payload={
            "vm_id": 303,
            "stream_server_id": "streamd-303",
            "wireguard_active": False,
        },
    )

    assert response is not None
    assert response["status"] == 403
    assert "vpn_required" in response["payload"]["error"]
    assert audit_events[-1][0] == "stream.server.register"
    assert audit_events[-1][1] == "forbidden"


def test_config_returns_dynamic_policy_and_vm_profile(tmp_path: Path) -> None:
    service, _audit_events = _service(tmp_path)
    service.route_post(
        "/api/v1/streams/register",
        json_payload={"vm_id": 303, "wireguard_active": True},
    )

    response = service.route_get("/api/v1/streams/303/config", query={})

    assert response is not None
    assert response["status"] == 200
    config = response["payload"]["config"]
    assert config["stream_host"] == "srv2.beagle-os.com"
    assert config["policy"]["max_fps"] == 120
    assert config["policy"]["codec"] == "h265"
    assert config["policy"]["network_mode"] == "vpn_required"
    assert config["wireguard_active"] is True
    assert config["connection_allowed"] is True


def test_config_rejects_direct_access_when_vpn_required(tmp_path: Path) -> None:
    service, _audit_events = _service(tmp_path)
    service.route_post(
        "/api/v1/streams/register",
        json_payload={"vm_id": 303, "wireguard_active": False},
    )

    response = service.route_get("/api/v1/streams/303/config", query={})

    assert response is not None
    assert response["status"] == 403
    assert "vpn_required" in response["payload"]["error"]
    assert response["payload"]["config"]["connection_allowed"] is False


def test_config_allows_direct_fallback_when_vpn_preferred(tmp_path: Path) -> None:
    service, _audit_events = _service(tmp_path, network_mode="vpn_preferred")
    service.route_post(
        "/api/v1/streams/register",
        json_payload={"vm_id": 303, "wireguard_active": False},
    )

    response = service.route_get("/api/v1/streams/303/config", query={})

    assert response is not None
    assert response["status"] == 200
    assert response["payload"]["config"]["policy"]["network_mode"] == "vpn_preferred"
    assert response["payload"]["config"]["wireguard_active"] is False
    assert response["payload"]["config"]["connection_allowed"] is True


def test_events_write_audit_records(tmp_path: Path) -> None:
    service, audit_events = _service(tmp_path)
    service.route_post(
        "/api/v1/streams/register",
        json_payload={"vm_id": 303, "wireguard_active": True},
    )

    response = service.route_post(
        "/api/v1/streams/303/events",
        json_payload={
            "event_type": "session.start",
            "details": {"user_id": "carol", "transport": "wireguard"},
        },
    )

    assert response is not None
    assert response["status"] == 200
    assert audit_events[-1][0] == "stream.session.start"
    assert audit_events[-1][1] == "success"
    assert audit_events[-1][2]["vm_id"] == 303
    assert audit_events[-1][2]["details"]["transport"] == "wireguard"


def test_events_reject_session_start_when_vpn_required_without_wireguard(tmp_path: Path) -> None:
    service, audit_events = _service(tmp_path, network_mode="vpn_required")
    service.route_post(
        "/api/v1/streams/register",
        json_payload={"vm_id": 303, "wireguard_active": True},
    )

    response = service.route_post(
        "/api/v1/streams/303/events",
        json_payload={
            "event_type": "session.start",
            "details": {"user_id": "carol", "wireguard_active": False},
        },
    )

    assert response is not None
    assert response["status"] == 403
    assert "vpn_required" in response["payload"]["error"]
    assert audit_events[-1][0] == "stream.session.start"
    assert audit_events[-1][1] == "forbidden"


def test_events_timeout_writes_error_audit(tmp_path: Path) -> None:
    service, audit_events = _service(tmp_path)
    service.route_post(
        "/api/v1/streams/register",
        json_payload={"vm_id": 303, "wireguard_active": True},
    )

    response = service.route_post(
        "/api/v1/streams/303/events",
        json_payload={
            "event_type": "session.timeout",
            "outcome": "error",
            "details": {"reason": "simulated-timeout"},
        },
    )

    assert response is not None
    assert response["status"] == 200
    assert response["payload"]["ok"] is True
    assert audit_events[-1][0] == "stream.session.timeout"
    assert audit_events[-1][1] == "error"


def test_events_timeout_audit_supports_dict_signature_writer(tmp_path: Path) -> None:
    vm = _Vm(303)
    audit_events: list[tuple[str, str, dict]] = []
    policy_service = StreamPolicyService(state_file=tmp_path / "stream-policies.json")
    policy_service.create_policy(StreamPolicy(policy_id="p1", name="P1"))
    policy_service.assign_policy("gaming-1", "p1")

    class _Pm:
        def list_active_sessions(self):
            return []

        def list_pools(self):
            return [_Pool("gaming-1")]

        def list_desktops(self, pool_id: str):
            return [{"vmid": 303, "node": "srv2"}] if pool_id == "gaming-1" else []

    def dict_writer(event_type: str, outcome: str, details: dict[str, Any] | None = None) -> None:
        audit_events.append((event_type, outcome, details if isinstance(details, dict) else {}))

    service = StreamHttpSurfaceService(
        state_file=tmp_path / "streams" / "servers.json",
        build_vm_profile=lambda found_vm: {"stream_host": "srv2.beagle-os.com", "beagle_stream_client_port": 47984},
        find_vm=lambda vmid: vm if int(vmid) == 303 else None,
        pool_manager_service=_Pm(),
        stream_policy_service=policy_service,
        requester_identity=lambda: "alice",
        audit_event=dict_writer,
        utcnow=lambda: "2026-04-28T12:00:00Z",
        version="test",
    )

    response = service.route_post(
        "/api/v1/streams/303/events",
        json_payload={
            "event_type": "session.timeout",
            "outcome": "error",
            "details": {"reason": "dict-signature"},
        },
    )

    assert response is not None
    assert response["status"] == 200
    assert audit_events[-1][0] == "stream.session.timeout"
    assert audit_events[-1][1] == "error"
    assert audit_events[-1][2]["username"] == "alice"


# ── D2 acceptance criteria: /api/v1/streams/allocate ─────────────────────────

def _allocate_service(
    tmp_path: Path,
    *,
    network_mode: str = "vpn_preferred",
    issue_pairing_token=None,
    build_wireguard_peer_config=None,
) -> tuple[StreamHttpSurfaceService, list[tuple]]:
    vm = _Vm(303)
    audit_events: list[tuple] = []
    policy_service = StreamPolicyService(state_file=tmp_path / "stream-policies.json")
    policy_service.create_policy(
        StreamPolicy(policy_id="pool1", name="Pool1", network_mode=network_mode)
    )
    policy_service.assign_policy("pool1", "pool1")

    class _Pm:
        def list_active_sessions(self):
            return []

        def list_pools(self):
            return [_Pool("pool1")]

        def list_desktops(self, pool_id):
            return [{"vmid": 303, "node": "srv2"}] if pool_id == "pool1" else []

        def allocate_desktop(self, pool_id, user_id):
            class _Lease:
                vm_id = 303
                session_id = f"{pool_id}:{user_id}"
            return _Lease()

    service = StreamHttpSurfaceService(
        state_file=tmp_path / "streams" / "servers.json",
        build_vm_profile=lambda found_vm: {
            "stream_host": "192.168.123.116",
            "beagle_stream_client_local_host": "10.88.1.100",
            "beagle_stream_client_port": 50000,
        },
        find_vm=lambda vmid: vm if int(vmid) == 303 else None,
        pool_manager_service=_Pm(),
        stream_policy_service=policy_service,
        requester_identity=lambda: "alice",
        audit_event=lambda event_type, outcome, **details: audit_events.append((event_type, outcome, details)),
        utcnow=lambda: "2026-05-04T12:00:00Z",
        version="test",
        issue_pairing_token=issue_pairing_token,
        build_wireguard_peer_config=build_wireguard_peer_config,
    )
    return service, audit_events


def test_allocate_returns_explicit_vm_target(tmp_path: Path) -> None:
    """D2: allocate must return an explicit vm_id, host_ip, and port — not just a pool reference."""
    service, _ = _allocate_service(tmp_path)
    response = service.route_post(
        "/api/v1/streams/allocate",
        json_payload={"pool_id": "pool1", "device_id": "dev-1"},
    )
    assert response is not None
    assert response["status"] == 200
    payload = response["payload"]
    assert payload["ok"] is True
    # Explicit VM target fields must be present and non-empty
    assert payload["allocation"]["vm_id"] == 303
    assert payload["host_ip"] != ""
    assert payload["port"] > 0


def test_allocate_vpn_preferred_uses_local_host_when_wg_peer_provided(tmp_path: Path) -> None:
    """D2: When WG peer config is in payload, allocate should prefer the local/VPN host IP."""
    service, _ = _allocate_service(tmp_path, network_mode="vpn_preferred")
    response = service.route_post(
        "/api/v1/streams/allocate",
        json_payload={
            "pool_id": "pool1",
            "device_id": "dev-1",
            "wg_peer_config": {"public_key": "abc", "endpoint": "1.2.3.4:51820", "allowed_ips": "10.88.0.0/16"},
        },
    )
    assert response is not None
    assert response["status"] == 200
    # With WG peer config present, local_stream_host should be used
    assert response["payload"]["host_ip"] == "10.88.1.100"


def test_allocate_vpn_required_blocks_without_wireguard_config(tmp_path: Path) -> None:
    """D2: vpn_required policy must block allocation when no WireGuard peer config is available."""
    service, _ = _allocate_service(tmp_path, network_mode="vpn_required")
    response = service.route_post(
        "/api/v1/streams/allocate",
        json_payload={"pool_id": "pool1", "device_id": "dev-1"},
    )
    assert response is not None
    assert response["status"] == 403
    assert response["payload"]["ok"] is False
    assert "vpn_required" in response["payload"]["error"]


def test_allocate_vpn_required_succeeds_with_wireguard_config(tmp_path: Path) -> None:
    """D2: vpn_required policy allows allocation when WireGuard peer config is present."""
    service, _ = _allocate_service(tmp_path, network_mode="vpn_required")
    response = service.route_post(
        "/api/v1/streams/allocate",
        json_payload={
            "pool_id": "pool1",
            "device_id": "dev-1",
            "wg_peer_config": {"public_key": "pk", "endpoint": "5.6.7.8:51820", "allowed_ips": "10.88.0.0/16"},
        },
    )
    assert response is not None
    assert response["status"] == 200


def test_allocate_pairing_token_not_in_audit_log(tmp_path: Path) -> None:
    """D2/Security: pairing tokens must never appear in audit log details."""
    SENSITIVE_TOKEN = "secret-pairing-token-xyz"
    service, audit_events = _allocate_service(
        tmp_path,
        issue_pairing_token=lambda vm_id, user_id, device_id: SENSITIVE_TOKEN,
    )
    response = service.route_post(
        "/api/v1/streams/allocate",
        json_payload={"pool_id": "pool1", "device_id": "dev-1"},
    )
    assert response is not None
    assert response["status"] == 200
    # Token is in the response payload (for the client) ...
    assert response["payload"]["token"] == SENSITIVE_TOKEN
    # ... but must NOT appear in any audit log entry
    for event_type, outcome, details in audit_events:
        for k, v in details.items():
            assert SENSITIVE_TOKEN not in str(v), (
                f"Token leaked into audit log field '{k}' of event '{event_type}'"
            )


def test_allocate_wg_peer_config_public_key_not_in_audit_log(tmp_path: Path) -> None:
    """D2/Security: WireGuard public keys and peer config must not appear verbatim in audit log."""
    WG_PUBLIC_KEY = "wg-public-key-abc123"
    service, audit_events = _allocate_service(
        tmp_path,
        build_wireguard_peer_config=lambda device_id, pool_id, user_id: {
            "public_key": WG_PUBLIC_KEY,
            "endpoint": "10.0.0.1:51820",
            "allowed_ips": ["10.88.0.0/16"],
        },
    )
    response = service.route_post(
        "/api/v1/streams/allocate",
        json_payload={"pool_id": "pool1", "device_id": "dev-1"},
    )
    assert response is not None
    assert response["status"] == 200
    # Audit log should record wireguard_profile=True but not the actual key
    allocate_events = [(e, o, d) for e, o, d in audit_events if e == "stream.client.allocate"]
    assert len(allocate_events) == 1
    _, _, details = allocate_events[0]
    assert "wireguard_profile" in details
    assert details["wireguard_profile"] is True
    for k, v in details.items():
        assert WG_PUBLIC_KEY not in str(v), (
            f"WG public key leaked into audit log field '{k}'"
        )


def test_allocate_missing_pool_id_returns_400(tmp_path: Path) -> None:
    service, _ = _allocate_service(tmp_path)
    response = service.route_post(
        "/api/v1/streams/allocate",
        json_payload={"device_id": "dev-1"},
    )
    assert response is not None
    assert response["status"] == 400


def test_allocate_missing_device_id_and_user_id_returns_400(tmp_path: Path) -> None:
    service, _ = _allocate_service(tmp_path)
    response = service.route_post(
        "/api/v1/streams/allocate",
        json_payload={"pool_id": "pool1"},
    )
    assert response is not None
    assert response["status"] == 400
