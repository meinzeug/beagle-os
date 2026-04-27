from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable


class StorageImageStoreService:
    _POOL_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
    _FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
    _EXTENSION_KIND = {
        ".iso": "iso",
        ".qcow2": "images",
        ".img": "images",
        ".raw": "images",
    }

    def __init__(
        self,
        *,
        list_storage_inventory: Callable[[], list[dict[str, Any]]],
        get_pool_quota: Callable[[str], dict[str, Any]],
    ) -> None:
        self._list_storage_inventory = list_storage_inventory
        self._get_pool_quota = get_pool_quota

    def _normalize_pool(self, pool_name: str) -> str:
        pool = str(pool_name or "").strip()
        if not pool:
            raise ValueError("missing pool name")
        if not self._POOL_PATTERN.fullmatch(pool):
            raise ValueError("invalid pool name")
        return pool

    def _normalize_filename(self, filename: str) -> str:
        name = str(filename or "").strip()
        if not name:
            raise ValueError("missing filename")
        if "/" in name or "\\" in name or Path(name).name != name:
            raise ValueError("invalid filename")
        if not self._FILENAME_PATTERN.fullmatch(name):
            raise ValueError("invalid filename")
        return name

    def _storage_entry(self, pool_name: str) -> dict[str, Any]:
        target = self._normalize_pool(pool_name)
        for entry in self._list_storage_inventory():
            if str(entry.get("storage", "")).strip() == target:
                return dict(entry)
        raise ValueError(f"storage pool '{target}' not found")

    def _content_kind_for_filename(self, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        kind = self._EXTENSION_KIND.get(suffix, "")
        if not kind:
            raise ValueError("unsupported file type; only .iso, .qcow2, .img, .raw are allowed")
        return kind

    def _target_path(self, entry: dict[str, Any], filename: str, *, content_kind: str) -> Path:
        pool_path = str(entry.get("path", "")).strip()
        if not pool_path:
            raise ValueError(f"storage pool '{entry.get('storage', '')}' has no writable path")
        supported = {item.strip() for item in str(entry.get("content", "")).split(",") if item.strip()}
        if content_kind not in supported:
            raise ValueError(
                f"storage pool '{entry.get('storage', '')}' does not support content type '{content_kind}'"
            )
        base_dir = Path(pool_path).expanduser()
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / filename

    def upload_image(
        self,
        pool_name: str,
        filename: str,
        payload: bytes,
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        pool = self._normalize_pool(pool_name)
        name = self._normalize_filename(filename)
        if not isinstance(payload, (bytes, bytearray)) or not payload:
            raise ValueError("missing payload")

        entry = self._storage_entry(pool)
        content_kind = self._content_kind_for_filename(name)
        target = self._target_path(entry, name, content_kind=content_kind)
        size_bytes = len(payload)

        existing_size = 0
        if target.exists():
            if not overwrite:
                raise ValueError(f"target '{name}' already exists")
            try:
                existing_size = int(target.stat().st_size)
            except OSError:
                existing_size = 0

        quota = self._get_pool_quota(pool)
        quota_bytes = max(int((quota or {}).get("quota_bytes", 0) or 0), 0)
        used_bytes = max(int(entry.get("used", 0) or 0), 0)
        projected_used = max(0, used_bytes - existing_size) + size_bytes
        if quota_bytes > 0 and projected_used > quota_bytes:
            raise ValueError(
                f"quota_exceeded: pool '{pool}' limit={quota_bytes} used={used_bytes} requested={size_bytes}"
            )

        tmp_target = target.with_name(f".{target.name}.uploading")
        tmp_target.write_bytes(bytes(payload))
        os.replace(tmp_target, target)

        return {
            "pool": pool,
            "filename": name,
            "content_kind": content_kind,
            "size_bytes": size_bytes,
            "storage_ref": f"{pool}:{content_kind}/{name}",
            "path": str(target),
            "overwritten": bool(existing_size > 0),
        }
