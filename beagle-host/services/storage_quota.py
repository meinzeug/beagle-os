from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class StorageQuotaService:
    _POOL_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

    def __init__(self, *, state_file: str | Path) -> None:
        self._state_file = Path(str(state_file)).expanduser()

    def _read_state(self) -> dict[str, Any]:
        if not self._state_file.is_file():
            return {"pools": {}}
        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {"pools": {}}
        if not isinstance(payload, dict):
            return {"pools": {}}
        pools = payload.get("pools")
        if not isinstance(pools, dict):
            payload["pools"] = {}
        return payload

    def _write_state(self, payload: dict[str, Any]) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _normalize_pool(self, pool_name: str) -> str:
        pool = str(pool_name or "").strip()
        if not pool:
            raise ValueError("missing pool name")
        if not self._POOL_PATTERN.fullmatch(pool):
            raise ValueError("invalid pool name")
        return pool

    def get_pool_quota(self, pool_name: str) -> dict[str, Any]:
        pool = self._normalize_pool(pool_name)
        state = self._read_state()
        pools = state.get("pools") if isinstance(state, dict) else {}
        record = pools.get(pool) if isinstance(pools, dict) else {}
        if not isinstance(record, dict):
            record = {}
        quota_bytes = int(record.get("quota_bytes", 0) or 0)
        if quota_bytes < 0:
            quota_bytes = 0
        return {
            "pool": pool,
            "quota_bytes": quota_bytes,
        }

    def set_pool_quota(self, pool_name: str, quota_bytes: int) -> dict[str, Any]:
        pool = self._normalize_pool(pool_name)
        quota = int(quota_bytes or 0)
        if quota < 0:
            raise ValueError("quota_bytes must be >= 0")

        state = self._read_state()
        pools = state.get("pools")
        if not isinstance(pools, dict):
            pools = {}
            state["pools"] = pools

        pools[pool] = {
            "quota_bytes": quota,
        }
        self._write_state(state)
        return {
            "pool": pool,
            "quota_bytes": quota,
        }
