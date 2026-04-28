from __future__ import annotations

import sys
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from auth_session_http_surface import AuthSessionHttpSurfaceService


class _AuthSessionStub:
    def __init__(self) -> None:
        self._require_totp = False

    def role_permissions(self, role: str) -> set[str]:
        if role == "kiosk_operator":
            return {"vm:read", "vm:power", "kiosk:operate"}
        return set()

    def onboarding_status(self, *, bootstrap_username: str, bootstrap_disabled: bool):
        return {"pending": False, "completed": True}

    def login(self, *, username: str, password: str, totp_code: str = "", remote_addr: str = "", user_agent: str = ""):
        if self._require_totp and not totp_code:
            raise PermissionError("invalid one-time code")
        return {
            "ok": True,
            "access_token": "access",
            "refresh_token": "refresh",
            "token_type": "Bearer",
            "expires_in": 900,
            "user": {"username": username, "role": "viewer", "totp_enabled": self._require_totp},
        }


class _FailingAuditHooksStub:
    def __call__(self, *args, **kwargs):
        raise RuntimeError("audit store unavailable")


class _IdpRegistryStub:
    def payload(self):
        return {"ok": True, "providers": []}


def _service(principal, *, auth_session=None, read_json_body=None):
    return AuthSessionHttpSurfaceService(
        auth_session=auth_session or _AuthSessionStub(),
        identity_provider_registry=_IdpRegistryStub(),
        oidc_service=object(),
        saml_service=object(),
        permission_catalog={},
        auth_bootstrap_username="admin",
        auth_bootstrap_disabled=False,
        auth_principal=lambda: principal,
        remote_addr=lambda: "127.0.0.1",
        user_agent=lambda: "pytest",
        read_json_body=read_json_body or (lambda: {}),
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


def test_auth_login_returns_invalid_totp_when_code_missing() -> None:
    auth_session = _AuthSessionStub()
    auth_session._require_totp = True
    service = _service(
        None,
        auth_session=auth_session,
        read_json_body=lambda: {"username": "alice", "password": "secret123"},
    )

    response = service.route_post("/api/v1/auth/login")

    assert int(response["status"]) == 401
    assert response["payload"]["code"] == "invalid_totp"


def test_auth_login_ignores_audit_side_effect_failures() -> None:
    service = _service(
        None,
        read_json_body=lambda: {"username": "alice", "password": "secret123"},
    )
    service._audit_event = _FailingAuditHooksStub()  # noqa: SLF001
    service._record_login_success = _FailingAuditHooksStub()  # noqa: SLF001

    response = service.route_post("/api/v1/auth/login")

    assert int(response["status"]) == 200
    assert response["payload"]["ok"] is True
