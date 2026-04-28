from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from attestation_service import AttestationReport, AttestationService
from device_registry import DeviceRegistryService
from endpoint_enrollment import EndpointEnrollmentService
from endpoint_http_surface import EndpointHttpSurfaceService
from mdm_policy_service import MDMPolicy, MDMPolicyService


class _Vm:
    def __init__(self, vmid: int, node: str) -> None:
        self.vmid = vmid
        self.node = node


def _make_endpoint_http_surface(
    *,
    registry: DeviceRegistryService,
    mdm: MDMPolicyService,
    attestation: AttestationService,
) -> EndpointHttpSurfaceService:
    vm = _Vm(100, "beagle-0")

    return EndpointHttpSurfaceService(
        build_vm_profile=lambda _vm: {"stream_host": "srv1.beagle-os.com", "moonlight_port": "47984"},
        dequeue_vm_actions=lambda _node, _vmid: [],
        device_registry_service=registry,
        mdm_policy_service=mdm,
        attestation_service=attestation,
        fleet_telemetry_service=None,
        alert_service=None,
        exchange_moonlight_pairing_token=lambda _vm, _identity, _token: {"ok": True},
        fetch_sunshine_server_identity=lambda _vm, _guest_user: {},
        find_vm=lambda vmid: vm if int(vmid) == vm.vmid else None,
        issue_moonlight_pairing_token=lambda _vm, _identity, _device_name: {"ok": True, "token": "token", "pin": "1234"},
        pool_manager_service=None,
        register_moonlight_certificate_on_vm=lambda _vm, _cert: {"ok": True},
        service_name="beagle-control-plane",
        prepare_virtual_display_on_vm=lambda _vm, _resolution: {"ok": True},
        session_manager_service=type("SessionManager", (), {"find_active_session": staticmethod(lambda **_kwargs: None)})(),
        store_action_result=lambda _node, _vmid, _payload: None,
        store_support_bundle=lambda _node, _vmid, _action_id, _filename, _payload: {},
        summarize_action_result=lambda payload: payload or {},
        utcnow=lambda: "2026-04-28T10:00:00Z",
        version="test",
    )


def _make_enrollment_service(tmp_path: Path) -> tuple[EndpointEnrollmentService, _Vm]:
    vm = _Vm(100, "beagle-0")
    tokens: dict[str, dict[str, object]] = {}
    endpoint_tokens: dict[str, dict[str, object]] = {}
    secret = {
        "sunshine_username": "sun",
        "sunshine_password": "pass",
        "sunshine_pin": "1234",
        "sunshine_pinned_pubkey": "pub",
        "usb_tunnel_port": 2222,
        "usb_tunnel_private_key": "ssh-private",
    }

    def _token_urlsafe(length: int) -> str:
        return "token-" + str(length) + "-abc"

    def _store_enrollment_token(token: str, payload: dict[str, object]) -> dict[str, object]:
        tokens[token] = dict(payload)
        return tokens[token]

    def _load_enrollment_token(token: str) -> dict[str, object] | None:
        payload = tokens.get(token)
        return dict(payload) if payload is not None else None

    def _token_is_valid(payload: dict[str, object] | None, endpoint_id: str) -> bool:
        return bool(payload) and str(payload.get("used_at", "")).strip() == "" and bool(endpoint_id)

    def _mark_enrollment_token_used(token: str, payload: dict[str, object], endpoint_id: str) -> None:
        if token in tokens:
            tokens[token]["used_at"] = "2026-04-28T10:00:00Z"
            tokens[token]["endpoint_id"] = endpoint_id

    def _store_endpoint_token(token: str, payload: dict[str, object]) -> dict[str, object]:
        endpoint_tokens[token] = dict(payload)
        return endpoint_tokens[token]

    svc = EndpointEnrollmentService(
        build_profile=lambda _vm: {
            "stream_host": "srv1.beagle-os.com",
            "moonlight_port": "47984",
            "update_enabled": True,
            "update_channel": "stable",
        },
        ensure_vm_secret=lambda _vm: dict(secret),
        enrollment_token_ttl_seconds=3600,
        find_vm=lambda vmid: vm if int(vmid) == vm.vmid else None,
        load_enrollment_token=_load_enrollment_token,
        manager_pinned_pubkey="manager-pub",
        mark_enrollment_token_used=_mark_enrollment_token_used,
        public_manager_url="https://manager.beagle-os.com",
        public_server_name="srv1.beagle-os.com",
        resolve_vm_sunshine_pinned_pubkey=lambda _vm: "pub",
        save_vm_secret=lambda _node, _vmid, updated: dict(updated),
        service_name="beagle-control-plane",
        store_endpoint_token=_store_endpoint_token,
        store_enrollment_token=_store_enrollment_token,
        token_is_valid=_token_is_valid,
        token_urlsafe=_token_urlsafe,
        usb_tunnel_attach_host="127.0.0.1",
        usb_tunnel_known_host_line=lambda: "srv1 ssh-ed25519 AAAA",
        usb_tunnel_user="beagle",
        utcnow=lambda: "2026-04-28T10:00:00Z",
        version="test",
    )
    return svc, vm


