from __future__ import annotations

from pathlib import Path

from core.persistence.sqlite_db import BeagleDb
from core.repository.pool_repository import PoolRepository


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "core" / "persistence" / "migrations"


def _repo(tmp_path: Path) -> PoolRepository:
    db = BeagleDb(tmp_path / "state.db")
    db.migrate(SCHEMA_DIR)
    return PoolRepository(db)


def test_save_and_get_roundtrip(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    saved = repo.save({
        "pool_id": "pool-1",
        "display_name": "My Pool",
        "template_id": "tmpl-ubuntu-22",
        "status": "active",
        "mode": "floating_non_persistent",
        "extra_config": {"gpu_class": "nvidia"},
    })
    loaded = repo.get("pool-1")

    assert saved["pool_id"] == "pool-1"
    assert loaded is not None
    assert loaded["display_name"] == "My Pool"
    assert loaded["template_id"] == "tmpl-ubuntu-22"
    assert loaded["status"] == "active"
    assert loaded["extra_config"] == {"gpu_class": "nvidia"}


def test_save_updates_existing_row(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    repo.save({"pool_id": "pool-1", "display_name": "Pool 1", "status": "active"})
    updated = repo.save({"pool_id": "pool-1", "display_name": "Pool 1 Updated", "status": "disabled"})

    assert updated["display_name"] == "Pool 1 Updated"
    assert updated["status"] == "disabled"
    assert len(repo.list()) == 1


def test_list_filters_by_status(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save({"pool_id": "pool-1", "display_name": "Pool 1", "status": "active"})
    repo.save({"pool_id": "pool-2", "display_name": "Pool 2", "status": "disabled"})
    repo.save({"pool_id": "pool-3", "display_name": "Pool 3", "status": "active"})

    active = repo.list(status="active")
    disabled = repo.list(status="disabled")
    all_pools = repo.list()

    assert [p["pool_id"] for p in active] == ["pool-1", "pool-3"]
    assert [p["pool_id"] for p in disabled] == ["pool-2"]
    assert len(all_pools) == 3


def test_list_filters_by_template_id(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save({"pool_id": "pool-1", "template_id": "tmpl-a", "status": "active"})
    repo.save({"pool_id": "pool-2", "template_id": "tmpl-b", "status": "active"})
    repo.save({"pool_id": "pool-3", "template_id": "tmpl-a", "status": "active"})

    tmpl_a = repo.list(template_id="tmpl-a")
    assert [p["pool_id"] for p in tmpl_a] == ["pool-1", "pool-3"]


def test_delete_removes_row(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save({"pool_id": "pool-1", "display_name": "Pool 1", "status": "active"})

    removed = repo.delete("pool-1")

    assert removed is True
    assert repo.get("pool-1") is None
    assert repo.list() == []


def test_delete_nonexistent_returns_false(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert repo.delete("nonexistent-pool") is False


def test_get_nonexistent_returns_none(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert repo.get("missing") is None


def test_save_requires_pool_id(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    import pytest
    with pytest.raises(ValueError, match="pool_id"):
        repo.save({"pool_id": "", "status": "active"})


def test_payload_extra_fields_preserved(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    pool = {
        "pool_id": "pool-x",
        "status": "active",
        "min_pool_size": 2,
        "max_pool_size": 10,
        "cpu_cores": 4,
        "memory_mib": 8192,
        "labels": ["vdi", "enterprise"],
    }
    saved = repo.save(pool)
    assert saved["min_pool_size"] == 2
    assert saved["labels"] == ["vdi", "enterprise"]
