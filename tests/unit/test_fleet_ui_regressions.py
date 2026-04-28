from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "website" / "index.html"
DASHBOARD_JS = ROOT / "website" / "ui" / "dashboard.js"
MAIN_JS = ROOT / "website" / "main.js"
FLEET_JS = ROOT / "website" / "ui" / "fleet_health.js"


def test_dashboard_wires_fleet_health_panel() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    dashboard = DASHBOARD_JS.read_text(encoding="utf-8")
    main = MAIN_JS.read_text(encoding="utf-8")

    assert 'id="fleet-health-panel"' in html
    assert "renderFleetHealth() {}" in dashboard
    assert "dashboardHooks.renderFleetHealth();" in dashboard
    assert "configureFleetHealth" in main
    assert "renderFleetHealth" in main


def test_fleet_health_uses_fleet_registry_api_surface() -> None:
    js = FLEET_JS.read_text(encoding="utf-8")

    assert "request('/fleet/devices')" in js
    assert "request('/fleet/policies')" in js
    assert "request('/fleet/policies/assignments')" in js
    assert "/fleet/devices/${encodeURIComponent(deviceId)}/effective-policy" in js
    assert "request('/fleet/anomalies')" in js
    assert "request('/fleet/maintenance')" in js
    assert "data-fleet-action" in js
    assert "data-mdm-action" in js
    assert "triggerDeviceAction" in js
    assert "savePolicy" in js
    assert "assignPolicy" in js
    assert "assignBulkDevices" in js
    assert "locationTreeSection" in js
    assert "requestConfirm" in js
    assert "Remote-Wipe anfordern" in js
    assert "MDM Policies" in js
    assert "Policy Editor" in js
    assert "Effective Policy Preview" in js
    assert "Bulk Device IDs" in js
    assert "Standort- und Gruppenansicht" in js
    assert "Unbekannter Standort" in js
    assert "ohne Gruppe" in js
    assert "Keine Geräte erfasst." in js
    assert "Standort / Gruppe" in js
    assert "Lade Fleet-Status" in js
