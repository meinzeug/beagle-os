"""Network zone and VLAN contract for multi-tenant isolation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@dataclass
class NetworkZoneSpec:
    """Network zone specification (VLAN, subnet, DHCP pool, gateway)."""
    
    zone_id: str
    zone_name: str
    vlan_id: int
    subnet: str  # CIDR, e.g. "192.168.10.0/24"
    gateway: str  # IP address
    dhcp_start: str
    dhcp_end: str
    dns_servers: list[str]  # e.g. ["8.8.8.8", "8.8.4.4"]
    description: str = ""


@dataclass
class NetworkZoneInfo:
    """Runtime info for a network zone."""
    
    zone_id: str
    zone_name: str
    vlan_id: int
    subnet: str
    gateway: str
    dhcp_start: str
    dhcp_end: str
    dns_servers: list[str]
    status: str  # "active" | "inactive"
    vm_count: int
    dhcp_leases: int


@dataclass
class VlanInterfaceSpec:
    """VLAN interface specification for VM attachment."""
    
    zone_id: str
    mac_address: Optional[str] = None  # auto-generate if None


@runtime_checkable
class NetworkBackend(Protocol):
    """Provider contract for network zone and VLAN operations."""

    def create_zone(self, spec: NetworkZoneSpec) -> NetworkZoneInfo:
        """Create a new network zone (VLAN)."""
        ...

    def get_zone(self, zone_id: str) -> NetworkZoneInfo:
        """Get info for a network zone."""
        ...

    def list_zones(self) -> list[NetworkZoneInfo]:
        """List all network zones."""
        ...

    def delete_zone(self, zone_id: str) -> None:
        """Delete a network zone."""
        ...

    def attach_vm_to_zone(self, zone_id: str, vm_id: str) -> str:
        """Attach VM to a zone. Returns MAC address."""
        ...

    def detach_vm_from_zone(self, zone_id: str, vm_id: str) -> None:
        """Detach VM from a zone."""
        ...

    def get_zone_vms(self, zone_id: str) -> list[str]:
        """List all VMs in a zone."""
        ...
