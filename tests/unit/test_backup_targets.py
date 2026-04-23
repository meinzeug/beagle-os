"""Unit tests for BackupTarget protocol implementations."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.backup_targets.local import LocalBackupTarget
from core.backup_targets.nfs import NfsBackupTarget


class LocalBackupTargetTests(unittest.TestCase):
    def test_write_and_read_chunk(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = LocalBackupTarget(base_path=tmp)
            data = b"hello backup"
            target.write_chunk("test-chunk.tar.gz", data)
            result = target.read_chunk("test-chunk.tar.gz")
            self.assertEqual(result, data)

    def test_list_snapshots_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = LocalBackupTarget(base_path=tmp)
            snaps = target.list_snapshots()
            self.assertEqual(snaps, [])

    def test_list_snapshots_with_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = LocalBackupTarget(base_path=tmp)
            target.write_chunk("beagle-backup-vm-101-2026.tar.gz", b"x")
            target.write_chunk("other-file.txt", b"y")
            snaps = target.list_snapshots(prefix="beagle-backup-vm-101")
            self.assertEqual(len(snaps), 1)
            self.assertEqual(snaps[0]["snapshot_id"], "beagle-backup-vm-101-2026.tar.gz")

    def test_delete_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = LocalBackupTarget(base_path=tmp)
            target.write_chunk("to-delete.tar.gz", b"data")
            target.delete_snapshot("to-delete.tar.gz")
            self.assertEqual(target.list_snapshots(), [])

    def test_read_missing_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = LocalBackupTarget(base_path=tmp)
            with self.assertRaises(FileNotFoundError):
                target.read_chunk("nonexistent.tar.gz")

    def test_invalid_chunk_id_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = LocalBackupTarget(base_path=tmp)
            with self.assertRaises(ValueError):
                target.write_chunk("", b"data")
            with self.assertRaises(ValueError):
                target.write_chunk("../../etc/passwd", b"bad")


class NfsBackupTargetTests(unittest.TestCase):
    def test_missing_mount_raises(self):
        target = NfsBackupTarget(mount_point="/nonexistent/mount/point-abc")
        with self.assertRaises(RuntimeError):
            target.write_chunk("test.tar.gz", b"data")

    def test_relative_mount_raises(self):
        with self.assertRaises(ValueError):
            NfsBackupTarget(mount_point="relative/path")

    def test_dotdot_mount_raises(self):
        with self.assertRaises(ValueError):
            NfsBackupTarget(mount_point="/valid/../path")

    def test_delegates_to_local_when_mounted(self):
        # Use a temp dir as the "mount point" for testing
        with tempfile.TemporaryDirectory() as tmp:
            target = NfsBackupTarget(mount_point=tmp)
            target.write_chunk("nfs-chunk.tar.gz", b"nfs data")
            data = target.read_chunk("nfs-chunk.tar.gz")
            self.assertEqual(data, b"nfs data")


class S3BackupTargetImportTest(unittest.TestCase):
    def test_import_without_boto3_raises(self):
        """S3BackupTarget must raise ImportError when boto3 is not installed."""
        import importlib
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "boto3":
                raise ImportError("boto3 not installed")
            return original_import(name, *args, **kwargs)

        builtins.__import__ = mock_import
        try:
            # Force reimport to trigger the boto3 check
            if "core.backup_targets.s3" in sys.modules:
                del sys.modules["core.backup_targets.s3"]
            from core.backup_targets.s3 import S3BackupTarget
            with self.assertRaises(ImportError):
                S3BackupTarget(bucket="test-bucket")
        finally:
            builtins.__import__ = original_import
            # Restore cached module if needed
            if "core.backup_targets.s3" in sys.modules:
                del sys.modules["core.backup_targets.s3"]


if __name__ == "__main__":
    unittest.main()
