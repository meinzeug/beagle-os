"""IPAM (IP Address Management) service for network zones."""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from core.persistence.json_state_store import JsonStateStore


@dataclass
class IpLease:
    """IP lease for a VM."""

    ip_address: str
    mac_address: str
    vm_id: str
    zone_id: str
    hostname: str
    static: bool = False
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None


class IpamService:
    """IPAM service for managing IP allocation per network zone."""

    STATE_FILE = Path("/var/lib/beagle/beagle-manager/ipam-state.json")

    def __init__(self, state_file: Optional[Path] = None):
        """Initialize IPAM service with persisted state."""
        if state_file is not None:
            self.STATE_FILE = state_file
        self._store = JsonStateStore(
            self.STATE_FILE,
            default_factory=lambda: {"leases": {}, "zone_subnets": {}},
            mode=0o644,
        )
        self._state = self._store.load()

    def _save_state(self) -> None:
        """Save IPAM state to disk (atomic write)."""
        self._store.save(self._state)

    def register_zone(
        self,
        zone_id: str,
        subnet: str,
        dhcp_start: str,
        dhcp_end: str,
        *,
        bridge_name: str = "",
    ) -> None:
        """Register a zone for IPAM tracking."""
        try:
            network = ipaddress.ip_network(subnet, strict=False)
            dhcp_start_ip = ipaddress.ip_address(dhcp_start)
            dhcp_end_ip = ipaddress.ip_address(dhcp_end)

            if not (dhcp_start_ip in network and dhcp_end_ip in network):
                raise ValueError(
                    f"DHCP range {dhcp_start}-{dhcp_end} not in subnet {subnet}"
                )
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as e:
            raise ValueError(f"Invalid subnet or DHCP range: {e}")

        self._state["zone_subnets"][zone_id] = {
            "subnet": subnet,
            "dhcp_start": dhcp_start,
            "dhcp_end": dhcp_end,
            "bridge_name": str(bridge_name or "").strip(),
        }
        self._save_state()

    def allocate_ip(
        self,
        zone_id: str,
        vm_id: str,
        mac_address: str,
        hostname: str,
        static_ip: Optional[str] = None,
    ) -> str:
        """Allocate an IP address for a VM in a zone."""
        if zone_id not in self._state["zone_subnets"]:
            raise ValueError(f"Zone {zone_id} not registered in IPAM")

        zone_config = self._state["zone_subnets"][zone_id]
        subnet = zone_config["subnet"]
        dhcp_start = zone_config["dhcp_start"]
        dhcp_end = zone_config["dhcp_end"]

        if static_ip:
            # Validate static IP is in subnet
            try:
                ip = ipaddress.ip_address(static_ip)
                network = ipaddress.ip_network(subnet, strict=False)
                if ip not in network:
                    raise ValueError(f"Static IP {static_ip} not in subnet {subnet}")
            except ipaddress.AddressValueError as e:
                raise ValueError(f"Invalid static IP: {e}")

            assigned_ip = static_ip
            static = True
        else:
            # Find next available IP in DHCP range
            assigned_ip = self._find_available_ip(zone_id, dhcp_start, dhcp_end)
            static = False

        # Record lease
        lease = IpLease(
            ip_address=assigned_ip,
            mac_address=mac_address,
            vm_id=vm_id,
            zone_id=zone_id,
            hostname=hostname,
            static=static,
            expires_at=(
                (datetime.now(timezone.utc) + timedelta(days=365)).isoformat() if not static else None
            ),
        )

        lease_key = f"{zone_id}:{vm_id}"
        self._state["leases"][lease_key] = lease.__dict__
        self._save_state()

        return assigned_ip

    def release_ip(self, zone_id: str, vm_id: str) -> None:
        """Release an IP lease for a VM."""
        lease_key = f"{zone_id}:{vm_id}"
        if lease_key in self._state["leases"]:
            del self._state["leases"][lease_key]
            self._save_state()

    def get_zone_leases(self, zone_id: str) -> list[IpLease]:
        """Get all IP leases in a zone."""
        leases = []
        for lease_key, lease_dict in self._state["leases"].items():
            if lease_key.startswith(f"{zone_id}:"):
                leases.append(IpLease(**lease_dict))
        return leases

    def get_vm_lease(self, zone_id: str, vm_id: str) -> Optional[IpLease]:
        """Get IP lease for a specific VM."""
        lease_key = f"{zone_id}:{vm_id}"
        if lease_key in self._state["leases"]:
            return IpLease(**self._state["leases"][lease_key])
        return None

    def _find_available_ip(self, zone_id: str, dhcp_start: str, dhcp_end: str) -> str:
        """Find next available IP in DHCP range."""
        start_ip = ipaddress.ip_address(dhcp_start)
        end_ip = ipaddress.ip_address(dhcp_end)

        # Get all currently allocated IPs in this zone
        allocated = set()
        for lease_key, lease_dict in self._state["leases"].items():
            if lease_key.startswith(f"{zone_id}:"):
                allocated.add(lease_dict["ip_address"])

        # Find first unallocated IP
        current = start_ip
        while current <= end_ip:
            if str(current) not in allocated:
                return str(current)
            current += 1

        raise RuntimeError(f"DHCP pool exhausted for zone {zone_id}")

    def get_all_zones(self) -> dict[str, Any]:
        """Return all registered zones with subnet info."""
        return {
            zone_id: {
                "zone_id": zone_id,
                "subnet": info["subnet"],
                "dhcp_start": info["dhcp_start"],
                "dhcp_end": info["dhcp_end"],
                "bridge_name": str(info.get("bridge_name") or "").strip(),
            }
            for zone_id, info in self._state.get("zone_subnets", {}).items()
        }
