from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "website" / "index.html"
IAM_JS = ROOT / "website" / "ui" / "iam.js"


def test_iam_panel_contains_detail_drawer_sessions_tenants_and_idp_sections() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="iam-user-detail"' in html
    assert 'id="iam-user-tenant"' in html
    assert 'id="iam-session-filter-user"' in html
    assert 'id="iam-session-filter-tenant"' in html
    assert 'id="iam-sessions-body"' in html
    assert 'id="iam-tenants-list"' in html
    assert 'id="iam-idp-cards"' in html
    assert 'id="iam-scim-status"' in html
    assert 'id="iam-role-permission-search"' in html
    assert 'id="iam-role-diff"' in html


def test_iam_js_contains_user_role_and_session_guardrails() -> None:
    js = IAM_JS.read_text(encoding="utf-8")

    assert "function roleProtected(role)" in js
    assert "viewer', 'kiosk_operator', 'ops', 'admin', 'superadmin'" in js
    assert "Sessions widerrufen" in js
    assert "Passwort zuruecksetzen" in js
    assert "admin_revoke_from_web_ui" in js
    assert "request('/auth/users/' + encodeURIComponent(username) + '/revoke-sessions'" in js
    assert "request('/auth/sessions/' + encodeURIComponent(jti), { method: 'DELETE' })" in js
    assert "Eingebaute Rollen sind geschuetzt" in js


def test_iam_js_contains_idp_scim_tenant_empty_states() -> None:
    js = IAM_JS.read_text(encoding="utf-8")

    assert "Keine Identity Provider konfiguriert. Nur lokale Anmeldung aktiv." in js
    assert "Bearer Token wird ueber <code>BEAGLE_SCIM_BEARER_TOKEN</code> gesetzt." in js
    assert "Tenants konnten nicht geladen werden." in js
    assert "Keine Tenants konfiguriert." in js
    assert "SCIM deaktiviert" in js
    assert "SP-Metadata unter <code>" in js
    assert "Redirect URI konfigurieren im IdP: <code>" in js
