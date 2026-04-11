"""Persistence helpers for per-VM secret records.

This service owns only the on-disk representation of a VM secret (path,
load, save). The higher-level `ensure_vm_secret` flow now lives in
`VmSecretBootstrapService`, while this service remains the persistence
boundary for the secret record itself.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable


class VmSecretStoreService:
    def __init__(
        self,
        *,
        data_dir: Callable[[], Path],
        load_json_file: Callable[..., Any],
        write_json_file: Callable[..., Any],
        safe_slug: Callable[..., str],
        utcnow: Callable[[], str],
    ) -> None:
        self._data_dir = data_dir
        self._load_json_file = load_json_file
        self._write_json_file = write_json_file
        self._safe_slug = safe_slug
        self._utcnow = utcnow

    def secrets_dir(self) -> Path:
        path = self._data_dir() / "vm-secrets"
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o700)
        return path

    def secret_path(self, node: str, vmid: int) -> Path:
        return self.secrets_dir() / f"{self._safe_slug(node, 'unknown')}-{int(vmid)}.json"

    def load(self, node: str, vmid: int) -> dict[str, Any] | None:
        payload = self._load_json_file(self.secret_path(node, vmid), None)
        return payload if isinstance(payload, dict) else None

    def save(self, node: str, vmid: int, payload: dict[str, Any]) -> dict[str, Any]:
        clean = dict(payload)
        clean["node"] = node
        clean["vmid"] = int(vmid)
        clean["updated_at"] = self._utcnow()
        self._write_json_file(self.secret_path(node, vmid), clean)
        return clean
