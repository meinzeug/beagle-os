"""Persistence helpers for endpoint-facing tokens.

This service owns the on-disk representation of endpoint tokens
(tokens_dir, token_path, store, load). The control plane continues to
own the higher-level lifecycle semantics (issuance, rotation, revocation)
and delegates the final persistence into this service.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Callable


class EndpointTokenStoreService:
    def __init__(
        self,
        *,
        data_dir: Callable[[], Path],
        load_json_file: Callable[..., Any],
        write_json_file: Callable[..., Any],
        utcnow: Callable[[], str],
    ) -> None:
        self._data_dir = data_dir
        self._load_json_file = load_json_file
        self._write_json_file = write_json_file
        self._utcnow = utcnow

    def tokens_dir(self) -> Path:
        path = self._data_dir() / "endpoint-tokens"
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o700)
        return path

    def token_path(self, token: str) -> Path:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return self.tokens_dir() / f"{digest}.json"

    def store(self, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        clean = dict(payload)
        clean["token_issued_at"] = self._utcnow()
        self._write_json_file(self.token_path(token), clean)
        return clean

    def load(self, token: str) -> dict[str, Any] | None:
        payload = self._load_json_file(self.token_path(token), None)
        return payload if isinstance(payload, dict) else None
