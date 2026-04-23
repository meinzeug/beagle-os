import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.virtualization.desktop_pool import (
    DesktopLease,
    DesktopPoolInfo,
    DesktopPoolMode,
    DesktopPoolSpec,
    SessionRecordingPolicy,
)
from core.virtualization.streaming_profile import StreamingProfile


class DesktopPoolContractTests(unittest.TestCase):
    def test_pool_mode_values(self) -> None:
        self.assertEqual(DesktopPoolMode.FLOATING_NON_PERSISTENT.value, "floating_non_persistent")
        self.assertEqual(DesktopPoolMode.FLOATING_PERSISTENT.value, "floating_persistent")
        self.assertEqual(DesktopPoolMode.DEDICATED.value, "dedicated")

    def test_pool_spec_fields(self) -> None:
        spec = DesktopPoolSpec(
            pool_id="pool-ux-1",
            template_id="tmpl-ubuntu-xfce-01",
            mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
            min_pool_size=2,
            max_pool_size=10,
            warm_pool_size=5,
            cpu_cores=4,
            memory_mib=8192,
            storage_pool="local",
            session_recording=SessionRecordingPolicy.ON_DEMAND,
            labels=("xfce", "office"),
            streaming_profile=StreamingProfile(),
        )
        self.assertEqual(spec.pool_id, "pool-ux-1")
        self.assertEqual(spec.template_id, "tmpl-ubuntu-xfce-01")
        self.assertEqual(spec.mode, DesktopPoolMode.FLOATING_NON_PERSISTENT)
        self.assertEqual(spec.min_pool_size, 2)
        self.assertEqual(spec.max_pool_size, 10)
        self.assertEqual(spec.warm_pool_size, 5)
        self.assertEqual(spec.cpu_cores, 4)
        self.assertEqual(spec.memory_mib, 8192)
        self.assertEqual(spec.storage_pool, "local")
        self.assertEqual(spec.labels, ("xfce", "office"))
        self.assertIsNotNone(spec.streaming_profile)
        self.assertTrue(spec.enabled)

    def test_pool_info_and_lease_fields(self) -> None:
        info = DesktopPoolInfo(
            pool_id="pool-ux-1",
            template_id="tmpl-ubuntu-xfce-01",
            mode=DesktopPoolMode.FLOATING_PERSISTENT,
            min_pool_size=2,
            max_pool_size=10,
            warm_pool_size=5,
            gpu_class="",
            session_recording=SessionRecordingPolicy.DISABLED,
            recording_retention_days=30,
            free_desktops=3,
            in_use_desktops=2,
            recycling_desktops=0,
            error_desktops=0,
            streaming_profile=StreamingProfile(resolution="2560x1440", fps=120),
        )
        lease = DesktopLease(
            pool_id="pool-ux-1",
            vmid=210,
            user_id="user-123",
            mode=DesktopPoolMode.FLOATING_PERSISTENT,
            state="in-use",
            assigned_at="2026-04-22T09:00:00Z",
        )
        self.assertEqual(info.mode, DesktopPoolMode.FLOATING_PERSISTENT)
        self.assertEqual(info.recording_retention_days, 30)
        self.assertEqual(info.free_desktops, 3)
        self.assertEqual(info.in_use_desktops, 2)
        self.assertEqual(info.streaming_profile.resolution if info.streaming_profile else "", "2560x1440")
        self.assertEqual(lease.vmid, 210)
        self.assertEqual(lease.user_id, "user-123")
        self.assertEqual(lease.state, "in-use")


if __name__ == "__main__":
    unittest.main()
