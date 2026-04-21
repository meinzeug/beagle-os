import unittest

import sys
from pathlib import Path
from http import HTTPStatus

SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from audit_helpers import build_vm_power_audit_event


class AuditHelpersTests(unittest.TestCase):
    def test_build_vm_power_audit_event_for_start(self):
        response = {
            "status": HTTPStatus.OK,
            "payload": {
                "ok": True,
                "vm_power": {
                    "vmid": 301,
                    "node": "srv1",
                    "action": "start",
                },
            },
        }

        event = build_vm_power_audit_event(response, requester_identity="admin")

        self.assertIsNotNone(event)
        self.assertEqual(event["event_type"], "vm.start")
        self.assertEqual(event["outcome"], "success")
        self.assertEqual(event["details"]["vmid"], 301)
        self.assertEqual(event["details"]["resource_type"], "vm")
        self.assertEqual(event["details"]["resource_id"], 301)

    def test_build_vm_power_audit_event_for_stop_error(self):
        response = {
            "status": HTTPStatus.BAD_GATEWAY,
            "payload": {
                "ok": False,
                "vm_power": {
                    "vmid": "302",
                    "node": "srv1",
                    "action": "stop",
                },
            },
        }

        event = build_vm_power_audit_event(response, requester_identity="ops")

        self.assertIsNotNone(event)
        self.assertEqual(event["event_type"], "vm.stop")
        self.assertEqual(event["outcome"], "error")
        self.assertEqual(event["details"]["vmid"], 302)
        self.assertEqual(event["details"]["username"], "ops")

    def test_build_vm_power_audit_event_ignores_non_power_payloads(self):
        response = {
            "status": HTTPStatus.OK,
            "payload": {
                "ok": True,
            },
        }

        event = build_vm_power_audit_event(response, requester_identity="admin")

        self.assertIsNone(event)


if __name__ == "__main__":
    unittest.main()
