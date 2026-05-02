from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from stream_http_surface import StreamHttpSurfaceService
from stream_policy_service import StreamPolicy, StreamPolicyService


class _Vm:
    def __init__(self, vmid: int, node: str = "srv1") -> None:
        self.vmid = vmid
        self.node = node


class _PoolManager:
    def __init__(self) -> None:
        self._allocated: list[tuple[str, str]] = []

    def allocate_desktop(self, pool_id: str, user_id: str):
        self._allocated.append((pool_id, user_id))
        return SimpleNamespace(session_id=f"{pool_id}:{user_id}:1", vm_id=303)

    def list_active_sessions(self):
        return []

    def list_pools(self):
        return []

    def list_desktops(self, _pool_id: str):
        return []


def _service(
    tmp_path: Path,
    *,
    network_mode: str,
    wg_config: dict | None = None,
) -> tuple[StreamHttpSurfaceService, _PoolManager]:
    vm = _Vm(303)
    pool_manager = _PoolManager()
    policy_service = StreamPolicyService(state_file=tmp_path / "stream-policies.json")
    policy_service.create_policy(
        StreamPolicy(
            policy_id="pool-policy",
            name="Pool Policy",
            network_mode=network_mode,
            max_fps=120,
            max_bitrate_mbps=35,
            resolution="1920x1080",
            codec="h265",
        )
    )
    policy_service.assign_policy("gaming-1", "pool-policy")

    return StreamHttpSurfaceService(
        state_file=tmp_path / "streams" / "servers.json",
        build_vm_profile=lambda _vm: {"stream_host": "10.10.10.5", "beagle_stream_client_port": 47984},
        find_vm=lambda vmid: vm if int(vmid) == 303 else None,
        pool_manager_service=pool_manager,
        stream_policy_service=policy_service,
        build_wireguard_peer_config=lambda _device_id, _pool_id, _user_id: dict(wg_config or {}),
        issue_pairing_token=lambda vm_id, user_id, device_id: f"tok-{vm_id}-{user_id}-{device_id}",
        requester_identity=lambda: "alice",
        utcnow=lambda: "2026-04-28T13:00:00Z",
        version="test",
    ), pool_manager


def test_stream_allocate_returns_broker_payload(tmp_path: Path) -> None:
    service, pool_manager = _service(tmp_path, network_mode="vpn_preferred", wg_config={"peer": "wg0"})

    response = service.route_post(
        "/api/v1/streams/allocate",
        json_payload={
            "pool_id": "gaming-1",
            "user_id": "carol",
            "device_id": "thin-01",
        },
    )

    assert response is not None
    assert response["status"] == 200
    allocation = response["payload"]["allocation"]
    assert allocation["pool_id"] == "gaming-1"
    assert allocation["user_id"] == "carol"
    assert allocation["vm_id"] == 303
    assert allocation["host_ip"] == "10.10.10.5"
    assert allocation["port"] == 47984
    assert allocation["token"].startswith("tok-303-carol")
    assert allocation["wg_peer_config"]["peer"] == "wg0"
    assert pool_manager._allocated == [("gaming-1", "carol")]


def test_stream_allocate_accepts_hostless_device_without_user_id(tmp_path: Path) -> None:
    service, pool_manager = _service(tmp_path, network_mode="vpn_preferred", wg_config={"peer": "wg0"})

    response = service.route_post(
        "/api/v1/streams/allocate",
        json_payload={
            "pool_id": "gaming-1",
            "user_id": "",
            "device_id": "thin-99",
        },
    )

    assert response is not None
    assert response["status"] == 200
    allocation = response["payload"]["allocation"]
    assert allocation["user_id"] == ""
    assert allocation["lease_user_id"] == "device:thin-99"
    assert allocation["token"] == "tok-303-device:thin-99-thin-99"
    assert pool_manager._allocated == [("gaming-1", "device:thin-99")]


def test_stream_allocate_accepts_direct_vm_id_with_endpoint_identity(tmp_path: Path) -> None:
    service, pool_manager = _service(tmp_path, network_mode="vpn_preferred", wg_config={"peer": "wg0"})

    response = service.route_post(
        "/api/v1/streams/allocate",
        json_payload={
            "pool_id": "vm-303",
            "user_id": "",
        },
        endpoint_identity={"endpoint_id": "thin-303"},
    )

    assert response is not None
    assert response["status"] == 200
    allocation = response["payload"]["allocation"]
    assert allocation["pool_id"] == "vm-303"
    assert allocation["vm_id"] == 303
    assert allocation["user_id"] == ""
    assert allocation["lease_user_id"] == "device:thin-303"
    assert allocation["session_id"] == "vm-303:device:thin-303"
    assert allocation["token"] == "tok-303-device:thin-303-thin-303"
    assert pool_manager._allocated == []


def test_stream_allocate_rejects_missing_user_and_device_identity(tmp_path: Path) -> None:
    service, pool_manager = _service(tmp_path, network_mode="vpn_preferred", wg_config={"peer": "wg0"})

    response = service.route_post(
        "/api/v1/streams/allocate",
        json_payload={
            "pool_id": "gaming-1",
            "user_id": "",
            "device_id": "",
        },
    )

    assert response is not None
    assert response["status"] == 400
    assert "device_id required" in response["payload"]["error"]
    assert pool_manager._allocated == []


def test_stream_allocate_rejects_when_vpn_required_and_no_wg(tmp_path: Path) -> None:
    service, _pool_manager = _service(tmp_path, network_mode="vpn_required", wg_config={})

    response = service.route_post(
        "/api/v1/streams/allocate",
        json_payload={
            "pool_id": "gaming-1",
            "user_id": "carol",
            "device_id": "thin-02",
        },
    )

    assert response is not None
    assert response["status"] == 403
    assert "vpn_required" in response["payload"]["error"]
