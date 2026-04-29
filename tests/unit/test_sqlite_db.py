from __future__ import annotations

import sqlite3
from pathlib import Path

from core.persistence.sqlite_db import BeagleDb


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "core" / "persistence" / "migrations"


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


def test_repo_initial_schema_creates_expected_tables_and_indexes(tmp_path: Path) -> None:
    db = BeagleDb(tmp_path / "state.db")

    applied = db.migrate(SCHEMA_DIR)
    table_rows = db.connect().execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    index_rows = db.connect().execute(
        "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
    ).fetchall()

    assert applied == ["001_init.sql"]
    assert {row[0] for row in table_rows} >= {
        "audit_events",
        "devices",
        "gpus",
        "pools",
        "schema_migrations",
        "secrets_meta",
        "sessions",
        "vms",
    }
    assert {row[0] for row in index_rows} >= {
        "idx_devices_fingerprint",
        "idx_gpus_pci_address",
        "idx_sessions_user_id",
        "idx_vms_node_id",
    }
    db.close()


def test_repo_initial_schema_foreign_keys_apply_cascade_and_set_null(tmp_path: Path) -> None:
    db = BeagleDb(tmp_path / "state.db")
    db.migrate(SCHEMA_DIR)
    conn = db.connect()

    conn.execute(
        "INSERT INTO pools(pool_id, display_name, status) VALUES (?, ?, ?)",
        ("pool-a", "Pool A", "ready"),
    )
    conn.execute(
        "INSERT INTO vms(vmid, node_id, name, status, pool_id) VALUES (?, ?, ?, ?, ?)",
        (101, "srv1", "vm-101", "running", "pool-a"),
    )
    conn.execute(
        "INSERT INTO sessions(session_id, pool_id, user_id, vmid, node_id, status) VALUES (?, ?, ?, ?, ?, ?)",
        ("sess-1", "pool-a", "alice", 101, "srv1", "active"),
    )
    conn.execute(
        "INSERT INTO devices(device_id, fingerprint, assigned_pool_id) VALUES (?, ?, ?)",
        ("dev-1", "fp-1", "pool-a"),
    )
    conn.execute(
        "INSERT INTO gpus(gpu_id, pci_address, vmid, node_id, status) VALUES (?, ?, ?, ?, ?)",
        ("gpu-1", "0000:01:00.0", 101, "srv1", "assigned"),
    )
    conn.commit()

    conn.execute("DELETE FROM vms WHERE vmid = ?", (101,))
    conn.commit()

    session_vmid = conn.execute(
        "SELECT vmid FROM sessions WHERE session_id = ?",
        ("sess-1",),
    ).fetchone()[0]
    gpu_vmid = conn.execute(
        "SELECT vmid FROM gpus WHERE gpu_id = ?",
        ("gpu-1",),
    ).fetchone()[0]
    assert session_vmid is None
    assert gpu_vmid is None

    conn.execute("DELETE FROM pools WHERE pool_id = ?", ("pool-a",))
    conn.commit()

    remaining_session = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE session_id = ?",
        ("sess-1",),
    ).fetchone()[0]
    assigned_pool = conn.execute(
        "SELECT assigned_pool_id FROM devices WHERE device_id = ?",
        ("dev-1",),
    ).fetchone()[0]
    assert remaining_session == 0
    assert assigned_pool is None
    db.close()