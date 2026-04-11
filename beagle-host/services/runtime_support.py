"""Shared runtime cache and shell-environment helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class RuntimeSupportService:
    def __init__(self, *, monotonic: Callable[[], float]) -> None:
        self._cache: dict[str, tuple[float, Any]] = {}
        self._monotonic = monotonic

    def cache_get(self, key: str, ttl_seconds: float) -> Any:
        entry = self._cache.get(key)
        if entry is None:
            return None
        created_at, value = entry
        if self._monotonic() - created_at > ttl_seconds:
            self._cache.pop(key, None)
            return None
        return value

    def cache_put(self, key: str, value: Any) -> Any:
        self._cache[key] = (self._monotonic(), value)
        return value

    def cache_invalidate(self, *keys: str) -> None:
        for key in keys:
            if key:
                self._cache.pop(key, None)

    def load_shell_env_file(self, path: Path) -> dict[str, str]:
        data: dict[str, str] = {}
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError:
            return data
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                data[key] = value
        return data
