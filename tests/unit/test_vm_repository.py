from __future__ import annotations

from pathlib import Path

from core.persistence.sqlite_db import BeagleDb
from core.repository.vm_repository import VmRepository


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "core" / "persistence" / "migrations"


def _repo(tmp_path: Path) -> VmRepository:
    db = BeagleDb(tmp_path / "state.db")
    db.migrate(SCHEMA_DIR)
    return VmRepository(db)


def test_save_and_get_roundtrip(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    saved = repo.save({
        "vmid": 101,
        "node": "srv1",
        "name": "vm-101",
        "status": "running",
        "pool_id": "",
        "custom": {"role": "worker"},
    })
    loaded = repo.get(101)

    assert saved["vmid"] == 101
    assert loaded is not None
    assert loaded["node"] == "srv1"
    assert loaded["status"] == "running"
    assert loaded["custom"] == {"role": "worker"}


def test_save_updates_existing_row(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    repo.save({"vmid": 101, "node": "srv1", "name": "vm-101", "status": "running"})
    updated = repo.save({"vmid": 101, "node": "srv2", "name": "vm-101", "status": "stopped"})

    assert updated["node"] == "srv2"
    assert updated["status"] == "stopped"
    assert len(repo.list()) == 1


def test_list_filters_by_node_and_status(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save({"vmid": 100, "node": "srv1", "name": "vm-100", "status": "running"})
    repo.save({"vmid": 101, "node": "srv1", "name": "vm-101", "status": "stopped"})
    repo.save({"vmid": 102, "node": "srv2", "name": "vm-102", "status": "running"})

    by_node = repo.list(node_id="srv1")
    by_status = repo.list(status="running")
    by_both = repo.list(node_id="srv1", status="running")

    assert [item["vmid"] for item in by_node] == [100, 101]
    assert [item["vmid"] for item in by_status] == [100, 102]
    assert [item["vmid"] for item in by_both] == [100]


def test_delete_returns_true_only_when_row_existed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save({"vmid": 200, "node": "srv1", "name": "vm-200", "status": "running"})

    assert repo.delete(200) is True
    assert repo.delete(200) is False
    assert repo.get(200) is None


def test_save_requires_positive_vmid(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    try:
        repo.save({"vmid": 0, "node": "srv1"})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for invalid vmid")