def test_qr_enrollment_token_then_device_sync_registers_hardware(tmp_path: Path) -> None:
    enrollment, vm = _make_enrollment_service(tmp_path)
    registry = DeviceRegistryService(state_file=tmp_path / "registry.json", utcnow=lambda: "2026-04-28T10:00:00Z")
    mdm = MDMPolicyService(state_file=tmp_path / "mdm.json")
    mdm.create_policy(MDMPolicy(policy_id="corp", name="Corp", allowed_pools=["pool-a"]))
    mdm.assign_to_device("thin-qr-01", "corp")
    attestation = AttestationService(state_file=tmp_path / "attestation.json", utcnow=lambda: "2026-04-28T10:00:00Z")

    token, _ = enrollment.issue_enrollment_token(vm)
    enroll_result = enrollment.enroll_endpoint({"enrollment_token": token, "endpoint_id": "thin-qr-01", "hostname": "tc-berlin-01"})

    assert enroll_result["ok"] is True
    assert enroll_result["config"]["device_id"] == "thin-qr-01"

    endpoint_surface = _make_endpoint_http_surface(registry=registry, mdm=mdm, attestation=attestation)
    sync_response = endpoint_surface.route_post(
        "/api/v1/endpoints/device/sync",
        endpoint_identity={"endpoint_id": "thin-qr-01", "vmid": 100, "node": "beagle-0", "hostname": "tc-berlin-01"},
        query={},
        json_payload={
            "hardware": {
                "cpu_model": "Intel N100",
                "cpu_cores": 4,
                "ram_gb": 16,
                "gpu_model": "Intel UHD",
                "network_interfaces": ["eth0"],
                "disk_gb": 256,
            },
            "vpn": {"active": True, "interface": "wg-beagle", "assigned_ip": "10.88.20.10/32"},
        },
    )

    assert int(sync_response["status"]) == 200
    device = registry.get_device("thin-qr-01")
    assert device is not None
    assert device.hardware.cpu_model == "Intel N100"
    assert device.hardware.ram_gb == 16
    assert device.vpn_active is True
    assert device.wg_assigned_ip == "10.88.20.10/32"


def test_tpm_compromised_device_is_blocked_for_session_allocation(tmp_path: Path) -> None:
    attestation = AttestationService(state_file=tmp_path / "attestation.json", utcnow=lambda: "2026-04-28T10:00:00Z")
    attestation.register_baseline(
        "beagle-image",
        {
            "pcr0": "abc123def456abc123def456abc123def456abc1",
            "pcr4": "fedcba9876543210fedcba9876543210fedcba98",
            "pcr7": "1234567890abcdef1234567890abcdef12345678",
        },
    )

    report = AttestationReport(
        device_id="thin-compromised-01",
        reported_at="2026-04-28T10:00:00Z",
        pcr_values={
            "pcr0": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            "pcr4": "fedcba9876543210fedcba9876543210fedcba98",
            "pcr7": "1234567890abcdef1234567890abcdef12345678",
        },
        signature="sig==",
    )

    record = attestation.validate_report(report, "beagle-image")
    allowed, reason = attestation.is_session_allowed("thin-compromised-01")

    assert record.status == "compromised"
    assert allowed is False
    assert "device_compromised" in reason


