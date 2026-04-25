"""Unit tests for VLAN, IPAM, and Firewall services."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
# Add beagle-host to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "beagle-host" / "services"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "providers"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from ipam_service import IpamService, IpLease
from firewall_service import FirewallService, FirewallProfile, FirewallRule
from beagle.network.vlan import VlanBackend
from beagle.network.vxlan import VxlanBackend
from core.virtualization.network import NetworkZoneSpec


class TestVlanBackend:
    """Tests for VLAN backend."""

    def setup_method(self):
        """Setup test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        
    def teardown_method(self):
        """Cleanup test fixtures."""
        self.tmpdir.cleanup()

    @patch('beagle.network.vlan._run_cmd_safe')
    def test_create_zone(self, mock_run):
        """Test creating a network zone."""
        # Mock run_cmd to succeed
        import subprocess as _sp
        mock_run.return_value = _sp.CompletedProcess([], 0, stdout="", stderr="")
        
        state_file = self.tmp_path / "network-zones.json"
        backend = VlanBackend(state_file=state_file)
        spec = NetworkZoneSpec(
            zone_id="zone-1",
            zone_name="Production",
            vlan_id=100,
            subnet="192.168.100.0/24",
            gateway="192.168.100.1",
            dhcp_start="192.168.100.10",
            dhcp_end="192.168.100.250",
            dns_servers=["8.8.8.8", "8.8.4.4"],
        )
        zone_info = backend.create_zone(spec)
        assert zone_info.zone_id == "zone-1"
        assert zone_info.vlan_id == 100
        assert zone_info.status == "active"

    def test_invalid_vlan_id(self):
        """Test that invalid VLAN IDs are rejected."""
        state_file = self.tmp_path / "network-zones.json"
        backend = VlanBackend(state_file=state_file)
        spec = NetworkZoneSpec(
            zone_id="zone-bad",
            zone_name="Bad",
            vlan_id=5000,  # Out of range
            subnet="10.0.0.0/24",
            gateway="10.0.0.1",
            dhcp_start="10.0.0.10",
            dhcp_end="10.0.0.250",
            dns_servers=["8.8.8.8"],
        )
        with pytest.raises(ValueError):
            backend.create_zone(spec)


