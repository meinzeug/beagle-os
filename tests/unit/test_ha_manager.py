import unittest
from dataclasses import dataclass

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from ha_manager import HaManagerService


@dataclass
class VmItem:
    vmid: int
    node: str
    name: str
    status: str


class HaManagerServiceTests(unittest.TestCase):
    def test_restart_policy_cold_restarts_on_target(self) -> None:
        calls = {"restart": []}
        service = HaManagerService(
            list_nodes=lambda: [{"name": "node-a", "status": "unreachable"}, {"name": "node-b", "status": "online"}],
            list_vms=lambda: [VmItem(vmid=101, node="node-a", name="vm-101", status="stopped")],
            get_vm_config=lambda node, vmid: {"ha_policy": "restart"},
            migrate_vm=lambda vmid, target_node, live, copy_storage, requester_identity: {},
            cold_restart_vm=lambda vmid, source_node, target_node: calls["restart"].append((vmid, source_node, target_node)) or {"ok": True},
            service_name="test",
            utcnow=lambda: "2026-04-23T00:00:00Z",
            version="1",
        )

        payload = service.reconcile_failed_node(failed_node="node-a", requester_identity="tester")

        self.assertEqual(payload["handled_vm_count"], 1)
        self.assertEqual(calls["restart"], [(101, "node-a", "node-b")])
        self.assertEqual(payload["actions"][0]["result"], "cold_restart")

    def test_fail_over_uses_migration_when_possible(self) -> None:
        calls = {"migrate": []}
        service = HaManagerService(
            list_nodes=lambda: [{"name": "node-a", "status": "unreachable"}, {"name": "node-b", "status": "online"}],
            list_vms=lambda: [VmItem(vmid=202, node="node-a", name="vm-202", status="running")],
            get_vm_config=lambda node, vmid: {"ha_policy": "fail_over"},
            migrate_vm=lambda vmid, target_node, live, copy_storage, requester_identity: calls["migrate"].append((vmid, target_node, live, requester_identity)) or {"migration": {"ok": True}},
            cold_restart_vm=lambda vmid, source_node, target_node: {"ok": True},
            service_name="test",
            utcnow=lambda: "2026-04-23T00:00:00Z",
            version="1",
        )

        payload = service.reconcile_failed_node(failed_node="node-a", requester_identity="tester")

        self.assertEqual(payload["handled_vm_count"], 1)
        self.assertEqual(calls["migrate"], [(202, "node-b", True, "tester")])
        self.assertEqual(payload["actions"][0]["result"], "live_migration")

    def test_fail_over_falls_back_to_cold_restart(self) -> None:
        calls = {"restart": []}

        def failing_migrate(vmid, target_node, live, copy_storage, requester_identity):
            raise RuntimeError("migration failed")

        service = HaManagerService(
            list_nodes=lambda: [{"name": "node-a", "status": "unreachable"}, {"name": "node-b", "status": "online"}],
            list_vms=lambda: [VmItem(vmid=303, node="node-a", name="vm-303", status="running")],
            get_vm_config=lambda node, vmid: {"ha_policy": "fail_over"},
            migrate_vm=failing_migrate,
            cold_restart_vm=lambda vmid, source_node, target_node: calls["restart"].append((vmid, source_node, target_node)) or {"ok": True},
            service_name="test",
            utcnow=lambda: "2026-04-23T00:00:00Z",
            version="1",
        )

        payload = service.reconcile_failed_node(failed_node="node-a", requester_identity="tester")

        self.assertEqual(calls["restart"], [(303, "node-a", "node-b")])
        self.assertEqual(payload["actions"][0]["result"], "cold_restart_fallback")


if __name__ == "__main__":
    unittest.main()
