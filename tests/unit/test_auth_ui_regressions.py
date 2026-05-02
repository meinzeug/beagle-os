from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "website" / "index.html"
PANELS_JS = ROOT / "website" / "ui" / "panels.js"
EVENTS_JS = ROOT / "website" / "ui" / "events.js"


def test_auth_and_onboarding_fields_are_wrapped_in_forms() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert '<form id="auth-form">' in html
    assert '<form id="onboarding-form">' in html
    assert 'id="auth-password"' in html
    assert 'id="onboarding-password"' in html


def test_panels_use_modal_state_helper_with_inert_and_blur() -> None:
    js = PANELS_JS.read_text(encoding="utf-8")

    assert "function setModalState(modal, open)" in js
    assert "modal.contains(active)" in js
    assert "active.blur()" in js
    assert "modal.inert = !open" in js


def test_auth_submit_is_centralized_and_prevents_native_form_submit() -> None:
    js = EVENTS_JS.read_text(encoding="utf-8")

    assert "const authForm = qs('auth-form');" in js
    assert "function submitAuthLogin()" in js
    assert "authForm.addEventListener('submit', (event) => {" in js
    assert "event.preventDefault();" in js
    assert "Anmeldung erfolgreich, aber das Dashboard konnte nicht geladen werden:" in js
