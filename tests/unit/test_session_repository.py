from __future__ import annotations

from pathlib import Path

from core.persistence.sqlite_db import BeagleDb
from core.repository.session_repository import SessionRepository


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "core" / "persistence" / "migrations"


def _repo(tmp_path: Path) -> SessionRepository:
    db = BeagleDb(tmp_path / "state.db")
    db.migrate(SCHEMA_DIR)
    db.connect().execute("INSERT INTO pools(pool_id, display_name, status) VALUES (?, ?, ?)", ("pool-a", "Pool A", "ready"))
    db.connect().execute("INSERT INTO vms(vmid, node_id, name, status) VALUES (?, ?, ?, ?)", (101, "srv1", "vm-101", "running"))
    db.connect().commit()
    return SessionRepository(db)


def test_save_and_get_roundtrip(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    saved = repo.save(
        {
            "session_id": "sess-001",
            "pool_id": "pool-a",
            "user_id": "alice",
            "vmid": 101,
            "node_id": "srv1",
            "status": "active",
        }
    )
    loaded = repo.get("sess-001")

    assert saved["session_id"] == "sess-001"
    assert loaded is not None
    assert loaded["pool_id"] == "pool-a"
    assert loaded["user_id"] == "alice"
    assert loaded["status"] == "active"


def test_save_updates_existing_session(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    repo.save({"session_id": "sess-001", "pool_id": "pool-a", "user_id": "alice", "status": "active"})
    updated = repo.save({"session_id": "sess-001", "pool_id": "pool-a", "user_id": "alice", "status": "ended"})

    assert updated["status"] == "ended"
    assert len(repo.list()) == 1


def test_list_filters_by_pool_user_and_status(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save({"session_id": "sess-001", "pool_id": "pool-a", "user_id": "alice", "status": "active"})
    repo.save({"session_id": "sess-002", "pool_id": "pool-a", "user_id": "bob", "status": "ended"})
    repo.save({"session_id": "sess-003", "pool_id": "pool-a", "user_id": "alice", "status": "ended"})

    by_user = repo.list(user_id="alice")
    by_status = repo.list(status="ended")
    by_both = repo.list(user_id="alice", status="ended")

    assert [item["session_id"] for item in by_user] == ["sess-001", "sess-003"]
    assert [item["session_id"] for item in by_status] == ["sess-002", "sess-003"]
    assert [item["session_id"] for item in by_both] == ["sess-003"]


def test_delete_returns_true_only_when_session_existed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save({"session_id": "sess-001", "pool_id": "pool-a", "user_id": "alice", "status": "active"})

    assert repo.delete("sess-001") is True
    assert repo.delete("sess-001") is False
    assert repo.get("sess-001") is None


def test_save_requires_session_id_and_pool_id(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    try:
        repo.save({"pool_id": "pool-a"})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError when session_id is missing")

    try:
        repo.save({"session_id": "sess-x"})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError when pool_id is missing")