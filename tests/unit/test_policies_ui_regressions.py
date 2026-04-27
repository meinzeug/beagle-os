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
    assert "humanizeGpuModelLabel" in js


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


def test_policies_panel_renders_pool_entitlement_editor() -> None:
    js = POLICIES_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "refreshSelectedPoolEntitlements" in js
    assert "mutateSelectedPoolEntitlements" in js
    assert "poolEntitlements" in js
    assert 'id="pool-entitlement-refresh"' in html
    assert 'id="pool-entitlement-user-input"' in html
    assert 'id="pool-entitlement-group-input"' in html
    assert 'id="pool-entitlement-users"' in html
    assert 'id="pool-entitlement-groups"' in html
    assert 'id="pool-entitlement-status"' in html
    assert "data-pool-entitlement-remove-user" in js
    assert "data-pool-entitlement-remove-group" in js


def test_policies_panel_has_hero_and_catalog_summary_layout() -> None:
    js = POLICIES_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = (ROOT / "website" / "styles" / "panels" / "_policies.css").read_text(encoding="utf-8")

    assert "renderPoliciesHero" in js
    assert "renderPoolCatalogSummary" in js
    assert "renderTemplateLibrary" in js
    assert 'class="policies-hero"' in html
    assert 'id="policies-hero-badges"' in html
    assert 'class="policies-workspace"' in html
    assert 'class="policies-main"' in html
    assert 'class="policies-side"' in html
    assert 'id="pool-catalog-summary"' in html
    assert 'id="template-library-list"' in html
    assert 'id="template-library-summary"' in html
    assert ".policies-workspace" in css
    assert ".policies-hero" in css
    assert ".pool-catalog-summary" in css
    assert ".template-library-grid" in css
    assert ".template-card" in css
    assert ".policy-list" in css
    assert ".policy-card:hover" in css


def test_policies_panel_renders_structured_policy_editor() -> None:
    js = POLICIES_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = (ROOT / "website" / "styles" / "panels" / "_policies.css").read_text(encoding="utf-8")

    assert "collectPolicyStructuredProfile" in js
    assert "populatePolicyStructuredProfile" in js
    assert "syncPolicyProfilePreview" in js
    assert 'id="policy-structured-grid"' in html
    assert 'id="policy-beagle-role"' in html
    assert 'id="policy-assigned-vmid"' in html
    assert 'id="policy-stream-host"' in html
    assert 'id="policy-update-enabled"' in html
    assert 'id="policy-egress-domains"' in html
    assert 'readonly placeholder=\'{"assigned_target":{"vmid":100},"beagle_role":"endpoint"}\'' in html or 'id="policy-profile"' in html
    assert ".policy-structured-grid" in css
    assert ".policy-summary-grid" in css


def test_policies_panel_renders_template_actions() -> None:
    js = POLICIES_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "useSelectedTemplate" in js
    assert "rebuildSelectedTemplate" in js
    assert "deleteSelectedTemplate" in js
    assert "deleteSelectedPool" in js
    assert "scaleSelectedPool" in js
    assert "recycleSelectedPoolVm" in js
    assert "openTemplateBuilderModal" in js
    assert 'data-template-use="' in js
    assert 'data-template-rebuild="' in js
    assert 'data-template-delete="' in js
    assert 'data-pool-delete="' in js
    assert 'data-pool-focus="' in js
    assert 'data-pool-vm-recycle="' in js
    assert 'id="pool-scale-target"' in html
    assert 'id="pool-scale-apply"' in html


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
