"""Integration tests — Backup → Restore chain.

GoAdvanced Plan 10 Schritt 3.

Tests the full backup/restore lifecycle at the service layer:
1. Policy CRUD (pool and VM policies)
2. Schedule-due logic (pure)
3. Backup execution → archive created
4. Restore from archive → files extracted
5. Single-file listing and extraction
6. Edge cases: corrupt archive, missing archive, bad restore path

The BackupService._run_backup_archive archives ``/etc/beagle`` by default.
We override it with a test-subclass that archives a temp directory so tests
work without root and without a real Beagle installation.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _sub in ("services", "providers", "bin"):
    _p = os.path.join(ROOT, "beagle-host", _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backup_service import BackupService  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class _TestBackupService(BackupService):
    """BackupService subclass that archives a controlled temp directory
    instead of /etc/beagle, so tests work without root privileges.
    """

    def __init__(self, *, state_file: Path, source_dir: Path, **kwargs):
        super().__init__(state_file=state_file, **kwargs)
        self._source_dir = Path(source_dir)

    def _run_backup_archive(
        self,
        *,
        scope_type: str,
        scope_id: str,
        target_path: str,
        incremental: bool = False,
    ) -> str:
        Path(target_path).mkdir(parents=True, exist_ok=True)
        now_iso = self._utcnow()
        safe_ts = now_iso.replace(":", "-").replace(" ", "_")
        archive = str(
            Path(target_path) / f"beagle-backup-{scope_type}-{scope_id}-{safe_ts}.tar.gz"
        )
        result = subprocess.run(
            ["tar", "-czf", archive, "-C", str(self._source_dir.parent), self._source_dir.name],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip()[:500])
        return archive


def _make_source_dir(tmp_path: Path) -> Path:
    """Create a small source directory with a few files for the backup."""
    src = tmp_path / "beagle-source"
    src.mkdir()
    (src / "config.json").write_text('{"service": "beagle"}', encoding="utf-8")
    (src / "secrets.env").write_text("KEY=value\n", encoding="utf-8")
    sub = src / "subdir"
    sub.mkdir()
    (sub / "data.txt").write_text("hello backup\n", encoding="utf-8")
    return src


def _make_corrupt_archive(tmp_path: Path) -> Path:
    """Write a file that looks like a .tar.gz but is corrupt."""
    p = tmp_path / "corrupt.tar.gz"
    p.write_bytes(b"NOT_A_VALID_GZIP_ARCHIVE\x00\xff\xfe" * 10)
    return p


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "backup-state.json"


@pytest.fixture
def source_dir(tmp_path):
    return _make_source_dir(tmp_path)


@pytest.fixture
def svc(state_file, source_dir):
    return _TestBackupService(
        state_file=state_file,
        source_dir=source_dir,
        utcnow=_utcnow,
    )


@pytest.fixture
def backup_dir(tmp_path):
    d = tmp_path / "backups"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Tests: Policy CRUD
# ---------------------------------------------------------------------------

class TestBackupPolicyCRUD:

    def test_pool_policy_defaults(self, svc):
        policy = svc.get_pool_policy("pool1")
        assert policy["pool_id"] == "pool1"
        assert policy["enabled"] is False
        assert policy["schedule"] == "daily"
        assert policy["retention_days"] == 7

    def test_update_pool_policy(self, svc):
        svc.update_pool_policy("pool1", {"enabled": True, "schedule": "hourly", "retention_days": 14})
        policy = svc.get_pool_policy("pool1")
        assert policy["enabled"] is True
        assert policy["schedule"] == "hourly"
        assert policy["retention_days"] == 14

    def test_vm_policy_defaults(self, svc):
        policy = svc.get_vm_policy(100)
        assert policy["vmid"] == 100
        assert policy["enabled"] is False

    def test_update_vm_policy(self, svc):
        svc.update_vm_policy(100, {"enabled": True, "retention_days": 30})
        policy = svc.get_vm_policy(100)
        assert policy["enabled"] is True
        assert policy["retention_days"] == 30

    def test_invalid_schedule_normalizes_to_daily(self, svc):
        svc.update_pool_policy("p", {"schedule": "monthly"})
        assert svc.get_pool_policy("p")["schedule"] == "daily"

    def test_retention_days_clamped_to_minimum_1(self, svc):
        svc.update_vm_policy(1, {"retention_days": 0})
        assert svc.get_vm_policy(1)["retention_days"] == 1

    def test_pool_id_required(self, svc):
        with pytest.raises(ValueError):
            svc.get_pool_policy("")

    def test_target_path_traversal_rejected(self, svc):
        svc.update_pool_policy("p", {"target_path": "/valid/../etc/passwd"})
        # Normalized to safe default
        assert svc.get_pool_policy("p")["target_path"] == "/var/backups/beagle"


# ---------------------------------------------------------------------------
# Tests: Schedule due logic
# ---------------------------------------------------------------------------

class TestScheduleDue:

    def test_empty_last_backup_is_due(self):
        assert BackupService._schedule_due("", "daily", "2026-01-02T12:00:00") is True

    def test_same_day_not_due_for_daily(self):
        assert BackupService._schedule_due("2026-01-02T06:00:00", "daily", "2026-01-02T12:00:00") is False

    def test_different_day_is_due_for_daily(self):
        assert BackupService._schedule_due("2026-01-01T06:00:00", "daily", "2026-01-02T12:00:00") is True

    def test_same_hour_not_due_for_hourly(self):
        assert BackupService._schedule_due("2026-01-02T12:00:00", "hourly", "2026-01-02T12:45:00") is False

    def test_different_hour_is_due_for_hourly(self):
        assert BackupService._schedule_due("2026-01-02T11:59:00", "hourly", "2026-01-02T12:00:00") is True

    def test_weekly_same_day_not_due(self):
        assert BackupService._schedule_due("2026-01-02T00:00:00", "weekly", "2026-01-02T23:59:00") is False

    def test_weekly_different_day_is_due(self):
        assert BackupService._schedule_due("2026-01-01T00:00:00", "weekly", "2026-01-03T00:00:00") is True


# ---------------------------------------------------------------------------
# Tests: run_backup_now
# ---------------------------------------------------------------------------

class TestRunBackupNow:

    def test_backup_succeeds_and_creates_archive(self, svc, backup_dir):
        svc.update_pool_policy("pool1", {
            "enabled": True,
            "target_type": "local",
            "target_path": str(backup_dir),
        })
        result = svc.run_backup_now(scope_type="pool", scope_id="pool1")

        assert result["ok"] is True
        archive_path = result["job"]["archive"]
        assert Path(archive_path).exists()
        assert archive_path.endswith(".tar.gz")

    def test_backup_job_recorded_in_state(self, svc, backup_dir):
        svc.update_vm_policy(200, {
            "enabled": True,
            "target_type": "local",
            "target_path": str(backup_dir),
        })
        svc.run_backup_now(scope_type="vm", scope_id="200")
        jobs = svc.list_jobs(scope_type="vm", scope_id="200")
        assert len(jobs) == 1
        assert jobs[0]["status"] == "success"

    def test_backup_updates_last_backup_timestamp(self, svc, backup_dir):
        svc.update_pool_policy("pool1", {"target_path": str(backup_dir)})
        result = svc.run_backup_now(scope_type="pool", scope_id="pool1")
        assert result["ok"] is True, f"Backup failed: {result['job'].get('error')}"
        policy = svc.get_pool_policy("pool1")
        assert policy["last_backup"] != ""

    def test_invalid_scope_type_raises(self, svc):
        with pytest.raises(ValueError, match="scope_type"):
            svc.run_backup_now(scope_type="invalid", scope_id="x")

    def test_empty_scope_id_raises(self, svc):
        with pytest.raises(ValueError, match="scope_id"):
            svc.run_backup_now(scope_type="pool", scope_id="")

    def test_multiple_backups_accumulate_jobs(self, svc, backup_dir):
        svc.update_pool_policy("pool1", {"target_path": str(backup_dir)})
        svc.run_backup_now(scope_type="pool", scope_id="pool1")
        svc.run_backup_now(scope_type="pool", scope_id="pool1")
        jobs = svc.list_jobs(scope_type="pool", scope_id="pool1")
        assert len(jobs) == 2


# ---------------------------------------------------------------------------
# Tests: restore_snapshot
# ---------------------------------------------------------------------------

class TestRestoreSnapshot:

    def _backup_and_get_job_id(self, svc, backup_dir):
        svc.update_pool_policy("pool1", {
            "target_type": "local",
            "target_path": str(backup_dir),
        })
        result = svc.run_backup_now(scope_type="pool", scope_id="pool1")
        assert result["ok"] is True
        return result["job"]["job_id"]

    def test_restore_extracts_files(self, svc, backup_dir, tmp_path):
        job_id = self._backup_and_get_job_id(svc, backup_dir)
        restore_dest = str(tmp_path / "restore-target")
        result = svc.restore_snapshot(job_id, restore_path=restore_dest)

        assert result["ok"] is True
        assert result["files_count"] > 0
        # restored_to exists
        assert Path(result["restored_to"]).exists()

    def test_restore_files_match_source(self, svc, backup_dir, tmp_path, source_dir):
        job_id = self._backup_and_get_job_id(svc, backup_dir)
        restore_dest = str(tmp_path / "restore-check")
        result = svc.restore_snapshot(job_id, restore_path=restore_dest)
        assert result["ok"] is True
        # At least config.json should be extractable
        # The archive contains the source_dir name as a relative path
        extracted = list(Path(restore_dest).rglob("config.json"))
        assert len(extracted) == 1
        data = json.loads(extracted[0].read_text())
        assert data["service"] == "beagle"

    def test_restore_nonexistent_job_raises(self, svc, tmp_path):
        with pytest.raises(ValueError, match="Job not found"):
            svc.restore_snapshot("nonexistent-job-id", restore_path=str(tmp_path / "x"))

    def test_restore_path_traversal_rejected(self, svc, backup_dir, tmp_path):
        job_id = self._backup_and_get_job_id(svc, backup_dir)
        result = svc.restore_snapshot(job_id, restore_path="/tmp/../../etc/bad")
        assert result["ok"] is False

    def test_restore_failed_job_raises(self, svc, tmp_path):
        # Manually inject a failed job
        import json as _json
        state_file = svc._state_file
        state = {"pool_policies": {}, "vm_policies": {}, "jobs": [
            {
                "job_id": "failed-job-id",
                "scope_type": "pool",
                "scope_id": "pool1",
                "status": "error",
                "created_at": _utcnow(),
                "error": "disk full",
            }
        ], "replication": {}}
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(_json.dumps(state))

        with pytest.raises(ValueError, match="did not succeed"):
            svc.restore_snapshot("failed-job-id", restore_path=str(tmp_path / "x"))


# ---------------------------------------------------------------------------
# Tests: list_snapshot_files / read_snapshot_file
# ---------------------------------------------------------------------------

class TestSnapshotFileListing:

    def _backup_and_get_job_id(self, svc, backup_dir):
        svc.update_vm_policy(300, {
            "target_type": "local",
            "target_path": str(backup_dir),
        })
        result = svc.run_backup_now(scope_type="vm", scope_id="300")
        assert result["ok"] is True
        return result["job"]["job_id"]

    def test_list_snapshot_files_returns_files(self, svc, backup_dir):
        job_id = self._backup_and_get_job_id(svc, backup_dir)
        result = svc.list_snapshot_files(job_id)

        assert result["ok"] is True
        assert isinstance(result["files"], list)
        assert len(result["files"]) > 0

    def test_list_snapshot_files_contains_known_file(self, svc, backup_dir):
        job_id = self._backup_and_get_job_id(svc, backup_dir)
        result = svc.list_snapshot_files(job_id)

        paths = [f["path"] for f in result["files"]]
        # At least one entry containing 'config.json'
        assert any("config.json" in p for p in paths)

    def test_list_nonexistent_job_raises(self, svc):
        with pytest.raises(ValueError, match="Job not found"):
            svc.list_snapshot_files("bad-job-id")

    def test_read_snapshot_file_returns_bytes(self, svc, backup_dir):
        job_id = self._backup_and_get_job_id(svc, backup_dir)
        listing = svc.list_snapshot_files(job_id)
        # Find a non-directory path
        file_path = next(
            f["path"] for f in listing["files"]
            if not f["is_dir"] and "config.json" in f["path"]
        )
        # Strip leading slash if present
        if file_path.startswith("/"):
            file_path = file_path[1:]
        data = svc.read_snapshot_file(job_id, file_path)
        assert isinstance(data, bytes)
        content = json.loads(data.decode())
        assert content["service"] == "beagle"

    def test_read_snapshot_file_path_traversal_rejected(self, svc, backup_dir):
        job_id = self._backup_and_get_job_id(svc, backup_dir)
        with pytest.raises(ValueError, match="Invalid file_path"):
            svc.read_snapshot_file(job_id, "../etc/passwd")


# ---------------------------------------------------------------------------
# Tests: Corrupt archive edge cases
# ---------------------------------------------------------------------------

class TestCorruptArchive:

    def test_restore_from_corrupt_archive_returns_error(self, svc, tmp_path):
        """Inject a job with a corrupt archive path and expect restore to fail gracefully."""
        corrupt = _make_corrupt_archive(tmp_path)
        import json as _json
        state = {
            "pool_policies": {"pool1": {**BackupService._default_policy(svc), "target_path": str(tmp_path)}},
            "vm_policies": {},
            "jobs": [{
                "job_id": "corrupt-job-id",
                "scope_type": "pool",
                "scope_id": "pool1",
                "status": "success",
                "archive": str(corrupt),
                "created_at": _utcnow(),
                "finished_at": _utcnow(),
            }],
            "replication": {},
        }
        svc._state_file.parent.mkdir(parents=True, exist_ok=True)
        svc._state_file.write_text(_json.dumps(state))

        result = svc.restore_snapshot("corrupt-job-id", restore_path=str(tmp_path / "bad-restore"))
        assert result["ok"] is False
        assert "error" in result

    def test_list_files_from_corrupt_archive_returns_error(self, svc, tmp_path):
        corrupt = _make_corrupt_archive(tmp_path)
        import json as _json
        state = {
            "pool_policies": {"pool1": {**BackupService._default_policy(svc), "target_path": str(tmp_path)}},
            "vm_policies": {},
            "jobs": [{
                "job_id": "corrupt-list-job",
                "scope_type": "pool",
                "scope_id": "pool1",
                "status": "success",
                "archive": str(corrupt),
                "created_at": _utcnow(),
                "finished_at": _utcnow(),
            }],
            "replication": {},
        }
        svc._state_file.write_text(_json.dumps(state))

        result = svc.list_snapshot_files("corrupt-list-job")
        assert result["ok"] is False
        assert "error" in result

    def test_restore_from_missing_archive_returns_error(self, svc, tmp_path):
        import json as _json
        state = {
            "pool_policies": {"pool1": {**BackupService._default_policy(svc), "target_path": str(tmp_path)}},
            "vm_policies": {},
            "jobs": [{
                "job_id": "missing-archive-job",
                "scope_type": "pool",
                "scope_id": "pool1",
                "status": "success",
                "archive": str(tmp_path / "does-not-exist.tar.gz"),
                "created_at": _utcnow(),
            }],
            "replication": {},
        }
        svc._state_file.write_text(_json.dumps(state))

        result = svc.restore_snapshot("missing-archive-job", restore_path=str(tmp_path / "dest"))
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Tests: Scheduled backups
# ---------------------------------------------------------------------------

class TestScheduledBackups:

    def test_scheduled_backup_runs_enabled_policies(self, svc, backup_dir):
        svc.update_pool_policy("pool1", {
            "enabled": True,
            "schedule": "daily",
            "target_path": str(backup_dir),
        })
        svc.update_pool_policy("pool2", {
            "enabled": False,
            "target_path": str(backup_dir),
        })
        triggered = svc.run_scheduled_backups()
        # Only the enabled policy should have been triggered
        triggered_ids = {j["scope_id"] for j in triggered}
        assert "pool1" in triggered_ids
        assert "pool2" not in triggered_ids

    def test_scheduled_backup_skips_already_backed_up_today(self, svc, backup_dir):
        # Set up and run the first backup to populate last_backup.
        svc.update_pool_policy("pool1", {
            "enabled": True,
            "schedule": "daily",
            "target_path": str(backup_dir),
        })
        result = svc.run_backup_now(scope_type="pool", scope_id="pool1")
        assert result["ok"] is True, f"First backup failed: {result['job'].get('error')}"
        # The policy now has last_backup = today.  Running scheduled backups
        # again in the same UTC day must NOT trigger another backup.
        triggered = svc.run_scheduled_backups()
        assert len(triggered) == 0
