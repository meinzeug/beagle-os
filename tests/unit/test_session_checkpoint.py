"""Tests for Session Checkpoint (GoEnterprise Plan 06, Schritt 1)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from session_manager import SessionManagerService


def make_svc(tmp_path: Path, **kwargs) -> SessionManagerService:
    return SessionManagerService(
        state_file=tmp_path / "sessions.json",
        checkpoint_dir=tmp_path / "checkpoints",
        utcnow=lambda: "2026-04-25T12:00:00Z",
        **kwargs,
    )


def register(svc: SessionManagerService, session_id: str = "s-001") -> dict:
    return svc.register_session(
        session_id=session_id,
        pool_id="pool-desktop",
        vm_id=100,
        user_id="alice",
        node_id="node-1",
    )


def test_register_session(tmp_path):
    svc = make_svc(tmp_path)
    entry = register(svc)
    assert entry["session_id"] == "s-001"
    assert entry["current_node"] == "node-1"
    assert entry["status"] == "active"


def test_get_session(tmp_path):
    svc = make_svc(tmp_path)
    register(svc)
    s = svc.get_session("s-001")
    assert s is not None
    assert s["user_id"] == "alice"


def test_get_session_unknown_returns_none(tmp_path):
    svc = make_svc(tmp_path)
    assert svc.get_session("nonexistent") is None


def test_checkpoint_without_provider(tmp_path):
    svc = make_svc(tmp_path)
    register(svc)
    ckpt = svc.checkpoint_session("s-001")
    assert ckpt.status == "ready"
    assert ckpt.session_id == "s-001"
    assert "s-001.checkpoint" in ckpt.checkpoint_path


def test_checkpoint_calls_save_vm_state(tmp_path):
    saved = []
    svc = make_svc(tmp_path, save_vm_state=lambda vmid, path: saved.append((vmid, path)))
    register(svc)
    ckpt = svc.checkpoint_session("s-001")
    assert ckpt.status == "ready"
    assert len(saved) == 1
    assert saved[0][0] == 100


def test_checkpoint_unknown_session_raises(tmp_path):
    svc = make_svc(tmp_path)
    with pytest.raises(KeyError):
        svc.checkpoint_session("nonexistent")


def test_checkpoint_stored_in_session(tmp_path):
    svc = make_svc(tmp_path)
    register(svc)
    svc.checkpoint_session("s-001")
    s = svc.get_session("s-001")
    assert len(s["checkpoints"]) == 1
    assert s["checkpoints"][0]["status"] == "ready"


def test_checkpoint_failure_marked(tmp_path):
    def failing_save(vmid, path):
        raise RuntimeError("disk full")

    svc = make_svc(tmp_path, save_vm_state=failing_save)
    register(svc)
    ckpt = svc.checkpoint_session("s-001")
    assert ckpt.status == "failed"


def test_get_current_node(tmp_path):
    svc = make_svc(tmp_path)
    register(svc)
    assert svc.get_current_node("s-001") == "node-1"


def test_end_session(tmp_path):
    svc = make_svc(tmp_path)
    register(svc)
    ended = svc.end_session("s-001")
    assert ended["status"] == "ended"
    assert ended["ended_at"] == "2026-04-25T12:00:00Z"


def test_list_sessions_filter_active(tmp_path):
    svc = make_svc(tmp_path)
    register(svc, "s-001")
    register(svc, "s-002")
    svc.end_session("s-001")
    active = svc.list_sessions(status="active")
    assert len(active) == 1
    assert active[0]["session_id"] == "s-002"


def test_session_persists(tmp_path):
    svc = make_svc(tmp_path)
    register(svc)
    svc2 = make_svc(tmp_path)
    assert svc2.get_session("s-001") is not None
