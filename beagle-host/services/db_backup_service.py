"""DB Backup Service — snapshot the Beagle SQLite state DB.

Uses SQLite's online backup API (equivalent of ``sqlite3 .backup``) so the
snapshot is consistent even while the DB is live.

Usage (from Python):

    svc = DbBackupService(db_path=Path("/var/lib/beagle/state.db"),
                          backup_dir=Path("/var/lib/beagle/backups/db"))
    result = svc.snapshot()
    result["path"]  # "/var/lib/beagle/backups/db/state-...db"

"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DbBackupService:
    """Create consistent online backups of the Beagle SQLite state database."""

    DEFAULT_BACKUP_DIR = Path("/var/lib/beagle/backups/db")
    MAX_BACKUPS = 30  # keep at most this many snapshots

    def __init__(
        self,
        db_path: Path,
        backup_dir: Path | None = None,
        max_backups: int | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._backup_dir = Path(backup_dir or self.DEFAULT_BACKUP_DIR)
        self._max_backups = int(max_backups or self.MAX_BACKUPS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def snapshot(self, *, target_path: Path | None = None) -> dict[str, Any]:
        """Create a consistent snapshot of the live SQLite DB.

        Returns a dict with ``path``, ``size_bytes``, and ``timestamp`` keys.
        Raises :exc:`FileNotFoundError` if the source DB does not exist.
        """
        if not self._db_path.exists():
            raise FileNotFoundError(f"SQLite DB not found: {self._db_path}")

        self._backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = target_path or (self._backup_dir / f"state-{ts}.db")

        # Use SQLite online backup API — safe while the DB is open
        src_conn = sqlite3.connect(str(self._db_path))
        dst_conn = sqlite3.connect(str(dest))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        result: dict[str, Any] = {
            "path": str(dest),
            "size_bytes": dest.stat().st_size,
            "timestamp": ts,
        }

        self._prune_old_backups()
        return result

    def list_backups(self) -> list[dict[str, Any]]:
        """Return metadata for all stored backup files, newest first."""
        if not self._backup_dir.exists():
            return []
        files = sorted(
            (f for f in self._backup_dir.iterdir() if f.suffix == ".db"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        return [
            {
                "path": str(f),
                "size_bytes": f.stat().st_size,
                "name": f.name,
            }
            for f in files
        ]

    def restore(self, backup_path: Path | str, *, target_path: Path | str | None = None) -> None:
        """Restore a backup to *target_path* (default: the live DB path).

        Writes to a temp file first, then atomically replaces the target so a
        failed restore never corrupts the live DB.
        """
        src = Path(backup_path)
        if not src.exists():
            raise FileNotFoundError(f"Backup file not found: {src}")

        dest = Path(target_path or self._db_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".restore_tmp")
        shutil.copy2(src, tmp)
        tmp.replace(dest)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _prune_old_backups(self) -> None:
        files = sorted(
            (f for f in self._backup_dir.iterdir() if f.suffix == ".db"),
            key=lambda f: f.stat().st_mtime,
        )
        while len(files) > self._max_backups:
            oldest = files.pop(0)
            try:
                oldest.unlink()
            except OSError:
                pass
