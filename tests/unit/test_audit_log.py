import json
import tempfile
import unittest

import sys
from pathlib import Path

SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from audit_log import AuditLogService


class AuditLogServiceTests(unittest.TestCase):
    def test_write_event_appends_json_line(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit" / "audit.jsonl"
            service = AuditLogService(log_file=log_path, now_utc=lambda: "2026-04-21T10:00:00Z")

            service.write_event("vm.start", "success", {"vmid": 301, "resource_type": "vm", "resource_id": 301})

            lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["event_type"], "vm.start")
            self.assertEqual(payload["outcome"], "success")
            self.assertEqual(payload["details"]["vmid"], 301)

    def test_write_event_records_auth_user_create(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit" / "audit.jsonl"
            service = AuditLogService(log_file=log_path, now_utc=lambda: "2026-04-21T10:00:00Z")

            service.write_event(
                "auth.user.create",
                "success",
                {"username": "temp-audit-user", "resource_type": "user", "resource_id": "temp-audit-user"},
            )

            payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload["event_type"], "auth.user.create")
            self.assertEqual(payload["details"]["resource_type"], "user")
            self.assertEqual(payload["details"]["resource_id"], "temp-audit-user")


if __name__ == "__main__":
    unittest.main()