def test_mdm_policy_restricts_device_to_allowed_pools(tmp_path: Path) -> None:
    mdm = MDMPolicyService(state_file=tmp_path / "mdm.json")
    mdm.create_policy(MDMPolicy(policy_id="restricted", name="Restricted", allowed_pools=["finance-pool"]))
    mdm.assign_to_device("thin-policy-01", "restricted")

    assert mdm.is_pool_allowed("thin-policy-01", "finance-pool") is True
    assert mdm.is_pool_allowed("thin-policy-01", "engineering-pool") is False


def test_remote_wipe_flow_marks_pending_then_confirmed(tmp_path: Path) -> None:
    registry = DeviceRegistryService(state_file=tmp_path / "registry.json", utcnow=lambda: "2026-04-28T10:00:00Z")
    registry.register_device(
        "thin-wipe-01",
        "tc-wipe-01",
        {"cpu_model": "Intel", "cpu_cores": 4, "ram_gb": 8, "gpu_model": "", "network_interfaces": ["eth0"], "disk_gb": 64},
        vpn_active=True,
        vpn_interface="wg-beagle",
        wg_public_key="pubkey",
        wg_assigned_ip="10.88.30.10/32",
    )

    pending = registry.wipe_device("thin-wipe-01")
    assert pending.status == "wipe_pending"

    confirmed = registry.confirm_wiped("thin-wipe-01")
    assert confirmed.status == "wiped"
    assert confirmed.vpn_active is False
    assert confirmed.wg_assigned_ip == ""


def test_group_policy_rollout_applies_automatically_to_all_group_devices(tmp_path: Path) -> None:
    registry = DeviceRegistryService(state_file=tmp_path / "registry.json", utcnow=lambda: "2026-04-28T10:00:00Z")
    mdm = MDMPolicyService(state_file=tmp_path / "mdm.json")

    registry.register_device("thin-group-01", "tc-a", {"cpu_model": "Intel", "cpu_cores": 4, "ram_gb": 8, "gpu_model": "", "network_interfaces": ["eth0"], "disk_gb": 64})
    registry.register_device("thin-group-02", "tc-b", {"cpu_model": "Intel", "cpu_cores": 4, "ram_gb": 8, "gpu_model": "", "network_interfaces": ["eth0"], "disk_gb": 64})
    registry.assign_group("berlin-reception", ["thin-group-01", "thin-group-02"])

    mdm.create_policy(MDMPolicy(policy_id="group-policy", name="Group Policy", allowed_pools=["pool-a"], screen_lock_timeout_seconds=300))
    mdm.assign_to_group("berlin-reception", "group-policy")

    first = mdm.resolve_policy("thin-group-01", group=registry.get_device("thin-group-01").group)
    second = mdm.resolve_policy("thin-group-02", group=registry.get_device("thin-group-02").group)

    assert first.policy_id == "group-policy"
    assert second.policy_id == "group-policy"

    mdm.update_policy(MDMPolicy(policy_id="group-policy", name="Group Policy", allowed_pools=["pool-a"], screen_lock_timeout_seconds=120))
    first_updated = mdm.resolve_policy("thin-group-01", group=registry.get_device("thin-group-01").group)
    second_updated = mdm.resolve_policy("thin-group-02", group=registry.get_device("thin-group-02").group)

    assert first_updated.screen_lock_timeout_seconds == 120
    assert second_updated.screen_lock_timeout_seconds == 120
