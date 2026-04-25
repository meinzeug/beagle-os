"""Shared file and JSON persistence helpers for host-side runtime code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.persistence.json_state_store import JsonStateStore


class PersistenceSupportService:
    def load_json_file(self, path: Path, fallback: Any) -> Any:
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return fallback
        except json.JSONDecodeError:
            return fallback

    def write_json_file(self, path: Path, payload: Any, *, mode: int = 0o600) -> None:
        """Atomic write via JsonStateStore (tempfile + fsync + rename)."""
        store = JsonStateStore(Path(path), default_factory=dict, mode=mode)
        store.save(payload)
