import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from cluster_inventory import ClusterInventoryService


class ClusterInventoryServiceTests(unittest.TestCase):
    def test_build_inventory_aggregates_nodes_and_vm_counts(self):
        service = ClusterInventoryService(
            build_vm_inventory=lambda: {
                "vms": [
                    {"vmid": 100, "node": "node-a", "status": "running"},
                    {"vmid": 101, "node": "node-a", "status": "running"},
                    {"vmid": 102, "node": "node-b", "status": "stopped"},
                ]
            },
            host_provider_kind="beagle",
            list_nodes_inventory=lambda: [
                {"name": "node-a", "status": "online", "cpu": 0.25, "mem": 1024, "maxmem": 4096, "maxcpu": 8},
                {"name": "node-b", "status": "offline", "cpu": 0.0, "mem": 0, "maxmem": 4096, "maxcpu": 8},
            ],
            service_name="beagle-control-plane",
            utcnow=lambda: "2026-04-22T08:00:00Z",
            version="7.0.0-dev",
        )

        payload = service.build_inventory()

        self.assertEqual(payload["provider"], "beagle")
        self.assertEqual(payload["node_count"], 2)
        self.assertEqual(payload["node_online_count"], 1)
        self.assertEqual(payload["node_unreachable_count"], 1)
        self.assertEqual(payload["vm_count"], 3)

        nodes = {item["name"]: item for item in payload["nodes"]}
        self.assertEqual(nodes["node-a"]["vm_count"], 2)
        self.assertEqual(nodes["node-b"]["vm_count"], 1)

    def test_build_inventory_marks_missing_node_as_unreachable(self):
        service = ClusterInventoryService(
            build_vm_inventory=lambda: {
                "vms": [
                    {"vmid": 110, "node": "node-z", "status": "running"},
                ]
            },
            host_provider_kind="beagle",
            list_nodes_inventory=lambda: [],
            service_name="beagle-control-plane",
            utcnow=lambda: "2026-04-22T08:30:00Z",
            version="7.0.0-dev",
        )

        payload = service.build_inventory()

        self.assertEqual(payload["node_count"], 1)
        self.assertEqual(payload["node_unreachable_count"], 1)
        self.assertEqual(payload["nodes"][0]["name"], "node-z")
        self.assertEqual(payload["nodes"][0]["status"], "unreachable")
        self.assertEqual(payload["nodes"][0]["vm_count"], 1)


if __name__ == "__main__":
    unittest.main()
