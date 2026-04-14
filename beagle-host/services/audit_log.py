"""Append-only audit event logger for control-plane security events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


class AuditLogService:
    def __init__(self, *, log_file: Path, now_utc: Callable[[], str]) -> None:
        self._log_file = Path(log_file)
        self._now_utc = now_utc

    def write_event(self, event_type: str, outcome: str, details: dict[str, Any] | None = None) -> None:
        payload = {
            "timestamp": self._now_utc(),
            "event_type": str(event_type or "unknown").strip() or "unknown",
            "outcome": str(outcome or "unknown").strip() or "unknown",
            "details": details if isinstance(details, dict) else {},
        }
        line = json.dumps(payload, separators=(",", ":"), ensure_ascii=True) + "\n"
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        with self._log_file.open("a", encoding="utf-8") as handle:
            handle.write(line)
