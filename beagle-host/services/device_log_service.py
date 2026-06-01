from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
        device_lookup: Callable[[str], Any | None] | None = None,
        max_entries_per_device: int = 500,
    ) -> None:
        self._repository = repository
        self._utcnow = utcnow
        self._device_lookup = device_lookup or (lambda _device_id: None)
        self._max_entries_per_device = max(1, int(max_entries_per_device))

    def _device_policy(self, device_id: str) -> tuple[bool, int]:
        try:
            device = self._device_lookup(str(device_id))
        except Exception:
            device = None
        if device is None:
            return True, 86400
        enabled = bool(getattr(device, "log_capture_enabled", True))
        try:
            retention_seconds = int(getattr(device, "log_retention_seconds", 86400) or 86400)
        except (TypeError, ValueError):
            retention_seconds = 86400
        return enabled, max(3600, retention_seconds)

    def _cutoff_timestamp(self, retention_seconds: int) -> str:
        raw = str(self._utcnow() or "").strip()
        try:
            now_dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            now_dt = datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        cutoff = now_dt - timedelta(seconds=max(1, int(retention_seconds)))
        return cutoff.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def enforce_device_policy(self, device_id: str) -> int:
        _, retention_seconds = self._device_policy(device_id)
        pruned = self._repository.prune_older_than(device_id, cutoff=self._cutoff_timestamp(retention_seconds))
        self._repository.prune(device_id, keep_last=self._max_entries_per_device)
        return pruned

    def ingest(self, device_id: str, payload: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        enabled, retention_seconds = self._device_policy(device_id)
        if not enabled:
            self.enforce_device_policy(device_id)
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
            self._repository.prune_older_than(device_id, cutoff=self._cutoff_timestamp(retention_seconds))
            self._repository.prune(device_id, keep_last=self._max_entries_per_device)
        return saved

    def list_recent(self, device_id: str, *, limit: int = 200, source: str | None = None) -> list[dict[str, Any]]:
        return self._repository.list(device_id, limit=limit, source=source)

    def count(self, device_id: str) -> int:
        return self._repository.count(device_id)