"""VXLAN backend for cross-host L2 overlays.

This backend mirrors the NetworkBackend contract and manages one VXLAN device
per NetworkZone. It is designed for cluster mode and can be used in parallel
to local VLAN zones.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from core.persistence.json_state_store import JsonStateStore
from core.virtualization.network import NetworkZoneInfo, NetworkZoneSpec


class VxlanBackend:
    """VXLAN-based network backend using Linux bridge + vxlan devices."""

    STATE_FILE = Path("/var/lib/beagle/beagle-manager/vxlan-zones.json")

    def __init__(
        self,
        state_file: Path | None = None,
        underlay_interface: str = "eth0",
        local_ip: str = "",
        peers: list[str] | None = None,
    ):
        if state_file is not None:
            self.STATE_FILE = state_file
        self._store = JsonStateStore(
            self.STATE_FILE,
            default_factory=lambda: {"zones": {}, "zone_vms": {}},
            mode=0o644,
        )
        self._state = self._store.load()
        self._underlay_interface = underlay_interface
        self._local_ip = local_ip
        self._peers = peers or []

    def _save_state(self) -> None:
        self._store.save(self._state)

    def _run_cmd(self, cmd: list[str]) -> str:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def _run_cmd_ignore_error(self, cmd: list[str]) -> str:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip()

    def _validate_vni(self, vni: int) -> None:
        if not 1 <= vni <= 16777215:
            raise ValueError(f"VNI must be 1-16777215, got {vni}")

    def _bridge_name(self, zone_id: str) -> str:
        safe_id = "".join(c for c in zone_id if c.isalnum() or c == "-")[:10]
        return f"brvx-{safe_id}"

    def _vxlan_interface_name(self, zone_id: str) -> str:
        safe_id = "".join(c for c in zone_id if c.isalnum() or c == "-")[:10]
        return f"vx-{safe_id}"

    def _sync_fdb(self, vx_iface: str, peers: list[str]) -> None:
        for peer in peers:
            peer = str(peer or "").strip()
            if not peer:
                continue
            self._run_cmd_ignore_error(
                ["sudo", "bridge", "fdb", "append", "00:00:00:00:00:00", "dev", vx_iface, "dst", peer]
            )

    def create_zone(self, spec: NetworkZoneSpec) -> NetworkZoneInfo:
        if spec.zone_id in self._state["zones"]:
            raise ValueError(f"Zone {spec.zone_id} already exists")

        self._validate_vni(spec.vlan_id)

        bridge = self._bridge_name(spec.zone_id)
        vx_iface = self._vxlan_interface_name(spec.zone_id)
        cmd = [
            "sudo",
            "ip",
            "link",
            "add",
            vx_iface,
            "type",
            "vxlan",
            "id",
            str(spec.vlan_id),
            "dstport",
            "4789",
            "dev",
            self._underlay_interface,
            "nolearning",
        ]
        if self._local_ip:
            cmd.extend(["local", self._local_ip])

        try:
            self._run_cmd(["sudo", "ip", "link", "add", bridge, "type", "bridge"])
            self._run_cmd(cmd)
            self._run_cmd(["sudo", "ip", "link", "set", vx_iface, "master", bridge])
            self._run_cmd(["sudo", "ip", "link", "set", vx_iface, "up"])
            self._run_cmd(["sudo", "ip", "link", "set", bridge, "up"])
            self._run_cmd(["sudo", "ip", "addr", "add", f"{spec.gateway}/{spec.subnet.split('/')[-1]}", "dev", bridge])
            self._sync_fdb(vx_iface, self._peers)
        except subprocess.CalledProcessError as exc:
            self._run_cmd_ignore_error(["sudo", "ip", "link", "del", vx_iface])
            self._run_cmd_ignore_error(["sudo", "ip", "link", "del", bridge])
            raise RuntimeError(f"Failed to create VXLAN zone {spec.zone_id}: {exc}")

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
            "vxlan_iface": vx_iface,
            "peers": list(self._peers),
            "status": "active",
            "vm_count": 0,
        }
        self._state["zone_vms"][spec.zone_id] = []
        self._save_state()
        return zone_info

    def get_zone(self, zone_id: str) -> NetworkZoneInfo:
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
        return [self.get_zone(zone_id) for zone_id in self._state["zones"]]

    def delete_zone(self, zone_id: str) -> None:
        if zone_id not in self._state["zones"]:
            raise ValueError(f"Zone {zone_id} not found")
        if self._state["zone_vms"].get(zone_id):
            raise ValueError(f"Cannot delete zone with {len(self._state['zone_vms'][zone_id])} VMs")

        zone_data = self._state["zones"][zone_id]
        vx_iface = zone_data.get("vxlan_iface")
        bridge = zone_data.get("bridge")
        if vx_iface:
            self._run_cmd_ignore_error(["sudo", "ip", "link", "del", vx_iface])
        if bridge:
            self._run_cmd_ignore_error(["sudo", "ip", "link", "del", bridge])

        del self._state["zones"][zone_id]
        if zone_id in self._state["zone_vms"]:
            del self._state["zone_vms"][zone_id]
        self._save_state()

    def attach_vm_to_zone(self, zone_id: str, vm_id: str) -> str:
        if zone_id not in self._state["zones"]:
            raise ValueError(f"Zone {zone_id} not found")
        zone_data = self._state["zones"][zone_id]
        vni = zone_data["spec"]["vlan_id"]
        vm_idx = len(self._state["zone_vms"].get(zone_id, []))
        mac = f"52:54:{(vni >> 16) & 0xff:02x}:{(vni >> 8) & 0xff:02x}:{vni & 0xff:02x}:{vm_idx:02x}"
        self._state["zone_vms"].setdefault(zone_id, []).append({"vm_id": vm_id, "mac": mac})
        self._state["zones"][zone_id]["vm_count"] = len(self._state["zone_vms"][zone_id])
        self._save_state()
        return mac

    def detach_vm_from_zone(self, zone_id: str, vm_id: str) -> None:
        if zone_id not in self._state["zones"]:
            raise ValueError(f"Zone {zone_id} not found")
        vms = self._state["zone_vms"].get(zone_id, [])
        vms[:] = [vm for vm in vms if vm["vm_id"] != vm_id]
        self._state["zones"][zone_id]["vm_count"] = len(vms)
        self._save_state()

    def get_zone_vms(self, zone_id: str) -> list[str]:
        if zone_id not in self._state["zones"]:
            raise ValueError(f"Zone {zone_id} not found")
        return [vm["vm_id"] for vm in self._state["zone_vms"].get(zone_id, [])]
