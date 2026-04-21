from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.audit_event import AuditEvent


def _parse_timestamp(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class AuditReportService:
    def __init__(self, *, log_file: Path) -> None:
        self._log_file = Path(log_file)

    def _iter_events(self) -> list[dict[str, Any]]:
        if not self._log_file.exists():
            return []
        events: list[dict[str, Any]] = []
        for raw_line in self._log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            events.append(AuditEvent.from_record(record).to_record())
        return events

    def query_events(
        self,
        *,
        start: str = "",
        end: str = "",
        tenant_id: str = "",
        action: str = "",
        resource_type: str = "",
        user_id: str = "",
    ) -> list[dict[str, Any]]:
        start_dt = _parse_timestamp(start)
        end_dt = _parse_timestamp(end)
        tenant_filter = str(tenant_id or "").strip()
        action_filter = str(action or "").strip().lower()
        resource_filter = str(resource_type or "").strip().lower()
        user_filter = str(user_id or "").strip().lower()
        results: list[dict[str, Any]] = []
        for event in self._iter_events():
            event_ts = _parse_timestamp(str(event.get("timestamp") or ""))
            if start_dt is not None and (event_ts is None or event_ts < start_dt):
                continue
            if end_dt is not None and (event_ts is None or event_ts > end_dt):
                continue
            if tenant_filter and str(event.get("tenant_id") or "") != tenant_filter:
                continue
            if action_filter and str(event.get("action") or "").strip().lower() != action_filter:
                continue
            if resource_filter and str(event.get("resource_type") or "").strip().lower() != resource_filter:
                continue
            if user_filter and user_filter not in str(event.get("user_id") or "").strip().lower():
                continue
            results.append(event)
        return results

    def build_json_report(self, *, start: str = "", end: str = "", tenant_id: str = "", action: str = "", resource_type: str = "", user_id: str = "") -> dict[str, Any]:
        events = self.query_events(start=start, end=end, tenant_id=tenant_id, action=action, resource_type=resource_type, user_id=user_id)
        return {
            "ok": True,
            "count": len(events),
            "filters": {
                "start": str(start or ""),
                "end": str(end or ""),
                "tenant_id": str(tenant_id or ""),
                "action": str(action or ""),
                "resource_type": str(resource_type or ""),
                "user_id": str(user_id or ""),
            },
            "events": events,
        }

    def build_csv_report(self, *, start: str = "", end: str = "", tenant_id: str = "", action: str = "", resource_type: str = "", user_id: str = "") -> bytes:
        events = self.query_events(start=start, end=end, tenant_id=tenant_id, action=action, resource_type=resource_type, user_id=user_id)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "timestamp",
                "action",
                "result",
                "tenant_id",
                "user_id",
                "session_id",
                "resource_type",
                "resource_id",
                "source_ip",
                "user_agent",
                "old_value",
                "new_value",
                "metadata",
            ]
        )
        for event in events:
            writer.writerow(
                [
                    str(event.get("timestamp") or ""),
                    str(event.get("action") or ""),
                    str(event.get("result") or ""),
                    str(event.get("tenant_id") or ""),
                    str(event.get("user_id") or ""),
                    str(event.get("session_id") or ""),
                    str(event.get("resource_type") or ""),
                    str(event.get("resource_id") or ""),
                    str(event.get("source_ip") or ""),
                    str(event.get("user_agent") or ""),
                    json.dumps(event.get("old_value"), ensure_ascii=True, separators=(",", ":")),
                    json.dumps(event.get("new_value"), ensure_ascii=True, separators=(",", ":")),
                    json.dumps(event.get("metadata") or {}, ensure_ascii=True, separators=(",", ":")),
                ]
            )
        return buffer.getvalue().encode("utf-8-sig")