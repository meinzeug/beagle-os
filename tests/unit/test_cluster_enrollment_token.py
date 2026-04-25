"""Tests for Cluster Enrollment Token (GoEnterprise Plan 08, Schritt 4)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from cluster_service import ClusterEnrollmentService, EnrollmentToken


def make_svc(tmp_path: Path, utcnow=None, ttl_hours=24) -> ClusterEnrollmentService:
    return ClusterEnrollmentService(
        state_file=tmp_path / "tokens.json",
        utcnow=utcnow or (lambda: "2026-04-25T12:00:00Z"),
        ttl_hours=ttl_hours,
    )


def test_generate_token_returns_token(tmp_path):
    svc = make_svc(tmp_path)
    token = svc.generate_token()
    assert isinstance(token, EnrollmentToken)
    assert len(token.token) == 64  # 32-byte hex
    assert token.used is False


def test_token_expires_at_correct_time(tmp_path):
    svc = make_svc(tmp_path, ttl_hours=24)
    token = svc.generate_token()
    assert token.expires_at == "2026-04-26T12:00:00Z"


def test_validate_token_valid(tmp_path):
    svc = make_svc(tmp_path)
    token = svc.generate_token()
    result = svc.validate_token(token.token)
    assert result is not None
    assert result.token_id == token.token_id


def test_validate_token_wrong_secret_returns_none(tmp_path):
    svc = make_svc(tmp_path)
    svc.generate_token()
    result = svc.validate_token("wrong_secret_abc123")
    assert result is None


def test_consume_token_marks_used(tmp_path):
    svc = make_svc(tmp_path)
    token = svc.generate_token()
    consumed = svc.consume_token(token.token, node_id="new-node-01")
    assert consumed is not None
    assert consumed.used is True
    assert consumed.used_by_node == "new-node-01"


def test_consumed_token_cannot_be_reused(tmp_path):
    svc = make_svc(tmp_path)
    token = svc.generate_token()
    svc.consume_token(token.token, "node-01")
    # Try to use again
    result = svc.validate_token(token.token)
    assert result is None


def test_expired_token_not_valid(tmp_path):
    # Create token with utcnow at the past
    svc_past = ClusterEnrollmentService(
        state_file=tmp_path / "tokens.json",
        utcnow=lambda: "2026-04-24T12:00:00Z",
        ttl_hours=24,
    )
    token = svc_past.generate_token()
    # token expires at 2026-04-25T12:00:00Z

    # Now validate at "future" time after expiry
    svc_future = ClusterEnrollmentService(
        state_file=tmp_path / "tokens.json",
        utcnow=lambda: "2026-04-25T13:00:00Z",
        ttl_hours=24,
    )
    result = svc_future.validate_token(token.token)
    assert result is None


def test_list_tokens(tmp_path):
    svc = make_svc(tmp_path)
    svc.generate_token(label="token-a")
    svc.generate_token(label="token-b")
    tokens = svc.list_tokens()
    assert len(tokens) == 2


def test_list_tokens_exclude_used(tmp_path):
    svc = make_svc(tmp_path)
    t1 = svc.generate_token()
    svc.generate_token()
    svc.consume_token(t1.token, "node-01")
    unused = svc.list_tokens(include_used=False)
    assert len(unused) == 1


def test_revoke_token(tmp_path):
    svc = make_svc(tmp_path)
    token = svc.generate_token()
    revoked = svc.revoke_token(token.token_id)
    assert revoked
    result = svc.validate_token(token.token)
    assert result is None


def test_revoke_nonexistent_returns_false(tmp_path):
    svc = make_svc(tmp_path)
    assert not svc.revoke_token("nonexistent_id")


def test_token_persists(tmp_path):
    svc = make_svc(tmp_path)
    t = svc.generate_token(cluster_id="cluster-1", label="test")
    svc2 = make_svc(tmp_path)
    fetched = svc2.get_token(t.token_id)
    assert fetched is not None
    assert fetched.cluster_id == "cluster-1"


def test_cleanup_expired_removes_expired_tokens(tmp_path):
    # Create token that is already expired
    svc_past = ClusterEnrollmentService(
        state_file=tmp_path / "tokens.json",
        utcnow=lambda: "2026-04-24T12:00:00Z",
        ttl_hours=24,
    )
    svc_past.generate_token()  # expires at 2026-04-25T12:00:00Z

    # Now in "future" — cleanup
    svc_now = ClusterEnrollmentService(
        state_file=tmp_path / "tokens.json",
        utcnow=lambda: "2026-04-26T00:00:00Z",
        ttl_hours=24,
    )
    removed = svc_now.cleanup_expired()
    assert removed == 1
    assert len(svc_now.list_tokens()) == 0


def test_single_use_token_security(tmp_path):
    """Token can only be used by one node; second attempt fails."""
    svc = make_svc(tmp_path)
    token = svc.generate_token()
    svc.consume_token(token.token, "node-A")
    second = svc.consume_token(token.token, "node-B")
    assert second is None
