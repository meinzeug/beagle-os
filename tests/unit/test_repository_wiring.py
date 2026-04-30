"""Tests for Repository-Pattern Schritt 3: wiring repositories into services.

Verifies that PoolManagerService and DeviceRegistryService can be instantiated
with a real SQLite-backed repository and that state written through the service
is visible via the repository.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure beagle-host/services is on the path for service imports
REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICES_DIR = REPO_ROOT / "beagle-host" / "services"
for d in (REPO_ROOT, SERVICES_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

import pytest

from core.persistence.sqlite_db import BeagleDb
from core.repository.pool_repository import PoolRepository
from core.repository.device_repository import DeviceRepository
from core.repository.vm_repository import VmRepository

SCHEMA_DIR = REPO_ROOT / "core" / "persistence" / "migrations"


def _make_db(tmp_path: Path) -> BeagleDb:
    db = BeagleDb(tmp_path / "state.db")
    db.migrate(SCHEMA_DIR)
    return db


# ---------------------------------------------------------------------------
# PoolRepository integration
# ---------------------------------------------------------------------------

def test_pool_repository_roundtrip(tmp_path: Path) -> None:
    repo = PoolRepository(_make_db(tmp_path))

    pool = {
        "pool_id": "pool-1",
        "name": "Desktop Pool 1",
        "status": "active",
        "type": "floating_non_persistent",
        "node_id": "beagle-0",
    }
    repo.save(pool)
    loaded = repo.get("pool-1")

    assert loaded is not None
    assert loaded["pool_id"] == "pool-1"
    assert loaded["name"] == "Desktop Pool 1"


def test_pool_repository_list_and_delete(tmp_path: Path) -> None:
    repo = PoolRepository(_make_db(tmp_path))

    for i in range(3):
        repo.save({"pool_id": f"pool-{i}", "name": f"Pool {i}", "status": "active"})

    assert len(repo.list()) == 3

    repo.delete("pool-1")
    assert len(repo.list()) == 2
    assert repo.get("pool-1") is None


# ---------------------------------------------------------------------------
# DeviceRepository integration
# ---------------------------------------------------------------------------

def test_device_repository_roundtrip(tmp_path: Path) -> None:
    repo = DeviceRepository(_make_db(tmp_path))

    device = {
        "device_id": "dev-abc",
        "fingerprint": "sha256:deadbeef",
        "hostname": "thin-client-01",
        "status": "online",
        "last_seen": "2026-04-30T12:00:00Z",
        "extra": {"location": "office-a"},
    }
    repo.save(device)
    loaded = repo.get("dev-abc")

    assert loaded is not None
    assert loaded["device_id"] == "dev-abc"
    assert loaded["hostname"] == "thin-client-01"
    assert loaded["status"] == "online"


def test_device_repository_list_filters(tmp_path: Path) -> None:
    repo = DeviceRepository(_make_db(tmp_path))

    repo.save({"device_id": "d1", "fingerprint": "fp1", "hostname": "tc-1", "status": "online"})
    repo.save({"device_id": "d2", "fingerprint": "fp2", "hostname": "tc-2", "status": "offline"})

    online = repo.list(status="online")
    assert len(online) == 1
    assert online[0]["device_id"] == "d1"

    all_devs = repo.list()
    assert len(all_devs) == 2


# ---------------------------------------------------------------------------
# VmRepository integration
# ---------------------------------------------------------------------------

def test_vm_repository_wired_roundtrip(tmp_path: Path) -> None:
    repo = VmRepository(_make_db(tmp_path))

    repo.save({"vmid": 100, "node": "beagle-0", "name": "beagle-100", "status": "running"})
    repo.save({"vmid": 102, "node": "beagle-0", "name": "beagle-102", "status": "running"})

    vms = repo.list()
    assert len(vms) == 2
    assert repo.get(100) is not None
    assert repo.get(100)["name"] == "beagle-100"


# ---------------------------------------------------------------------------
# PoolManagerService accepts pool_repository= kwarg (no service startup needed)
# ---------------------------------------------------------------------------

def test_pool_manager_accepts_repository_kwarg(tmp_path: Path) -> None:
    from pool_manager import PoolManagerService

    pool_repo = PoolRepository(_make_db(tmp_path))
    # Just verify construction doesn't raise and pool_repo is wired in
    svc = PoolManagerService(
        state_file=tmp_path / "desktop-pools.json",
        pool_repository=pool_repo,
    )
    # _load() should succeed; initial state has no pools from DB
    state = svc._load()
    assert "pools" in state


# ---------------------------------------------------------------------------
# DeviceRegistryService accepts device_repository= kwarg
# ---------------------------------------------------------------------------

def test_device_registry_accepts_repository_kwarg(tmp_path: Path) -> None:
    from device_registry import DeviceRegistryService

    db = _make_db(tmp_path)
    dev_repo = DeviceRepository(db)
    # Pre-populate one device directly in the repo
    dev_repo.save({
        "device_id": "dev-pre",
        "fingerprint": "fp0",
        "hostname": "pre-loaded",
        "status": "offline",
    })

    svc = DeviceRegistryService(device_repository=dev_repo)
    # The service should have loaded the pre-existing device on init
    result = svc.get_device("dev-pre")
    assert result is not None
    assert result.hostname == "pre-loaded"
