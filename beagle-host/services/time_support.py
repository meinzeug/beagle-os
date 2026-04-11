"""Shared UTC timestamp helpers for host-side runtime code."""

from __future__ import annotations

from datetime import datetime
from typing import Callable


class TimeSupportService:
    def __init__(self, *, now: Callable[[], datetime]) -> None:
        self._now = now

    def utcnow(self) -> str:
        return self._now().isoformat()

    def parse_utc_timestamp(self, value: str) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    def timestamp_age_seconds(self, value: str) -> int | None:
        parsed = self.parse_utc_timestamp(value)
        if parsed is None:
            return None
        return max(0, int((self._now() - parsed).total_seconds()))
