"""Shared file and JSON persistence helpers for host-side runtime code."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class PersistenceSupportService:
    def load_json_file(self, path: Path, fallback: Any) -> Any:
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return fallback
        except json.JSONDecodeError:
            return fallback

    def write_json_file(self, path: Path, payload: Any, *, mode: int = 0o600) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        try:
            os.chmod(target, mode)
        except OSError:
            pass
