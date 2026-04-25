"""Linux bridge + VLAN implementation for NetworkBackend."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from core.exec.safe_subprocess import run_cmd as _run_cmd_safe
from core.persistence.json_state_store import JsonStateStore
from core.virtualization.network import NetworkBackend, NetworkZoneInfo, NetworkZoneSpec, VlanInterfaceSpec


class VlanBackend:
    """VLAN-based network backend using Linux bridges and ip link."""

    STATE_FILE = Path("/var/lib/beagle/beagle-manager/network-zones.json")

    def __init__(self, state_file: Path | None = None):
        """Initialize VLAN backend with persisted state."""
        if state_file is not None:
            self.STATE_FILE = state_file
        self._store = JsonStateStore(
            self.STATE_FILE,
            default_factory=lambda: {"zones": {}, "zone_vms": {}},
            mode=0o644,
        )
        self._state = self._store.load()

    def _save_state(self) -> None:
        """Save zones state to disk (atomic write via JsonStateStore)."""
        self._store.save(self._state)

    def _run_cmd(self, cmd: list[str]) -> str:
        """Run a command and return output."""
        result = _run_cmd_safe(cmd, check=True)
        return result.stdout.strip()

    def _run_cmd_ignore_error(self, cmd: list[str]) -> str:
        """Run a command, ignoring errors."""
        result = _run_cmd_safe(cmd, check=False)
        return result.stdout.strip()

    def _validate_vlan_id(self, vlan_id: int) -> None:
        """Validate VLAN ID is in range 1-4094."""
        if not 1 <= vlan_id <= 4094:
            raise ValueError(f"VLAN ID must be 1-4094, got {vlan_id}")

    def _bridge_name(self, zone_id: str) -> str:
        """Generate bridge name from zone ID."""
        safe_id = "".join(c for c in zone_id if c.isalnum() or c == "-")[:10]
        return f"br-{safe_id}"

    def _vlan_interface_name(self, zone_id: str) -> str:
        """Generate VLAN interface name from zone ID."""
        safe_id = "".join(c for c in zone_id if c.isalnum() or c == "-")[:10]
        return f"vlan-{safe_id}"

    def create_zone(self, spec: NetworkZoneSpec) -> NetworkZoneInfo:
        """Create a new network zone (VLAN)."""
        self._validate_vlan_id(spec.vlan_id)

        # Check if zone already exists
        if spec.zone_id in self._state["zones"]:
            raise ValueError(f"Zone {spec.zone_id} already exists")

        bridge = self._bridge_name(spec.zone_id)
        vlan_iface = self._vlan_interface_name(spec.zone_id)

        # Create bridge
        try:
            self._run_cmd(["sudo", "ip", "link", "add", bridge, "type", "bridge"])
            self._run_cmd(["sudo", "ip", "link", "set", bridge, "up"])
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create bridge {bridge}: {e}")

        # Create VLAN interface on bridge
        try:
            self._run_cmd(
                [
                    "sudo",
                    "ip",
                    "link",
                    "add",
                    vlan_iface,
                    "link",
                    "eth0",
                    "type",
                    "vlan",
                    "id",
                    str(spec.vlan_id),
                ]
            )
            self._run_cmd(["sudo", "ip", "link", "set", vlan_iface, "up"])
            self._run_cmd(["sudo", "ip", "link", "set", vlan_iface, "master", bridge])
        except subprocess.CalledProcessError as e:
            # Clean up bridge on failure
            self._run_cmd_ignore_error(["sudo", "ip", "link", "del", bridge])
            raise RuntimeError(f"Failed to create VLAN {spec.vlan_id}: {e}")

        # Configure bridge interface with gateway IP
        try:
            # Extract subnet prefix length from CIDR
            if "/" in spec.subnet:
                subnet_base, prefix = spec.subnet.split("/")
            else:
                subnet_base, prefix = spec.subnet, "24"

            self._run_cmd(
                ["sudo", "ip", "addr", "add", f"{spec.gateway}/{prefix}", "dev", bridge]
            )
        except subprocess.CalledProcessError as e:
            self._run_cmd_ignore_error(["sudo", "ip", "link", "del", bridge])
            raise RuntimeError(f"Failed to assign gateway IP to bridge: {e}")

        # Persist zone state
        zone_info = NetworkZoneInfo(
            zone_id=spec.zone_id,
            zone_name=spec.zone_name,
            vlan_id=spec.vlan_id,
            subnet=spec.subnet,
            gateway=spec.gateway,
            dhcp_start=spec.dhcp_start,
            dhcp_end=spec.dhcp_end,
            dns_servers=spec.dns_servers,
            status="active",
            vm_count=0,
            dhcp_leases=0,
        )

        self._state["zones"][spec.zone_id] = {
            "spec": spec.__dict__,
            "bridge": bridge,
            "vlan_iface": vlan_iface,
            "status": "active",
            "vm_count": 0,
        }
        self._state["zone_vms"][spec.zone_id] = []
        self._save_state()

        return zone_info

    def get_zone(self, zone_id: str) -> NetworkZoneInfo:
        """Get info for a network zone."""
        if zone_id not in self._state["zones"]:
            raise ValueError(f"Zone {zone_id} not found")

        zone_data = self._state["zones"][zone_id]
        spec_dict = zone_data["spec"]

        return NetworkZoneInfo(
            zone_id=zone_id,
            zone_name=spec_dict["zone_name"],
            vlan_id=spec_dict["vlan_id"],
            subnet=spec_dict["subnet"],
            gateway=spec_dict["gateway"],
            dhcp_start=spec_dict["dhcp_start"],
            dhcp_end=spec_dict["dhcp_end"],
            dns_servers=spec_dict["dns_servers"],
            status=zone_data.get("status", "active"),
            vm_count=zone_data.get("vm_count", 0),
            dhcp_leases=zone_data.get("dhcp_leases", 0),
        )

    def list_zones(self) -> list[NetworkZoneInfo]:
        """List all network zones."""
        return [self.get_zone(zone_id) for zone_id in self._state["zones"]]

    def delete_zone(self, zone_id: str) -> None:
        """Delete a network zone."""
        if zone_id not in self._state["zones"]:
            raise ValueError(f"Zone {zone_id} not found")

        zone_data = self._state["zones"][zone_id]

        # Fail if zone has VMs
        if self._state["zone_vms"].get(zone_id):
            raise ValueError(f"Cannot delete zone with {len(self._state['zone_vms'][zone_id])} VMs")

        # Remove interfaces
        bridge = zone_data.get("bridge")
        if bridge:
            self._run_cmd_ignore_error(["sudo", "ip", "link", "del", bridge])

        # Remove state
        del self._state["zones"][zone_id]
        if zone_id in self._state["zone_vms"]:
            del self._state["zone_vms"][zone_id]
        self._save_state()

    def attach_vm_to_zone(self, zone_id: str, vm_id: str) -> str:
        """Attach VM to a zone. Returns MAC address (simulated)."""
        if zone_id not in self._state["zones"]:
            raise ValueError(f"Zone {zone_id} not found")

        # Generate deterministic MAC for VM in zone
        zone_data = self._state["zones"][zone_id]
        vlan_id = zone_data["spec"]["vlan_id"]
        vm_idx = len(self._state["zone_vms"].get(zone_id, []))

        # Simple MAC generation: 52:54:00:vlan:vm_idx (libvirt-like)
        mac = f"52:54:00:{vlan_id:02x}:{vm_idx:02x}:00"

        self._state["zone_vms"].setdefault(zone_id, []).append(
            {"vm_id": vm_id, "mac": mac}
        )
        self._state["zones"][zone_id]["vm_count"] = len(self._state["zone_vms"][zone_id])
        self._save_state()

        return mac

    def detach_vm_from_zone(self, zone_id: str, vm_id: str) -> None:
        """Detach VM from a zone."""
        if zone_id not in self._state["zones"]:
            raise ValueError(f"Zone {zone_id} not found")

        vms = self._state["zone_vms"].get(zone_id, [])
        vms[:] = [v for v in vms if v["vm_id"] != vm_id]
        self._state["zones"][zone_id]["vm_count"] = len(vms)
        self._save_state()

    def get_zone_vms(self, zone_id: str) -> list[str]:
        """List all VMs in a zone."""
        if zone_id not in self._state["zones"]:
            raise ValueError(f"Zone {zone_id} not found")

        return [v["vm_id"] for v in self._state["zone_vms"].get(zone_id, [])]
