from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from ca_manager import ClusterCaService
from cluster_membership import ClusterMembershipService


class ClusterMembershipServiceTests(unittest.TestCase):
    def make_service(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        ca_service = ClusterCaService(data_dir=Path(temp_dir.name))
        service = ClusterMembershipService(
            data_dir=Path(temp_dir.name),
            ca_service=ca_service,
            public_manager_url="https://leader.example.test/beagle-api",
            rpc_port=9089,
            utcnow=lambda: "2026-04-23T12:00:00Z",
        )
        return service

    def test_initialize_cluster_creates_local_member_and_ca(self):
        service = self.make_service()

        payload = service.initialize_cluster(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )

        self.assertTrue(payload["cluster"]["cluster_id"])
        self.assertEqual(payload["member"]["name"], "leader-node")
        self.assertTrue(service.is_initialized())
        self.assertEqual(len(service.list_members()), 1)

    def test_create_accept_and_apply_join_roundtrip(self):
        leader = self.make_service()
        leader.initialize_cluster(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )
        token_payload = leader.create_join_token()

        accepted = leader.accept_join_request(
            join_token=token_payload["join_token"],
            node_name="node-b",
            api_url="https://node-b.example.test/beagle-api",
            advertise_host="node-b.example.test",
            rpc_url="https://node-b.example.test:9192/rpc",
        )
        self.assertEqual(accepted["member"]["rpc_url"], "https://node-b.example.test:9192/rpc")

        follower = self.make_service()
        applied = follower.apply_join_response(node_name="node-b", payload=accepted)

        self.assertEqual(applied["member"]["name"], "node-b")
        self.assertEqual(len(applied["members"]), 2)
        local = follower.local_member()
        self.assertIsNotNone(local)
        self.assertEqual(local["name"], "node-b")

    def test_probe_unreachable_marks_member_offline(self):
        service = self.make_service()
        service.initialize_cluster(
            node_name="leader",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )
        # Manually inject an unreachable remote member.
        members = service.list_members()
        members.append({
            "name": "dead-node",
            "api_url": "http://127.0.0.1:19999/api/v1",
            "rpc_url": "https://127.0.0.1:20000/rpc",
            "status": "online",
            "local": False,
        })
        service._write_json(service.members_file(), members)

        service.probe_and_update_member_statuses(timeout=0.5)

        after = {m["name"]: m for m in service.list_members()}
        self.assertEqual(after["dead-node"]["status"], "unreachable")
