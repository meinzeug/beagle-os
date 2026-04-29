from __future__ import annotations

from pathlib import Path

from core.persistence.sqlite_db import BeagleDb
from core.repository.device_repository import DeviceRepository


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "core" / "persistence" / "migrations"


def _repo(tmp_path: Path) -> DeviceRepository:
    db = BeagleDb(tmp_path / "state.db")
    db.migrate(SCHEMA_DIR)
    return DeviceRepository(db)


def test_save_and_get_roundtrip(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    saved = repo.save(
        {
            "device_id": "dev-001",
            "fingerprint": "fp-001",
            "hostname": "tc-001",
            "status": "offline",
            "assigned_pool_id": "",
            "hardware": {"cpu_model": "Intel"},
        }
    )
    loaded = repo.get("dev-001")

    assert saved["device_id"] == "dev-001"
    assert loaded is not None
    assert loaded["fingerprint"] == "fp-001"
    assert loaded["hostname"] == "tc-001"
    assert loaded["status"] == "offline"


def test_save_updates_existing_device(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    repo.save({"device_id": "dev-001", "hostname": "tc-001", "status": "offline"})
    updated = repo.save({"device_id": "dev-001", "hostname": "tc-001-new", "status": "online"})

    assert updated["hostname"] == "tc-001-new"
    assert updated["status"] == "online"
    assert len(repo.list()) == 1


def test_list_filters_by_status_and_fingerprint(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save({"device_id": "dev-001", "fingerprint": "fp-a", "status": "online"})
    repo.save({"device_id": "dev-002", "fingerprint": "fp-b", "status": "offline"})
    repo.save({"device_id": "dev-003", "fingerprint": "fp-a", "status": "offline"})

    by_status = repo.list(status="offline")
    by_fingerprint = repo.list(fingerprint="fp-a")
    by_both = repo.list(status="offline", fingerprint="fp-a")

    assert [item["device_id"] for item in by_status] == ["dev-002", "dev-003"]
    assert [item["device_id"] for item in by_fingerprint] == ["dev-001", "dev-003"]
    assert [item["device_id"] for item in by_both] == ["dev-003"]


def test_delete_returns_true_only_when_device_existed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save({"device_id": "dev-001", "hostname": "tc-001"})

    assert repo.delete("dev-001") is True
    assert repo.delete("dev-001") is False
    assert repo.get("dev-001") is None


def test_save_requires_device_id(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    try:
        repo.save({"hostname": "tc-001"})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError when device_id is missing")