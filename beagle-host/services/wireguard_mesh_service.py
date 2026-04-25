"""WireGuard mesh service for BeagleStream Zero-Trust networking.

Manages a hub-and-spoke (or full-mesh) WireGuard overlay where:
- Each Beagle hypervisor node runs interface wg-beagle
- Each enrolled thin-client receives a peer config
- The Control Plane is the mesh coordinator

GoEnterprise Plan 01, Schritt 3
"""
from __future__ import annotations

import ipaddress
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class WireguardPeer:
    device_id: str          # stable device identifier
    public_key: str         # WireGuard public key (base64)
    endpoint: str | None    # host:port, None for roaming clients
    allowed_ips: list[str]  # CIDR list
    preshared_key: str = ""


@dataclass
class WireguardMeshConfig:
    """Returned to a device after successful registration."""
    interface_ip: str           # assigned IP in mesh (e.g. 10.beagle.0.x/32)
    server_public_key: str
    server_endpoint: str        # host:51820
    preshared_key: str
    allowed_ips: list[str]      # typically mesh subnet CIDR
    dns: str = "10.88.0.1"


class WireguardMeshService:
    """
    Manages WireGuard peer list for the Beagle mesh.

    The mesh uses a /16 subnet: 10.88.0.0/16
      - Control-Plane nodes:  10.88.0.1 – 10.88.0.254
      - Thin clients:         10.88.1.0/24 – 10.88.254.0/24

    This service:
    - Assigns IPs from the pool
    - Writes wg-beagle.conf (or uses `wg` commands live)
    - Provides peer_config for registered devices
    """

    MESH_SUBNET = ipaddress.IPv4Network("10.88.0.0/16")
    CLIENT_START = ipaddress.IPv4Address("10.88.1.1")
    STATE_DIR = Path("/var/lib/beagle/wireguard-mesh")
    WGCONF = Path("/etc/wireguard/wg-beagle.conf")
    INTERFACE = "wg-beagle"

    def __init__(
        self,
        *,
        server_public_key: str = "",
        server_endpoint: str = "",
        state_dir: Path | None = None,
        run_cmd: Any = None,
    ) -> None:
        self._server_public_key = server_public_key
        self._server_endpoint = server_endpoint
        self._state_dir = Path(state_dir) if state_dir else self.STATE_DIR
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._run_cmd = run_cmd or self._default_run
        self._state = self._load_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_peer(
        self,
        device_id: str,
        public_key: str,
        endpoint: str | None = None,
        preshared_key: str = "",
    ) -> WireguardMeshConfig:
        """Register a device in the mesh and return its peer config."""
        if device_id in self._state["peers"]:
            ip = self._state["peers"][device_id]["assigned_ip"]
        else:
            ip = self._allocate_ip()
            self._state["peers"][device_id] = {
                "public_key": public_key,
                "endpoint": endpoint,
                "assigned_ip": ip,
                "preshared_key": preshared_key,
            }
            self._save_state()

        # Apply peer live if interface exists
        try:
            self._apply_peer(public_key, ip, endpoint, preshared_key)
        except Exception:
            pass  # interface may not exist in test / non-root

        return WireguardMeshConfig(
            interface_ip=f"{ip}/32",
            server_public_key=self._server_public_key,
            server_endpoint=self._server_endpoint,
            preshared_key=preshared_key,
            allowed_ips=[str(self.MESH_SUBNET)],
        )

    def remove_peer(self, device_id: str) -> bool:
        """Remove a device from the mesh."""
        if device_id not in self._state["peers"]:
            return False
        peer = self._state["peers"].pop(device_id)
        allocated = set(self._state.get("allocated_ips", []))
        allocated.discard(peer["assigned_ip"])
        self._state["allocated_ips"] = list(allocated)
        self._save_state()
        try:
            self._run_cmd(["wg", "set", self.INTERFACE, "peer", peer["public_key"], "remove"])
        except Exception:
            pass
        return True

    def list_peers(self) -> list[dict[str, Any]]:
        """Return all registered peers."""
        return [
            {
                "device_id": did,
                "assigned_ip": info["assigned_ip"],
                "endpoint": info.get("endpoint"),
                "public_key": info["public_key"],
            }
            for did, info in self._state["peers"].items()
        ]

    def get_peer_config(self, device_id: str) -> WireguardMeshConfig | None:
        """Return the stored mesh config for a device (for re-enrollment)."""
        info = self._state["peers"].get(device_id)
        if not info:
            return None
        return WireguardMeshConfig(
            interface_ip=f"{info['assigned_ip']}/32",
            server_public_key=self._server_public_key,
            server_endpoint=self._server_endpoint,
            preshared_key=info.get("preshared_key", ""),
            allowed_ips=[str(self.MESH_SUBNET)],
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _allocate_ip(self) -> str:
        """Allocate the next free IP in the client range."""
        allocated = set(self._state.get("allocated_ips", []))
        host = self.CLIENT_START
        while str(host) in allocated:
            host += 1
            if host not in self.MESH_SUBNET:
                raise RuntimeError("WireGuard mesh IP pool exhausted")
        allocated.add(str(host))
        self._state["allocated_ips"] = list(allocated)
        return str(host)

    def _apply_peer(
        self,
        public_key: str,
        ip: str,
        endpoint: str | None,
        preshared_key: str,
    ) -> None:
        cmd = ["wg", "set", self.INTERFACE, "peer", public_key, "allowed-ips", f"{ip}/32"]
        if endpoint:
            cmd += ["endpoint", endpoint]
        if preshared_key:
            cmd += ["preshared-key", "/dev/stdin"]
        self._run_cmd(cmd)

    def _load_state(self) -> dict[str, Any]:
        f = self._state_dir / "mesh-state.json"
        if f.exists():
            return json.loads(f.read_text())
        return {"peers": {}, "allocated_ips": []}

    def _save_state(self) -> None:
        f = self._state_dir / "mesh-state.json"
        f.write_text(json.dumps(self._state, indent=2))

    @staticmethod
    def _default_run(cmd: list[str]) -> None:
        subprocess.run(cmd, check=True, capture_output=True)
