from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIVE_JS = ROOT / "website" / "ui" / "live.js"


def test_live_updates_surface_reconnect_banner_and_activity_log() -> None:
    js = LIVE_JS.read_text(encoding="utf-8")

    assert "Live-Updates getrennt. Neuer Verbindungsversuch laeuft ..." in js
    assert "liveHooks.addToActivityLog('live-reconnect', null, 'warn', 'SSE getrennt, Reconnect geplant');" in js
    assert "source.onerror = () => {" in js
    assert "scheduleReconnect();" in js