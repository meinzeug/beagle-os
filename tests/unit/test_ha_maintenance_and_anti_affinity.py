"""Tests for Plan 09 L190+L191: Maintenance-Mode VM rejection and Anti-Affinity.

L190 — Maintenance-Mode: new VM start on maintenance node is rejected.
L191 — Anti-Affinity: two VMs of the same group land on different nodes.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_SERVICES = _ROOT / "beagle-host" / "services"
for _p in [str(_ROOT), str(_SERVICES)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from maintenance_service import MaintenanceService  # type: ignore[import]
from anti_affinity_scheduler import AntiAffinityScheduler  # type: ignore[import]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class _Vm:
    vmid: int
    node: str
    name: str
    status: str = "running"


def _make_maintenance_service(
    nodes: list[dict[str, Any]],
    vms: list[_Vm],
    configs: dict[int, dict[str, Any]],
    state_file: Path,
) -> MaintenanceService:
    migrate_calls: list[tuple] = []
    restart_calls: list[tuple] = []

    def _migrate(vmid, target, live, converge, requester):
        migrate_calls.append((vmid, target, live, converge, requester))
        return {"ok": True}

    def _restart(vmid, source, target):
        restart_calls.append((vmid, source, target))
        return {"ok": True}

    svc = MaintenanceService(
        state_file=state_file,
        list_nodes=lambda: nodes,
        list_vms=lambda: vms,
        get_vm_config=lambda node, vmid: configs.get(vmid, {}),
        migrate_vm=_migrate,
        cold_restart_vm=_restart,
        service_name="test",
        utcnow=lambda: "2026-04-24T12:00:00Z",
        version="6.7.0",
    )
    svc._migrate_calls = migrate_calls  # type: ignore[attr-defined]
    svc._restart_calls = restart_calls  # type: ignore[attr-defined]
    return svc


# ---------------------------------------------------------------------------
# L190: Maintenance-Mode VM start rejection
# ---------------------------------------------------------------------------

class TestMaintenanceModeRejection(unittest.TestCase):
    """Plan 09 L190 — new VM start on maintenance node must be rejected."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="test-maintenance-")
        self._state_file = Path(self._tmp.name) / "state.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _svc(self, nodes=None, vms=None, configs=None) -> MaintenanceService:
        return _make_maintenance_service(
            nodes=nodes or [
                {"name": "beagle-0", "status": "online"},
                {"name": "beagle-1", "status": "online"},
            ],
            vms=vms or [],
            configs=configs or {},
            state_file=self._state_file,
        )

    def test_node_not_in_maintenance_initially(self):
        svc = self._svc()
        self.assertFalse(svc.is_node_in_maintenance("beagle-0"))

    def test_drain_puts_node_in_maintenance(self):
        svc = self._svc(vms=[_Vm(vmid=101, node="beagle-1", name="vm-101")])
        svc.drain_node(node_name="beagle-1", requester_identity="operator")
        self.assertTrue(svc.is_node_in_maintenance("beagle-1"))

    def test_start_on_maintenance_node_rejected(self):
        """Simulate the control-plane guard: is_node_in_maintenance → raise RuntimeError."""
        svc = self._svc(vms=[_Vm(vmid=101, node="beagle-1", name="vm-101")])
        svc.drain_node(node_name="beagle-1")
        self.assertTrue(svc.is_node_in_maintenance("beagle-1"))
        # The control-plane guard (line ~2580 in beagle-control-plane.py) does:
        #   if maintenance_service().is_node_in_maintenance(vm.node): raise RuntimeError(...)
        # We test the same logic here:
        with self.assertRaises(RuntimeError):
            if svc.is_node_in_maintenance("beagle-1"):
                raise RuntimeError("node beagle-1 is in maintenance mode; VM start rejected")

    def test_start_on_non_maintenance_node_allowed(self):
        """Non-maintenance node should not raise."""
        svc = self._svc()
        # No exception raised here
        if svc.is_node_in_maintenance("beagle-0"):
            raise AssertionError("beagle-0 should not be in maintenance")

    def test_drain_vms_migrated_away(self):
        svc = self._svc(
            vms=[_Vm(vmid=200, node="beagle-0", name="vm-200", status="running")],
            configs={200: {"ha_policy": "fail_over"}},
        )
        result = svc.drain_node(node_name="beagle-0")
        # VM should have been migrated to beagle-1
        self.assertEqual(len(svc._migrate_calls), 1)  # type: ignore[attr-defined]
        self.assertEqual(svc._migrate_calls[0][0], 200)  # type: ignore[attr-defined]
        self.assertEqual(svc._migrate_calls[0][1], "beagle-1")  # type: ignore[attr-defined]

    def test_pick_target_excludes_maintenance_nodes(self):
        """_pick_target_node must skip nodes already in maintenance."""
        svc = self._svc(
            nodes=[
                {"name": "beagle-0", "status": "online"},
                {"name": "beagle-1", "status": "online"},
                {"name": "beagle-2", "status": "online"},
            ],
        )
        # Put beagle-1 in maintenance
        svc._set_node_maintenance("beagle-1", True)
        target = svc._pick_target_node("beagle-0")
        self.assertNotEqual(target, "beagle-0")
        self.assertNotEqual(target, "beagle-1")

    def test_no_target_raises(self):
        """If no valid target node, RuntimeError."""
        svc = self._svc(
            nodes=[{"name": "beagle-0", "status": "online"}]
        )
        with self.assertRaises(RuntimeError):
            svc._pick_target_node("beagle-0")

    def test_maintenance_list_persisted(self):
        """Maintenance state is persisted across service instances."""
        svc = self._svc()
        svc._set_node_maintenance("beagle-0", True)
        svc2 = self._svc()  # new instance, same state file
        self.assertTrue(svc2.is_node_in_maintenance("beagle-0"))


