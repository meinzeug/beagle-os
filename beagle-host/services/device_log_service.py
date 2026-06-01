from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from core.repository.device_log_repository import DeviceLogRepository


@dataclass
class DeviceLogEntry:
    device_id: str
    source: str
    level: str
    captured_at: str
    content: str


class DeviceLogService:
    """Durable per-device log stream for thin clients."""

    def __init__(
        self,
        *,
        repository: DeviceLogRepository,
        utcnow: Callable[[], str],
        max_entries_per_device: int = 500,
    ) -> None:
        self._repository = repository
        self._utcnow = utcnow
        self._max_entries_per_device = max(1, int(max_entries_per_device))

    def ingest(self, device_id: str, payload: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        entries = payload.get("entries")
        if not isinstance(entries, list):
            entries = []
        saved: list[dict[str, Any]] = []
        default_timestamp = str(payload.get("captured_at") or self._utcnow())
        for raw in entries:
            if not isinstance(raw, dict):
                continue
            content = str(raw.get("content") or raw.get("message") or "").strip()
            if not content:
                continue
            entry = DeviceLogEntry(
                device_id=str(device_id),
                source=str(raw.get("source") or payload.get("source") or "runtime").strip() or "runtime",
                level=str(raw.get("level") or payload.get("level") or "info").strip().lower() or "info",
                captured_at=str(raw.get("captured_at") or default_timestamp),
                content=content,
            )
            stored = self._repository.append(asdict(entry))
            saved.append(stored)
        if saved:
            self._repository.prune(device_id, keep_last=self._max_entries_per_device)
        return saved

    def list_recent(self, device_id: str, *, limit: int = 200, source: str | None = None) -> list[dict[str, Any]]:
        return self._repository.list(device_id, limit=limit, source=source)

    def count(self, device_id: str) -> int:
        return self._repository.count(device_id)