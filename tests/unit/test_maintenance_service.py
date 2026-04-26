import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from maintenance_service import MaintenanceService


@dataclass
class VmItem:
    vmid: int
    node: str
    name: str
    status: str


class MaintenanceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="maintenance-service-test-")
        self.state_file = Path(self._tmp.name) / "maintenance-state.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_drain_moves_vms_by_policy(self) -> None:
        calls = {"migrate": [], "restart": []}

        service = MaintenanceService(
            state_file=self.state_file,
            list_nodes=lambda: [
                {"name": "node-a", "status": "online"},
                {"name": "node-b", "status": "online"},
            ],
            list_vms=lambda: [
                VmItem(vmid=101, node="node-a", name="vm-r", status="stopped"),
                VmItem(vmid=102, node="node-a", name="vm-f", status="running"),
                VmItem(vmid=103, node="node-a", name="vm-d", status="running"),
            ],
            get_vm_config=lambda node, vmid: {
                101: {"ha_policy": "restart"},
                102: {"ha_policy": "fail_over"},
                103: {"ha_policy": "disabled"},
            }[vmid],
            migrate_vm=lambda vmid, target_node, live, copy_storage, requester_identity: calls["migrate"].append((vmid, target_node, live)) or {"ok": True},
            cold_restart_vm=lambda vmid, source_node, target_node: calls["restart"].append((vmid, source_node, target_node)) or {"ok": True},
            service_name="test",
            utcnow=lambda: "2026-04-23T00:00:00Z",
            version="1",
        )

        payload = service.drain_node(node_name="node-a", requester_identity="tester")

        self.assertTrue(service.is_node_in_maintenance("node-a"))
        self.assertEqual(payload["handled_vm_count"], 2)
        self.assertEqual(calls["restart"], [(101, "node-a", "node-b")])
        self.assertEqual(calls["migrate"], [(102, "node-b", True)])

    def test_drain_requires_known_node(self) -> None:
        service = MaintenanceService(
            state_file=self.state_file,
            list_nodes=lambda: [{"name": "node-a", "status": "online"}],
            list_vms=lambda: [],
            get_vm_config=lambda node, vmid: {},
            migrate_vm=lambda vmid, target_node, live, copy_storage, requester_identity: {},
            cold_restart_vm=lambda vmid, source_node, target_node: {},
            service_name="test",
            utcnow=lambda: "2026-04-23T00:00:00Z",
            version="1",
        )

        with self.assertRaises(RuntimeError):
            service.drain_node(node_name="node-missing", requester_identity="tester")

    def test_preview_does_not_enable_maintenance(self) -> None:
        service = MaintenanceService(
            state_file=self.state_file,
            list_nodes=lambda: [
                {"name": "node-a", "status": "online"},
                {"name": "node-b", "status": "online"},
            ],
            list_vms=lambda: [
                VmItem(vmid=201, node="node-a", name="vm-preview", status="running"),
            ],
            get_vm_config=lambda node, vmid: {"ha_policy": "fail_over"},
            migrate_vm=lambda vmid, target_node, live, copy_storage, requester_identity: {"ok": True},
            cold_restart_vm=lambda vmid, source_node, target_node: {"ok": True},
            service_name="test",
            utcnow=lambda: "2026-04-23T00:00:00Z",
            version="1",
        )

        payload = service.preview_drain_node(node_name="node-a")

        self.assertEqual(payload["node_name"], "node-a")
        self.assertEqual(payload["evaluated_vm_count"], 1)
        self.assertFalse(service.is_node_in_maintenance("node-a"))


if __name__ == "__main__":
    unittest.main()
