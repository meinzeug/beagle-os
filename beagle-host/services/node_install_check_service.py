"""Persist post-install health reports from newly installed cluster nodes."""

from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class NodeInstallCheckService:
    def __init__(
        self,
        *,
        state_file: Path,
        report_token: str,
        now: callable,
        persistence_support: Any,
        recent_window_hours: int = 24,
        max_reports: int = 50,
    ) -> None:
        self._state_file = Path(state_file)
        self._report_token = str(report_token or "").strip()
        self._now = now
        self._persistence = persistence_support
        self._recent_window_hours = max(1, int(recent_window_hours))
        self._max_reports = max(1, int(max_reports))

    def is_authorized(self, authorization_header: str) -> bool:
        expected = self._report_token
        if not expected:
            return False
        header = str(authorization_header or "").strip()
        if not header.startswith("Bearer "):
            return False
        supplied = header[7:].strip()
        return bool(supplied) and hmac.compare_digest(supplied, expected)

    def submit_report(self, payload: dict[str, Any] | None, *, remote_addr: str = "") -> dict[str, Any]:
        item = self._normalize_report(payload or {}, remote_addr=remote_addr)
        state = self._load_state()
        reports = [report for report in state.get("reports", []) if isinstance(report, dict)]
        reports.insert(0, item)
        state["reports"] = reports[: self._max_reports]
        self._save_state(state)
        return {"ok": True, "report": item}

    def list_payload(self) -> dict[str, Any]:
        reports = self._load_state().get("reports", [])
        recent_threshold = self._now() - timedelta(hours=self._recent_window_hours)
        recent_reports = []
        for item in reports:
            if not isinstance(item, dict):
                continue
            timestamp = self._parse_timestamp(str(item.get("timestamp") or ""))
            if timestamp is None or timestamp < recent_threshold:
                continue
            recent_reports.append(item)
        latest_ready = next(
            (item for item in recent_reports if str(item.get("status") or "").lower() == "pass"),
            None,
        )
        return {
            "ok": True,
            "reports": reports,
            "recent_reports": recent_reports,
            "latest_ready_report": latest_ready,
        }

    def _normalize_report(self, payload: dict[str, Any], *, remote_addr: str = "") -> dict[str, Any]:
        device_id = str(payload.get("device_id") or "").strip() or "unknown"
        timestamp = str(payload.get("timestamp") or "").strip() or self._now().strftime("%Y-%m-%dT%H:%M:%SZ")
        status = str(payload.get("status") or "").strip().lower() or "unknown"
        raw_checks = payload.get("checks")
        checks = raw_checks if isinstance(raw_checks, list) else []
        return {
            "device_id": device_id,
            "timestamp": timestamp,
            "status": status,
            "checks": checks,
            "remote_addr": str(remote_addr or "").strip(),
            "received_at": self._now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def _load_state(self) -> dict[str, Any]:
        state = self._persistence.load_json_file(self._state_file, {"reports": []})
        if not isinstance(state, dict):
            return {"reports": []}
        reports = state.get("reports")
        if not isinstance(reports, list):
            state["reports"] = []
        return state

    def _save_state(self, payload: dict[str, Any]) -> None:
        self._persistence.write_json_file(self._state_file, payload, mode=0o640)

    @staticmethod
    def _parse_timestamp(value: str) -> datetime | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            if raw.endswith("Z"):
                return datetime.fromisoformat(raw[:-1] + "+00:00")
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None
