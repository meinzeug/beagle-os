"""SQLite persistence layer for Beagle host state.

Provides a small reusable wrapper around ``sqlite3`` with:

* one database file per host
* per-thread cached connections
* WAL mode enabled by default
* foreign keys enforced on every connection
* ordered SQL-file migrations tracked in ``schema_migrations``
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class BeagleDb:
    """Small SQLite DB wrapper with per-thread connection caching."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._local = threading.local()

    @property
    def path(self) -> Path:
        return self._path

    def connect(self) -> sqlite3.Connection:
        """Return a cached connection for the current thread."""
        cached = getattr(self._local, "connection", None)
        if cached is not None:
            return cached

        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self._path), timeout=30.0, check_same_thread=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        self._local.connection = connection
        return connection

    def close(self) -> None:
        connection = getattr(self._local, "connection", None)
        if connection is None:
            return
        connection.close()
        self._local.connection = None

    def migrate(self, schema_dir: Path | str) -> list[str]:
        """Apply ordered ``*.sql`` migrations from *schema_dir* once."""
        directory = Path(schema_dir)
        connection = self.connect()
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        applied_rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
        applied = {str(row[0]) for row in applied_rows}
        pending = sorted(path for path in directory.glob("*.sql") if path.name not in applied)

        executed: list[str] = []
        for migration_path in pending:
            sql_text = migration_path.read_text(encoding="utf-8")
            with connection:
                connection.executescript(sql_text)
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (?)",
                    (migration_path.name,),
                )
            executed.append(migration_path.name)
        return executed