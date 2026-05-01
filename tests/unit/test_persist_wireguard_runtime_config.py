from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

RUNTIME_DIR = ROOT_DIR / "thin-client-assistant" / "runtime"
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from persist_wireguard_runtime_config import persist_wireguard_runtime_config


class PersistWireguardRuntimeConfigTests(unittest.TestCase):
    def test_persists_wireguard_fields_to_runtime_env_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "thinclient.conf"
            credentials_path = root / "credentials.env"
            config_path.write_text('PVE_THIN_CLIENT_BEAGLE_MANAGER_URL="https://srv1.example/beagle-api"\n', encoding="utf-8")
            credentials_path.write_text('PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN="token"\n', encoding="utf-8")

            persist_wireguard_runtime_config(
                config_path=config_path,
                credentials_path=credentials_path,
                interface_ip="10.88.1.1/32",
                dns="1.1.1.1",
                server_public_key="server-pub",
                server_endpoint="vpn.example:51820",
                allowed_ips="0.0.0.0/0 192.168.123.0/24",
                private_key="private-key",
                preshared_key="psk",
                keepalive="25",
            )

            config_text = config_path.read_text(encoding="utf-8")
            credentials_text = credentials_path.read_text(encoding="utf-8")

            self.assertIn('PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_ADDRESS="10.88.1.1/32"', config_text)
            self.assertIn('PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PUBLIC_KEY="server-pub"', config_text)
            self.assertIn('PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_ENDPOINT="vpn.example:51820"', config_text)
            self.assertIn('PVE_THIN_CLIENT_BEAGLE_EGRESS_ALLOWED_IPS="0.0.0.0/0 192.168.123.0/24"', config_text)
            self.assertIn('PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PRIVATE_KEY="private-key"', credentials_text)
            self.assertIn('PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PRESHARED_KEY="psk"', credentials_text)


if __name__ == "__main__":
    unittest.main()
