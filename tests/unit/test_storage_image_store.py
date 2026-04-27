import tempfile
import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from storage_image_store import StorageImageStoreService


class StorageImageStoreServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._pool_dir = Path(self._tmp.name) / "local"
        self._pool_dir.mkdir(parents=True, exist_ok=True)
        self._inventory = [
            {
                "storage": "local",
                "content": "images,iso,backup",
                "path": str(self._pool_dir),
                "used": 10,
            }
        ]
        self._quota_bytes = 0
        self.service = StorageImageStoreService(
            list_storage_inventory=lambda: list(self._inventory),
            get_pool_quota=lambda _pool: {"quota_bytes": self._quota_bytes},
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_upload_iso_writes_file_and_returns_storage_ref(self) -> None:
        result = self.service.upload_image("local", "ubuntu.iso", b"abc123")
        self.assertEqual(result["storage_ref"], "local:iso/ubuntu.iso")
        self.assertEqual((self._pool_dir / "ubuntu.iso").read_bytes(), b"abc123")

    def test_upload_qcow2_writes_file_and_returns_storage_ref(self) -> None:
        result = self.service.upload_image("local", "vm-100.qcow2", b"diskdata")
        self.assertEqual(result["storage_ref"], "local:images/vm-100.qcow2")
        self.assertEqual((self._pool_dir / "vm-100.qcow2").read_bytes(), b"diskdata")

    def test_upload_rejects_unsupported_extension(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported file type"):
            self.service.upload_image("local", "notes.txt", b"text")

    def test_upload_rejects_overwrite_by_default(self) -> None:
        (self._pool_dir / "ubuntu.iso").write_bytes(b"old")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.service.upload_image("local", "ubuntu.iso", b"new")

    def test_upload_allows_overwrite_when_requested(self) -> None:
        (self._pool_dir / "ubuntu.iso").write_bytes(b"old")
        result = self.service.upload_image("local", "ubuntu.iso", b"new", overwrite=True)
        self.assertTrue(result["overwritten"])
        self.assertEqual((self._pool_dir / "ubuntu.iso").read_bytes(), b"new")

    def test_upload_rejects_when_quota_exceeded(self) -> None:
        self._quota_bytes = 12
        with self.assertRaisesRegex(ValueError, "quota_exceeded"):
            self.service.upload_image("local", "ubuntu.iso", b"1234")


if __name__ == "__main__":
    unittest.main()
