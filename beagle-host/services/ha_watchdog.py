from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from core.persistence.json_state_store import JsonStateStore


class HaWatchdogService:
    """Track cluster heartbeats and trigger fencing when nodes time out."""

    def __init__(
        self,
        *,
        state_file: Path,
        node_name: str,
        list_nodes: Callable[[], list[dict[str, Any]]],
        send_heartbeat: Callable[[str, dict[str, Any]], None],
        run_fencing_action: Callable[[str, str], bool],
        utcnow: Callable[[], str],
        now: Callable[[], float] | None = None,
        heartbeat_interval_seconds: float = 2.0,
        missed_heartbeats_before_fencing: int = 3,
    ) -> None:
        self._state_file = Path(state_file)
        self._store = JsonStateStore(self._state_file, default_factory=lambda: {"nodes": {}, "sent_seq": 0})
        self._node_name = str(node_name or "").strip()
        self._list_nodes = list_nodes
        self._send_heartbeat = send_heartbeat
        self._run_fencing_action = run_fencing_action
        self._utcnow = utcnow
        self._now = now or time.time
        self._heartbeat_interval_seconds = max(float(heartbeat_interval_seconds or 2.0), 0.1)
        self._missed_heartbeats_before_fencing = max(int(missed_heartbeats_before_fencing or 3), 1)

        if not self._node_name:
            raise ValueError("node_name is required")

    @staticmethod
    def _fencing_priority() -> list[str]:
        return [
            "ipmi_reset",
            "watchdog_timer",
            "vm_forcestop",
            "software_isolation",
        ]

    def _read_state(self) -> dict[str, Any]:
        payload = self._store.load()
        if isinstance(payload, dict):
            return payload
        return {"nodes": {}, "sent_seq": 0}

    def _write_state(self, payload: dict[str, Any]) -> None:
        self._store.save(payload)

    def record_heartbeat(self, source_node: str, *, received_at: float | None = None) -> None:
        node = str(source_node or "").strip()
        if not node:
            return
        state = self._read_state()
        nodes = state.get("nodes") if isinstance(state.get("nodes"), dict) else {}
        item = nodes.get(node) if isinstance(nodes.get(node), dict) else {}
        item["last_heartbeat_at"] = float(received_at if received_at is not None else self._now())
        item["last_heartbeat_utc"] = self._utcnow()
        item["status"] = "online"
        item["fencing_active"] = False
        item.pop("last_fencing_method", None)
        item.pop("last_fencing_at", None)
        nodes[node] = item
        state["nodes"] = nodes
        self._write_state(state)

    def send_heartbeats(self) -> dict[str, Any]:
        state = self._read_state()
        sent_seq = int(state.get("sent_seq", 0) or 0) + 1
        sent_at = float(self._now())
        payload = {
            "kind": "ha_heartbeat",
            "source_node": self._node_name,
            "sequence": sent_seq,
            "sent_at": sent_at,
            "sent_at_utc": self._utcnow(),
        }
        target_count = 0
        for item in self._list_nodes():
            if not isinstance(item, dict):
                continue
            target = str(item.get("name") or item.get("node") or "").strip()
            if not target or target == self._node_name:
                continue
            self._send_heartbeat(target, payload)
            target_count += 1
        state["sent_seq"] = sent_seq
        self._write_state(state)
        return {
            "sequence": sent_seq,
            "sent_at": sent_at,
            "target_count": target_count,
            "interval_seconds": self._heartbeat_interval_seconds,
        }

    def evaluate_timeouts(self) -> dict[str, Any]:
        state = self._read_state()
        nodes = state.get("nodes") if isinstance(state.get("nodes"), dict) else {}
        now = float(self._now())
        timeout_seconds = self._heartbeat_interval_seconds * float(self._missed_heartbeats_before_fencing)

        fenced_nodes: list[dict[str, Any]] = []
        for node_name in sorted(nodes.keys()):
            item = nodes[node_name] if isinstance(nodes[node_name], dict) else {}
            if str(item.get("status") or "").lower() == "fenced":
                continue
            last_heartbeat_at = float(item.get("last_heartbeat_at") or 0.0)
            if last_heartbeat_at <= 0.0:
                continue
            age = now - last_heartbeat_at
            if age < timeout_seconds:
                continue

            item["status"] = "unreachable"
            item["fencing_active"] = True
            method_used = ""
            for method in self._fencing_priority():
                if self._run_fencing_action(node_name, method):
                    method_used = method
                    break
            item["status"] = "fenced" if method_used else "unreachable"
            item["fencing_active"] = False
            item["last_fencing_method"] = method_used
            item["last_fencing_at"] = self._utcnow()
            nodes[node_name] = item
            fenced_nodes.append(
                {
                    "node": node_name,
                    "fenced": bool(method_used),
                    "method": method_used,
                    "heartbeat_age_seconds": round(age, 3),
                }
            )

        state["nodes"] = nodes
        self._write_state(state)
        return {
            "ok": True,
            "timeout_seconds": timeout_seconds,
            "fenced_nodes": fenced_nodes,
        }

    def list_node_health(self) -> list[dict[str, Any]]:
        state = self._read_state()
        nodes = state.get("nodes") if isinstance(state.get("nodes"), dict) else {}
        payload: list[dict[str, Any]] = []
        for node_name in sorted(nodes.keys()):
            item = nodes[node_name] if isinstance(nodes[node_name], dict) else {}
            payload.append(
                {
                    "name": node_name,
                    "status": str(item.get("status") or "unknown"),
                    "last_heartbeat_at": float(item.get("last_heartbeat_at") or 0.0),
                    "last_heartbeat_utc": str(item.get("last_heartbeat_utc") or ""),
                    "fencing_active": bool(item.get("fencing_active")),
                    "last_fencing_method": str(item.get("last_fencing_method") or ""),
                    "last_fencing_at": str(item.get("last_fencing_at") or ""),
                }
            )
        return payload
