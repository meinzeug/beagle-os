from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROVISIONING_PY = ROOT / "beagle-host" / "services" / "ubuntu_beagle_provisioning.py"


def test_provisioning_status_messages_reference_beaglestream_server() -> None:
    content = PROVISIONING_PY.read_text(encoding="utf-8")

    assert "LightDM und BeagleStream Server werden im Guest eingerichtet." in content
    assert "LightDM und BeagleStream Server zu provisionieren." in content
