"""Integration tests — Endpoint Boot → Enrollment → Streaming Config.

GoAdvanced Plan 10 Schritt 2.

Tests the full lifecycle:
1. Control plane issues an enrollment token for a VM
2. Thin-client endpoint presents the token → receives bearer + stream config
3. Stream config contains Beagle Stream Client/Beagle Stream Server coordinates
4. Token is single-use: a second endpoint is rejected
5. Same endpoint can re-enroll (idempotent)
6. Expired token is rejected

These tests use real service instances with temp-dir state, no mocks.
No HTTP server is started — the service layer is called directly.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _sub in ("services", "providers", "bin"):
    _p = os.path.join(ROOT, "beagle-host", _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from endpoint_enrollment import EndpointEnrollmentService  # noqa: E402
from enrollment_token_store import EnrollmentTokenStoreService  # noqa: E402
from endpoint_token_store import EndpointTokenStoreService  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json(path, data):
    os.makedirs(str(path.parent), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


def _parse_utc(value: str):
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _make_vm(vmid: int = 100, node: str = "srv1"):
    """Create a minimal fake VM object."""
    vm = types.SimpleNamespace()
    vm.vmid = vmid
    vm.node = node
    return vm


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def state_dir(tmp_path):
    d = tmp_path / "state"
    d.mkdir()
    return d


@pytest.fixture
def enrollment_store(state_dir):
    return EnrollmentTokenStoreService(
        data_dir=lambda: state_dir,
        load_json_file=_load_json,
        write_json_file=_write_json,
        parse_utc_timestamp=_parse_utc,
        utcnow=_utcnow,
    )


@pytest.fixture
def endpoint_store(state_dir):
    return EndpointTokenStoreService(
        data_dir=lambda: state_dir,
        load_json_file=_load_json,
        write_json_file=_write_json,
        utcnow=_utcnow,
    )


def _make_enrollment_service(
    enrollment_store: EnrollmentTokenStoreService,
    endpoint_store: EndpointTokenStoreService,
    *,
    vm_registry: dict | None = None,
    vm_secrets: dict | None = None,
    enrollment_token_ttl_seconds: int = 300,
):
    """Wire a real EndpointEnrollmentService against the given stores."""
    vm_registry = vm_registry if vm_registry is not None else {}
    vm_secrets = vm_secrets if vm_secrets is not None else {}

    def _build_profile(vm):
        return {
            "update_enabled": True,
            "update_channel": "stable",
            "update_behavior": "prompt",
            "beagle_stream_server_api_url": f"https://vm-{vm.vmid}.internal:47990",
            "stream_host": f"vm-{vm.vmid}.internal",
            "beagle_stream_client_local_host": f"192.168.100.{vm.vmid}",
            "beagle_stream_client_port": "47984",
            "beagle_stream_client_app": "Desktop",
            "egress_mode": "full",
            "egress_type": "wireguard",
            "egress_interface": "wg-beagle",
        }

    def _ensure_vm_secret(vm):
        key = (vm.node, vm.vmid)
        if key not in vm_secrets:
            vm_secrets[key] = {
                "beagle_stream_server_username": "beagle",
                "beagle_stream_server_password": f"pw-{vm.vmid}",
                "beagle_stream_server_pin": "1234",
                "beagle_stream_server_pinned_pubkey": "",
                "usb_tunnel_port": 2222,
                "usb_tunnel_private_key": "MOCK_PRIVATE_KEY",
                "thinclient_password": f"tc-pw-{vm.vmid}",
            }
        return vm_secrets[key]

    def _find_vm(vmid):
        return vm_registry.get(vmid)

    def _load_enrollment_token(token):
        return enrollment_store.load(token)

    def _mark_enrollment_token_used(token, payload, endpoint_id):
        enrollment_store.mark_used(token, payload, endpoint_id=endpoint_id)

    def _resolve_vm_beagle_stream_server_pinned_pubkey(vm):
        return ""

    def _save_vm_secret(node, vmid, secret):
        vm_secrets[(node, vmid)] = secret
        return secret

    def _store_endpoint_token(token, payload):
        return endpoint_store.store(token, payload)

    def _store_enrollment_token(token, payload):
        return enrollment_store.store(token, payload)

    def _token_is_valid(enrollment, endpoint_id=""):
        return enrollment_store.is_valid(enrollment, endpoint_id=endpoint_id)

    return EndpointEnrollmentService(
        build_profile=_build_profile,
        ensure_vm_secret=_ensure_vm_secret,
        enrollment_token_ttl_seconds=enrollment_token_ttl_seconds,
        find_vm=_find_vm,
        load_enrollment_token=_load_enrollment_token,
        manager_pinned_pubkey="MOCK_MANAGER_PUBKEY",
        mark_enrollment_token_used=_mark_enrollment_token_used,
        public_manager_url="https://beagle.internal",
        public_server_name="srv1",
        resolve_vm_beagle_stream_server_pinned_pubkey=_resolve_vm_beagle_stream_server_pinned_pubkey,
        save_vm_secret=_save_vm_secret,
        service_name="beagle-host",
        store_endpoint_token=_store_endpoint_token,
        store_enrollment_token=_store_enrollment_token,
        token_is_valid=_token_is_valid,
        token_urlsafe=secrets.token_urlsafe,
        usb_tunnel_attach_host="usb.internal",
        usb_tunnel_known_host_line=lambda: "srv1 ssh-ed25519 AAAA==",
        usb_tunnel_user="beagle-usb",
        utcnow=_utcnow,
        version="7.0.0-test",
    )


# ---------------------------------------------------------------------------
# Tests: Enrollment token issuance
# ---------------------------------------------------------------------------

class TestEnrollmentTokenIssuance:

    def test_issue_token_returns_raw_token_and_payload(
        self, enrollment_store, endpoint_store
    ):
        vm = _make_vm(vmid=100)
        vm_registry = {100: vm}
        svc = _make_enrollment_service(enrollment_store, endpoint_store, vm_registry=vm_registry)

        raw_token, payload = svc.issue_enrollment_token(vm)

        assert raw_token and len(raw_token) >= 32
        assert payload["vmid"] == 100
        assert payload["node"] == "srv1"
        assert payload["expires_at"] != ""
        assert payload["thinclient_password"] != ""

    def test_issued_token_is_stored_in_enrollment_store(
        self, enrollment_store, endpoint_store
    ):
        vm = _make_vm(vmid=101)
        svc = _make_enrollment_service(enrollment_store, endpoint_store, vm_registry={101: vm})

        raw_token, _ = svc.issue_enrollment_token(vm)
        stored = enrollment_store.load(raw_token)

        assert stored is not None
        assert stored["vmid"] == 101
        assert "thinclient_password" not in stored

    def test_issued_token_is_valid(self, enrollment_store, endpoint_store):
        vm = _make_vm(vmid=102)
        svc = _make_enrollment_service(enrollment_store, endpoint_store, vm_registry={102: vm})

        raw_token, _ = svc.issue_enrollment_token(vm)
        stored = enrollment_store.load(raw_token)

        assert enrollment_store.is_valid(stored) is True


# ---------------------------------------------------------------------------
# Tests: Endpoint enrollment → streaming config
# ---------------------------------------------------------------------------

class TestEndpointEnrollment:

    def test_enroll_returns_ok_and_config(self, enrollment_store, endpoint_store):
        vm = _make_vm(vmid=200)
        svc = _make_enrollment_service(enrollment_store, endpoint_store, vm_registry={200: vm})

        raw_token, _ = svc.issue_enrollment_token(vm)
        result = svc.enroll_endpoint({
            "enrollment_token": raw_token,
            "endpoint_id": "ep-thinclient-01",
            "hostname": "thin01.local",
        })

        assert result["ok"] is True
        assert result["version"] == "7.0.0-test"
        assert result["service"] == "beagle-host"

    def test_enroll_result_contains_stream_config(self, enrollment_store, endpoint_store):
        vm = _make_vm(vmid=201)
        svc = _make_enrollment_service(enrollment_store, endpoint_store, vm_registry={201: vm})

        raw_token, _ = svc.issue_enrollment_token(vm)
        result = svc.enroll_endpoint({
            "enrollment_token": raw_token,
            "endpoint_id": "ep-01",
        })

        config = result["config"]
        assert config["beagle_stream_client_host"] == "vm-201.internal"
        assert config["beagle_stream_server_api_url"] == "https://vm-201.internal:47990"
        assert config["beagle_stream_server_username"] == "beagle"
        assert config["beagle_stream_server_password"] != ""
        assert config["beagle_manager_url"] == "https://beagle.internal"

    def test_enroll_result_contains_bearer_token(self, enrollment_store, endpoint_store):
        vm = _make_vm(vmid=202)
        svc = _make_enrollment_service(enrollment_store, endpoint_store, vm_registry={202: vm})

        raw_token, _ = svc.issue_enrollment_token(vm)
        result = svc.enroll_endpoint({
            "enrollment_token": raw_token,
            "endpoint_id": "ep-02",
        })

        bearer = result["config"]["beagle_manager_token"]
        assert bearer and len(bearer) >= 32
        # Bearer is stored in endpoint store
        stored = endpoint_store.load(bearer)
        assert stored is not None
        assert stored["endpoint_id"] == "ep-02"

    def test_enrollment_marks_token_as_used(self, enrollment_store, endpoint_store):
        vm = _make_vm(vmid=203)
        svc = _make_enrollment_service(enrollment_store, endpoint_store, vm_registry={203: vm})

        raw_token, _ = svc.issue_enrollment_token(vm)
        svc.enroll_endpoint({
            "enrollment_token": raw_token,
            "endpoint_id": "ep-03",
        })

        stored = enrollment_store.load(raw_token)
        assert stored["used_at"] != ""
        assert stored["endpoint_id"] == "ep-03"

    def test_second_endpoint_rejected_after_use(self, enrollment_store, endpoint_store):
        vm = _make_vm(vmid=204)
        svc = _make_enrollment_service(enrollment_store, endpoint_store, vm_registry={204: vm})

        raw_token, _ = svc.issue_enrollment_token(vm)
        # First enrollment
        svc.enroll_endpoint({"enrollment_token": raw_token, "endpoint_id": "ep-first"})
        # Second enrollment with different endpoint → rejected
        with pytest.raises(PermissionError):
            svc.enroll_endpoint({"enrollment_token": raw_token, "endpoint_id": "ep-other"})

    def test_same_endpoint_reenroll_is_idempotent(self, enrollment_store, endpoint_store):
        vm = _make_vm(vmid=205)
        svc = _make_enrollment_service(enrollment_store, endpoint_store, vm_registry={205: vm})

        raw_token, _ = svc.issue_enrollment_token(vm)
        res1 = svc.enroll_endpoint({"enrollment_token": raw_token, "endpoint_id": "ep-same"})
        res2 = svc.enroll_endpoint({"enrollment_token": raw_token, "endpoint_id": "ep-same"})

        # Both succeed; each issues a fresh bearer token
        assert res1["ok"] is True
        assert res2["ok"] is True

    def test_missing_enrollment_token_raises(self, enrollment_store, endpoint_store):
        svc = _make_enrollment_service(enrollment_store, endpoint_store)

        with pytest.raises(ValueError, match="missing"):
            svc.enroll_endpoint({"endpoint_id": "ep-x"})

    def test_missing_endpoint_id_raises(self, enrollment_store, endpoint_store):
        vm = _make_vm(vmid=206)
        svc = _make_enrollment_service(enrollment_store, endpoint_store, vm_registry={206: vm})
        raw_token, _ = svc.issue_enrollment_token(vm)

        with pytest.raises(ValueError, match="missing"):
            svc.enroll_endpoint({"enrollment_token": raw_token})

    def test_unknown_token_raises_permission_error(self, enrollment_store, endpoint_store):
        svc = _make_enrollment_service(enrollment_store, endpoint_store)

        with pytest.raises(PermissionError):
            svc.enroll_endpoint({
                "enrollment_token": "nonexistent-token-xyz",
                "endpoint_id": "ep-x",
            })

    def test_vm_not_found_raises_lookup_error(self, enrollment_store, endpoint_store):
        vm = _make_vm(vmid=207)
        svc = _make_enrollment_service(
            enrollment_store, endpoint_store,
            vm_registry={},  # VM not registered → find_vm returns None
        )
        raw_token, _ = svc.issue_enrollment_token(vm)

        with pytest.raises(LookupError):
            svc.enroll_endpoint({
                "enrollment_token": raw_token,
                "endpoint_id": "ep-x",
            })


# ---------------------------------------------------------------------------
# Tests: Expired enrollment token
# ---------------------------------------------------------------------------

class TestExpiredEnrollmentToken:

    def test_expired_token_raises_permission_error(self, enrollment_store, endpoint_store):
        """A token that has passed its expires_at is rejected."""
        # Manually inject an already-expired token into the store
        raw_token = secrets.token_urlsafe(32)
        expired_payload = {
            "vmid": 300,
            "node": "srv1",
            "profile_name": "vm-300",
            "expires_at": datetime(2000, 1, 1, tzinfo=timezone.utc).isoformat(),
            "issued_at": datetime(2000, 1, 1, tzinfo=timezone.utc).isoformat(),
            "used_at": "",
            "thinclient_password": "tc-pw",
        }
        enrollment_store.store(raw_token, expired_payload)

        vm = _make_vm(vmid=300)
        svc = _make_enrollment_service(enrollment_store, endpoint_store, vm_registry={300: vm})

        with pytest.raises(PermissionError):
            svc.enroll_endpoint({
                "enrollment_token": raw_token,
                "endpoint_id": "ep-expired",
            })


# ---------------------------------------------------------------------------
# Tests: Full boot-to-streaming config fields
# ---------------------------------------------------------------------------

class TestStreamingConfigFields:

    def _enroll(self, vmid, enrollment_store, endpoint_store):
        vm = _make_vm(vmid=vmid)
        svc = _make_enrollment_service(enrollment_store, endpoint_store, vm_registry={vmid: vm})
        raw_token, _ = svc.issue_enrollment_token(vm)
        return svc.enroll_endpoint({"enrollment_token": raw_token, "endpoint_id": f"ep-{vmid}"})

    def test_config_has_manager_fields(self, enrollment_store, endpoint_store):
        result = self._enroll(400, enrollment_store, endpoint_store)
        cfg = result["config"]
        assert cfg["beagle_manager_url"] == "https://beagle.internal"
        assert cfg["beagle_manager_pinned_pubkey"] == "MOCK_MANAGER_PUBKEY"
        assert len(cfg["beagle_manager_token"]) >= 32

    def test_config_has_usb_tunnel_fields(self, enrollment_store, endpoint_store):
        result = self._enroll(401, enrollment_store, endpoint_store)
        cfg = result["config"]
        assert cfg["usb_enabled"] is True
        assert cfg["usb_tunnel_host"] == "srv1"
        assert cfg["usb_tunnel_user"] == "beagle-usb"
        assert cfg["usb_tunnel_attach_host"] == "usb.internal"
        assert "srv1 ssh-ed25519" in cfg["usb_tunnel_known_host"]

    def test_config_has_update_fields(self, enrollment_store, endpoint_store):
        result = self._enroll(402, enrollment_store, endpoint_store)
        cfg = result["config"]
        assert cfg["update_enabled"] is True
        assert cfg["update_channel"] == "stable"
        assert cfg["update_behavior"] == "prompt"

    def test_config_has_egress_fields(self, enrollment_store, endpoint_store):
        result = self._enroll(403, enrollment_store, endpoint_store)
        cfg = result["config"]
        assert cfg["egress_mode"] == "full"
        assert isinstance(cfg["egress_domains"], list)
        assert isinstance(cfg["egress_resolvers"], list)
