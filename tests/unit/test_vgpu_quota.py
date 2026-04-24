"""Plan 12 L91: vGPU quota test — 4 VMs each get 1 vGPU, 5th stays pending-gpu.

This test validates the pool manager GPU quota enforcement for vGPU slots.
With 4 available mdev slots (nvidia-grid-p40-8q) and 5 VMs registered:
- VMs 1-4 each get state=free with a reserved GPU slot
- VM 5 gets state=pending-gpu (no slot available)
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SERVICES = _ROOT / "beagle-host" / "services"
for _p in [str(_ROOT), str(_SERVICES)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pool_manager import DesktopPoolMode, DesktopPoolSpec, PoolManagerService  # type: ignore[import]


def _make_service(state_file: Path, gpu_slots: list[str]) -> PoolManagerService:
    """Build PoolManagerService with configurable number of GPU slots on node-a."""
    nodes = [{"name": "node-a", "status": "online"}]

    # Each slot is a distinct PCI address representing a vGPU mdev slot
    gpu_inventory = [
        {
            "node": "node-a",
            "pci_address": slot,
            "vendor": "nvidia",
            "model": "NVIDIA P40",
            "status": "available-for-passthrough",
        }
        for slot in gpu_slots
    ]

    return PoolManagerService(
        state_file=state_file,
        list_nodes=lambda: nodes,
        list_gpu_inventory=lambda: gpu_inventory,
        utcnow=lambda: "2026-04-24T12:00:00Z",
    )


class TestVgpuQuota4SlotsAnd5VMs(unittest.TestCase):
    """Plan 12 L91 — 4 vGPU slots, 5 VMs: first 4 get slot, 5th goes to pending-gpu."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="test-vgpu-quota-")
        self._state_file = Path(self._tmp.name) / "state.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _pool_with_4_slots(self) -> PoolManagerService:
        slots = [
            "0000:01:00.0",
            "0000:01:01.0",
            "0000:01:02.0",
            "0000:01:03.0",
        ]
        svc = _make_service(self._state_file, slots)
        svc.create_pool(
            DesktopPoolSpec(
                pool_id="vgpu-pool",
                template_id="tpl-vgpu",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=10,
                warm_pool_size=4,
                cpu_cores=4,
                memory_mib=8192,
                storage_pool="local",
                gpu_class="passthrough-nvidia-p40",
            )
        )
        return svc

    def test_first_four_vms_each_get_a_gpu_slot(self):
        """VMs 1-4 are registered with state=free, each assigned a unique GPU slot."""
        svc = self._pool_with_4_slots()
        results = [svc.register_vm("vgpu-pool", vmid) for vmid in [101, 102, 103, 104]]
        for i, result in enumerate(results):
            with self.subTest(vmid=101 + i):
                self.assertEqual(result["state"], "free",
                    f"VM {101+i} expected state=free, got {result['state']}")

    def test_fifth_vm_stays_pending_gpu(self):
        """5th VM has no GPU slot → state=pending-gpu, node=''."""
        svc = self._pool_with_4_slots()
        for vmid in [101, 102, 103, 104]:
            svc.register_vm("vgpu-pool", vmid)
        fifth = svc.register_vm("vgpu-pool", 105)
        self.assertEqual(fifth["state"], "pending-gpu")
        self.assertEqual(fifth["node"], "")

    def test_each_vm_gets_unique_slot(self):
        """Each of the 4 VMs reserves a distinct GPU slot (no double-booking)."""
        svc = self._pool_with_4_slots()
        state = None
        for vmid in [101, 102, 103, 104]:
            svc.register_vm("vgpu-pool", vmid)
        # Read the internal state to inspect reservations
        state_data = svc._load()
        reservations = state_data.get("gpu_reservations", {})
        slots_reserved = [r["slot"] for r in reservations.values()]
        self.assertEqual(len(slots_reserved), len(set(slots_reserved)),
            f"Duplicate GPU slots found: {slots_reserved}")

    def test_exactly_four_reservations_after_4_vms(self):
        """After 4 VMs registered, exactly 4 GPU reservations exist."""
        svc = self._pool_with_4_slots()
        for vmid in [101, 102, 103, 104]:
            svc.register_vm("vgpu-pool", vmid)
        state_data = svc._load()
        reservations = state_data.get("gpu_reservations", {})
        self.assertEqual(len(reservations), 4)

    def test_no_reservation_for_pending_vm(self):
        """5th VM (pending-gpu) must not have a GPU reservation."""
        svc = self._pool_with_4_slots()
        for vmid in [101, 102, 103, 104]:
            svc.register_vm("vgpu-pool", vmid)
        svc.register_vm("vgpu-pool", 105)
        state_data = svc._load()
        reservations = state_data.get("gpu_reservations", {})
        self.assertNotIn("105", reservations,
            "pending-gpu VM should not have a GPU reservation")

    def test_single_slot_only_one_vm_gets_gpu(self):
        """Sanity: with 1 slot, only 1st VM gets free, 2nd is pending-gpu."""
        svc = _make_service(self._state_file, ["0000:02:00.0"])
        svc.create_pool(
            DesktopPoolSpec(
                pool_id="vgpu-single",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=1,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
                gpu_class="passthrough-nvidia-p40",
            )
        )
        first = svc.register_vm("vgpu-single", 201)
        second = svc.register_vm("vgpu-single", 202)
        self.assertEqual(first["state"], "free")
        self.assertEqual(second["state"], "pending-gpu")

    def test_no_slots_all_vms_pending(self):
        """With 0 slots, every VM goes to pending-gpu."""
        svc = _make_service(self._state_file, [])
        svc.create_pool(
            DesktopPoolSpec(
                pool_id="vgpu-empty",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=1,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
                gpu_class="passthrough-nvidia-p40",
            )
        )
        for vmid in [301, 302, 303]:
            result = svc.register_vm("vgpu-empty", vmid)
            self.assertEqual(result["state"], "pending-gpu")


if __name__ == "__main__":
    unittest.main()
