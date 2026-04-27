"""Integration test for session handover timing budget.

Uses real SessionManagerService state with lightweight stubbed VM actions.
The transfer path must complete within the configured <5s reconnect budget.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _sub in ("services", "providers", "bin"):
    _p = os.path.join(ROOT, "beagle-host", _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from session_manager import SessionManagerService  # noqa: E402


def test_session_handover_timing_under_five_seconds(tmp_path: Path) -> None:
    calls = iter([0.0, 0.8, 1.9, 3.6])
    transferred: list[tuple[str, str, str]] = []
    restored: list[tuple[int, str]] = []
    saved: list[tuple[int, str]] = []

    svc = SessionManagerService(
        state_file=tmp_path / "sessions.json",
        checkpoint_dir=tmp_path / "checkpoints",
        utcnow=lambda: "2026-04-27T12:00:00Z",
        monotonic=lambda: next(calls),
        save_vm_state=lambda vmid, path: saved.append((vmid, path)),
        transfer_checkpoint=lambda src, tgt, dst: transferred.append((src, tgt, dst)),
        restore_vm_state=lambda vmid, path: restored.append((vmid, path)),
        slow_handover_threshold_seconds=10.0,
    )
    svc.register_session(
        session_id="sess-timing-1",
        pool_id="pool-a",
        vm_id=101,
        user_id="alice",
        node_id="srv1",
    )

    transfer = svc.transfer_session("sess-timing-1", "srv2")

    assert transfer.status == "completed"
    assert transfer.duration_seconds < 5.0
    assert saved and transferred and restored
    assert svc.get_current_node("sess-timing-1") == "srv2"
    assert svc.list_handover_alerts(session_id="sess-timing-1") == []
