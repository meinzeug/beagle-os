import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.virtualization.storage import SnapshotSpec, VolumeSpec
from providers.beagle.storage.lvm_thin import LvmThinStorageBackend


class LvmThinStorageBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.commands: list[list[str]] = []

        def fake_run(command: list[str]) -> str:
            self.commands.append(command)
            if command and command[0] == "lvs":
                return """
vm-101-root 21474836480 beagle-thinpool - Vwi-a-tz--
vm-101-snap 21474836480 beagle-thinpool vm-101-root Vwi-a-tz--
system-meta 4194304 - - -wi-a-----
""".strip()
            return "ok"

        self.backend = LvmThinStorageBackend(volume_group="beagle-vg", thin_pool="beagle-thinpool", run_checked=fake_run)

    def test_create_volume_uses_lvcreate_thin(self) -> None:
        payload = self.backend.create_volume(
            VolumeSpec(name="vm-101-root", size_gib=20, format="raw", pool_name="beagle-thinpool")
        )
        self.assertEqual(payload["id"], "beagle-vg/vm-101-root")
        self.assertEqual(payload["pool"], "beagle-thinpool")
        self.assertEqual(self.commands[0], [
            "lvcreate",
            "--yes",
            "--thin",
            "-V",
            "20G",
            "-n",
            "vm-101-root",
            "beagle-vg/beagle-thinpool",
        ])

    def test_snapshot_uses_lvcreate_snapshot(self) -> None:
        result = self.backend.snapshot(SnapshotSpec(volume_id="beagle-vg/vm-101-root", name="pre-upgrade"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["snapshot_id"], "beagle-vg/pre-upgrade")
        self.assertEqual(self.commands[-1], ["lvcreate", "--yes", "-s", "-n", "pre-upgrade", "beagle-vg/vm-101-root"])

    def test_clone_linked_uses_snapshot_clone(self) -> None:
        payload = self.backend.clone(
            "beagle-vg/vm-101-root",
            VolumeSpec(name="vm-101-clone", size_gib=20, format="raw", pool_name="beagle-thinpool"),
            linked=True,
        )
        self.assertTrue(payload["linked"])
        self.assertEqual(payload["source_volume_id"], "beagle-vg/vm-101-root")
        self.assertEqual(self.commands[-1], ["lvcreate", "--yes", "-s", "-n", "vm-101-clone", "beagle-vg/vm-101-root"])

    def test_list_volumes_filters_thin_pool(self) -> None:
        volumes = self.backend.list_volumes()
        self.assertEqual(len(volumes), 2)
        names = [item["name"] for item in volumes]
        self.assertIn("vm-101-root", names)
        self.assertIn("vm-101-snap", names)


if __name__ == "__main__":
    unittest.main()
