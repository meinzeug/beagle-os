from __future__ import annotations

import json
import sys
from pathlib import Path


RUNTIME_DIR = Path(__file__).resolve().parents[2] / "thin-client-assistant" / "runtime"
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from apply_enrollment_config import apply_enrollment_config


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