class TestIpamService:
    """Tests for IPAM service."""

    def setup_method(self):
        """Setup test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def teardown_method(self):
        """Cleanup test fixtures."""
        self.tmpdir.cleanup()

    def test_register_zone(self):
        """Test registering a zone for IPAM."""
        ipam = IpamService(state_file=self.tmp_path / "ipam.json")
        ipam.register_zone(
            "zone-1", "192.168.1.0/24", "192.168.1.10", "192.168.1.250"
        )
        assert "zone-1" in ipam._state["zone_subnets"]

    def test_allocate_dynamic_ip(self):
        """Test allocating a dynamic IP."""
        ipam = IpamService(state_file=self.tmp_path / "ipam.json")
        ipam.register_zone(
            "zone-1", "192.168.1.0/24", "192.168.1.10", "192.168.1.250"
        )
        ip = ipam.allocate_ip("zone-1", "vm-001", "52:54:00:00:00:01", "vm1")
        assert ip == "192.168.1.10"

    def test_allocate_static_ip(self):
        """Test allocating a static IP."""
        ipam = IpamService(state_file=self.tmp_path / "ipam.json")
        ipam.register_zone(
            "zone-1", "192.168.1.0/24", "192.168.1.10", "192.168.1.250"
        )
        ip = ipam.allocate_ip(
            "zone-1", "vm-002", "52:54:00:00:00:02", "vm2", static_ip="192.168.1.100"
        )
        assert ip == "192.168.1.100"

    def test_get_zone_leases(self):
        """Test retrieving leases in a zone."""
        ipam = IpamService(state_file=self.tmp_path / "ipam.json")
        ipam.register_zone(
            "zone-1", "192.168.1.0/24", "192.168.1.10", "192.168.1.250"
        )
        ipam.allocate_ip("zone-1", "vm-001", "52:54:00:00:00:01", "vm1")
        ipam.allocate_ip("zone-1", "vm-002", "52:54:00:00:00:02", "vm2")
        leases = ipam.get_zone_leases("zone-1")
        assert len(leases) == 2

    def test_invalid_subnet(self):
        """Test that invalid subnets are rejected."""
        ipam = IpamService(state_file=self.tmp_path / "ipam.json")
        with pytest.raises(ValueError):
            ipam.register_zone("zone-bad", "invalid/subnet", "1.1.1.1", "1.1.1.2")


class TestVxlanBackend:
    """Tests for VXLAN backend."""

    def setup_method(self):
        """Setup test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def teardown_method(self):
        """Cleanup test fixtures."""
        self.tmpdir.cleanup()

    @patch('beagle.network.vxlan._run_cmd_safe')
    def test_create_zone(self, mock_run):
        """Test creating a VXLAN network zone."""
        import subprocess as _sp
        mock_run.return_value = _sp.CompletedProcess([], 0, stdout="", stderr="")

        state_file = self.tmp_path / "vxlan-zones.json"
        backend = VxlanBackend(
            state_file=state_file,
            underlay_interface="eth0",
            local_ip="10.10.10.1",
            peers=["10.10.10.2", "10.10.10.3"],
        )
        spec = NetworkZoneSpec(
            zone_id="ovl-1",
            zone_name="Overlay",
            vlan_id=10001,
            subnet="10.200.1.0/24",
            gateway="10.200.1.1",
            dhcp_start="10.200.1.10",
            dhcp_end="10.200.1.250",
            dns_servers=["1.1.1.1"],
        )
        zone_info = backend.create_zone(spec)
        assert zone_info.zone_id == "ovl-1"
        assert zone_info.vlan_id == 10001
        assert zone_info.status == "active"

    @patch('beagle.network.vxlan._run_cmd_safe')
    def test_attach_and_detach_vm(self, mock_run):
        """Test VM membership bookkeeping in VXLAN zone."""
        import subprocess as _sp
        mock_run.return_value = _sp.CompletedProcess([], 0, stdout="", stderr="")

        state_file = self.tmp_path / "vxlan-zones.json"
        backend = VxlanBackend(state_file=state_file)
        spec = NetworkZoneSpec(
            zone_id="ovl-2",
            zone_name="Overlay 2",
            vlan_id=20002,
            subnet="10.200.2.0/24",
            gateway="10.200.2.1",
            dhcp_start="10.200.2.10",
            dhcp_end="10.200.2.250",
            dns_servers=["8.8.8.8"],
        )
        backend.create_zone(spec)

        mac = backend.attach_vm_to_zone("ovl-2", "vm-101")
        assert mac.startswith("52:54:")
        assert backend.get_zone_vms("ovl-2") == ["vm-101"]

        backend.detach_vm_from_zone("ovl-2", "vm-101")
        assert backend.get_zone_vms("ovl-2") == []

    def test_invalid_vni(self):
        """Test that invalid VNI is rejected."""
        state_file = self.tmp_path / "vxlan-zones.json"
        backend = VxlanBackend(state_file=state_file)
        spec = NetworkZoneSpec(
            zone_id="ovl-bad",
            zone_name="Bad",
            vlan_id=0,
            subnet="10.201.0.0/24",
            gateway="10.201.0.1",
            dhcp_start="10.201.0.10",
            dhcp_end="10.201.0.250",
            dns_servers=["8.8.8.8"],
        )
        with pytest.raises(ValueError):
            backend.create_zone(spec)


class TestFirewallService:
    """Tests for firewall service."""

    def setup_method(self):
        """Setup test fixtures."""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def teardown_method(self):
        """Cleanup test fixtures."""
        self.tmpdir.cleanup()

    def test_create_profile(self):
        """Test creating a firewall profile."""
        fw = FirewallService(state_file=self.tmp_path / "fw.json")
        rules = [
            FirewallRule(
                direction="inbound", protocol="tcp", port=22, action="allow"
            ),
            FirewallRule(
                direction="inbound", protocol="tcp", port=80, action="allow"
            ),
        ]
        profile = FirewallProfile(
            profile_id="web-server",
            name="Web Server",
            rules=rules,
        )
        fw.create_profile(profile)
        retrieved = fw.get_profile("web-server")
        assert retrieved.name == "Web Server"
        assert len(retrieved.rules) == 2

    @patch('firewall_service.subprocess.run')
    def test_apply_profile_to_vm(self, mock_run):
        """Test applying a profile to a VM."""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        fw = FirewallService(state_file=self.tmp_path / "fw.json")
        rules = [
            FirewallRule(
                direction="inbound", protocol="tcp", port=443, action="allow"
            )
        ]
        profile = FirewallProfile(
            profile_id="https",
            name="HTTPS",
            rules=rules,
        )
        fw.create_profile(profile)
        fw.apply_profile_to_vm("https", "vm-001")
        retrieved = fw.get_vm_profile("vm-001")
        assert retrieved.profile_id == "https"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
