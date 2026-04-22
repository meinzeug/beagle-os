import tempfile
import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from core.virtualization.desktop_pool import DesktopPoolMode, DesktopPoolSpec
from pool_manager import PoolManagerService


class PoolManagerServiceTests(unittest.TestCase):
    def _build_service(self) -> PoolManagerService:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        state_file = Path(temp_dir.name) / "desktop-pools.json"
        return PoolManagerService(state_file=state_file, utcnow=lambda: "2026-04-22T12:00:00Z")

    def test_create_pool_and_list(self) -> None:
        service = self._build_service()
        info = service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-a",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=2,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
            )
        )
        self.assertEqual(info.pool_id, "pool-a")
        self.assertEqual(len(service.list_pools()), 1)

    def test_allocate_release_recycle_non_persistent(self) -> None:
        service = self._build_service()
        service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-a",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=1,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
            )
        )
        service.register_vm("pool-a", 101)
        lease = service.allocate_desktop("pool-a", "alice")
        self.assertEqual(lease.vmid, 101)
        self.assertEqual(lease.state, "in_use")

        released = service.release_desktop("pool-a", 101, "alice")
        self.assertEqual(released.state, "recycling")

        recycled = service.recycle_desktop("pool-a", 101)
        self.assertEqual(recycled.state, "free")
        self.assertEqual(recycled.user_id, "")

    def test_persistent_mode_reuses_same_vm(self) -> None:
        service = self._build_service()
        service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-p",
                template_id="tpl-1",
                mode=DesktopPoolMode.FLOATING_PERSISTENT,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=1,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
            )
        )
        service.register_vm("pool-p", 201)
        lease1 = service.allocate_desktop("pool-p", "alice")
        self.assertEqual(lease1.vmid, 201)
        released = service.release_desktop("pool-p", 201, "alice")
        self.assertEqual(released.state, "free")
        lease2 = service.allocate_desktop("pool-p", "alice")
        self.assertEqual(lease2.vmid, 201)

    def test_dedicated_mode_keeps_assignment(self) -> None:
        service = self._build_service()
        service.create_pool(
            DesktopPoolSpec(
                pool_id="pool-d",
                template_id="tpl-1",
                mode=DesktopPoolMode.DEDICATED,
                min_pool_size=1,
                max_pool_size=5,
                warm_pool_size=1,
                cpu_cores=2,
                memory_mib=4096,
                storage_pool="local",
            )
        )
        service.register_vm("pool-d", 301)
        lease1 = service.allocate_desktop("pool-d", "alice")
        self.assertEqual(lease1.vmid, 301)
        service.release_desktop("pool-d", 301, "alice")
        lease2 = service.allocate_desktop("pool-d", "alice")
        self.assertEqual(lease2.vmid, 301)


if __name__ == "__main__":
    unittest.main()
