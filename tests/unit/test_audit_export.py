import json
import tempfile
import unittest

import sys
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from audit_export import AuditExportConfig, AuditExportService


class _FakeResponse:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class AuditExportServiceTests(unittest.TestCase):
    def test_webhook_export_sends_signed_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            captured = {}

            def fake_urlopen(req, timeout=0):
                captured["url"] = req.full_url
                captured["data"] = req.data
                captured["headers"] = dict(req.header_items())
                captured["timeout"] = timeout
                return _FakeResponse(200)

            service = AuditExportService(
                config=AuditExportConfig(
                    webhook_url="http://127.0.0.1:18080/audit",
                    webhook_secret="top-secret",
                ),
                data_dir=Path(tmpdir),
                now_utc=lambda: "2026-04-21T10:00:00Z",
            )

            with patch("audit_export.urllib_request.urlopen", side_effect=fake_urlopen):
                service.export_event({"id": "evt-1", "timestamp": "2026-04-21T10:00:00Z", "action": "vm.start"})

            self.assertEqual(captured["url"], "http://127.0.0.1:18080/audit")
            self.assertIn("X-beagle-signature", captured["headers"])
            self.assertEqual(captured["timeout"], 5.0)
            payload = json.loads(captured["data"].decode("utf-8"))
            self.assertEqual(payload["id"], "evt-1")

    def test_failed_webhook_is_buffered_in_failure_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AuditExportService(
                config=AuditExportConfig(
                    webhook_url="http://127.0.0.1:1/audit",
                    webhook_secret="",
                ),
                data_dir=Path(tmpdir),
                now_utc=lambda: "2026-04-21T11:00:00Z",
            )

            with patch("audit_export.urllib_request.urlopen", side_effect=RuntimeError("connection refused")):
                service.export_event({"id": "evt-2", "timestamp": "2026-04-21T11:00:00Z", "action": "vm.stop"})

            failure_log = Path(tmpdir) / "audit" / "export-failures.log"
            self.assertTrue(failure_log.exists())
            lines = failure_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["target"], "webhook")
            self.assertEqual(entry["event_id"], "evt-2")

    def test_failure_log_redacts_sensitive_payload_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AuditExportService(
                config=AuditExportConfig(webhook_url="http://127.0.0.1:1/audit"),
                data_dir=Path(tmpdir),
                now_utc=lambda: "2026-04-21T11:00:00Z",
            )

            with patch("audit_export.urllib_request.urlopen", side_effect=RuntimeError("connection refused")):
                service.export_event(
                    {
                        "id": "evt-3",
                        "action": "auth.user.update",
                        "new_value": {"password": "plain", "role": "viewer"},
                    }
                )

            entry = json.loads((Path(tmpdir) / "audit" / "export-failures.log").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(entry["payload"]["new_value"]["password"], "[REDACTED]")
            self.assertEqual(entry["payload"]["new_value"]["role"], "viewer")

    def test_targets_status_includes_last_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = AuditExportService(
                config=AuditExportConfig(webhook_url="http://127.0.0.1:1/audit"),
                data_dir=Path(tmpdir),
                now_utc=lambda: "2026-04-21T11:00:00Z",
            )

            with patch("audit_export.urllib_request.urlopen", side_effect=RuntimeError("connection refused")):
                service.export_event({"id": "evt-4", "action": "vm.stop"})

            webhook = [item for item in service.get_targets_status() if item["type"] == "webhook"][0]
            self.assertEqual(webhook["last_error"], "connection refused")


if __name__ == "__main__":
    unittest.main()
