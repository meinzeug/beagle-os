import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.virtualization.storage import SnapshotSpec, VolumeSpec
from providers.beagle.storage.zfs import ZfsStorageBackend


class ZfsStorageBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.commands: list[list[str]] = []

        def fake_run(command: list[str]) -> str:
            self.commands.append(command)
            if command[:2] == ["zfs", "list"]:
                return "\n".join([
                    "beagle/vm/vm-101-root\t21474836480\t-",
                    "beagle/vm/vm-101-clone\t21474836480\tbeagle/vm/vm-101-root@clone-vm-101-clone",
                ])
            return "ok"

        self.backend = ZfsStorageBackend(zpool="beagle", dataset_prefix="vm", run_checked=fake_run)

    def test_create_volume_uses_zfs_create(self) -> None:
        payload = self.backend.create_volume(VolumeSpec(name="vm-101-root", size_gib=20, format="raw", pool_name="ignored"))
        self.assertEqual(payload["id"], "beagle/vm/vm-101-root")
        self.assertEqual(self.commands[0], ["zfs", "create", "-V", "20G", "beagle/vm/vm-101-root"])

    def test_snapshot_uses_zfs_snapshot(self) -> None:
        result = self.backend.snapshot(SnapshotSpec(volume_id="beagle/vm/vm-101-root", name="pre-upgrade"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["snapshot_id"], "beagle/vm/vm-101-root@pre-upgrade")
        self.assertEqual(self.commands[-1], ["zfs", "snapshot", "beagle/vm/vm-101-root@pre-upgrade"])

    def test_clone_uses_snapshot_and_clone(self) -> None:
        result = self.backend.clone(
            "beagle/vm/vm-101-root",
            VolumeSpec(name="vm-101-clone", size_gib=20, format="raw", pool_name="ignored"),
            linked=True,
        )
        self.assertTrue(result["linked"])
        self.assertEqual(self.commands[-2], ["zfs", "snapshot", "beagle/vm/vm-101-root@clone-vm-101-clone"])
        self.assertEqual(self.commands[-1], ["zfs", "clone", "beagle/vm/vm-101-root@clone-vm-101-clone", "beagle/vm/vm-101-clone"])

    def test_list_volumes_parses_zfs_output(self) -> None:
        volumes = self.backend.list_volumes()
        self.assertEqual(len(volumes), 2)
        self.assertEqual(volumes[0]["name"], "vm-101-root")
        self.assertEqual(volumes[1]["origin"], "beagle/vm/vm-101-root@clone-vm-101-clone")


if __name__ == "__main__":
    unittest.main()
