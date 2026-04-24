"""Beagle network provider for VLAN, firewall, and IPAM."""
"""Network provider package for Beagle host."""

from .vlan import VlanBackend
from .vxlan import VxlanBackend

__all__ = ["VlanBackend", "VxlanBackend"]
