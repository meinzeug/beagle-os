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


if __name__ == "__main__":
    unittest.main()
