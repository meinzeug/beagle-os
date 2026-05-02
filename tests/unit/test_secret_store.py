"""Unit tests for beagle-host/services/secret_store_service.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
for _p in [str(ROOT_DIR), str(ROOT_DIR / "beagle-host" / "services")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from secret_store_service import (
    SecretNotFoundError,
    SecretRevokedError,
    SecretStoreService,
)


def make_store(tmp_path: Path, **kwargs) -> SecretStoreService:
    return SecretStoreService(secrets_dir=tmp_path, **kwargs)


# ---------------------------------------------------------------------------
# Basic set / get
# ---------------------------------------------------------------------------

def test_set_and_get_secret(tmp_path: Path) -> None:
    svc = make_store(tmp_path)
    svc.set_secret("api_token", "supersecret")
    sv = svc.get_secret("api_token")
    assert sv.value == "supersecret"
    assert sv.status == "active"
    assert sv.version == 1


def test_get_missing_raises(tmp_path: Path) -> None:
    svc = make_store(tmp_path)
    with pytest.raises(SecretNotFoundError):
        svc.get_secret("nonexistent")


def test_has_secret_tracks_presence(tmp_path: Path) -> None:
    svc = make_store(tmp_path)
    assert svc.has_secret("api_token") is False
    svc.set_secret("api_token", "supersecret")
    assert svc.has_secret("api_token") is True


def test_secret_name_invalid_raises(tmp_path: Path) -> None:
    svc = make_store(tmp_path)
    with pytest.raises(ValueError):
        svc.set_secret("bad name!", "val")
    with pytest.raises(ValueError):
        svc.set_secret("../etc/passwd", "val")


# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------

def test_rotation_creates_new_version(tmp_path: Path) -> None:
    svc = make_store(tmp_path)
    svc.set_secret("tok", "v1")
    sv2 = svc.rotate_secret("tok")
    assert sv2.version == 2
    assert sv2.status == "active"
    assert sv2.value != "v1"  # randomly generated


def test_old_version_superseded_after_rotation(tmp_path: Path) -> None:
    svc = make_store(tmp_path)
    svc.set_secret("tok", "v1-value")
    svc.rotate_secret("tok")
    from core.persistence.json_state_store import JsonStateStore
    data = JsonStateStore(tmp_path / "tok.json", default_factory=dict).load()
    v1 = data["versions"][0]
    assert v1["status"] == "superseded"


def test_rotation_of_nonexistent_raises(tmp_path: Path) -> None:
    svc = make_store(tmp_path)
    with pytest.raises(SecretNotFoundError):
        svc.rotate_secret("ghost")


def test_rotation_custom_value(tmp_path: Path) -> None:
    svc = make_store(tmp_path)
    svc.set_secret("tok", "first")
    sv = svc.rotate_secret("tok", new_value="custom-new-value")
    assert sv.value == "custom-new-value"


# ---------------------------------------------------------------------------
# Revocation
# ---------------------------------------------------------------------------

def test_revoke_active_version(tmp_path: Path) -> None:
    svc = make_store(tmp_path)
    svc.set_secret("tok", "val")
    sv = svc.get_secret("tok")
    svc.revoke_secret("tok", sv.version)
    with pytest.raises(SecretRevokedError):
        svc.get_secret("tok")


def test_revoke_unknown_version_raises(tmp_path: Path) -> None:
    svc = make_store(tmp_path)
    svc.set_secret("tok", "val")
    with pytest.raises(SecretNotFoundError):
        svc.revoke_secret("tok", 999)


# ---------------------------------------------------------------------------
# is_valid — grace period
# ---------------------------------------------------------------------------

def test_is_valid_active(tmp_path: Path) -> None:
    svc = make_store(tmp_path)
    svc.set_secret("tok", "myval")
    assert svc.is_valid("tok", "myval") is True
    assert svc.is_valid("tok", "wrongval") is False


def test_is_valid_within_grace_period(tmp_path: Path) -> None:
    """Old version stays valid within grace period after rotation."""
    svc = make_store(tmp_path, grace_period_seconds=3600)
    svc.set_secret("tok", "old-value")
    svc.rotate_secret("tok", new_value="new-value")
    # old value should still be valid (superseded_at is now, grace=1h)
    assert svc.is_valid("tok", "old-value") is True
    assert svc.is_valid("tok", "new-value") is True


def test_is_valid_expired_grace_period(tmp_path: Path) -> None:
    """Old version invalid after grace period."""
    # 6 clock calls: set_secret(1) + rotate_secret(2) + is_valid(old)(1) + is_valid(new)(1) + spare
    times = [
        "2026-01-01T00:00:00Z",  # set_secret: now (created_at of v1)
        "2026-01-01T00:00:00Z",  # rotate_secret: now (superseded_at of v1 + created_at of v2)
        "2026-01-02T02:00:00Z",  # is_valid(old): now — 26h later, past grace period
        "2026-01-02T02:00:00Z",  # is_valid(new): now
    ]
    clock = iter(times)
    svc = make_store(tmp_path, grace_period_seconds=3600, utcnow=lambda: next(clock))
    svc.set_secret("tok", "old")
    svc.rotate_secret("tok", new_value="new")
    # Now time is 26h later — old is past grace period
    assert svc.is_valid("tok", "old") is False
    assert svc.is_valid("tok", "new") is True


def test_is_valid_revoked_never_valid(tmp_path: Path) -> None:
    svc = make_store(tmp_path, grace_period_seconds=3600)
    svc.set_secret("tok", "val")
    svc.revoke_secret("tok", 1)
    assert svc.is_valid("tok", "val") is False


# ---------------------------------------------------------------------------
# list_secrets — no values exposed
# ---------------------------------------------------------------------------

def test_list_secrets_no_values(tmp_path: Path) -> None:
    svc = make_store(tmp_path)
    svc.set_secret("alpha", "secret_a")
    svc.set_secret("beta", "secret_b")
    metas = svc.list_secrets()
    assert len(metas) == 2
    names = {m.name for m in metas}
    assert names == {"alpha", "beta"}
    # No values exposed
    for m in metas:
        assert not hasattr(m, "value") or not getattr(m, "value", None)


def test_list_secrets_versions_count(tmp_path: Path) -> None:
    svc = make_store(tmp_path)
    svc.set_secret("tok", "v1")
    svc.rotate_secret("tok")
    svc.rotate_secret("tok")
    metas = svc.list_secrets()
    assert metas[0].versions_count == 3


# ---------------------------------------------------------------------------
# File permissions
# ---------------------------------------------------------------------------

def test_secret_file_permissions_600(tmp_path: Path) -> None:
    import os, stat
    svc = make_store(tmp_path)
    svc.set_secret("tok", "val")
    path = tmp_path / "tok.json"
    assert path.exists()
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

def test_audit_fn_called_on_get(tmp_path: Path) -> None:
    events: list[tuple[str, dict]] = []
    svc = make_store(tmp_path, audit_fn=lambda e, kw: events.append((e, kw)))
    svc.set_secret("tok", "val")
    events.clear()
    svc.get_secret("tok")
    assert any(ev[0] == "secret_accessed" for ev in events)
    # Value must not appear in audit
    for ev_name, ev_data in events:
        assert "val" not in str(ev_data)


def test_audit_fn_called_on_rotate(tmp_path: Path) -> None:
    events: list[tuple[str, dict]] = []
    svc = make_store(tmp_path, audit_fn=lambda e, kw: events.append((e, kw)))
    svc.set_secret("tok", "val")
    events.clear()
    svc.rotate_secret("tok")
    assert any(ev[0] == "secret_rotated" for ev in events)


def test_audit_fn_called_on_revoke(tmp_path: Path) -> None:
    events: list[tuple[str, dict]] = []
    svc = make_store(tmp_path, audit_fn=lambda e, kw: events.append((e, kw)))
    svc.set_secret("tok", "val")
    events.clear()
    svc.revoke_secret("tok", 1)
    assert any(ev[0] == "secret_revoked" for ev in events)
