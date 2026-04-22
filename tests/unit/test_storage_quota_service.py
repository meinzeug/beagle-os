import tempfile
import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from storage_quota import StorageQuotaService


class StorageQuotaServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.service = StorageQuotaService(state_file=Path(self._tmp.name) / "storage-quotas.json")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_storage_quota_roundtrip(self) -> None:
        initial = self.service.get_pool_quota("local")
        self.assertEqual(initial["pool"], "local")
        self.assertEqual(initial["quota_bytes"], 0)

        updated = self.service.set_pool_quota("local", 128 * 1024 * 1024 * 1024)
        self.assertEqual(updated["pool"], "local")
        self.assertEqual(updated["quota_bytes"], 128 * 1024 * 1024 * 1024)

        loaded = self.service.get_pool_quota("local")
        self.assertEqual(loaded["quota_bytes"], 128 * 1024 * 1024 * 1024)

    def test_storage_quota_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            self.service.get_pool_quota("../etc/passwd")
        with self.assertRaises(ValueError):
            self.service.set_pool_quota("local", -1)


if __name__ == "__main__":
    unittest.main()
