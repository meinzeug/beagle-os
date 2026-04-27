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

    def test_list_images_returns_supported_files_only(self) -> None:
        (self._pool_dir / "ubuntu.iso").write_bytes(b"iso")
        (self._pool_dir / "disk.qcow2").write_bytes(b"disk")
        (self._pool_dir / "notes.txt").write_text("ignore", encoding="utf-8")

        items = self.service.list_images("local")

        self.assertEqual([item["filename"] for item in items], ["disk.qcow2", "ubuntu.iso"])
        self.assertEqual(items[0]["content_kind"], "images")
        self.assertEqual(items[1]["content_kind"], "iso")

    def test_read_image_returns_bytes_and_content_type(self) -> None:
        (self._pool_dir / "ubuntu.iso").write_bytes(b"iso-data")

        result = self.service.read_image("local", "ubuntu.iso")

        self.assertEqual(result["filename"], "ubuntu.iso")
        self.assertEqual(result["content_kind"], "iso")
        self.assertEqual(result["content_type"], "application/x-iso9660-image")
        self.assertEqual(result["payload"], b"iso-data")

    def test_read_image_rejects_missing_file(self) -> None:
        with self.assertRaisesRegex(ValueError, "not found"):
            self.service.read_image("local", "missing.iso")


if __name__ == "__main__":
    unittest.main()
