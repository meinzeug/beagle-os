from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SETTINGS_JS = ROOT / "website" / "ui" / "settings.js"
INDEX_HTML = ROOT / "website" / "index.html"


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