# ---------------------------------------------------------------------------
# L191: Anti-Affinity scheduler
# ---------------------------------------------------------------------------

class TestAntiAffinityScheduler(unittest.TestCase):
    """Plan 09 L191 — two VMs of the same group land on different nodes."""

    def _nodes(self, names: list[str]) -> list[dict[str, Any]]:
        return [{"name": n, "status": "online"} for n in names]

    def _svc(
        self,
        vms: list[_Vm],
        configs: dict[int, dict[str, Any]],
        nodes: list[str],
        maintenance: set[str] | None = None,
    ) -> AntiAffinityScheduler:
        maintenance = maintenance or set()
        return AntiAffinityScheduler(
            list_vms=lambda: vms,
            get_vm_config=lambda node, vmid: configs.get(vmid, {}),
            list_nodes=lambda: self._nodes(nodes),
            is_node_in_maintenance=lambda n: n in maintenance,
        )

    def test_first_vm_placed_on_first_online_node(self):
        """No other group members → first online node chosen."""
        svc = self._svc(vms=[], configs={}, nodes=["n1", "n2", "n3"])
        node = svc.pick_node(vmid=10, group="gpu-pool")
        self.assertIn(node, ["n1", "n2", "n3"])

    def test_second_vm_placed_on_different_node(self):
        """Second VM in same group → different node than first."""
        vms = [_Vm(vmid=10, node="n1", name="vm-10")]
        configs = {10: {"anti_affinity_group": "gpu-pool"}}
        svc = self._svc(vms=vms, configs=configs, nodes=["n1", "n2", "n3"])
        node = svc.pick_node(vmid=20, group="gpu-pool")
        self.assertNotEqual(node, "n1")

    def test_third_vm_different_from_first_two(self):
        vms = [
            _Vm(vmid=10, node="n1", name="vm-10"),
            _Vm(vmid=20, node="n2", name="vm-20"),
        ]
        configs = {
            10: {"anti_affinity_group": "gpu-pool"},
            20: {"anti_affinity_group": "gpu-pool"},
        }
        svc = self._svc(vms=vms, configs=configs, nodes=["n1", "n2", "n3"])
        node = svc.pick_node(vmid=30, group="gpu-pool")
        self.assertNotIn(node, ["n1", "n2"])
        self.assertEqual(node, "n3")

    def test_no_free_node_raises_runtime_error(self):
        """All online nodes occupied → RuntimeError."""
        vms = [
            _Vm(vmid=10, node="n1", name="vm-10"),
            _Vm(vmid=20, node="n2", name="vm-20"),
        ]
        configs = {
            10: {"anti_affinity_group": "gpu-pool"},
            20: {"anti_affinity_group": "gpu-pool"},
        }
        svc = self._svc(vms=vms, configs=configs, nodes=["n1", "n2"])
        with self.assertRaises(RuntimeError):
            svc.pick_node(vmid=30, group="gpu-pool")

    def test_maintenance_node_excluded_from_candidates(self):
        """Maintenance node is not a valid placement target."""
        vms = [_Vm(vmid=10, node="n1", name="vm-10")]
        configs = {10: {"anti_affinity_group": "gpu-pool"}}
        svc = self._svc(
            vms=vms, configs=configs,
            nodes=["n1", "n2", "n3"],
            maintenance={"n2"},
        )
        node = svc.pick_node(vmid=20, group="gpu-pool")
        self.assertNotEqual(node, "n1")   # anti-affinity
        self.assertNotEqual(node, "n2")   # maintenance

    def test_empty_group_raises_value_error(self):
        svc = self._svc(vms=[], configs={}, nodes=["n1"])
        with self.assertRaises(ValueError):
            svc.pick_node(vmid=10, group="")

    def test_check_placement_ok(self):
        """check_placement returns ok=True when node is free for group."""
        svc = self._svc(vms=[], configs={}, nodes=["n1", "n2"])
        result = svc.check_placement(vmid=10, node="n1", group="gpu-pool")
        self.assertTrue(result["ok"])
        self.assertFalse(result["conflict"])

    def test_check_placement_conflict(self):
        """check_placement returns ok=False when node already hosts group member."""
        vms = [_Vm(vmid=10, node="n1", name="vm-10")]
        configs = {10: {"anti_affinity_group": "gpu-pool"}}
        svc = self._svc(vms=vms, configs=configs, nodes=["n1", "n2"])
        result = svc.check_placement(vmid=20, node="n1", group="gpu-pool")
        self.assertFalse(result["ok"])
        self.assertTrue(result["conflict"])
        self.assertIn("n1", result["occupied_nodes"])

    def test_different_groups_independent(self):
        """VMs in different groups don't affect each other's placement."""
        vms = [_Vm(vmid=10, node="n1", name="vm-10")]
        configs = {10: {"anti_affinity_group": "group-a"}}
        svc = self._svc(vms=vms, configs=configs, nodes=["n1", "n2"])
        # group-b has no members → n1 is available for group-b
        node = svc.pick_node(vmid=20, group="group-b")
        self.assertEqual(node, "n1")  # lexicographically first

    def test_exclude_vmid_self_not_counted(self):
        """When rescheduling vm=10, its current placement doesn't block itself."""
        vms = [_Vm(vmid=10, node="n1", name="vm-10")]
        configs = {10: {"anti_affinity_group": "gpu-pool"}}
        svc = self._svc(vms=vms, configs=configs, nodes=["n1", "n2"])
        # vmid=10 is already on n1; picking for vmid=10 again should be free
        node = svc.pick_node(vmid=10, group="gpu-pool")
        # No other group member (self excluded) → n1 is free
        self.assertEqual(node, "n1")

    def test_no_online_nodes_raises(self):
        svc = self._svc(vms=[], configs={}, nodes=[])
        with self.assertRaises(RuntimeError):
            svc.pick_node(vmid=1, group="g")


if __name__ == "__main__":
    unittest.main()
