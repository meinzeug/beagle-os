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
    response.write_text(
        json.dumps(
            {
                "config": {
                    "device_id": "endpoint-001",
                    "beagle_manager_token": "manager-token",
                    "moonlight_host": "srv1.beagle-os.com",
                }
            }
        ),
        encoding="utf-8",
    )
    config.write_text("", encoding="utf-8")
    credentials.write_text("", encoding="utf-8")

    apply_enrollment_config(response, config, credentials)

    config_text = config.read_text(encoding="utf-8")
    assert 'PVE_THIN_CLIENT_BEAGLE_DEVICE_ID="endpoint-001"' in config_text
