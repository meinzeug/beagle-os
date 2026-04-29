from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from beagle_host.services.db_backup_service import DbBackupService


def _make_db(path: Path) -> None:
    """Create a minimal valid SQLite DB at *path*."""
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
    conn.execute("INSERT INTO test VALUES (1, 'hello')")
    conn.commit()
    conn.close()


def test_snapshot_creates_backup_file(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _make_db(db)
    svc = DbBackupService(db_path=db, backup_dir=tmp_path / "backups")

    result = svc.snapshot()

    assert Path(result["path"]).exists()
    assert result["size_bytes"] > 0
    assert result["timestamp"]


def test_snapshot_is_readable_sqlite(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _make_db(db)
    svc = DbBackupService(db_path=db, backup_dir=tmp_path / "backups")

    result = svc.snapshot()

    conn = sqlite3.connect(result["path"])
    rows = conn.execute("SELECT val FROM test WHERE id=1").fetchall()
    conn.close()
    assert rows == [("hello",)]


def test_snapshot_to_explicit_target_path(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _make_db(db)
    svc = DbBackupService(db_path=db, backup_dir=tmp_path / "backups")
    dest = tmp_path / "explicit_backup.db"

    result = svc.snapshot(target_path=dest)

    assert result["path"] == str(dest)
    assert dest.exists()


def test_snapshot_raises_if_db_missing(tmp_path: Path) -> None:
    svc = DbBackupService(db_path=tmp_path / "nonexistent.db", backup_dir=tmp_path / "backups")

    with pytest.raises(FileNotFoundError):
        svc.snapshot()


def test_list_backups_returns_metadata(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _make_db(db)
    svc = DbBackupService(db_path=db, backup_dir=tmp_path / "backups")
    svc.snapshot(target_path=tmp_path / "backups" / "backup-1.db")
    svc.snapshot(target_path=tmp_path / "backups" / "backup-2.db")

    backups = svc.list_backups()

    assert len(backups) == 2
    for b in backups:
        assert "path" in b
        assert "size_bytes" in b
        assert b["size_bytes"] > 0


def test_list_backups_empty_dir(tmp_path: Path) -> None:
    svc = DbBackupService(db_path=tmp_path / "state.db", backup_dir=tmp_path / "backups")
    assert svc.list_backups() == []


def test_max_backups_prunes_oldest(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _make_db(db)
    svc = DbBackupService(db_path=db, backup_dir=tmp_path / "backups", max_backups=2)

    svc.snapshot()
    svc.snapshot()
    svc.snapshot()

    backups = svc.list_backups()
    assert len(backups) <= 2


def test_restore_replaces_target_db(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _make_db(db)
    svc = DbBackupService(db_path=db, backup_dir=tmp_path / "backups")
    backup = svc.snapshot()

    # Corrupt the live DB
    db.write_bytes(b"corrupted")

    # Restore
    svc.restore(backup["path"])

    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT val FROM test WHERE id=1").fetchall()
    conn.close()
    assert rows == [("hello",)]


def test_restore_to_explicit_target(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _make_db(db)
    svc = DbBackupService(db_path=db, backup_dir=tmp_path / "backups")
    backup = svc.snapshot()
    restored = tmp_path / "restored.db"

    svc.restore(backup["path"], target_path=restored)

    assert restored.exists()


def test_restore_raises_if_backup_missing(tmp_path: Path) -> None:
    svc = DbBackupService(db_path=tmp_path / "state.db", backup_dir=tmp_path / "backups")

    with pytest.raises(FileNotFoundError):
        svc.restore(tmp_path / "no_such_backup.db")
