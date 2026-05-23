from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICE_REGISTRY = ROOT / "beagle-host" / "services" / "service_registry.py"


def test_pair_token_uses_vm_stream_server_token_as_pairing_secret() -> None:
    code = SERVICE_REGISTRY.read_text(encoding="utf-8")

    assert 'pairing_secret = str(vm_secret.get("beagle_stream_server_token", "") or "").strip()' in code
    assert 'if not pairing_secret:' in code
    assert 'rotated = rotate_beagle_stream_server_token(vm)' in code
    assert '"pairing_secret": pairing_secret,' in code
