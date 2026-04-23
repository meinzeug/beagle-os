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

from ha_watchdog import HaWatchdogService


class HaWatchdogServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ha-watchdog-test-")
        self.state_file = Path(self._tmp.name) / "ha-watchdog-state.json"
        self.now_value = 1_000.0
        self.sent = []
        self.fencing_attempts = []

        def run_fencing(node: str, method: str) -> bool:
            self.fencing_attempts.append((node, method))
            return method == "vm_forcestop"

        self.service = HaWatchdogService(
            state_file=self.state_file,
            node_name="node-a",
            list_nodes=lambda: [{"name": "node-a"}, {"name": "node-b"}, {"name": "node-c"}],
            send_heartbeat=lambda target, payload: self.sent.append((target, payload)),
            run_fencing_action=run_fencing,
            utcnow=lambda: "2026-04-23T10:00:00Z",
            now=lambda: self.now_value,
            heartbeat_interval_seconds=2.0,
            missed_heartbeats_before_fencing=3,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_send_heartbeats_targets_remote_nodes(self) -> None:
        result = self.service.send_heartbeats()

        self.assertEqual(result["target_count"], 2)
        self.assertEqual({target for target, _ in self.sent}, {"node-b", "node-c"})
        self.assertTrue(all(payload["kind"] == "ha_heartbeat" for _, payload in self.sent))

    def test_timeout_triggers_fencing_with_priority(self) -> None:
        self.service.record_heartbeat("node-b", received_at=1_000.0)
        self.now_value = 1_007.0

        result = self.service.evaluate_timeouts()

        self.assertEqual(len(result["fenced_nodes"]), 1)
        self.assertEqual(result["fenced_nodes"][0]["node"], "node-b")
        self.assertTrue(result["fenced_nodes"][0]["fenced"])
        self.assertEqual(result["fenced_nodes"][0]["method"], "vm_forcestop")
        self.assertEqual(
            self.fencing_attempts,
            [
                ("node-b", "ipmi_reset"),
                ("node-b", "watchdog_timer"),
                ("node-b", "vm_forcestop"),
            ],
        )

    def test_recent_heartbeat_does_not_fence(self) -> None:
        self.service.record_heartbeat("node-b", received_at=1_000.0)
        self.now_value = 1_004.0

        result = self.service.evaluate_timeouts()

        self.assertEqual(result["fenced_nodes"], [])
        self.assertEqual(self.fencing_attempts, [])


if __name__ == "__main__":
    unittest.main()
