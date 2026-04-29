from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
IMPORTER = SCRIPTS_DIR / "migrate-json-to-sqlite.py"


def _make_state_root(tmp_path: Path) -> Path:
    """Create a minimal fake state root with sample JSON files."""
    state = tmp_path / "beagle-state"

    # VMs
    vms_dir = state / "providers" / "beagle"
    vms_dir.mkdir(parents=True)
    (vms_dir / "vms.json").write_text(json.dumps([
        {"vmid": 100, "node": "srv1", "name": "vm-100", "status": "running"},
        {"vmid": 101, "node": "srv1", "name": "vm-101", "status": "stopped"},
    ]))

    # Pools
    mgr_dir = state / "beagle-manager"
    mgr_dir.mkdir(parents=True)
    (mgr_dir / "desktop-pools.json").write_text(json.dumps({
        "pools": {
            "pool-a": {
                "pool_id": "pool-a",
                "display_name": "Pool A",
                "template_id": "tmpl-ubuntu",
                "status": "active",
                "mode": "floating_non_persistent",
            },
        },
        "vms": {},
    }))

    # Devices
    (mgr_dir / "device-registry.json").write_text(json.dumps({
        "devices": {
            "dev-1": {
                "device_id": "dev-1",
                "fingerprint": "abc123",
                "hostname": "thin-client-1",
                "status": "online",
                "last_seen": "2026-04-29T10:00:00+00:00",
            },
        }
    }))

    return state


def _run_importer(state_root: Path, db_path: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(IMPORTER),
        "--state-root", str(state_root),
        "--db", str(db_path),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)


def test_dry_run_exits_zero_no_db_created(tmp_path: Path) -> None:
    state_root = _make_state_root(tmp_path)
    db_path = tmp_path / "state.db"

    result = _run_importer(state_root, db_path, ["--dry-run"])

    assert result.returncode == 0, result.stderr
    assert not db_path.exists(), "dry-run must not create DB"
    assert "dry-run complete" in result.stdout.lower()


def test_live_run_migrates_all_entities(tmp_path: Path) -> None:
    state_root = _make_state_root(tmp_path)
    db_path = tmp_path / "state.db"

    result = _run_importer(state_root, db_path)

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert db_path.exists()
    assert "Total migrated : 4" in result.stdout  # 2 vms + 1 pool + 1 device


def test_live_run_creates_backup(tmp_path: Path) -> None:
    state_root = _make_state_root(tmp_path)
    db_path = tmp_path / "state.db"

    _run_importer(state_root, db_path)

    bak_dir = state_root / ".bak"
    assert bak_dir.exists()
    # At least one timestamped subdirectory
    subdirs = list(bak_dir.iterdir())
    assert len(subdirs) >= 1


def test_idempotent_second_run(tmp_path: Path) -> None:
    state_root = _make_state_root(tmp_path)
    db_path = tmp_path / "state.db"

    r1 = _run_importer(state_root, db_path)
    r2 = _run_importer(state_root, db_path)

    assert r1.returncode == 0, r1.stderr
    assert r2.returncode == 0, r2.stderr
    # No errors on second run (UPSERT)
    assert "errors   : 0" in r2.stdout


def test_missing_state_root_exits_nonzero(tmp_path: Path) -> None:
    missing = tmp_path / "nonexistent"
    db_path = tmp_path / "state.db"

    result = _run_importer(missing, db_path)

    assert result.returncode != 0


def test_empty_state_root_skips_gracefully(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    db_path = tmp_path / "state.db"

    result = _run_importer(empty, db_path)

    assert result.returncode == 0
    assert "Total migrated : 0" in result.stdout


def test_dry_run_counts_but_no_backup(tmp_path: Path) -> None:
    state_root = _make_state_root(tmp_path)
    db_path = tmp_path / "state.db"

    result = _run_importer(state_root, db_path, ["--dry-run"])

    assert result.returncode == 0
    bak_dir = state_root / ".bak"
    assert not bak_dir.exists(), "dry-run must not create backup"
