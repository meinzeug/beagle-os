from __future__ import annotations

import json
import sys
from pathlib import Path


RUNTIME_DIR = Path(__file__).resolve().parents[2] / "thin-client-assistant" / "runtime"
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from apply_enrollment_config import apply_enrollment_config, apply_runtime_usb_config


def test_apply_enrollment_config_persists_device_id(tmp_path: Path) -> None:
    response = tmp_path / "response.json"
    config = tmp_path / "thinclient.conf"
    credentials = tmp_path / "credentials.env"
    enrollment_conf = tmp_path / "enrollment.conf"
    response.write_text(
        json.dumps(
            {
                "config": {
                    "device_id": "endpoint-001",
                    "beagle_manager_token": "manager-token",
                    "beagle_manager_url": "https://srv1.beagle-os.com",
                    "beagle_stream_mode": "broker",
                    "beagle_stream_allocation_id": "vm-100",
                }
            }
        ),
        encoding="utf-8",
    )
    config.write_text("", encoding="utf-8")
    credentials.write_text("", encoding="utf-8")

    apply_enrollment_config(response, config, credentials, enrollment_conf)

    config_text = config.read_text(encoding="utf-8")
    assert 'PVE_THIN_CLIENT_BEAGLE_DEVICE_ID="endpoint-001"' in config_text
    assert 'PVE_THIN_CLIENT_BEAGLE_MANAGER_URL="https://srv1.beagle-os.com"' in config_text
    assert 'PVE_THIN_CLIENT_CONNECTION_METHOD="broker"' in config_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST=""' in config_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BIN="beagle-stream"' in config_text
    assert enrollment_conf.read_text(encoding="utf-8").splitlines() == [
        'control_plane="https://srv1.beagle-os.com"',
        'enrollment_token="manager-token"',
        'device_id="endpoint-001"',
        'pool_id="vm-100"',
    ]
    assert oct(enrollment_conf.stat().st_mode & 0o777) == "0o640"
    assert oct(enrollment_conf.parent.stat().st_mode & 0o777) == "0o750"


def test_apply_runtime_usb_config_preserves_existing_credentials(tmp_path: Path) -> None:
    response = tmp_path / "response.json"
    config = tmp_path / "thinclient.conf"
    response.write_text(
        json.dumps(
            {
                "runtime_config": {
                    "usb_enabled": True,
                    "usb_tunnel_host": "srv1.beagle-os.com",
                    "usb_tunnel_user": "beagle-tunnel",
                    "usb_tunnel_port": 43100,
                    "usb_audio_input_port": 43200,
                    "usb_tunnel_attach_host": "192.168.123.1",
                    "usb_tunnel_private_key": "PRIVATE-KEY\n",
                    "usb_tunnel_known_host": "srv1 ssh-ed25519 AAAA",
                }
            }
        ),
        encoding="utf-8",
    )
    config.write_text(
        'PVE_THIN_CLIENT_BEAGLE_MANAGER_URL="https://manager.example"\n'
        'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST="keep-me"\n'
        'PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_HOST=""\n',
        encoding="utf-8",
    )

    assert apply_runtime_usb_config(response, config) is True
    assert apply_runtime_usb_config(response, config) is False

    config_text = config.read_text(encoding="utf-8")
    assert 'PVE_THIN_CLIENT_BEAGLE_MANAGER_URL="https://manager.example"' in config_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST="keep-me"' in config_text
    assert 'PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_HOST="srv1.beagle-os.com"' in config_text
    assert 'PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PORT="43100"' in config_text
    assert 'PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_PORT="43200"' in config_text
    assert (tmp_path / "usb-tunnel.key").read_text(encoding="utf-8") == "PRIVATE-KEY\n"
    assert oct((tmp_path / "usb-tunnel.key").stat().st_mode & 0o777) == "0o600"
    assert (tmp_path / "usb-tunnel-known_hosts").read_text(encoding="utf-8") == "srv1 ssh-ed25519 AAAA\n"
