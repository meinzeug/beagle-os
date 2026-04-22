import tempfile
import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.virtualization.storage import SnapshotSpec, VolumeSpec
from providers.beagle.storage.nfs import NfsStorageBackend


class NfsStorageBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.commands: list[list[str]] = []

        def fake_run(command: list[str]) -> str:
            self.commands.append(command)
            if command[:2] == ["qemu-img", "create"]:
                target = Path(command[-2] if command[-1].endswith("G") else command[-1])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch()
                return "created"
            if command[:2] == ["qemu-img", "resize"]:
                Path(command[2]).touch()
                return "resized"
            if command[:2] == ["qemu-img", "convert"]:
                target = Path(command[-1])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch()
                return "converted"
            return "ok"

        self.backend = NfsStorageBackend(
            mount_path=self._tmp.name,
            default_pool="nfs",
            run_checked=fake_run,
            is_mountpoint=lambda _p: True,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_create_volume_uses_qemu_img_create(self) -> None:
        payload = self.backend.create_volume(VolumeSpec(name="vm-301-root", size_gib=15, format="qcow2", pool_name="nfs"))
        self.assertEqual(payload["driver"], "nfs")
        self.assertTrue(payload["id"].endswith("nfs/vm-301-root.qcow2"))
        self.assertEqual(self.commands[0], [
            "qemu-img",
            "create",
            "-f",
            "qcow2",
            str(Path(self._tmp.name) / "nfs" / "vm-301-root.qcow2"),
            "15G",
        ])

    def test_mount_guard_blocks_unmounted_path(self) -> None:
        backend = NfsStorageBackend(
            mount_path=self._tmp.name,
            default_pool="nfs",
            run_checked=lambda _cmd: "ok",
            is_mountpoint=lambda _p: False,
        )
        with self.assertRaises(RuntimeError):
            backend.list_volumes()

    def test_snapshot_and_clone_paths(self) -> None:
        volume = self.backend.create_volume(VolumeSpec(name="vm-302-root", size_gib=8, format="qcow2", pool_name="nfs"))
        snap = self.backend.snapshot(SnapshotSpec(volume_id=volume["id"], name="pre"))
        clone = self.backend.clone(
            volume["id"],
            VolumeSpec(name="vm-302-clone", size_gib=8, format="qcow2", pool_name="nfs"),
            linked=True,
        )
        self.assertTrue(snap["ok"])
        self.assertTrue(clone["linked"])
        self.assertTrue(clone["id"].endswith("nfs/vm-302-clone.qcow2"))

    def test_list_volumes_filters_formats(self) -> None:
        self.backend.create_volume(VolumeSpec(name="vm-303-root", size_gib=8, format="qcow2", pool_name="nfs"))
        self.backend.create_volume(VolumeSpec(name="vm-304-root", size_gib=8, format="raw", pool_name="nfs"))
        (Path(self._tmp.name) / "nfs" / "ignore.log").write_text("x", encoding="utf-8")
        volumes = self.backend.list_volumes("nfs")
        self.assertEqual(len(volumes), 2)


if __name__ == "__main__":
    unittest.main()
