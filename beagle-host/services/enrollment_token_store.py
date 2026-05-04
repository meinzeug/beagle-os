"""Persistence and validity helpers for enrollment tokens.

This service owns the on-disk representation and lifetime semantics of
enrollment tokens (path, load, store, mark-used, validity check). The
higher-level `issue_enrollment_token` flow in the control plane continues
to own payload construction (VM summary, thinclient password lookup,
ensure_vm_secret) and delegates the final persistence into this service.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class EnrollmentTokenStoreService:
    def __init__(
        self,
        *,
        data_dir: Callable[[], Path],
        load_json_file: Callable[..., Any],
        write_json_file: Callable[..., Any],
        parse_utc_timestamp: Callable[[str], datetime | None],
        utcnow: Callable[[], str],
    ) -> None:
        self._data_dir = data_dir
        self._load_json_file = load_json_file
        self._write_json_file = write_json_file
        self._parse_utc_timestamp = parse_utc_timestamp
        self._utcnow = utcnow

    def tokens_dir(self) -> Path:
        path = self._data_dir() / "enrollment-tokens"
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o700)
        return path

    def token_path(self, token: str) -> Path:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return self.tokens_dir() / f"{digest}.json"

    @staticmethod
    def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
        clean = dict(payload)
        clean.pop("thinclient_password", None)
        return clean

    def store(self, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        clean = self._sanitize_payload(payload)
        self._write_json_file(self.token_path(token), clean)
        return clean

    def load(self, token: str) -> dict[str, Any] | None:
        payload = self._load_json_file(self.token_path(token), None)
        return payload if isinstance(payload, dict) else None

    def mark_used(self, token: str, payload: dict[str, Any], *, endpoint_id: str) -> None:
        clean = self._sanitize_payload(payload)
        clean["used_at"] = self._utcnow()
        clean["endpoint_id"] = endpoint_id
        self._write_json_file(self.token_path(token), clean)

    def is_valid(
        self,
        payload: dict[str, Any] | None,
        *,
        endpoint_id: str = "",
    ) -> bool:
        if not isinstance(payload, dict):
            return False
        expires_at = self._parse_utc_timestamp(str(payload.get("expires_at", "")))
        if expires_at is None:
            return False
        if expires_at <= datetime.now(timezone.utc):
            return False
        used_at = str(payload.get("used_at", "")).strip()
        if not used_at:
            return True
        if endpoint_id and str(payload.get("endpoint_id", "")).strip() == endpoint_id:
            return True
        return False
