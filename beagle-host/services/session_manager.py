"""Session Manager — Checkpoint + Live-Transfer für Session-Handover.

GoEnterprise Plan 06, Schritte 1 + 2 + 3
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class SessionCheckpoint:
    session_id: str
    pool_id: str
    vm_id: int
    user_id: str
    source_node: str
    checkpoint_path: str
    checkpointed_at: str
    status: str = "pending"   # "pending" | "ready" | "restored" | "failed"
    error: str = ""


@dataclass
class SessionTransfer:
    session_id: str
    source_node: str
    target_node: str
    checkpoint_path: str
    started_at: str
    completed_at: str = ""
    status: str = "in_progress"  # "in_progress" | "completed" | "failed"
    error: str = ""


class SessionManagerService:
    """
    Manages session checkpointing and live transfer between nodes.

    Used by Plan 06 (Session Handover) to move running sessions.

    Requires injectable callables for VM operations:
      - save_vm_state(vmid, checkpoint_path) → None
      - restore_vm_state(vmid, checkpoint_path) → None
      - transfer_checkpoint(src_path, target_node, dst_path) → None

    GoEnterprise Plan 06
    """

    STATE_FILE = Path("/var/lib/beagle/session-manager/sessions.json")
    CHECKPOINT_DIR = Path("/var/lib/beagle/session-manager/checkpoints")

    def __init__(
        self,
        state_file: Path | None = None,
        checkpoint_dir: Path | None = None,
        utcnow: Callable[[], str] | None = None,
        save_vm_state: Callable[[int, str], None] | None = None,
        restore_vm_state: Callable[[int, str], None] | None = None,
        transfer_checkpoint: Callable[[str, str, str], None] | None = None,
    ) -> None:
        self._state_file = state_file or self.STATE_FILE
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._ckpt_dir = checkpoint_dir or self.CHECKPOINT_DIR
        self._ckpt_dir.mkdir(parents=True, exist_ok=True)
        self._utcnow = utcnow or self._default_utcnow
        self._save_vm_state = save_vm_state
        self._restore_vm_state = restore_vm_state
        self._transfer_checkpoint = transfer_checkpoint
        self._state = self._load()

    # ------------------------------------------------------------------
    # Session registration
    # ------------------------------------------------------------------

    def register_session(
        self,
        *,
        session_id: str,
        pool_id: str,
        vm_id: int,
        user_id: str,
        node_id: str,
    ) -> dict[str, Any]:
        """Register a new active session so it can be checkpointed/transferred."""
        entry = {
            "session_id": session_id,
            "pool_id": pool_id,
            "vm_id": vm_id,
            "user_id": user_id,
            "current_node": node_id,
            "started_at": self._utcnow(),
            "status": "active",
            "checkpoints": [],
            "transfers": [],
        }
        self._state["sessions"][session_id] = entry
        self._save()
        return entry

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self._state["sessions"].get(session_id)

    def get_current_node(self, session_id: str) -> str:
        """Return current node for a session (for client redirect after transfer)."""
        s = self._state["sessions"].get(session_id)
        if not s:
            raise KeyError(f"Session {session_id!r} not found")
        return str(s.get("current_node", ""))

    # ------------------------------------------------------------------
    # Checkpoint (Plan 06, Schritt 1)
    # ------------------------------------------------------------------

    def checkpoint_session(self, session_id: str) -> SessionCheckpoint:
        """
        Save VM state to disk (virsh managedsave equivalent).
        Requires save_vm_state injectable.
        """
        s = self._state["sessions"].get(session_id)
        if not s:
            raise KeyError(f"Session {session_id!r} not found")

        checkpoint_path = str(self._ckpt_dir / f"{session_id}.checkpoint")
        ckpt = SessionCheckpoint(
            session_id=session_id,
            pool_id=s.get("pool_id", ""),
            vm_id=int(s.get("vm_id", 0)),
            user_id=s.get("user_id", ""),
            source_node=s.get("current_node", ""),
            checkpoint_path=checkpoint_path,
            checkpointed_at=self._utcnow(),
        )

        if self._save_vm_state:
            try:
                self._save_vm_state(ckpt.vm_id, checkpoint_path)
                ckpt = SessionCheckpoint(**{**asdict(ckpt), "status": "ready"})
            except Exception as e:
                ckpt = SessionCheckpoint(**{**asdict(ckpt), "status": "failed", "error": str(e)})  # type: ignore[call-arg]
        else:
            # No provider: mark ready (used in tests / offline mode)
            ckpt = SessionCheckpoint(**{**asdict(ckpt), "status": "ready"})

        s["checkpoints"].append(asdict(ckpt))
        s["last_checkpoint"] = asdict(ckpt)
        self._save()
        return ckpt

    # ------------------------------------------------------------------
    # Transfer (Plan 06, Schritt 2)
    # ------------------------------------------------------------------

    def transfer_session(self, session_id: str, target_node: str) -> SessionTransfer:
        """
        Transfer a checkpointed session to target_node and restore it there.
        Steps:
        1. Checkpoint the session (if not already done)
        2. Transfer checkpoint file to target node
        3. Restore VM on target node
        4. Update session's current_node
        """
        s = self._state["sessions"].get(session_id)
        if not s:
            raise KeyError(f"Session {session_id!r} not found")

        # Ensure we have a ready checkpoint
        last_ckpt = s.get("last_checkpoint")
        if not last_ckpt or last_ckpt.get("status") != "ready":
            ckpt = self.checkpoint_session(session_id)
            if ckpt.status != "ready":
                raise RuntimeError(f"Checkpoint failed for session {session_id!r}")
            last_ckpt = asdict(ckpt)

        source_node = str(s.get("current_node", ""))
        src_path = last_ckpt["checkpoint_path"]
        dst_path = src_path  # same path on target node

        transfer = SessionTransfer(
            session_id=session_id,
            source_node=source_node,
            target_node=target_node,
            checkpoint_path=src_path,
            started_at=self._utcnow(),
        )

        try:
            if self._transfer_checkpoint:
                self._transfer_checkpoint(src_path, target_node, dst_path)
            if self._restore_vm_state:
                self._restore_vm_state(int(s.get("vm_id", 0)), dst_path)
            transfer = SessionTransfer(
                **{**asdict(transfer),
                   "status": "completed",
                   "completed_at": self._utcnow()}
            )
            s["current_node"] = target_node
        except Exception as e:
            transfer = SessionTransfer(
                **{**asdict(transfer),
                   "status": "failed",
                   "error": str(e)}
            )

        s["transfers"].append(asdict(transfer))
        self._save()
        return transfer

    # ------------------------------------------------------------------
    # Session end
    # ------------------------------------------------------------------

    def end_session(self, session_id: str) -> dict[str, Any]:
        s = self._state["sessions"].get(session_id)
        if not s:
            raise KeyError(f"Session {session_id!r} not found")
        s["status"] = "ended"
        s["ended_at"] = self._utcnow()
        self._save()
        return s

    def list_sessions(self, status: str | None = None) -> list[dict[str, Any]]:
        sessions = list(self._state["sessions"].values())
        if status:
            sessions = [s for s in sessions if s.get("status") == status]
        return sessions

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if self._state_file.exists():
            return json.loads(self._state_file.read_text())
        return {"sessions": {}}

    def _save(self) -> None:
        self._state_file.write_text(json.dumps(self._state, indent=2))

    @staticmethod
    def _default_utcnow() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
