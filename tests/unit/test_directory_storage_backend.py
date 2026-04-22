import tempfile
import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.virtualization.storage import SnapshotSpec, VolumeSpec
from providers.beagle.storage.directory import DirectoryStorageBackend


class DirectoryStorageBackendTests(unittest.TestCase):
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
                target = Path(command[2])
                target.touch()
                return "resized"
            if command[:2] == ["qemu-img", "snapshot"]:
                return "snapshot"
            if command[:2] == ["qemu-img", "convert"]:
                target = Path(command[-1])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch()
                return "converted"
            return "ok"

        self.backend = DirectoryStorageBackend(base_dir=self._tmp.name, run_checked=fake_run)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_create_volume_executes_qemu_img_create(self) -> None:
        payload = self.backend.create_volume(VolumeSpec(name="vm-101-root", size_gib=20, format="qcow2", pool_name="local"))
        self.assertTrue(payload["id"].endswith("local/vm-101-root.qcow2"))
        self.assertEqual(payload["pool"], "local")
        self.assertEqual(payload["format"], "qcow2")
        self.assertEqual(self.commands[0], [
            "qemu-img",
            "create",
            "-f",
            "qcow2",
            str(Path(self._tmp.name) / "local" / "vm-101-root.qcow2"),
            "20G",
        ])

    def test_snapshot_executes_qemu_img_snapshot(self) -> None:
        volume = self.backend.create_volume(VolumeSpec(name="vm-102-root", size_gib=16, format="qcow2", pool_name="local"))
        result = self.backend.snapshot(SnapshotSpec(volume_id=volume["id"], name="pre-update", description="before patch"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["name"], "pre-update")
        self.assertEqual(self.commands[-1], ["qemu-img", "snapshot", "-c", "pre-update", volume["id"]])

    def test_clone_linked_uses_backing_file(self) -> None:
        source = self.backend.create_volume(VolumeSpec(name="vm-103-root", size_gib=10, format="qcow2", pool_name="local"))
        result = self.backend.clone(
            source["id"],
            VolumeSpec(name="vm-103-clone", size_gib=10, format="qcow2", pool_name="local"),
            linked=True,
        )
        self.assertTrue(result["linked"])
        self.assertEqual(self.commands[-1], [
            "qemu-img",
            "create",
            "-f",
            "qcow2",
            "-b",
            source["id"],
            str(Path(self._tmp.name) / "local" / "vm-103-clone.qcow2"),
        ])

    def test_list_volumes_returns_supported_formats(self) -> None:
        self.backend.create_volume(VolumeSpec(name="vm-201-root", size_gib=8, format="qcow2", pool_name="pool-a"))
        self.backend.create_volume(VolumeSpec(name="vm-202-root", size_gib=8, format="raw", pool_name="pool-a"))
        (Path(self._tmp.name) / "pool-a" / "ignore.txt").write_text("x", encoding="utf-8")

        volumes = self.backend.list_volumes("pool-a")
        ids = [item["id"] for item in volumes]
        self.assertEqual(len(volumes), 2)
        self.assertTrue(any(value.endswith("vm-201-root.qcow2") for value in ids))
        self.assertTrue(any(value.endswith("vm-202-root.raw") for value in ids))


if __name__ == "__main__":
    unittest.main()
