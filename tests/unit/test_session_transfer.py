"""Tests for Session Transfer (GoEnterprise Plan 06, Schritt 2)."""
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


def register(svc: SessionManagerService, session_id: str = "s-001", node_id: str = "node-1"):
    return svc.register_session(
        session_id=session_id,
        pool_id="pool-desktop",
        vm_id=100,
        user_id="alice",
        node_id=node_id,
    )


def test_transfer_updates_current_node(tmp_path):
    svc = make_svc(tmp_path)
    register(svc)
    transfer = svc.transfer_session("s-001", target_node="node-2")
    assert transfer.status == "completed"
    assert svc.get_current_node("s-001") == "node-2"


def test_transfer_calls_transfer_and_restore(tmp_path):
    transferred = []
    restored = []

    svc = make_svc(
        tmp_path,
        transfer_checkpoint=lambda src, tgt, dst: transferred.append((src, tgt, dst)),
        restore_vm_state=lambda vmid, path: restored.append((vmid, path)),
    )
    register(svc)
    transfer = svc.transfer_session("s-001", target_node="node-2")
    assert transfer.status == "completed"
    assert len(transferred) == 1
    assert transferred[0][1] == "node-2"
    assert len(restored) == 1
    assert restored[0][0] == 100


def test_transfer_unknown_session_raises(tmp_path):
    svc = make_svc(tmp_path)
    with pytest.raises(KeyError):
        svc.transfer_session("nonexistent", "node-2")


def test_transfer_stored_in_session(tmp_path):
    svc = make_svc(tmp_path)
    register(svc)
    svc.transfer_session("s-001", "node-2")
    s = svc.get_session("s-001")
    assert len(s["transfers"]) == 1
    assert s["transfers"][0]["target_node"] == "node-2"


def test_transfer_failure_on_restore_error(tmp_path):
    def failing_restore(vmid, path):
        raise RuntimeError("VM restore failed")

    svc = make_svc(tmp_path, restore_vm_state=failing_restore)
    register(svc)
    transfer = svc.transfer_session("s-001", "node-2")
    assert transfer.status == "failed"
    assert "VM restore failed" in transfer.error


def test_transfer_from_original_node(tmp_path):
    svc = make_svc(tmp_path)
    register(svc, node_id="node-1")
    transfer = svc.transfer_session("s-001", "node-3")
    assert transfer.source_node == "node-1"
    assert transfer.target_node == "node-3"


def test_multiple_transfers(tmp_path):
    svc = make_svc(tmp_path)
    register(svc, node_id="node-1")
    svc.transfer_session("s-001", "node-2")
    svc.transfer_session("s-001", "node-3")
    assert svc.get_current_node("s-001") == "node-3"
    s = svc.get_session("s-001")
    assert len(s["transfers"]) == 2
