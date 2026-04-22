"""Append-only audit event logger for control-plane security events."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.audit_event import AuditEvent


class AuditLogService:
    def __init__(
        self,
        *,
        log_file: Path,
        now_utc: Callable[[], str],
        export_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._log_file = Path(log_file)
        self._now_utc = now_utc
        self._export_event = export_event

    def write_event(self, event_type: str, outcome: str, details: dict[str, Any] | None = None) -> None:
        payload = AuditEvent.create(
            timestamp=self._now_utc(),
            action=str(event_type or "unknown").strip() or "unknown",
            result=str(outcome or "unknown").strip() or "unknown",
            details=details if isinstance(details, dict) else {},
        ).to_record()
        line = json.dumps(payload, separators=(",", ":"), ensure_ascii=True) + "\n"
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        with self._log_file.open("a", encoding="utf-8") as handle:
            handle.write(line)
        if self._export_event is not None:
            self._export_event(payload)
