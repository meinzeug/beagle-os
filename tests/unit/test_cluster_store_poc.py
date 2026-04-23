import json
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from providers.beagle.cluster import store_poc


class ClusterStorePocTests(unittest.TestCase):
    def test_parse_etcd_endpoint_status_json_normalizes_member_ids(self):
        payload = json.dumps(
            [
                {
                    "Endpoint": "http://127.0.0.1:23791",
                    "Status": {
                        "header": {"member_id": 123},
                        "leader": 456,
                        "raftTerm": 9,
                    },
                },
                {
                    "Endpoint": "http://127.0.0.1:23792",
                    "Status": {
                        "header": {"member_id": "0x1c8"},
                        "leader": "0x1c8",
                        "raftTerm": 9,
                    },
                },
            ]
        )

        statuses = store_poc.parse_etcd_endpoint_status_json(payload)

        self.assertEqual(len(statuses), 2)
        self.assertEqual(statuses[0].member_id, format(123, "x"))
        self.assertEqual(statuses[0].leader_id, format(456, "x"))
        self.assertEqual(statuses[1].member_id, "1c8")
        self.assertEqual(statuses[1].raft_term, 9)

    def test_assert_single_leader_raises_on_split_brain(self):
        statuses = [
            store_poc.EtcdEndpointStatus(
                endpoint="a",
                member_id="0x1",
                leader_id="0x1",
                raft_term=1,
            ),
            store_poc.EtcdEndpointStatus(
                endpoint="b",
                member_id="0x2",
                leader_id="0x2",
                raft_term=1,
            ),
        ]

        with self.assertRaises(RuntimeError):
            store_poc.assert_single_leader(statuses)

    def test_evaluate_sqlite_litestream_returns_recommendation(self):
        result = store_poc.evaluate_sqlite_litestream()
        self.assertEqual(result["mode"], "sqlite_litestream_evaluation")
        self.assertIn("etcd", result["matrix"])
        self.assertIn("sqlite_litestream", result["matrix"])
        self.assertIn("witness", result["recommendation"].lower())


if __name__ == "__main__":
    unittest.main()
