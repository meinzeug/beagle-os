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
from audit_report_http_surface import AuditReportHttpSurfaceService


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

    def test_http_surface_routes_export_target_test_and_replay(self):
        class ExportStub:
            def test_target(self, target):
                return {"target": target, "event_id": "evt-test"}

            def replay_failures(self, *, limit=100):
                return {"replayed": 1, "skipped": 0, "errors": []}

        surface = AuditReportHttpSurfaceService(
            audit_report_service=object(),
            audit_export_service=ExportStub(),
            audit_event=lambda *args, **kwargs: None,
            requester_identity=lambda: "admin",
            accept_header=lambda: "application/json",
        )

        test_response = surface.route_post("/api/v1/audit/export-targets/webhook/test")
        replay_response = surface.route_post("/api/v1/audit/failures/replay", {"limit": 5})

        self.assertEqual(int(test_response["status"]), 200)
        self.assertEqual(test_response["payload"]["target"], "webhook")
        self.assertEqual(int(replay_response["status"]), 200)
        self.assertEqual(replay_response["payload"]["replayed"], 1)

    def test_http_surface_instance_handles_post_does_not_match_auth_login(self):
        surface = AuditReportHttpSurfaceService(
            audit_report_service=object(),
            audit_export_service=object(),
            audit_event=lambda *args, **kwargs: None,
            requester_identity=lambda: "admin",
            accept_header=lambda: "application/json",
        )

        self.assertTrue(surface.handles_post("/api/v1/audit/failures/replay"))
        self.assertFalse(surface.handles_post("/api/v1/auth/login"))


if __name__ == "__main__":
    unittest.main()
