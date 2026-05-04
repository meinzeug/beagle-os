from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "apply-beagle-wireguard.sh"


def test_wireguard_script_renders_registered_mesh_peers_into_server_config() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'WG_MESH_STATE_FILE="${BEAGLE_WIREGUARD_MESH_STATE_FILE:-/var/lib/beagle/beagle-manager/wireguard-mesh/mesh-state.json}"' in script
    assert 'WG_ALLOWED_IPS="${BEAGLE_WIREGUARD_ALLOWED_IPS:-10.88.0.0/16,192.168.123.0/24}"' in script
    assert 'WG_VM_BRIDGE_CIDRS="${BEAGLE_WIREGUARD_VM_BRIDGE_CIDRS:-192.168.123.0/24,192.168.122.0/24}"' in script
    assert 'bridge_masquerade_rule="ip saddr ${WG_SUBNET} ip daddr != { ${bridge_cidr_set} } oifname { ${bridge_set} } masquerade"' in script
    assert "ensure_libvirt_wireguard_no_snat_rules" in script
    assert "beagle-wireguard-no-snat-from-vm-bridges" in script
    assert "append_mesh_peers()" in script
    assert 'print(f"AllowedIPs = {assigned_ip}/32")' in script
    assert 'append_mesh_peers >>"$WG_CONF"' in script
