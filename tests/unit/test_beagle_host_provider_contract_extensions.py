import tempfile
import unittest

import sys
from pathlib import Path

PROVIDERS_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "providers"
if str(PROVIDERS_DIR) not in sys.path:
    sys.path.insert(0, str(PROVIDERS_DIR))

from beagle_host_provider import BeagleHostProvider


class BeagleHostProviderContractExtensionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.provider = BeagleHostProvider(state_dir=self._tmp.name)
        self.provider.create_vm(
            101,
            {
                "node": "beagle-0",
                "name": "vm-101",
                "status": "running",
                "scsi0": "local:20",
            },
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_snapshot_vm_records_snapshot_metadata(self):
        msg = self.provider.snapshot_vm(101, "pre-update", description="before package update")
        self.assertIn("created snapshot pre-update", msg)
        cfg = self.provider.get_vm_config("beagle-0", 101)
        snapshots = cfg.get("_snapshots", [])
        self.assertTrue(isinstance(snapshots, list) and len(snapshots) >= 1)
        self.assertEqual(snapshots[-1]["name"], "pre-update")

    def test_reset_vm_to_snapshot_uses_recorded_metadata_without_libvirt(self):
        self.provider.snapshot_vm(101, "sealed")
        msg = self.provider.reset_vm_to_snapshot(101, "sealed")
        self.assertIn("reset beagle vm 101 to snapshot sealed", msg)
        vms = self.provider.list_vms(refresh=True)
        vm = next(item for item in vms if int(item["vmid"]) == 101)
        self.assertEqual(vm.get("status"), "stopped")

    def test_reset_vm_to_snapshot_rejects_unknown_snapshot_without_libvirt(self):
        with self.assertRaises(RuntimeError):
            self.provider.reset_vm_to_snapshot(101, "sealed")

    def test_clone_vm_creates_target_vm_record(self):
        msg = self.provider.clone_vm(101, 202, name="vm-202-clone")
        self.assertIn("cloned beagle vm 101 to 202", msg)
        vms = self.provider.list_vms(refresh=True)
        ids = sorted(int(item["vmid"]) for item in vms)
        self.assertIn(202, ids)
        cfg = self.provider.get_vm_config("beagle-0", 202)
        self.assertEqual(cfg.get("name"), "vm-202-clone")

    def test_get_console_proxy_returns_unavailable_without_libvirt(self):
        payload = self.provider.get_console_proxy(101)
        self.assertEqual(payload.get("provider"), "beagle")
        self.assertFalse(payload.get("available"))
        self.assertEqual(payload.get("scheme"), "vnc")


if __name__ == "__main__":
    unittest.main()
