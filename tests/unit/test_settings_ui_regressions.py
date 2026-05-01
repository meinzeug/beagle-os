from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SETTINGS_JS = ROOT / "website" / "ui" / "settings.js"
INDEX_HTML = ROOT / "website" / "index.html"
CONTROL_PLANE_HANDLER = ROOT / "beagle-host" / "services" / "control_plane_handler.py"


def test_settings_ipam_requests_use_api_relative_paths() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "request('/network/ipam/zones')" in js
    assert "request('/network/ipam/zones/' + encodeURIComponent(zoneId) + '/leases')" in js
    assert "request('/api/v1/network/ipam/zones')" not in js


def test_settings_updates_panel_states_apt_policy_as_manual_only() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "APT-Updates bleiben absichtlich manuell" in js
    assert "Installation erfolgt bewusst erst nach Klick." in js
    assert 'id="upd-policy-message"' in html


def test_settings_updates_panel_uses_sse_for_live_status() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "new EventSource(streamUrl.toString())" in js
    assert "apiBase() + '/settings/updates/stream'" in js
    assert "renderUpdateStreamPayload" in js
    assert "apt-get update" not in js
    assert 'id="update-live-state"' in html


def test_artifact_running_build_message_does_not_show_blocked_gate_as_primary() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "Public-Gate wartet auf den laufenden Build" in js
    assert "Artefakte werden gerade neu gebaut" in js
    assert "runningRefresh ? 'Nach Build'" in js


def test_update_sse_access_token_is_redacted_from_control_plane_logs() -> None:
    handler = CONTROL_PLANE_HANDLER.read_text(encoding="utf-8")

    assert "_redact_request_target" in handler
    assert "access_token|token|refresh_token" in handler
    assert "path=_redact_request_target" in handler
    assert "structured_logger().log_message(fmt, *safe_args)" in handler
