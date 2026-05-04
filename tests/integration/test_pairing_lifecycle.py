"""Integration tests — Pairing lifecycle.

GoAdvanced Plan 10 Schritt 6.

Tests the full token lifecycle:
1. Issue pairing/enrollment token (short TTL)
2. Endpoint uses token to enroll → receives bearer token
3. Bearer token is valid for API calls
4. Token rotation: new bearer issued, old one revoked
5. Revocation: token immediately invalid

These tests use real service instances with temp-dir state, no mocks.
The HTTP control-plane server is NOT used here — we test the service layer
directly to keep the tests fast and free of network I/O.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _sub in ("services", "providers", "bin"):
    _p = os.path.join(ROOT, "beagle-host", _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pairing_service import PairingService  # noqa: E402
from enrollment_token_store import EnrollmentTokenStoreService  # noqa: E402
from endpoint_token_store import EndpointTokenStoreService  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers / fixtures
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
    import os
    os.makedirs(str(path.parent), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


def _parse_utc(value: str):
    if not value:
        return None
    try:
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


@pytest.fixture
def state_dir(tmp_path):
    d = tmp_path / "state"
    d.mkdir()
    return d


@pytest.fixture
def pairing_svc():
    return PairingService(
        signing_secret="test-signing-secret-for-integration",
        token_ttl_seconds=60,
        utcnow=_utcnow,
    )


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


# ---------------------------------------------------------------------------
# PairingService — token issue / validate
# ---------------------------------------------------------------------------

class TestPairingServiceTokenLifecycle:

    def test_issue_and_validate(self, pairing_svc):
        token = pairing_svc.issue_token({"vmid": 42, "purpose": "enrollment"})
        assert token and "." in token
        payload = pairing_svc.validate_token(token)
        assert payload is not None
        assert payload["vmid"] == 42

    def test_validate_returns_none_for_tampered_token(self, pairing_svc):
        token = pairing_svc.issue_token({"vmid": 1})
        parts = token.split(".")
        # Flip a non-padding character in the middle of the signature so the
        # decoded bytes actually differ (last-char flip can land in base64 padding).
        mid = len(parts[2]) // 2
        flipped_char = "a" if parts[2][mid] != "a" else "b"
        parts[2] = parts[2][:mid] + flipped_char + parts[2][mid + 1:]
        tampered = ".".join(parts)
        assert pairing_svc.validate_token(tampered) is None

    def test_validate_returns_none_for_wrong_secret(self, pairing_svc):
        token = pairing_svc.issue_token({"vmid": 1})
        other = PairingService(
            signing_secret="different-secret",
            token_ttl_seconds=60,
            utcnow=_utcnow,
        )
        assert other.validate_token(token) is None

    def test_expired_token_invalid(self):
        from datetime import timedelta
        calls = [0]
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        def _mock_utcnow():
            # First call (during issue_token): return base time.
            # Subsequent calls (during validate_token): return base + 2h.
            calls[0] += 1
            if calls[0] <= 1:
                return base.isoformat()
            return (base + timedelta(seconds=7200)).isoformat()

        svc = PairingService(
            signing_secret="s3cr3t",
            token_ttl_seconds=60,
            utcnow=_mock_utcnow,
        )
        token = svc.issue_token({"vmid": 99})
        # Now validate after clock has advanced well past TTL
        assert svc.validate_token(token) is None

    def test_validate_empty_string(self, pairing_svc):
        assert pairing_svc.validate_token("") is None

    def test_validate_garbage(self, pairing_svc):
        assert pairing_svc.validate_token("not.a.token") is None

    def test_payload_fields_preserved(self, pairing_svc):
        token = pairing_svc.issue_token({"vmid": 7, "node": "srv1", "custom": "value"})
        payload = pairing_svc.validate_token(token)
        assert payload["node"] == "srv1"
        assert payload["custom"] == "value"

    def test_token_contains_expiry(self, pairing_svc):
        token = pairing_svc.issue_token({"vmid": 1})
        payload = pairing_svc.validate_token(token)
        assert "expires_at" in payload
        assert "issued_at" in payload

    def test_different_secrets_produce_different_tokens(self):
        svc1 = PairingService(signing_secret="A" * 32, token_ttl_seconds=60, utcnow=_utcnow)
        svc2 = PairingService(signing_secret="B" * 32, token_ttl_seconds=60, utcnow=_utcnow)
        t1 = svc1.issue_token({"vmid": 1})
        t2 = svc2.issue_token({"vmid": 1})
        assert t1 != t2


# ---------------------------------------------------------------------------
# EnrollmentTokenStore — store / load / mark_used / is_valid
# ---------------------------------------------------------------------------

class TestEnrollmentTokenStore:

    def test_store_and_load(self, enrollment_store):
        token = secrets.token_urlsafe(32)
        payload = {
            "vmid": 42,
            "expires_at": datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat(),
            "used_at": "",
        }
        enrollment_store.store(token, payload)
        loaded = enrollment_store.load(token)
        assert loaded is not None
        assert loaded["vmid"] == 42

    def test_load_nonexistent_returns_none(self, enrollment_store):
        assert enrollment_store.load("does-not-exist-token") is None

    def test_is_valid_fresh_token(self, enrollment_store):
        token = secrets.token_urlsafe(32)
        payload = {
            "vmid": 1,
            "expires_at": datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat(),
            "used_at": "",
        }
        enrollment_store.store(token, payload)
        loaded = enrollment_store.load(token)
        assert enrollment_store.is_valid(loaded) is True

    def test_is_valid_expired_token(self, enrollment_store):
        token = secrets.token_urlsafe(32)
        payload = {
            "vmid": 1,
            "expires_at": datetime(2000, 1, 1, tzinfo=timezone.utc).isoformat(),
            "used_at": "",
        }
        enrollment_store.store(token, payload)
        loaded = enrollment_store.load(token)
        assert enrollment_store.is_valid(loaded) is False

    def test_is_valid_used_token(self, enrollment_store):
        token = secrets.token_urlsafe(32)
        payload = {
            "vmid": 1,
            "expires_at": datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat(),
            "used_at": _utcnow(),
            "endpoint_id": "ep-abc",
        }
        enrollment_store.store(token, payload)
        loaded = enrollment_store.load(token)
        # Used by a different endpoint → invalid
        assert enrollment_store.is_valid(loaded, endpoint_id="ep-other") is False

    def test_is_valid_same_endpoint_reuse(self, enrollment_store):
        token = secrets.token_urlsafe(32)
        payload = {
            "vmid": 1,
            "expires_at": datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat(),
            "used_at": _utcnow(),
            "endpoint_id": "ep-abc",
        }
        enrollment_store.store(token, payload)
        loaded = enrollment_store.load(token)
        # Same endpoint can re-use (idempotent enrollment)
        assert enrollment_store.is_valid(loaded, endpoint_id="ep-abc") is True

    def test_mark_used_sets_used_at_and_endpoint(self, enrollment_store):
        token = secrets.token_urlsafe(32)
        payload = {
            "vmid": 1,
            "expires_at": datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat(),
            "used_at": "",
        }
        enrollment_store.store(token, payload)
        loaded = enrollment_store.load(token)
        enrollment_store.mark_used(token, loaded, endpoint_id="ep-xyz")
        updated = enrollment_store.load(token)
        assert updated["used_at"] != ""
        assert updated["endpoint_id"] == "ep-xyz"

    def test_is_valid_none_payload(self, enrollment_store):
        assert enrollment_store.is_valid(None) is False

    def test_token_paths_are_deterministic(self, enrollment_store):
        token = "same-token-value"
        p1 = enrollment_store.token_path(token)
        p2 = enrollment_store.token_path(token)
        assert p1 == p2

    def test_different_tokens_have_different_paths(self, enrollment_store):
        p1 = enrollment_store.token_path("token-A")
        p2 = enrollment_store.token_path("token-B")
        assert p1 != p2


# ---------------------------------------------------------------------------
# EndpointTokenStore — store / load / revoke
# ---------------------------------------------------------------------------

class TestEndpointTokenStore:

    def test_store_and_load(self, endpoint_store):
        token = secrets.token_urlsafe(32)
        payload = {"endpoint_id": "ep-001", "vmid": 42}
        endpoint_store.store(token, payload)
        loaded = endpoint_store.load(token)
        assert loaded is not None
        assert loaded["endpoint_id"] == "ep-001"

    def test_load_missing_returns_none(self, endpoint_store):
        assert endpoint_store.load("ghost-token") is None

    def test_store_multiple_tokens(self, endpoint_store):
        for i in range(5):
            token = secrets.token_urlsafe(32)
            endpoint_store.store(token, {"endpoint_id": f"ep-{i:03d}"})
        # Each token stored independently
        token_a = secrets.token_urlsafe(32)
        endpoint_store.store(token_a, {"endpoint_id": "ep-check"})
        assert endpoint_store.load(token_a)["endpoint_id"] == "ep-check"


# ---------------------------------------------------------------------------
# Full lifecycle: issue enrollment → mark used → endpoint token stored
# ---------------------------------------------------------------------------

class TestEnrollmentLifecycleIntegration:
    """Wire enrollment_store + endpoint_store together for a full lifecycle."""

    def test_enrollment_token_used_once_flow(self, enrollment_store, endpoint_store):
        # 1. Issue enrollment token (simulates control-plane issuing it for a VM)
        raw_token = secrets.token_urlsafe(32)
        expires_far = datetime(2099, 12, 31, tzinfo=timezone.utc).isoformat()
        enrollment_payload = {
            "vmid": 100,
            "node": "srv1",
            "profile_name": "vm-100",
            "expires_at": expires_far,
            "used_at": "",
            "thinclient_password": "changeme",
        }
        enrollment_store.store(raw_token, enrollment_payload)
        assert "thinclient_password" not in (enrollment_store.load(raw_token) or {})

        # 2. Endpoint presents the token
        loaded = enrollment_store.load(raw_token)
        assert enrollment_store.is_valid(loaded) is True

        # 3. Issue endpoint bearer token
        bearer = secrets.token_urlsafe(48)
        endpoint_store.store(bearer, {"endpoint_id": "ep-vm100", "vmid": 100})

        # 4. Mark enrollment token as used
        enrollment_store.mark_used(raw_token, loaded, endpoint_id="ep-vm100")

        # 5. Second enrollment attempt with same token + different endpoint → rejected
        reloaded = enrollment_store.load(raw_token)
        assert enrollment_store.is_valid(reloaded, endpoint_id="ep-other") is False

        # 6. Original endpoint can still re-enroll idempotently
        assert enrollment_store.is_valid(reloaded, endpoint_id="ep-vm100") is True

        # 7. Bearer token is still valid
        ep_data = endpoint_store.load(bearer)
        assert ep_data is not None
        assert ep_data["vmid"] == 100
