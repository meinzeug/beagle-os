from __future__ import annotations

import sys
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from auth_session_http_surface import AuthSessionHttpSurfaceService


class _AuthSessionStub:
    def role_permissions(self, role: str) -> set[str]:
        if role == "kiosk_operator":
            return {"vm:read", "vm:power", "kiosk:operate"}
        return set()

    def onboarding_status(self, *, bootstrap_username: str, bootstrap_disabled: bool):
        return {"pending": False, "completed": True}


class _IdpRegistryStub:
    def payload(self):
        return {"ok": True, "providers": []}


def _service(principal):
    return AuthSessionHttpSurfaceService(
        auth_session=_AuthSessionStub(),
        identity_provider_registry=_IdpRegistryStub(),
        oidc_service=object(),
        saml_service=object(),
        permission_catalog={},
        auth_bootstrap_username="admin",
        auth_bootstrap_disabled=False,
        auth_principal=lambda: principal,
        remote_addr=lambda: "127.0.0.1",
        user_agent=lambda: "pytest",
        read_json_body=lambda: {},
        has_body=lambda: False,
        check_login_guard=lambda username: (True, 0),
        record_login_success=lambda username: None,
        record_login_failure=lambda username: None,
        refresh_cookie_header=lambda token: ("Set-Cookie", "refresh=1"),
        clear_refresh_cookie_header=lambda: ("Set-Cookie", "refresh=; Max-Age=0"),
        read_refresh_cookie=lambda: "",
        bearer_token=lambda: "",
        read_raw_body=lambda size: b"",
        audit_event=lambda *args, **kwargs: None,
    )


def test_auth_me_includes_effective_permissions() -> None:
    service = _service(
        {
            "username": "kiosk-op",
            "role": "kiosk_operator",
            "auth_type": "session",
        }
    )

    response = service.route_get("/api/v1/auth/me")

    assert int(response["status"]) == 200
    user = response["payload"]["user"]
    assert user["username"] == "kiosk-op"
    assert user["role"] == "kiosk_operator"
    assert sorted(user["permissions"]) == ["kiosk:operate", "vm:power", "vm:read"]

