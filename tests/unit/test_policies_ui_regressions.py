from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICIES_JS = ROOT / "website" / "ui" / "policies.js"
KIOSK_JS = ROOT / "website" / "ui" / "kiosk_controller.js"
INDEX_HTML = ROOT / "website" / "index.html"


def test_pool_wizard_collects_pool_type_gpu_and_kiosk_fields() -> None:
    js = POLICIES_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "pool_type: poolType" in js
    assert "gpu_class: gpuClass" in js
    assert "session_time_limit_minutes" in js
    assert "session_cost_per_minute" in js
    assert "session_extension_options_minutes" in js
    assert "Gaming-Pools brauchen eine GPU-Klasse." in js
    assert "Kiosk-Pools brauchen ein Session-Limit > 0 Minuten." in js
    assert "Kiosk-Pools brauchen mindestens eine Verlaengerungsstufe." in js
    assert 'select id="pool-gpu-class"' in html
    assert 'id="pool-session-extensions"' in html
    assert "renderPoolGpuClassOptions" in js
    assert "request('/virtualization/mdev/types')" in js
    assert "request('/virtualization/sriov')" in js
    assert "Keine live erkannte Passthrough-GPU-Klasse gefunden." in js
    assert "normalizedGpuModelToken" in js


def test_policies_panel_renders_kiosk_controller() -> None:
    js = POLICIES_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "renderKioskController" in js
    assert "kiosk-controller-panel" in html


def test_policies_panel_renders_gaming_metrics_dashboard() -> None:
    js = POLICIES_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "renderGamingMetricsDashboard" in js
    assert "refreshGamingMetricsDashboard" in js
    assert "request('/gaming/metrics'" in js
    assert "gaming-metrics-dashboard" in html
    assert "gaming-metrics-refresh" in html


def test_policies_panel_renders_session_handover_dashboard() -> None:
    js = POLICIES_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "renderSessionHandoverDashboard" in js
    assert "refreshSessionHandoverDashboard" in js
    assert "request('/sessions/handover'" in js
    assert "Session-Handover-Daten konnten nicht geladen werden" in js
    assert "session-handover-dashboard" in html
    assert "session-handover-refresh" in html


def test_kiosk_controller_uses_request_api_signature() -> None:
    js = KIOSK_JS.read_text(encoding="utf-8")

    assert "request('/pools/kiosk/sessions')" in js
    assert "request(`/pools/kiosk/sessions/${vmId}/extend`" in js
    assert "request(`/pools/kiosk/sessions/${vmId}/end`, { method: 'POST' })" in js
    assert "if (!state.token)" in js
    assert "session_extension_options_minutes" in js
    assert "extensionButtons(session)" in js
    assert ">+${escapeHtml(String(minutes))}m</button>" in js
    assert "window_title" in js
    assert "gpu_util_pct" in js
    assert "gpu_temp_c" in js
    assert "encoder_load" in js
    assert "dropped_frames" in js
    assert "Beenden + Reset" in js
