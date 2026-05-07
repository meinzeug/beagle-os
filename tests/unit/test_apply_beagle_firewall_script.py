from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "apply-beagle-firewall.sh"


def test_firewall_includes_wireguard_rules_when_enabled(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    nft_conf = tmp_path / "nftables.conf"
    nft_rules = tmp_path / "beagle-firewall.nft"
    config_dir.mkdir(parents=True)
    (config_dir / "beagle-manager.env").write_text(
        "\n".join(
            [
                "BEAGLE_WIREGUARD_ENABLED=1",
                "BEAGLE_WIREGUARD_INTERFACE=wg-beagle",
                "BEAGLE_WIREGUARD_PORT=51820",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PVE_DCV_CONFIG_DIR"] = str(config_dir)
    env["BEAGLE_NFTABLES_CONF"] = str(nft_conf)
    env["BEAGLE_FIREWALL_RULE_FILE"] = str(nft_rules)

    subprocess.run(["bash", str(SCRIPT), "--write-only"], cwd=str(ROOT_DIR), env=env, check=True)

    rendered = nft_rules.read_text(encoding="utf-8")
    assert 'udp dport 51820' in rendered
    assert 'iifname "wg-beagle" accept' in rendered


def test_firewall_script_adds_libvirt_forward_compatibility_for_wireguard() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "ensure_libvirt_wireguard_forward_rules()" in script
    assert 'nft insert rule ip filter FORWARD iifname "$wg_iface" oifname "$bridge" accept comment "beagle-wireguard-forward-to-${bridge}"' in script
    assert 'nft insert rule ip filter FORWARD iifname "$bridge" oifname "$wg_iface" accept comment "beagle-wireguard-forward-from-${bridge}"' in script
    assert 'nft insert rule ip filter LIBVIRT_FWI iifname "$wg_iface" oifname "$bridge" accept comment "beagle-wireguard-to-${bridge}"' in script
    assert 'nft insert rule ip filter LIBVIRT_FWO iifname "$bridge" oifname "$wg_iface" accept comment "beagle-wireguard-from-${bridge}"' in script


def test_firewall_defensively_removes_legacy_public_stream_dnat_table() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'LEGACY_PUBLIC_STREAM_TABLE="${BEAGLE_LEGACY_PUBLIC_STREAM_TABLE:-beagle_stream}"' in script
    assert 'nft delete table inet "$LEGACY_PUBLIC_STREAM_TABLE" >/dev/null 2>&1 || true' in script


def test_firewall_write_only_includes_public_stream_drop_guard(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    nft_conf = tmp_path / "nftables.conf"
    nft_rules = tmp_path / "beagle-firewall.nft"
    config_dir.mkdir(parents=True)

    env = os.environ.copy()
    env["PVE_DCV_CONFIG_DIR"] = str(config_dir)
    env["BEAGLE_NFTABLES_CONF"] = str(nft_conf)
    env["BEAGLE_FIREWALL_RULE_FILE"] = str(nft_rules)
    env["BEAGLE_PUBLIC_STREAM_GUARD_ADDR"] = "46.4.96.80"

    subprocess.run(["bash", str(SCRIPT), "--write-only"], cwd=str(ROOT_DIR), env=env, check=True)

    rendered = nft_rules.read_text(encoding="utf-8")
    assert "type filter hook prerouting priority -110; policy accept;" in rendered
    assert "ip daddr 46.4.96.80 tcp dport { 49995, 50000, 50001, 50021 } drop" in rendered
    assert "ip daddr 46.4.96.80 udp dport { 50009, 50010, 50011, 50012, 50013, 50014, 50015 } drop" in rendered
