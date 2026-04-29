from __future__ import annotations

from pathlib import Path

from core.persistence.sqlite_db import BeagleDb
from core.repository.gpu_repository import GpuRepository


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "core" / "persistence" / "migrations"


def _repo(tmp_path: Path) -> GpuRepository:
    db = BeagleDb(tmp_path / "state.db")
    db.migrate(SCHEMA_DIR)
    return GpuRepository(db)


def test_save_and_get_roundtrip(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    saved = repo.save({
        "gpu_id": "srv1:0000:01:00.0",
        "node_id": "srv1",
        "pci_address": "0000:01:00.0",
        "model": "NVIDIA RTX 4090",
        "vram_gb": 24.0,
        "status": "available",
        "current_assignment": "",
    })
    loaded = repo.get("srv1:0000:01:00.0")

    assert saved["gpu_id"] == "srv1:0000:01:00.0"
    assert loaded is not None
    assert loaded["node_id"] == "srv1"
    assert loaded["pci_address"] == "0000:01:00.0"
    assert loaded["status"] == "available"
    assert loaded["vram_gb"] == 24.0


def test_save_updates_existing_row(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    repo.save({"gpu_id": "srv1:0000:01:00.0", "node_id": "srv1", "status": "available"})
    updated = repo.save({"gpu_id": "srv1:0000:01:00.0", "node_id": "srv1", "status": "assigned", "current_assignment": "vm-101"})

    assert updated["status"] == "assigned"
    assert len(repo.list()) == 1


def test_list_filters_by_node_id(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save({"gpu_id": "srv1:0000:01:00.0", "node_id": "srv1", "status": "available"})
    repo.save({"gpu_id": "srv1:0000:02:00.0", "node_id": "srv1", "status": "available"})
    repo.save({"gpu_id": "srv2:0000:01:00.0", "node_id": "srv2", "status": "available"})

    srv1_gpus = repo.list(node_id="srv1")
    srv2_gpus = repo.list(node_id="srv2")

    assert [g["gpu_id"] for g in srv1_gpus] == ["srv1:0000:01:00.0", "srv1:0000:02:00.0"]
    assert len(srv2_gpus) == 1


def test_list_filters_by_status(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save({"gpu_id": "gpu-1", "node_id": "srv1", "status": "available"})
    repo.save({"gpu_id": "gpu-2", "node_id": "srv1", "status": "assigned"})
    repo.save({"gpu_id": "gpu-3", "node_id": "srv2", "status": "available"})

    available = repo.list(status="available")
    assigned = repo.list(status="assigned")

    assert [g["gpu_id"] for g in available] == ["gpu-1", "gpu-3"]
    assert [g["gpu_id"] for g in assigned] == ["gpu-2"]


def test_delete_removes_row(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save({"gpu_id": "gpu-1", "node_id": "srv1", "status": "available"})

    removed = repo.delete("gpu-1")

    assert removed is True
    assert repo.get("gpu-1") is None


def test_delete_nonexistent_returns_false(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert repo.delete("no-such-gpu") is False


def test_get_nonexistent_returns_none(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert repo.get("missing") is None


def test_save_requires_gpu_id(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    import pytest
    with pytest.raises(ValueError, match="gpu_id"):
        repo.save({"gpu_id": "", "node_id": "srv1", "status": "available"})


def test_status_derived_from_assignment_when_missing(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    saved = repo.save({"gpu_id": "gpu-free", "node_id": "srv1", "current_assignment": ""})
    assert saved["status"] == "available"

    saved2 = repo.save({"gpu_id": "gpu-used", "node_id": "srv1", "current_assignment": "vm-50"})
    assert saved2["status"] == "assigned"


def test_payload_extra_fields_preserved(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    gpu = {
        "gpu_id": "gpu-extra",
        "node_id": "srv1",
        "status": "available",
        "model": "NVIDIA A100",
        "vram_gb": 80.0,
        "gpu_class": "a100",
        "supports_vgpu": True,
        "driver_version": "535.161.08",
    }
    saved = repo.save(gpu)
    assert saved["model"] == "NVIDIA A100"
    assert saved["supports_vgpu"] is True
    assert saved["driver_version"] == "535.161.08"
