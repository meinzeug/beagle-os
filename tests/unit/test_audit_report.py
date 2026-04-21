import csv
import json
import tempfile
import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from audit_log import AuditLogService
from audit_report import AuditReportService


class AuditReportServiceTests(unittest.TestCase):
    def test_build_json_report_filters_by_action_and_user(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit" / "events.log"
            writer = AuditLogService(log_file=log_path, now_utc=lambda: "2026-04-21T10:00:00Z")
            writer.write_event("vm.start", "success", {"username": "admin", "resource_type": "vm", "resource_id": 100})
            writer.write_event("vm.stop", "success", {"username": "ops", "resource_type": "vm", "resource_id": 101})

            report = AuditReportService(log_file=log_path).build_json_report(action="vm.stop", resource_type="vm", user_id="ops")

            self.assertTrue(report["ok"])
            self.assertEqual(report["count"], 1)
            self.assertEqual(report["events"][0]["action"], "vm.stop")
            self.assertEqual(report["events"][0]["user_id"], "ops")
            self.assertEqual(report["filters"]["resource_type"], "vm")

    def test_build_csv_report_includes_header_and_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit" / "events.log"
            writer = AuditLogService(log_file=log_path, now_utc=lambda: "2026-04-21T10:00:00Z")
            writer.write_event(
                "auth.user.create",
                "success",
                {
                    "username": "admin",
                    "resource_type": "user",
                    "resource_id": "alice",
                    "new_value": {"username": "alice", "role": "viewer"},
                },
            )

            content = AuditReportService(log_file=log_path).build_csv_report().decode("utf-8-sig")
            rows = list(csv.reader(content.splitlines()))

            self.assertEqual(rows[0][0], "timestamp")
            self.assertEqual(rows[1][1], "auth.user.create")
            self.assertEqual(json.loads(rows[1][11])["username"], "alice")


if __name__ == "__main__":
    unittest.main()