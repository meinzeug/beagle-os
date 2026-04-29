from __future__ import annotations

import sqlite3
from pathlib import Path

from core.persistence.sqlite_db import BeagleDb


def test_connect_enables_wal_and_foreign_keys(tmp_path: Path) -> None:
    db = BeagleDb(tmp_path / "state.db")

    conn = db.connect()

    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    db.close()


def test_connect_reuses_connection_per_thread(tmp_path: Path) -> None:
    db = BeagleDb(tmp_path / "state.db")

    first = db.connect()
    second = db.connect()

    assert first is second
    db.close()


def test_migrate_applies_sql_files_in_order_once(tmp_path: Path) -> None:
    schema_dir = tmp_path / "migrations"
    schema_dir.mkdir()
    (schema_dir / "001_init.sql").write_text(
        "CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT NOT NULL);\n",
        encoding="utf-8",
    )
    (schema_dir / "002_seed.sql").write_text(
        "INSERT INTO widgets(name) VALUES ('alpha');\n",
        encoding="utf-8",
    )
    db = BeagleDb(tmp_path / "state.db")

    applied = db.migrate(schema_dir)
    rows = db.connect().execute("SELECT name FROM widgets ORDER BY id").fetchall()
    applied_again = db.migrate(schema_dir)

    assert applied == ["001_init.sql", "002_seed.sql"]
    assert [row[0] for row in rows] == ["alpha"]
    assert applied_again == []
    db.close()


def test_migrate_rolls_back_failed_script(tmp_path: Path) -> None:
    schema_dir = tmp_path / "migrations"
    schema_dir.mkdir()
    (schema_dir / "001_ok.sql").write_text(
        "CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT NOT NULL);\n",
        encoding="utf-8",
    )
    (schema_dir / "002_broken.sql").write_text(
        "INSERT INTO missing_table(name) VALUES ('boom');\n",
        encoding="utf-8",
    )
    db = BeagleDb(tmp_path / "state.db")

    try:
        db.migrate(schema_dir)
    except sqlite3.Error:
        recorded = db.connect().execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        assert [row[0] for row in recorded] == ["001_ok.sql"]
    else:
        raise AssertionError("expected sqlite3.Error for broken migration")
    finally:
        db.close()