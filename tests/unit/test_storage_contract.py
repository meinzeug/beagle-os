import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.virtualization.storage import SnapshotSpec, StoragePoolInfo, VolumeSpec


class StorageContractTests(unittest.TestCase):
    def test_volume_spec_fields(self) -> None:
        spec = VolumeSpec(name="vm-101-root", size_gib=32, format="qcow2", pool_name="local")
        self.assertEqual(spec.name, "vm-101-root")
        self.assertEqual(spec.size_gib, 32)
        self.assertEqual(spec.format, "qcow2")
        self.assertEqual(spec.pool_name, "local")
        self.assertEqual(spec.description, "")

    def test_snapshot_spec_fields(self) -> None:
        snap = SnapshotSpec(volume_id="local/vm-101-root.qcow2", name="pre-upgrade", description="before update")
        self.assertEqual(snap.volume_id, "local/vm-101-root.qcow2")
        self.assertEqual(snap.name, "pre-upgrade")
        self.assertEqual(snap.description, "before update")

    def test_storage_pool_info_fields(self) -> None:
        pool = StoragePoolInfo(
            name="local",
            driver="directory",
            path="/var/lib/beagle/images",
            total_bytes=100,
            used_bytes=40,
            available_bytes=60,
            active=True,
            shared=False,
            quota_bytes=80,
        )
        self.assertEqual(pool.name, "local")
        self.assertEqual(pool.driver, "directory")
        self.assertEqual(pool.path, "/var/lib/beagle/images")
        self.assertEqual(pool.total_bytes, 100)
        self.assertEqual(pool.used_bytes, 40)
        self.assertEqual(pool.available_bytes, 60)
        self.assertTrue(pool.active)
        self.assertFalse(pool.shared)
        self.assertEqual(pool.quota_bytes, 80)


if __name__ == "__main__":
    unittest.main()
