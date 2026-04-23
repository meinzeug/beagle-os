import tarfile
import tempfile
import unittest
from pathlib import Path

import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from backup_service import BackupService


def _make_tar(archive_path: Path, content: dict[str, bytes]) -> None:
    """Create a tar.gz at archive_path with given {relative_path: bytes} content."""
    with tarfile.open(str(archive_path), "w:gz") as tf:
        for name, data in content.items():
            import io
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


class BackupServiceTests(unittest.TestCase):
    def test_pool_policy_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = BackupService(
                state_file=Path(tmp) / "backup-state.json",
                utcnow=lambda: "2026-04-23T17:00:00Z",
            )
            updated = service.update_pool_policy(
                "pool-a",
                {
                    "enabled": True,
                    "schedule": "weekly",
                    "retention_days": 30,
                    "target_path": "/var/backups/pools",
                },
            )
            self.assertEqual(updated["pool_id"], "pool-a")
            self.assertTrue(updated["enabled"])
            self.assertEqual(updated["schedule"], "weekly")
            self.assertEqual(updated["retention_days"], 30)

    def test_pool_policy_target_type_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = BackupService(
                state_file=Path(tmp) / "backup-state.json",
                utcnow=lambda: "2026-04-23T17:00:00Z",
            )
            updated = service.update_pool_policy(
                "pool-s3",
                {
                    "target_type": "s3",
                    "s3_bucket": "my-bucket",
                    "s3_prefix": "backups/",
                },
            )
            self.assertEqual(updated["target_type"], "s3")
            self.assertEqual(updated["s3_bucket"], "my-bucket")
            self.assertEqual(updated["s3_prefix"], "backups/")

    def test_run_backup_now_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = BackupService(
                state_file=Path(tmp) / "backup-state.json",
                utcnow=lambda: "2026-04-23T17:00:00Z",
            )
            service.update_vm_policy(101, {"enabled": True, "target_path": str(Path(tmp) / "archives")})
            service._run_backup_archive = lambda **_: str(Path(tmp) / "archives" / "ok.tar.gz")

            result = service.run_backup_now(scope_type="vm", scope_id="101")
            self.assertTrue(result["ok"])
            self.assertEqual(result["job"]["status"], "success")
            self.assertTrue(str(result["job"].get("archive", "")).endswith("ok.tar.gz"))

    def test_scheduler_triggers_enabled_due_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = BackupService(
                state_file=Path(tmp) / "backup-state.json",
                utcnow=lambda: "2026-04-23T17:00:00Z",
            )
            service.update_pool_policy("pool-a", {"enabled": True, "schedule": "daily", "target_path": str(Path(tmp) / "archives")})
            service._run_backup_archive = lambda **_: str(Path(tmp) / "archives" / "daily.tar.gz")

            jobs = service.run_scheduled_backups()
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["scope_type"], "pool")
            self.assertEqual(jobs[0]["status"], "success")

    # ------------------------------------------------------------------
    # Schritt 4 — Live-Restore
    # ------------------------------------------------------------------

    def test_restore_snapshot_extracts_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            archives_dir = Path(tmp) / "archives"
            archives_dir.mkdir()
            archive_path = archives_dir / "beagle-backup-vm-101-test.tar.gz"
            _make_tar(archive_path, {"etc/beagle/config.json": b'{"ok": true}'})

            service = BackupService(
                state_file=Path(tmp) / "backup-state.json",
                utcnow=lambda: "2026-04-23T17:00:00Z",
            )
            service.update_vm_policy(101, {"enabled": True, "target_path": str(archives_dir)})
            service._run_backup_archive = lambda **_: str(archive_path)
            result_run = service.run_backup_now(scope_type="vm", scope_id="101")
            self.assertTrue(result_run["ok"])

            job_id = result_run["job"]["job_id"]
            restore_target = str(Path(tmp) / "restore-out")
            result = service.restore_snapshot(job_id, restore_path=restore_target)
            self.assertTrue(result["ok"], msg=result.get("error"))
            self.assertGreater(result.get("files_count", 0), 0)
            restored = Path(restore_target) / "etc" / "beagle" / "config.json"
            self.assertTrue(restored.exists(), "restored file should exist")

    def test_restore_snapshot_missing_job_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = BackupService(
                state_file=Path(tmp) / "backup-state.json",
                utcnow=lambda: "2026-04-23T17:00:00Z",
            )
            with self.assertRaises(ValueError):
                service.restore_snapshot("00000000-0000-0000-0000-000000000000")

    # ------------------------------------------------------------------
    # Schritt 5 — Single-File-Restore
    # ------------------------------------------------------------------

    def test_list_snapshot_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            archives_dir = Path(tmp) / "archives"
            archives_dir.mkdir()
            archive_path = archives_dir / "beagle-backup-vm-102-test.tar.gz"
            _make_tar(archive_path, {
                "etc/beagle/config.json": b'{"ok": true}',
                "etc/beagle/token": b"secret-token",
            })

            service = BackupService(
                state_file=Path(tmp) / "backup-state.json",
                utcnow=lambda: "2026-04-23T17:00:00Z",
            )
            service.update_vm_policy(102, {"enabled": True, "target_path": str(archives_dir)})
            service._run_backup_archive = lambda **_: str(archive_path)
            result_run = service.run_backup_now(scope_type="vm", scope_id="102")
            self.assertTrue(result_run["ok"])

            job_id = result_run["job"]["job_id"]
            result = service.list_snapshot_files(job_id)
            self.assertTrue(result["ok"], msg=result.get("error"))
            paths = [f["path"] for f in result["files"]]
            self.assertTrue(any("config.json" in p for p in paths), f"config.json not found in {paths}")

    def test_read_snapshot_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            archives_dir = Path(tmp) / "archives"
            archives_dir.mkdir()
            archive_path = archives_dir / "beagle-backup-vm-103-test.tar.gz"
            _make_tar(archive_path, {"etc/beagle/myfile.txt": b"file content here"})

            service = BackupService(
                state_file=Path(tmp) / "backup-state.json",
                utcnow=lambda: "2026-04-23T17:00:00Z",
            )
            service.update_vm_policy(103, {"enabled": True, "target_path": str(archives_dir)})
            service._run_backup_archive = lambda **_: str(archive_path)
            result_run = service.run_backup_now(scope_type="vm", scope_id="103")
            self.assertTrue(result_run["ok"])

            job_id = result_run["job"]["job_id"]
            data = service.read_snapshot_file(job_id, "etc/beagle/myfile.txt")
            self.assertEqual(data, b"file content here")

    def test_read_snapshot_file_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archives_dir = Path(tmp) / "archives"
            archives_dir.mkdir()
            archive_path = archives_dir / "beagle-backup-vm-104-test.tar.gz"
            _make_tar(archive_path, {"etc/beagle/file.txt": b"x"})

            service = BackupService(
                state_file=Path(tmp) / "backup-state.json",
                utcnow=lambda: "2026-04-23T17:00:00Z",
            )
            service.update_vm_policy(104, {"enabled": True, "target_path": str(archives_dir)})
            service._run_backup_archive = lambda **_: str(archive_path)
            result_run = service.run_backup_now(scope_type="vm", scope_id="104")
            job_id = result_run["job"]["job_id"]

            with self.assertRaises(ValueError):
                service.read_snapshot_file(job_id, "../etc/passwd")
            with self.assertRaises(ValueError):
                service.read_snapshot_file(job_id, "/etc/passwd")

    # ------------------------------------------------------------------
    # Schritt 6 — Replication config
    # ------------------------------------------------------------------

    def test_replication_config_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = BackupService(
                state_file=Path(tmp) / "backup-state.json",
                utcnow=lambda: "2026-04-23T17:00:00Z",
            )
            cfg = service.update_replication_config({
                "enabled": True,
                "remote_url": "https://remote.beagle.example.com",
                "api_token": "secret-api-token",
                "auto_replicate": True,
            })
            self.assertTrue(cfg["enabled"])
            self.assertEqual(cfg["remote_url"], "https://remote.beagle.example.com")
            self.assertTrue(cfg["api_token_set"])
            self.assertTrue(cfg["auto_replicate"])
            # api_token must not be returned
            self.assertNotIn("api_token", cfg)

    def test_replication_config_invalid_url_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = BackupService(
                state_file=Path(tmp) / "backup-state.json",
                utcnow=lambda: "2026-04-23T17:00:00Z",
            )
            with self.assertRaises(ValueError):
                service.update_replication_config({"remote_url": "ftp://bad-scheme.com"})

    def test_replicate_to_remote_missing_config_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = BackupService(
                state_file=Path(tmp) / "backup-state.json",
                utcnow=lambda: "2026-04-23T17:00:00Z",
            )
            with self.assertRaises(ValueError):
                service.replicate_to_remote("some-job-id")

    def test_ingest_replicated_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = BackupService(
                state_file=Path(tmp) / "backup-state.json",
                utcnow=lambda: "2026-04-23T17:00:00Z",
            )
            # Patch dest dir to tmp
            import unittest.mock as mock
            with mock.patch("pathlib.Path.mkdir"), mock.patch("pathlib.Path.write_bytes"):
                result = service.ingest_replicated_backup(
                    archive_bytes=b"fake archive",
                    meta={
                        "archive_name": "beagle-backup-vm-101-2026.tar.gz",
                        "scope_type": "vm",
                        "scope_id": "101",
                        "job_id": "orig-job-id",
                    },
                )
            self.assertTrue(result["ok"])
            self.assertIn("job_id", result)


if __name__ == "__main__":
    unittest.main()
