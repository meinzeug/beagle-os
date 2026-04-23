"""LocalBackupTarget — stores backup chunks on the local filesystem."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _safe_id(chunk_id: str) -> str:
    """Sanitize chunk_id to a safe filename component (no path traversal)."""
    raw = str(chunk_id)
    if not raw or ".." in raw or "/" in raw or raw.startswith("."):
        raise ValueError(f"Invalid chunk_id: {chunk_id!r}")
    safe = "".join(c for c in raw if c.isalnum() or c in "-_.")
    if not safe:
        raise ValueError(f"Invalid chunk_id: {chunk_id!r}")
    return safe


class LocalBackupTarget:
    """BackupTarget that reads/writes chunks to the local filesystem."""

    def __init__(self, *, base_path: str = "/var/backups/beagle") -> None:
        self._base = Path(base_path)

    def write_chunk(self, chunk_id: str, data: bytes) -> None:
        self._base.mkdir(parents=True, exist_ok=True)
        (self._base / _safe_id(chunk_id)).write_bytes(data)

    def read_chunk(self, chunk_id: str) -> bytes:
        p = self._base / _safe_id(chunk_id)
        if not p.exists():
            raise FileNotFoundError(f"Snapshot chunk not found: {chunk_id!r}")
        return p.read_bytes()

    def list_snapshots(self, *, prefix: str = "") -> list[dict[str, Any]]:
        if not self._base.exists():
            return []
        results: list[dict[str, Any]] = []
        for p in sorted(self._base.iterdir()):
            if p.is_file() and (not prefix or p.name.startswith(prefix)):
                stat = p.stat()
                results.append(
                    {
                        "snapshot_id": p.name,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    }
                )
        return results

    def delete_snapshot(self, snapshot_id: str) -> None:
        p = self._base / _safe_id(snapshot_id)
        if p.exists():
            p.unlink()
