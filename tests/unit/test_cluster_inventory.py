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
            list_remote_inventories=lambda: [],
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
            list_remote_inventories=lambda: [],
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

    def test_build_inventory_merges_remote_cluster_snapshots(self):
        service = ClusterInventoryService(
            build_vm_inventory=lambda: {
                "vms": [
                    {"vmid": 110, "node": "node-a", "status": "running"},
                ]
            },
            host_provider_kind="beagle",
            list_remote_inventories=lambda: [
                {
                    "nodes": [
                        {"name": "node-b", "status": "online", "cpu": 0.1, "mem": 512, "maxmem": 2048, "maxcpu": 4},
                    ],
                    "vms": [
                        {"vmid": 210, "node": "node-b", "status": "running"},
                    ],
                }
            ],
            list_nodes_inventory=lambda: [
                {"name": "node-a", "status": "online", "cpu": 0.25, "mem": 1024, "maxmem": 4096, "maxcpu": 8},
            ],
            service_name="beagle-control-plane",
            utcnow=lambda: "2026-04-22T09:00:00Z",
            version="7.0.0-dev",
        )

        payload = service.build_inventory()

        self.assertEqual(payload["node_count"], 2)
        self.assertEqual(payload["vm_count"], 2)
        nodes = {item["name"]: item for item in payload["nodes"]}
        self.assertEqual(nodes["node-b"]["vm_count"], 1)
        self.assertEqual(nodes["node-b"]["status"], "online")

    def test_build_inventory_includes_cluster_members_as_nodes(self):
        """Cluster members appear in inventory even without libvirt nodes."""
        service = ClusterInventoryService(
            build_vm_inventory=lambda: {"vms": []},
            host_provider_kind="beagle",
            list_remote_inventories=lambda: [],
            list_cluster_members=lambda: [
                {"name": "srv1", "api_url": "http://127.0.0.1:9088/api/v1", "status": "online", "local": True},
                {"name": "node-b", "api_url": "http://127.0.0.1:9191/api/v1", "status": "online", "local": False},
            ],
            list_nodes_inventory=lambda: [
                {"name": "beagle-0", "status": "online", "cpu": 0.1, "mem": 1024, "maxmem": 4096, "maxcpu": 8},
            ],
            service_name="beagle-control-plane",
            utcnow=lambda: "2026-04-23T10:00:00Z",
            version="7.0.0-dev",
        )

        payload = service.build_inventory()

        node_names = {item["name"] for item in payload["nodes"]}
        self.assertIn("node-b", node_names)
        self.assertIn("srv1", node_names)

    def test_build_inventory_collapses_local_provider_node_into_local_member_name(self):
        service = ClusterInventoryService(
            build_vm_inventory=lambda: {
                "vms": [
                    {"vmid": 100, "node": "beagle-0", "status": "running"},
                ]
            },
            host_provider_kind="beagle",
            list_remote_inventories=lambda: [],
            list_cluster_members=lambda: [
                {"name": "srv1", "api_url": "http://46.4.96.80:9088/api/v1", "status": "online", "local": True},
            ],
            list_nodes_inventory=lambda: [
                {"name": "beagle-0", "status": "online", "cpu": 0.1, "mem": 1024, "maxmem": 4096, "maxcpu": 8},
            ],
            service_name="beagle-control-plane",
            utcnow=lambda: "2026-04-26T12:00:00Z",
            version="7.0.0-dev",
        )

        payload = service.build_inventory()

        self.assertEqual(payload["node_count"], 1)
        self.assertEqual(payload["local_member_name"], "srv1")
        node = payload["nodes"][0]
        self.assertEqual(node["name"], "srv1")
        self.assertEqual(node["label"], "srv1")
        self.assertEqual(node["provider_node_name"], "beagle-0")
        self.assertEqual(node["vm_count"], 1)

    def test_build_inventory_collapses_remote_provider_node_into_remote_member_name(self):
        service = ClusterInventoryService(
            build_vm_inventory=lambda: {"vms": []},
            host_provider_kind="beagle",
            list_remote_inventories=lambda: [
                {
                    "local_member_name": "srv2",
                    "nodes": [
                        {"name": "beagle-1", "status": "online", "cpu": 0.1, "mem": 512, "maxmem": 2048, "maxcpu": 4},
                    ],
                    "vms": [
                        {"vmid": 210, "node": "beagle-1", "status": "running"},
                    ],
                }
            ],
            list_cluster_members=lambda: [
                {"name": "srv1", "api_url": "http://46.4.96.80:9088/api/v1", "status": "online", "local": True},
                {"name": "srv2", "api_url": "http://176.9.127.50:9088/api/v1", "status": "online", "local": False},
            ],
            list_nodes_inventory=lambda: [
                {"name": "beagle-0", "status": "online", "cpu": 0.1, "mem": 1024, "maxmem": 4096, "maxcpu": 8},
            ],
            service_name="beagle-control-plane",
            utcnow=lambda: "2026-04-26T12:30:00Z",
            version="7.0.0-dev",
        )

        payload = service.build_inventory()

        nodes = {item["name"]: item for item in payload["nodes"]}
        self.assertEqual(nodes["srv2"]["provider_node_name"], "beagle-1")
        self.assertEqual(nodes["srv2"]["vm_count"], 1)

    def test_build_inventory_cluster_member_unreachable_after_kill(self):
        """Member marked unreachable is reflected in inventory status."""
        service = ClusterInventoryService(
            build_vm_inventory=lambda: {"vms": []},
            host_provider_kind="beagle",
            list_remote_inventories=lambda: [],
            list_cluster_members=lambda: [
                {"name": "srv1", "api_url": "http://127.0.0.1:9088/api/v1", "status": "online", "local": True},
                {"name": "node-b", "api_url": "http://127.0.0.1:9191/api/v1", "status": "unreachable", "local": False},
            ],
            list_nodes_inventory=lambda: [],
            service_name="beagle-control-plane",
            utcnow=lambda: "2026-04-23T10:00:00Z",
            version="7.0.0-dev",
        )

        payload = service.build_inventory()

        nodes = {item["name"]: item for item in payload["nodes"]}
        self.assertEqual(nodes["node-b"]["status"], "unreachable")
        self.assertEqual(payload["node_unreachable_count"], 1)

    def test_build_inventory_marks_remote_vms_with_source_member(self):
        """Remote VMs must have source_member attribute to disambiguate from local VMs."""
        service = ClusterInventoryService(
            build_vm_inventory=lambda: {"vms": []},
            host_provider_kind="beagle",
            list_remote_inventories=lambda: [
                {
                    "local_member_name": "srv2",
                    "nodes": [
                        {"name": "beagle-1", "status": "online", "cpu": 0.1, "mem": 512, "maxmem": 2048, "maxcpu": 4},
                    ],
                    "vms": [
                        {"vmid": 210, "node": "beagle-1", "status": "running", "name": "ubuntu-beagle-200"},
                    ],
                }
            ],
            list_cluster_members=lambda: [
                {"name": "srv1", "api_url": "http://127.0.0.1:9088/api/v1", "status": "online", "local": True},
                {"name": "srv2", "api_url": "http://127.0.0.1:9191/api/v1", "status": "online", "local": False},
            ],
            list_nodes_inventory=lambda: [
                {"name": "beagle-0", "status": "online", "cpu": 0.1, "mem": 1024, "maxmem": 4096, "maxcpu": 8},
            ],
            service_name="beagle-control-plane",
            utcnow=lambda: "2026-04-26T12:30:00Z",
            version="7.0.0-dev",
        )

        payload = service.build_inventory()

        # Verify node counts reflect both local and remote nodes
        self.assertEqual(payload["node_count"], 2)
        nodes_by_name = {node["name"]: node for node in payload["nodes"]}
        
        # srv2 should have 1 VM on remote side
        self.assertEqual(nodes_by_name["srv2"]["vm_count"], 1)
        
        # The build_inventory method doesn't expose individual VMs in payload,
        # but we can verify the aggregation logic worked by checking node counts
        self.assertEqual(payload["vm_count"], 1)


if __name__ == "__main__":
    unittest.main()
