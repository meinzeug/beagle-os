from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from installer_log_service import InstallerLogService


class InstallerLogServiceTests(unittest.TestCase):
    def test_scoped_token_accepts_event_and_redacts_sensitive_details(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = InstallerLogService(
                log_dir=Path(temp_dir) / "installer-logs",
                signing_secret="test-secret",
                token_ttl_seconds=3600,
                utcnow=lambda: "2026-04-27T10:00:00+00:00",
            )
            context = service.issue_log_context(
                vmid=100,
                node="srv1",
                script_kind="linux-installer-usb",
                script_name="installer.sh",
            )

            response = service.submit_event(
                payload={
                    "event": "script_started",
                    "stage": "init",
                    "status": "ok",
                    "message": "started",
                    "details": {"token": "must-not-leak", "device": "/dev/sdb"},
                },
                authorization_header=f"Bearer {context['token']}",
                remote_addr="192.0.2.10",
                user_agent="curl/8",
            )

            self.assertEqual(int(response["status"]), 202)
            self.assertTrue(response["payload"]["ok"])

            session_response = service.route_get(f"/api/v1/installer-logs/{context['session_id']}")
            self.assertEqual(int(session_response["status"]), 200)
            events = session_response["payload"]["events"]
            self.assertEqual(events[0]["event"], "script_started")
            self.assertEqual(events[0]["details"]["token"], "[redacted]")
            self.assertEqual(events[0]["details"]["device"], "/dev/sdb")

            summary_file = Path(temp_dir) / "installer-logs" / "sessions.json"
            summaries = json.loads(summary_file.read_text(encoding="utf-8"))["sessions"]
            self.assertEqual(summaries[0]["vmid"], 100)
            self.assertEqual(summaries[0]["last_event"], "script_started")

    def test_missing_bearer_token_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = InstallerLogService(
                log_dir=Path(temp_dir) / "installer-logs",
                signing_secret="test-secret",
                token_ttl_seconds=3600,
                utcnow=lambda: "2026-04-27T10:00:00+00:00",
            )
            response = service.submit_event(
                payload={"event": "script_started"},
                authorization_header="",
                remote_addr="",
                user_agent="",
            )
            self.assertEqual(int(response["status"]), 401)


if __name__ == "__main__":
    unittest.main()
