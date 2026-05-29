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


def test_settings_updates_panel_mentions_background_system_update_automation() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "Systemupdates koennen sofort manuell gestartet werden" in js
    assert "regelmaessig im Hintergrund installiert" in js
    assert 'id="upd-policy-message"' in html


def test_settings_updates_panel_uses_sse_for_live_status() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "new EventSource(streamUrl.toString())" in js
    assert "apiBase() + '/settings/updates/stream'" in js
    assert "renderUpdateStreamPayload" in js
    assert "apt-get update" not in js
    assert 'id="update-live-state"' in html


def test_settings_updates_panel_shows_installed_and_remote_versions() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "formatProductVersion(status.installed_version || '')" in js
    assert "formatProductVersion(status.remote_version || '')" in js
    assert "formatProductVersion(status.target_version || status.remote_version || '')" in js
    assert 'id="repo-update-current"' in html
    assert 'id="repo-update-target"' in html
    assert 'id="repo-update-position"' in html
    assert 'id="update-center-installed-version"' in html
    assert 'id="update-center-position"' in html
    assert 'id="repo-update-current-commit"' in html
    assert 'id="repo-update-remote-version"' in html
    assert 'id="update-center-remote-version"' in html
    assert "text('update-center-installed-version', installedVersion);" in js
    assert "text('update-center-remote-version', targetLabel);" in js
    assert "text('update-center-position', position.shortLabel);" in js


def test_settings_updates_panel_exposes_stable_rolling_channel_switch() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="repo-update-channel"' in html
    assert 'data-repo-update-channel="stable"' in html
    assert 'data-repo-update-channel="rolling"' in html
    assert 'id="repo-update-channel-advisory"' in html
    assert "function setRepoUpdateChannel(channel)" in js
    assert "function describeRepoUpdatePosition(config, status, installedVersion, targetVersion)" in js
    assert "Kein Downgrade wird ausgefuehrt" in js
    assert "channel: normalizeUpdateChannel(qs('repo-update-channel')" in js
    assert "saveRepoAutoUpdate();" in js


def test_artifact_running_build_message_does_not_show_blocked_gate_as_primary() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "Public-Gate wartet auf den laufenden Build" in js
    assert "Artefakte werden gerade neu gebaut" in js
    assert "runningRefresh ? 'Nach Build'" in js


def test_update_sse_access_token_is_redacted_from_control_plane_logs() -> None:
    handler = CONTROL_PLANE_HANDLER.read_text(encoding="utf-8")

    assert "_redact_request_target" in handler
    assert r"access_token|token|refresh_token)=)([^&\s]+)" in handler
    assert "path=_redact_request_target" in handler
    assert "structured_logger().log_message(fmt, *safe_args)" in handler


def test_stream_config_endpoint_auth_runs_before_global_get_auth_guard() -> None:
    handler = CONTROL_PLANE_HANDLER.read_text(encoding="utf-8")

    stream_index = handler.index("if stream_http_surface_service().handles_get(path):")
    global_auth_index = handler.rindex("if not self._is_authenticated():")

    assert stream_index < global_auth_index


def test_index_html_avoids_inline_styles_for_csp() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "style=" not in html
    assert 'class="card compact-card settings-modal-card"' in html
    assert 'class="settings-switch settings-switch-spaced"' in html
