import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.virtualization.scheduler_policy import SchedulerPolicy, scheduler_policy_from_payload


class SchedulerPolicyContractTests(unittest.TestCase):
    def test_scheduler_policy_from_payload_parses_groups(self) -> None:
        payload = {
            "affinity_groups": [
                {"group_id": "app-db", "vmids": [101, 102]},
            ],
            "anti_affinity_groups": [
                {"group_id": "replicas", "vmids": [201, 202, 203]},
            ],
        }
        policy = scheduler_policy_from_payload(payload)

        self.assertIsInstance(policy, SchedulerPolicy)
        self.assertEqual(len(policy.affinity_groups), 1)
        self.assertEqual(policy.affinity_groups[0].group_id, "app-db")
        self.assertEqual(policy.affinity_groups[0].vmids, (101, 102))
        self.assertEqual(len(policy.anti_affinity_groups), 1)
        self.assertEqual(policy.anti_affinity_groups[0].group_id, "replicas")
        self.assertEqual(policy.anti_affinity_groups[0].vmids, (201, 202, 203))

    def test_scheduler_policy_ignores_invalid_groups(self) -> None:
        policy = scheduler_policy_from_payload(
            {
                "affinity_groups": [{"group_id": "invalid", "vmids": [100]}],
                "anti_affinity_groups": [{"group_id": "broken", "vmids": ["x", 1]}],
            }
        )
        self.assertEqual(policy.affinity_groups, ())
        self.assertEqual(policy.anti_affinity_groups, ())


if __name__ == "__main__":
    unittest.main()
