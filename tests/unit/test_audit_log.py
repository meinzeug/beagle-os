import json
import tempfile
import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from core.audit_event import AuditEvent
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
            self.assertEqual(payload["schema_version"], "1")
            self.assertEqual(payload["action"], "vm.start")
            self.assertEqual(payload["result"], "success")
            self.assertEqual(payload["resource_type"], "vm")
            self.assertEqual(payload["resource_id"], "301")
            self.assertEqual(payload["metadata"]["vmid"], 301)

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
            self.assertEqual(payload["action"], "auth.user.create")
            self.assertEqual(payload["user_id"], "temp-audit-user")
            self.assertEqual(payload["resource_type"], "user")
            self.assertEqual(payload["resource_id"], "temp-audit-user")

    def test_audit_event_normalizes_legacy_record(self):
        legacy = AuditEvent.from_record(
            {
                "timestamp": "2026-04-21T10:00:00Z",
                "event_type": "vm.stop",
                "outcome": "denied",
                "details": {
                    "username": "ops",
                    "resource_type": "vm",
                    "resource_id": 401,
                    "remote_addr": "127.0.0.1",
                    "vmid": 401,
                },
            }
        ).to_record()

        self.assertEqual(legacy["action"], "vm.stop")
        self.assertEqual(legacy["result"], "rejected")
        self.assertEqual(legacy["user_id"], "ops")
        self.assertEqual(legacy["resource_id"], "401")
        self.assertEqual(legacy["source_ip"], "127.0.0.1")
        self.assertEqual(legacy["metadata"]["vmid"], 401)

    def test_audit_event_redacts_passwords_and_tokens_in_old_new_values(self):
        record = AuditEvent.create(
            timestamp="2026-04-21T10:00:00Z",
            action="auth.user.create",
            result="success",
            details={
                "resource_type": "user",
                "resource_id": "alice",
                "old_value": {
                    "password": "before",
                    "nested": {"api_token": "secret-token"},
                },
                "new_value": {
                    "username": "alice",
                    "private_key": "pem-data",
                    "profile": [{"session_token": "abc123"}],
                },
            },
        ).to_record()

        self.assertEqual(record["old_value"]["password"], "[REDACTED]")
        self.assertEqual(record["old_value"]["nested"]["api_token"], "[REDACTED]")
        self.assertEqual(record["new_value"]["private_key"], "[REDACTED]")
        self.assertEqual(record["new_value"]["profile"][0]["session_token"], "[REDACTED]")
        self.assertEqual(record["new_value"]["username"], "alice")


if __name__ == "__main__":
    unittest.main()
