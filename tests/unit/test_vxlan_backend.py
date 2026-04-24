"""Unit tests for VxlanBackend state management.

These tests exercise state operations (create/list/attach/detach/delete)
without running actual `ip link` commands by mocking subprocess.run.
"""

from __future__ import annotations

import json
import sys
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from providers.beagle.network.vxlan import VxlanBackend
from core.virtualization.network import NetworkZoneSpec


def _make_backend(tmp_path: Path) -> VxlanBackend:
    state_file = tmp_path / "vxlan-zones.json"
    return VxlanBackend(
        state_file=state_file,
        underlay_interface="eth0",
        local_ip="10.0.0.1",
        peers=["10.0.0.2", "10.0.0.3"],
    )


def _make_spec(zone_id: str = "zone-a", vni: int = 100) -> NetworkZoneSpec:
    return NetworkZoneSpec(
        zone_id=zone_id,
        zone_name=f"Test Zone {zone_id}",
        vlan_id=vni,
        subnet="10.1.0.0/24",
        gateway="10.1.0.1",
        dhcp_start="10.1.0.100",
        dhcp_end="10.1.0.200",
        dns_servers=["8.8.8.8"],
    )


class TestVxlanBackendStateManagement(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.mkdtemp()
        self._tmp_path = Path(self._tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _make_backend_mocked(self) -> VxlanBackend:
        """Create backend with mocked subprocess calls."""
        backend = _make_backend(self._tmp_path)
        backend._run_cmd = MagicMock(return_value="")
        backend._run_cmd_ignore_error = MagicMock(return_value="")
        return backend

    def test_create_zone_stores_state(self):
        """create_zone persists zone data in state file."""
        backend = self._make_backend_mocked()
        spec = _make_spec("zone-1", vni=100)
        zone_info = backend.create_zone(spec)

        self.assertEqual(zone_info.zone_id, "zone-1")
        self.assertEqual(zone_info.vlan_id, 100)
        self.assertEqual(zone_info.status, "active")

        # State file must be persisted
        state = json.loads((self._tmp_path / "vxlan-zones.json").read_text())
        self.assertIn("zone-1", state["zones"])
        self.assertEqual(state["zones"]["zone-1"]["spec"]["vlan_id"], 100)

    def test_create_zone_peers_are_stored(self):
        """Peers configured on backend are stored with zone."""
        backend = self._make_backend_mocked()
        spec = _make_spec("zone-peers", vni=200)
        backend.create_zone(spec)

        state = json.loads((self._tmp_path / "vxlan-zones.json").read_text())
        stored_peers = state["zones"]["zone-peers"]["peers"]
        self.assertIn("10.0.0.2", stored_peers)
        self.assertIn("10.0.0.3", stored_peers)

    def test_create_zone_calls_ip_link_add(self):
        """create_zone runs ip link add vxlan and bridge commands."""
        backend = self._make_backend_mocked()
        spec = _make_spec("zone-cmds", vni=300)
        backend.create_zone(spec)

        # Check actual args passed to subprocess via mock
        all_args = [list(c.args[0]) for c in backend._run_cmd.call_args_list]
        has_bridge = any("bridge" in a for cmd in all_args for a in cmd)
        has_vxlan = any("vxlan" in a for cmd in all_args for a in cmd)
        self.assertTrue(has_bridge, f"Expected bridge creation, got: {all_args}")
        self.assertTrue(has_vxlan, f"Expected vxlan creation, got: {all_args}")

    def test_create_zone_sets_vni_in_command(self):
        """create_zone uses the correct VNI from the spec."""
        backend = self._make_backend_mocked()
        spec = _make_spec("zone-vni", vni=42)
        backend.create_zone(spec)

        calls = [str(c) for c in backend._run_cmd.call_args_list]
        has_vni = any("42" in c and "vxlan" in c for c in calls)
        self.assertTrue(has_vni, f"Expected VNI 42 in vxlan cmd: {calls}")

    def test_duplicate_zone_raises(self):
        """Creating the same zone twice raises ValueError."""
        backend = self._make_backend_mocked()
        spec = _make_spec("zone-dup", vni=150)
        backend.create_zone(spec)
        with self.assertRaises(ValueError, msg="zone-dup"):
            backend.create_zone(spec)

    def test_invalid_vni_raises(self):
        """VNI out of range (0 or > 16777215) raises ValueError."""
        backend = self._make_backend_mocked()
        spec_bad = _make_spec("zone-bad", vni=0)
        with self.assertRaises(ValueError):
            backend.create_zone(spec_bad)

        spec_bad2 = _make_spec("zone-bad2", vni=16777216)
        with self.assertRaises(ValueError):
            backend.create_zone(spec_bad2)

    def test_list_zones_empty(self):
        """list_zones returns empty list when no zones exist."""
        backend = self._make_backend_mocked()
        self.assertEqual(backend.list_zones(), [])

    def test_list_zones_returns_all(self):
        """list_zones returns all created zones."""
        backend = self._make_backend_mocked()
        backend.create_zone(_make_spec("zone-a", vni=101))
        backend.create_zone(_make_spec("zone-b", vni=102))
        zones = backend.list_zones()
        self.assertEqual(len(zones), 2)
        ids = {z.zone_id for z in zones}
        self.assertIn("zone-a", ids)
        self.assertIn("zone-b", ids)

    def test_attach_vm_generates_mac(self):
        """attach_vm_to_zone returns a MAC address."""
        backend = self._make_backend_mocked()
        backend.create_zone(_make_spec("zone-mac", vni=111))
        mac = backend.attach_vm_to_zone("zone-mac", "vm-001")
        # MAC format: xx:xx:xx:xx:xx:xx
        parts = mac.split(":")
        self.assertEqual(len(parts), 6)

    def test_attach_vm_increments_count(self):
        """vm_count increases as VMs are attached."""
        backend = self._make_backend_mocked()
        backend.create_zone(_make_spec("zone-cnt", vni=222))
        self.assertEqual(backend.get_zone("zone-cnt").vm_count, 0)
        backend.attach_vm_to_zone("zone-cnt", "vm-001")
        self.assertEqual(backend.get_zone("zone-cnt").vm_count, 1)
        backend.attach_vm_to_zone("zone-cnt", "vm-002")
        self.assertEqual(backend.get_zone("zone-cnt").vm_count, 2)

    def test_detach_vm_decrements_count(self):
        """detach_vm_from_zone decrements vm_count."""
        backend = self._make_backend_mocked()
        backend.create_zone(_make_spec("zone-det", vni=333))
        backend.attach_vm_to_zone("zone-det", "vm-001")
        backend.attach_vm_to_zone("zone-det", "vm-002")
        backend.detach_vm_from_zone("zone-det", "vm-001")
        self.assertEqual(backend.get_zone("zone-det").vm_count, 1)

    def test_delete_zone_cleanup(self):
        """delete_zone calls ip link del for bridge and vxlan interface."""
        backend = self._make_backend_mocked()
        backend.create_zone(_make_spec("zone-del", vni=444))
        backend.delete_zone("zone-del")

        all_args = [list(c.args[0]) for c in backend._run_cmd_ignore_error.call_args_list]
        has_del = any("del" in a for cmd in all_args for a in cmd)
        self.assertTrue(has_del, f"Expected ip link del calls: {all_args}")

        # Zone no longer in state
        self.assertNotIn("zone-del", backend._state["zones"])

    def test_delete_zone_with_vms_raises(self):
        """delete_zone raises ValueError if VMs are attached."""
        backend = self._make_backend_mocked()
        backend.create_zone(_make_spec("zone-nonempty", vni=555))
        backend.attach_vm_to_zone("zone-nonempty", "vm-001")
        with self.assertRaises(ValueError):
            backend.delete_zone("zone-nonempty")

    def test_fdb_sync_on_create(self):
        """Peer FDB entries are synced when creating a zone."""
        backend = self._make_backend_mocked()
        spec = _make_spec("zone-fdb", vni=666)
        backend.create_zone(spec)

        calls = [str(c) for c in backend._run_cmd_ignore_error.call_args_list]
        fdb_calls = [c for c in calls if "fdb" in c and "append" in c]
        # Expect one FDB entry per peer
        self.assertEqual(len(fdb_calls), 2, f"Expected 2 fdb entries for 2 peers: {calls}")
        has_peer1 = any("10.0.0.2" in c for c in fdb_calls)
        has_peer2 = any("10.0.0.3" in c for c in fdb_calls)
        self.assertTrue(has_peer1, f"Missing peer 10.0.0.2: {fdb_calls}")
        self.assertTrue(has_peer2, f"Missing peer 10.0.0.3: {fdb_calls}")


if __name__ == "__main__":
    unittest.main()
