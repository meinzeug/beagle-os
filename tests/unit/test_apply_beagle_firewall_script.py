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
