"""Session Manager — Checkpoint + Live-Transfer für Session-Handover.

GoEnterprise Plan 06, Schritte 1 + 2 + 3
"""
from __future__ import annotations

import ipaddress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from core.persistence.json_state_store import JsonStateStore
from core.repository.session_repository import SessionRepository


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
    duration_seconds: float = 0.0


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
        monotonic: Callable[[], float] | None = None,
        save_vm_state: Callable[[int, str], None] | None = None,
        restore_vm_state: Callable[[int, str], None] | None = None,
        transfer_checkpoint: Callable[[str, str, str], None] | None = None,
        user_geo_resolver: Callable[[str], dict[str, Any] | None] | None = None,
        audit_event: Callable[[str, str], None] | None = None,
        slow_handover_threshold_seconds: float = 10.0,
        session_repository: SessionRepository | None = None,
    ) -> None:
        self._store = JsonStateStore(
            state_file or self.STATE_FILE,
            default_factory=lambda: {"sessions": {}, "handover_events": [], "handover_alerts": []},
        )
        self._ckpt_dir = checkpoint_dir or self.CHECKPOINT_DIR
        self._ckpt_dir.mkdir(parents=True, exist_ok=True)
        self._utcnow = utcnow or self._default_utcnow
        self._monotonic = monotonic or self._default_monotonic
        self._save_vm_state = save_vm_state
        self._restore_vm_state = restore_vm_state
        self._transfer_checkpoint = transfer_checkpoint
        self._user_geo_resolver = user_geo_resolver
        self._audit_event = audit_event
        self._slow_handover_threshold_seconds = max(0.0, float(slow_handover_threshold_seconds or 0.0))
        self._session_repo: SessionRepository | None = session_repository
        self._state = {}
        self._refresh_state()

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
        self._refresh_state()
        geo_routing = None
        if self._user_geo_resolver is not None:
            try:
                resolved = self._user_geo_resolver(user_id)
                if isinstance(resolved, dict):
                    geo_routing = resolved
            except Exception:
                geo_routing = None
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
        if geo_routing:
            entry["session_geo_routing"] = geo_routing
        self._state["sessions"][session_id] = entry
        self._save()
        return entry

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        self._refresh_state()
        return self._state["sessions"].get(session_id)

    def get_current_node(self, session_id: str) -> str:
        """Return current node for a session (for client redirect after transfer)."""
        s = self._state["sessions"].get(session_id)
        if not s:
            raise KeyError(f"Session {session_id!r} not found")
        return str(s.get("current_node", ""))

    def find_active_session(
        self,
        *,
        session_id: str = "",
        vm_id: int = 0,
        user_id: str = "",
    ) -> dict[str, Any] | None:
        self._refresh_state()
        session_key = str(session_id or "").strip()
        user_key = str(user_id or "").strip()
        vmid = int(vm_id or 0)
        if session_key:
            session = self.get_session(session_key)
            if session and str(session.get("status") or "") == "active":
                return session
            return None
        for session in self._state["sessions"].values():
            if str(session.get("status") or "") != "active":
                continue
            if vmid > 0 and int(session.get("vm_id") or 0) != vmid:
                continue
            if user_key and str(session.get("user_id") or "").strip() != user_key:
                continue
            return session
        return None

    def set_session_geo_routing(self, session_id: str, geo_routing: dict[str, Any] | None) -> dict[str, Any]:
        self._refresh_state()
        session = self._state["sessions"].get(str(session_id or "").strip())
        if not isinstance(session, dict):
            raise KeyError(f"Session {session_id!r} not found")
        if isinstance(geo_routing, dict) and geo_routing:
            session["session_geo_routing"] = geo_routing
        else:
            session.pop("session_geo_routing", None)
        self._save()
        return session

    # ------------------------------------------------------------------
    # Checkpoint (Plan 06, Schritt 1)
    # ------------------------------------------------------------------

    def checkpoint_session(self, session_id: str) -> SessionCheckpoint:
        """
        Save VM state to disk (virsh managedsave equivalent).
        Requires save_vm_state injectable.
        """
        self._refresh_state()
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
        self._refresh_state()
        s = self._state["sessions"].get(session_id)
        if not s:
            raise KeyError(f"Session {session_id!r} not found")
        started_ts = self._monotonic()
        self._record_handover_event(
            {
                "session_id": session_id,
                "pool_id": str(s.get("pool_id") or ""),
                "user_id": str(s.get("user_id") or ""),
                "source_node": str(s.get("current_node") or ""),
                "target_node": str(target_node or ""),
                "status": "started",
                "started_at": self._utcnow(),
            }
        )
        self._save()
        self._emit_audit("session_handover_started", "success")

        # Ensure we have a ready checkpoint
        last_ckpt = s.get("last_checkpoint")
        if not last_ckpt or last_ckpt.get("status") != "ready":
            ckpt = self.checkpoint_session(session_id)
            if ckpt.status != "ready":
                raise RuntimeError(f"Checkpoint failed for session {session_id!r}")
            last_ckpt = asdict(ckpt)
        self._refresh_state()
        s = self._state["sessions"].get(session_id)
        if not isinstance(s, dict):
            raise KeyError(f"Session {session_id!r} not found")

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
            duration_seconds = max(0.0, self._monotonic() - started_ts)
            transfer = SessionTransfer(
                **{**asdict(transfer),
                   "status": "completed",
                   "completed_at": self._utcnow(),
                   "duration_seconds": duration_seconds}
            )
            s["current_node"] = target_node
            self._record_handover_event(
                {
                    "session_id": session_id,
                    "pool_id": str(s.get("pool_id") or ""),
                    "user_id": str(s.get("user_id") or ""),
                    "source_node": source_node,
                    "target_node": str(target_node or ""),
                    "status": "completed",
                    "started_at": transfer.started_at,
                    "completed_at": transfer.completed_at,
                    "duration_seconds": duration_seconds,
                }
            )
            self._emit_audit("session_handover_completed", "success")
            if self._slow_handover_threshold_seconds > 0 and duration_seconds > self._slow_handover_threshold_seconds:
                self._record_handover_alert(
                    {
                        "session_id": session_id,
                        "user_id": str(s.get("user_id") or ""),
                        "severity": "warning",
                        "metric": "handover_duration_seconds",
                        "threshold": self._slow_handover_threshold_seconds,
                        "current_value": duration_seconds,
                        "message": (
                            f"session {session_id} handover took {duration_seconds:.2f}s"
                            f" > {self._slow_handover_threshold_seconds:.2f}s"
                        ),
                        "fired_at": self._utcnow(),
                    }
                )
        except Exception as e:
            duration_seconds = max(0.0, self._monotonic() - started_ts)
            transfer = SessionTransfer(
                **{**asdict(transfer),
                   "status": "failed",
                   "error": str(e),
                   "duration_seconds": duration_seconds}
            )
            self._record_handover_event(
                {
                    "session_id": session_id,
                    "pool_id": str(s.get("pool_id") or ""),
                    "user_id": str(s.get("user_id") or ""),
                    "source_node": source_node,
                    "target_node": str(target_node or ""),
                    "status": "failed",
                    "started_at": transfer.started_at,
                    "completed_at": self._utcnow(),
                    "duration_seconds": duration_seconds,
                    "error": str(e),
                }
            )
            self._emit_audit("session_handover_failed", "error")

        s["transfers"].append(asdict(transfer))
        self._save()
        return transfer

    # ------------------------------------------------------------------
    # Session end
    # ------------------------------------------------------------------

    def end_session(self, session_id: str) -> dict[str, Any]:
        self._refresh_state()
        s = self._state["sessions"].get(session_id)
        if not s:
            raise KeyError(f"Session {session_id!r} not found")
        s["status"] = "ended"
        s["ended_at"] = self._utcnow()
        self._save()
        return s

    def list_sessions(self, status: str | None = None) -> list[dict[str, Any]]:
        self._refresh_state()
        sessions = list(self._state["sessions"].values())
        if status:
            sessions = [s for s in sessions if s.get("status") == status]
        return sessions

    def list_handover_events(
        self,
        *,
        session_id: str = "",
        user_id: str = "",
        status: str = "",
        only_alerting: bool = False,
    ) -> list[dict[str, Any]]:
        session_key = str(session_id or "").strip()
        user_key = str(user_id or "").strip()
        status_key = str(status or "").strip().lower()
        self._refresh_state()
        items = list(self._state.get("handover_events") or [])
        result: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if session_key and str(item.get("session_id") or "").strip() != session_key:
                continue
            if user_key and str(item.get("user_id") or "").strip() != user_key:
                continue
            if status_key and str(item.get("status") or "").strip().lower() != status_key:
                continue
            if only_alerting and float(item.get("duration_seconds") or 0.0) <= self._slow_handover_threshold_seconds:
                continue
            result.append(dict(item))
        result.sort(key=lambda item: str(item.get("started_at") or item.get("completed_at") or ""), reverse=True)
        return result

    def list_handover_alerts(self, *, session_id: str = "", user_id: str = "") -> list[dict[str, Any]]:
        session_key = str(session_id or "").strip()
        user_key = str(user_id or "").strip()
        self._refresh_state()
        items = list(self._state.get("handover_alerts") or [])
        result: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if session_key and str(item.get("session_id") or "").strip() != session_key:
                continue
            if user_key and str(item.get("user_id") or "").strip() != user_key:
                continue
            result.append(dict(item))
        result.sort(key=lambda item: str(item.get("fired_at") or ""), reverse=True)
        return result

    def evaluate_geo_handover(self, session_id: str, *, client_ip: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"Session {session_id!r} not found")
        geo = session.get("session_geo_routing") if isinstance(session.get("session_geo_routing"), dict) else {}
        if not geo or not bool(geo.get("enabled")):
            return {
                "session_id": session_id,
                "matched_site": "",
                "target_node": "",
                "current_node": str(session.get("current_node") or ""),
                "should_handover": False,
            }
        matched_site = ""
        target_node = ""
        ip = ipaddress.ip_address(str(client_ip or "").strip())
        sites = geo.get("sites") if isinstance(geo.get("sites"), dict) else {}
        for site_name, raw_site in sites.items():
            if not isinstance(raw_site, dict):
                continue
            cidrs = raw_site.get("cidrs") if isinstance(raw_site.get("cidrs"), list) else []
            for cidr in cidrs:
                try:
                    if ip in ipaddress.ip_network(str(cidr).strip(), strict=False):
                        matched_site = str(site_name or "").strip()
                        target_node = str(raw_site.get("target_node") or "").strip()
                        break
                except ValueError:
                    continue
            if matched_site:
                break
        current_node = str(session.get("current_node") or "")
        return {
            "session_id": session_id,
            "matched_site": matched_site,
            "target_node": target_node,
            "current_node": current_node,
            "should_handover": bool(matched_site and target_node and current_node and current_node != target_node),
        }

    def apply_geo_handover(self, session_id: str, *, client_ip: str) -> dict[str, Any]:
        decision = self.evaluate_geo_handover(session_id, client_ip=client_ip)
        if not bool(decision.get("should_handover")):
            return {"ok": False, **decision}
        transfer = self.transfer_session(session_id, str(decision.get("target_node") or ""))
        return {"ok": transfer.status == "completed", **decision, "transfer": asdict(transfer)}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _save(self) -> None:
        if self._session_repo is not None:
            for session_dict in self._state.get("sessions", {}).values():
                try:
                    self._session_repo.save(session_dict)
                except Exception:  # pragma: no cover
                    pass
            # Remove sessions deleted from in-memory state from the repository
            repo_ids = {s["session_id"] for s in self._session_repo.list()}
            mem_ids = set(self._state.get("sessions", {}).keys())
            for stale_id in repo_ids - mem_ids:
                try:
                    self._session_repo.delete(stale_id)
                except Exception:  # pragma: no cover
                    pass
        self._store.save(self._state)

    def _refresh_state(self) -> None:
        self._state = self._store.load()
        self._state.setdefault("sessions", {})
        self._state.setdefault("handover_events", [])
        self._state.setdefault("handover_alerts", [])
        if self._session_repo is not None:
            # Overlay sessions from SQLite repository (authoritative when repo is set)
            for session_dict in self._session_repo.list():
                sid = session_dict.get("session_id")
                if sid:
                    self._state["sessions"].setdefault(sid, session_dict)

    def _record_handover_event(self, event: dict[str, Any]) -> None:
        self._state.setdefault("handover_events", [])
        self._state["handover_events"].append(event)

    def _record_handover_alert(self, alert: dict[str, Any]) -> None:
        self._state.setdefault("handover_alerts", [])
        self._state["handover_alerts"].append(alert)

    def _emit_audit(self, event_type: str, outcome: str) -> None:
        if self._audit_event is None:
            return
        try:
            self._audit_event(event_type, outcome)
        except Exception:
            return

    @staticmethod
    def _default_utcnow() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _default_monotonic() -> float:
        import time
        return time.monotonic()
