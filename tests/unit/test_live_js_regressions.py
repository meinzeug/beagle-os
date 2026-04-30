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


def test_reconnect_delay_caps_at_15_seconds() -> None:
    """Backoff must cap at 15 000 ms to avoid infinite-silence after host reboot."""
    js = LIVE_JS.read_text(encoding="utf-8")
    # min(15000, ...) is the cap pattern used in scheduleReconnect
    assert "Math.min(15000," in js
    # Initial delay must not be zero (instant flood would be harmful)
    assert "reconnectDelayMs = 1500" in js


def test_reconnect_resets_delay_on_success() -> None:
    """After a successful hello event, backoff delay must reset to initial value."""
    js = LIVE_JS.read_text(encoding="utf-8")
    # The hello handler must reset the delay
    assert "reconnectDelayMs = 1500;" in js
    # And set liveFeedConnected = true
    assert "state.liveFeedConnected = true;" in js


def test_live_feed_connected_false_on_sse_error() -> None:
    """state.liveFeedConnected must be cleared immediately on SSE error (before reconnect)."""
    js = LIVE_JS.read_text(encoding="utf-8")
    # onerror handler must clear the state
    assert "state.liveFeedConnected = false;" in js


def test_sse_url_includes_access_token() -> None:
    """SSE URL must include access_token param (auth for EventSource which can't set headers)."""
    js = LIVE_JS.read_text(encoding="utf-8")
    assert "parsed.searchParams.set('access_token', state.token);" in js


def test_disconnect_clears_reconnect_timer() -> None:
    """disconnectLiveUpdates() must cancel any pending reconnect timer."""
    js = LIVE_JS.read_text(encoding="utf-8")
    assert "window.clearTimeout(reconnectTimer);" in js
    assert "reconnectTimer = null;" in js
    assert "disconnectLiveUpdates" in js


def test_connect_guard_prevents_double_connection() -> None:
    """connectLiveUpdates() must guard against opening a second EventSource."""
    js = LIVE_JS.read_text(encoding="utf-8")
    # Early return if source already exists
    assert "if (source) {" in js
    assert "return;" in js


def test_scheduleReconnect_skips_when_no_token() -> None:
    """No reconnect attempt if the user has no token (logged out)."""
    js = LIVE_JS.read_text(encoding="utf-8")
    assert "if (reconnectTimer || !state.token) {" in js