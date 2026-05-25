from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_pairing.sh"


def test_broker_pairing_bypass_requires_explicit_override() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'connection_method="$(beagle_stream_connection_method 2>/dev/null || true)"' in script
    assert 'if [[ "$connection_method" == "broker" && "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BROKER_PAIRING_BYPASS:-0}" == "1" ]]; then' in script
    assert 'beagle_stream_client_pair_log "pairing gate bypassed in broker mode (override=1)"' in script
    assert "return 0" in script
