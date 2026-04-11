"""Persistence and validity helpers for sunshine access tokens.

This service owns the on-disk representation and lifetime semantics of
sunshine access tokens (tokens_dir, token_path, store, load, is_valid).
The higher-level `issue_sunshine_access_token` flow in the control plane
continues to own payload construction (VM summary + TTL math) and
delegates the final persistence into this service.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class SunshineAccessTokenStoreService:
    def __init__(
        self,
        *,
        data_dir: Callable[[], Path],
        load_json_file: Callable[..., Any],
        write_json_file: Callable[..., Any],
        parse_utc_timestamp: Callable[[str], datetime | None],
    ) -> None:
        self._data_dir = data_dir
        self._load_json_file = load_json_file
        self._write_json_file = write_json_file
        self._parse_utc_timestamp = parse_utc_timestamp

    def tokens_dir(self) -> Path:
        path = self._data_dir() / "sunshine-access-tokens"
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o700)
        return path

    def token_path(self, token: str) -> Path:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return self.tokens_dir() / f"{digest}.json"

    def store(self, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        clean = dict(payload)
        self._write_json_file(self.token_path(token), clean)
        return clean

    def load(self, token: str) -> dict[str, Any] | None:
        payload = self._load_json_file(self.token_path(token), None)
        return payload if isinstance(payload, dict) else None

    def is_valid(self, payload: dict[str, Any] | None) -> bool:
        if not isinstance(payload, dict):
            return False
        expires_at = self._parse_utc_timestamp(str(payload.get("expires_at", "")))
        if expires_at is None:
            return False
        return expires_at > datetime.now(timezone.utc)
