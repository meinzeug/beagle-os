from __future__ import annotations

import sys
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from endpoint_http_surface import EndpointHttpSurfaceService
from core.virtualization.desktop_pool import DesktopPoolInfo, DesktopPoolMode, DesktopPoolType, SessionRecordingPolicy
from core.virtualization.streaming_profile import StreamingNetworkMode, StreamingProfile


class _Vm:
    def __init__(self, vmid: int, node: str) -> None:
        self.vmid = vmid
        self.node = node


def _service(*, prepare_ok: bool = True, network_mode: str = "vpn_preferred") -> EndpointHttpSurfaceService:
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

    class _DeviceRegistry:
        def __init__(self) -> None:
            self.devices = {}

        def register_or_update_device(self, device_id, hostname, hardware_info, **kwargs):
            self.devices[device_id] = {
                "device_id": device_id,
                "hostname": hostname,
                "hardware": hardware_info,
                "os_version": kwargs.get("os_version", ""),
                "group": self.devices.get(device_id, {}).get("group", ""),
                "location": self.devices.get(device_id, {}).get("location", ""),
                "status": self.devices.get(device_id, {}).get("status", "offline"),
                "vpn_active": bool(kwargs.get("vpn_active", self.devices.get(device_id, {}).get("vpn_active", False))),
                "vpn_interface": kwargs.get("vpn_interface", self.devices.get(device_id, {}).get("vpn_interface", "")),
                "wg_assigned_ip": kwargs.get("wg_assigned_ip", self.devices.get(device_id, {}).get("wg_assigned_ip", "")),
                "last_seen": "",
                "last_wipe_report": self.devices.get(device_id, {}).get("last_wipe_report", {}),
            }
            return type("Device", (), self.devices[device_id])()

        def update_heartbeat(self, device_id, metrics=None):
            self.devices[device_id]["last_seen"] = "2026-04-22T00:00:00Z"
            return type("Device", (), self.devices[device_id])()

        def get_device(self, device_id):
            payload = self.devices.get(device_id)
            if payload is None:
                return None
            return type("Device", (), payload)()

        def confirm_wiped(self, device_id):
            self.devices[device_id]["status"] = "wiped"
            self.devices[device_id]["vpn_active"] = False
            self.devices[device_id]["vpn_interface"] = ""
            self.devices[device_id]["wg_assigned_ip"] = ""
            return type("Device", (), self.devices[device_id])()

        def update_wipe_report(self, device_id, report):
            self.devices[device_id]["last_wipe_report"] = dict(report or {})
            return type("Device", (), self.devices[device_id])()

    class _PoolManager:
        @staticmethod
        def get_pool(pool_id):
            if pool_id != "pool-a":
                return None
            return DesktopPoolInfo(
                pool_id="pool-a",
                template_id="tpl-a",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=2,
                warm_pool_size=0,
                gpu_class="",
                session_recording=SessionRecordingPolicy.DISABLED,
                recording_retention_days=30,
                free_desktops=0,
                in_use_desktops=1,
                recycling_desktops=0,
                error_desktops=0,
                enabled=True,
                streaming_profile=StreamingProfile(network_mode=StreamingNetworkMode(network_mode)),
                tenant_id="",
                pool_type=DesktopPoolType.DESKTOP,
            )

    class _Policy:
        policy_id = "corp"
        name = "Corp"
        allowed_networks = ["wg"]
        allowed_pools = ["pool-a"]
        max_resolution = "1920x1080"
        allowed_codecs = ["h264"]
        auto_update = True
        update_window_start_hour = 2
        update_window_end_hour = 4
        screen_lock_timeout_seconds = 300

    class _AttestationRecord:
        status = "attested"
        last_checked = "2026-04-22T00:00:00Z"

    class _AttestationService:
        @staticmethod
        def get_record(device_id):
            return _AttestationRecord()

        @staticmethod
        def is_session_allowed(device_id):
            return True, "status=attested"

    return EndpointHttpSurfaceService(
        build_vm_profile=lambda found_vm: profiles.get(int(found_vm.vmid), {}),
        dequeue_vm_actions=lambda node, vmid: [],
        device_registry_service=_DeviceRegistry(),
        mdm_policy_service=type("Mdm", (), {"resolve_policy": staticmethod(lambda device_id, group="": _Policy())})(),
        attestation_service=_AttestationService(),
        exchange_moonlight_pairing_token=lambda vm, endpoint_identity, pairing_token: {"ok": pairing_token == "valid-token"},
        fetch_sunshine_server_identity=lambda vm, guest_user: {},
        find_vm=_find,
        issue_moonlight_pairing_token=lambda vm, endpoint_identity, device_name: {
            "ok": True,
            "token": "valid-token",
            "pin": "1234",
            "expires_at": "2026-04-22T00:10:00Z",
        },
        pool_manager_service=_PoolManager(),
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
    assert EndpointHttpSurfaceService.handles_path("/api/v1/endpoints/device/sync") is True
    assert EndpointHttpSurfaceService.handles_path("/api/v1/endpoints/device/confirm-wiped") is True
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
    service.route_post(
        "/api/v1/endpoints/device/sync",
        endpoint_identity={"endpoint_id": "endpoint-a", "vmid": 100, "node": "beagle-0", "hostname": "endpoint-a"},
        query={},
        json_payload={"vpn": {"active": True, "interface": "wg-beagle", "assigned_ip": "10.88.0.10/32"}},
    )
    response = service.route_get(
        "/api/v1/session/current",
        endpoint_identity={"endpoint_id": "endpoint-a", "vmid": 100, "node": "beagle-0", "hostname": "endpoint-a"},
        query={},
    )

    assert int(response["status"]) == 200
    assert response["payload"]["ok"] is True
    assert response["payload"]["current_node"] == "beagle-2"
    assert response["payload"]["stream_host"] == "srv2.beagle-os.com"
    assert response["payload"]["moonlight_port"] == "47984"
    assert response["payload"]["reconnect_required"] is True
    assert response["payload"]["network_mode"] == "vpn_preferred"
    assert response["payload"]["wireguard_active"] is True


def test_session_current_blocks_direct_access_when_pool_requires_vpn() -> None:
    service = _service(network_mode="vpn_required")
    response = service.route_get(
        "/api/v1/session/current",
        endpoint_identity={"endpoint_id": "endpoint-a", "vmid": 100, "node": "beagle-0", "hostname": "endpoint-a"},
        query={},
    )

    assert int(response["status"]) == 403
    assert response["payload"]["ok"] is False
    assert "vpn_required" in response["payload"]["error"]


def test_session_current_allows_when_pool_requires_vpn_and_wireguard_is_active() -> None:
    service = _service(network_mode="vpn_required")
    service.route_post(
        "/api/v1/endpoints/device/sync",
        endpoint_identity={"endpoint_id": "endpoint-a", "vmid": 100, "node": "beagle-0", "hostname": "endpoint-a"},
        query={},
        json_payload={"vpn": {"active": True, "interface": "wg-beagle", "assigned_ip": "10.88.0.10/32"}},
    )
    response = service.route_get(
        "/api/v1/session/current",
        endpoint_identity={"endpoint_id": "endpoint-a", "vmid": 100, "node": "beagle-0", "hostname": "endpoint-a"},
        query={},
    )

    assert int(response["status"]) == 200
    assert response["payload"]["ok"] is True


def test_device_sync_route_persists_wipe_report() -> None:
    service = _service()
    response = service.route_post(
        "/api/v1/endpoints/device/sync",
        endpoint_identity={"endpoint_id": "endpoint-a", "vmid": 100, "node": "beagle-0", "hostname": "endpoint-a"},
        query={},
        json_payload={
            "reports": {
                "wipe": {
                    "status": "completed",
                    "artifacts_removed": 3,
                }
            }
        },
    )

    assert int(response["status"]) == 200
    assert response["payload"]["device"]["last_wipe_report"]["status"] == "completed"
    assert response["payload"]["device"]["last_wipe_report"]["artifacts_removed"] == 3


def test_device_sync_route_returns_policy_and_commands() -> None:
    service = _service()
    response = service.route_post(
        "/api/v1/endpoints/device/sync",
        endpoint_identity={"endpoint_id": "endpoint-a", "vmid": 100, "node": "beagle-0", "hostname": "thin-01"},
        query={},
        json_payload={
            "hardware": {"cpu_model": "Intel", "cpu_cores": 4, "ram_gb": 8, "gpu_model": "", "network_interfaces": ["eth0"], "disk_gb": 64},
            "vpn": {"active": True, "interface": "wg-beagle", "assigned_ip": "10.88.0.10/32"},
        },
    )

    assert int(response["status"]) == 200
    assert response["payload"]["ok"] is True
    assert response["payload"]["device"]["device_id"] == "endpoint-a"
    assert response["payload"]["policy"]["policy_id"] == "corp"
    assert response["payload"]["attestation"]["allowed"] is True
    assert response["payload"]["vpn"]["active"] is True


def test_device_confirm_wiped_route_marks_device_wiped() -> None:
    service = _service()
    service.route_post(
        "/api/v1/endpoints/device/sync",
        endpoint_identity={"endpoint_id": "endpoint-a", "vmid": 100, "node": "beagle-0", "hostname": "thin-01"},
        query={},
        json_payload={"hardware": {"cpu_model": "Intel", "cpu_cores": 4, "ram_gb": 8, "gpu_model": "", "network_interfaces": ["eth0"], "disk_gb": 64}},
    )
    response = service.route_post(
        "/api/v1/endpoints/device/confirm-wiped",
        endpoint_identity={"endpoint_id": "endpoint-a", "vmid": 100, "node": "beagle-0", "hostname": "thin-01"},
        query={},
        json_payload={},
    )

    assert int(response["status"]) == 200
    assert response["payload"]["ok"] is True
    assert response["payload"]["device"]["status"] == "wiped"
