from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable

try:
    from saml_service import SamlAssertionError  # type: ignore[import]
except ImportError:  # saml not installed in all environments
    class SamlAssertionError(Exception):  # type: ignore[no-redef]
        pass


class AuthSessionHttpSurfaceService:
    """Handles auth session endpoints: login, logout, refresh, me, onboarding, OIDC, SAML.

    Separated from AuthHttpSurfaceService (which handles user/role CRUD) because these
    endpoints are unauthenticated entry-points and require special response types
    (redirects, cookies, bytes).
    """

    _GET_PATHS = frozenset({
        "/api/v1/auth/me",
        "/api/v1/auth/onboarding/status",
        "/api/v1/auth/providers",
        "/api/v1/auth/permission-tags",
        "/api/v1/auth/oidc/login",
        "/api/v1/auth/oidc/callback",
        "/api/v1/auth/saml/login",
        "/api/v1/auth/saml/metadata",
    })

    _POST_PATHS = frozenset({
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/onboarding/complete",
        "/api/v1/auth/saml/callback",
    })

    def __init__(
        self,
        *,
        auth_session: Any,
        identity_provider_registry: Any,
        oidc_service: Any,
        saml_service: Any,
        permission_catalog: dict[str, Any],
        auth_bootstrap_username: str,
        auth_bootstrap_disabled: bool,
        # Per-request callables
        auth_principal: Callable[[], dict[str, Any] | None],
        remote_addr: Callable[[], str],
        user_agent: Callable[[], str],
        read_json_body: Callable[[], dict[str, Any]],
        has_body: Callable[[], bool],
        check_login_guard: Callable[[str], tuple[bool, int]],
        record_login_success: Callable[[str], None],
        record_login_failure: Callable[[str], None],
        refresh_cookie_header: Callable[[str], tuple[str, str]],
        clear_refresh_cookie_header: Callable[[], tuple[str, str]],
        read_refresh_cookie: Callable[[], str],
        bearer_token: Callable[[], str],
        read_raw_body: Callable[[int], bytes],
        audit_event: Callable[..., None],
        scim_enabled: Callable[[], bool] | None = None,
        public_manager_url: str = "",
    ) -> None:
        self._auth_session = auth_session
        self._idp_registry = identity_provider_registry
        self._oidc = oidc_service
        self._saml = saml_service
        self._permission_catalog = permission_catalog
        self._bootstrap_username = auth_bootstrap_username
        self._bootstrap_disabled = auth_bootstrap_disabled
        self._scim_enabled = scim_enabled or (lambda: False)
        self._public_manager_url = str(public_manager_url or "").strip()
        # Per-request
        self._auth_principal = auth_principal
        self._remote_addr = remote_addr
        self._user_agent = user_agent
        self._read_json_body = read_json_body
        self._has_body = has_body
        self._check_login_guard = check_login_guard
        self._record_login_success = record_login_success
        self._record_login_failure = record_login_failure
        self._refresh_cookie_header = refresh_cookie_header
        self._clear_refresh_cookie_header = clear_refresh_cookie_header
        self._read_refresh_cookie = read_refresh_cookie
        self._bearer_token = bearer_token
        self._read_raw_body = read_raw_body
        self._audit_event = audit_event

    # ── Response helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _json(
        status: HTTPStatus,
        payload: dict[str, Any],
        *,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        r: dict[str, Any] = {"kind": "json", "status": status, "payload": payload}
        if extra_headers:
            r["extra_headers"] = extra_headers
        return r

    @staticmethod
    def _redirect(location: str) -> dict[str, Any]:
        return {"kind": "redirect", "status": HTTPStatus.FOUND, "location": location}

    @staticmethod
    def _bytes(status: HTTPStatus, body: bytes, content_type: str) -> dict[str, Any]:
        return {"kind": "bytes", "status": status, "body": body, "content_type": content_type}

    @staticmethod
    def _sanitize_identifier(raw: Any, *, label: str, pattern: str) -> str:
        text = str(raw or "").strip()
        if not text:
            raise ValueError(f"{label} is required")
        if not re.fullmatch(pattern, text):
            raise ValueError(f"invalid {label}")
        return text

    @staticmethod
    def _safe_side_effect(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        try:
            fn(*args, **kwargs)
        except Exception:
            # Authentication must not fail just because telemetry/audit storage is degraded.
            pass

    @staticmethod
    def _validate_whitelist(
        payload: dict[str, Any],
        *,
        required: set[str] | None = None,
        optional: set[str] | None = None,
    ) -> None:
        required = required or set()
        optional = optional or set()
        allowed = required | optional
        for key in payload:
            if key not in allowed:
                raise ValueError(f"unexpected field: {key}")
        for key in required:
            if key not in payload:
                raise ValueError(f"missing required field: {key}")

    # ── Dispatch ───────────────────────────────────────────────────────────────

    @staticmethod
    def handles_get(path: str) -> bool:
        return path in AuthSessionHttpSurfaceService._GET_PATHS

    @staticmethod
    def handles_post(path: str) -> bool:
        return path in AuthSessionHttpSurfaceService._POST_PATHS

    def route_get(
        self,
        path: str,
        *,
        query: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        query = query or {}

        if path == "/api/v1/auth/me":
            return self._handle_me()

        if path == "/api/v1/auth/onboarding/status":
            return self._handle_onboarding_status()

        if path == "/api/v1/auth/providers":
            return self._handle_providers()

        if path == "/api/v1/auth/permission-tags":
            return self._json(
                HTTPStatus.OK, {"ok": True, "catalog": self._permission_catalog}
            )

        if path == "/api/v1/auth/oidc/login":
            return self._handle_oidc_login()

        if path == "/api/v1/auth/oidc/callback":
            return self._handle_oidc_callback(query)

        if path == "/api/v1/auth/saml/login":
            return self._handle_saml_login(query)

        if path == "/api/v1/auth/saml/metadata":
            return self._handle_saml_metadata()

        return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def route_post(self, path: str) -> dict[str, Any]:
        if path == "/api/v1/auth/login":
            return self._handle_login()

        if path == "/api/v1/auth/refresh":
            return self._handle_refresh()

        if path == "/api/v1/auth/logout":
            return self._handle_logout()

        if path == "/api/v1/auth/onboarding/complete":
            return self._handle_onboarding_complete()

        if path == "/api/v1/auth/saml/callback":
            return self._handle_saml_callback()

        return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    # ── GET handlers ──────────────────────────────────────────────────────────

    def _handle_me(self) -> dict[str, Any]:
        principal = self._auth_principal()
        if principal is None:
            return self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
        role = str(principal.get("role") or "viewer")
        permissions = sorted(self._auth_session.role_permissions(role))
        return self._json(
            HTTPStatus.OK,
            {
                "ok": True,
                "server_url": self._public_manager_url,
                "scim_enabled": bool(self._scim_enabled()),
                "scim_base_url": self._public_manager_url,
                "user": {
                    "username": str(principal.get("username") or ""),
                    "role": role,
                    "auth_type": str(principal.get("auth_type") or "session"),
                    "tenant_id": principal.get("tenant_id") or None,
                    "permissions": permissions,
                },
            },
        )

    def _handle_onboarding_status(self) -> dict[str, Any]:
        status_payload = self._auth_session.onboarding_status(
            bootstrap_username=self._bootstrap_username,
            bootstrap_disabled=self._bootstrap_disabled,
        )
        public_status = {
            "pending": bool(status_payload.get("pending")),
            "completed": bool(status_payload.get("completed")),
        }
        return self._json(HTTPStatus.OK, {"ok": True, "onboarding": public_status})

    def _handle_providers(self) -> dict[str, Any]:
        try:
            payload = self._idp_registry.payload()
        except Exception:
            payload = {
                "ok": True,
                "providers": [
                    {
                        "id": "local",
                        "type": "local",
                        "label": "Lokaler Account",
                        "description": "Benutzername + Passwort (Break-Glass).",
                        "mode": "password",
                        "enabled": True,
                        "login_url": "",
                    }
                ],
                "provider_hint": "",
            }
        return self._json(HTTPStatus.OK, payload)

    def _handle_oidc_login(self) -> dict[str, Any]:
        try:
            login_url = self._oidc.begin_login()
        except RuntimeError as exc:
            return self._json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": str(exc)})
        except Exception as exc:
            return self._json(
                HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"oidc unavailable: {exc}"}
            )
        return self._redirect(login_url)

    def _handle_oidc_callback(self, query: dict[str, list[str]]) -> dict[str, Any]:
        code = str((query.get("code") or [""])[0] or "").strip()
        state = str((query.get("state") or [""])[0] or "").strip()
        if not code or not state:
            return self._json(
                HTTPStatus.BAD_REQUEST, {"ok": False, "error": "missing code/state"}
            )
        try:
            payload = self._oidc.finish_login(code=code, state=state)
        except PermissionError as exc:
            return self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": str(exc)})
        except Exception as exc:
            return self._json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": f"oidc callback failed: {exc}"},
            )
        return self._json(HTTPStatus.OK, payload)

    def _handle_saml_login(self, query: dict[str, list[str]]) -> dict[str, Any]:
        relay_state = str((query.get("relay") or [""])[0] or "").strip()
        try:
            login_url = self._saml.begin_login(relay_state=relay_state)
        except RuntimeError as exc:
            return self._json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": str(exc)})
        except Exception as exc:
            return self._json(
                HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"saml unavailable: {exc}"}
            )
        return self._redirect(login_url)

    def _handle_saml_metadata(self) -> dict[str, Any]:
        xml = self._saml.metadata_xml().encode("utf-8")
        return self._bytes(
            HTTPStatus.OK, xml, "application/samlmetadata+xml; charset=utf-8"
        )

    # ── POST handlers ─────────────────────────────────────────────────────────

    def _handle_login(self) -> dict[str, Any]:
        try:
            payload = self._read_json_body()
            self._validate_whitelist(payload, required={"username", "password"}, optional={"totp_code"})
            username = self._sanitize_identifier(
                payload.get("username"),
                label="username",
                pattern=r"^[A-Za-z0-9._-]{1,64}$",
            )
        except Exception as exc:
            return self._json(
                HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"}
            )
        password = str(payload.get("password") or "")
        if not password:
            return self._json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "username and password are required"},
            )
        allowed, wait_seconds = self._check_login_guard(username)
        if not allowed:
            return self._json(
                HTTPStatus.TOO_MANY_REQUESTS,
                {
                    "ok": False,
                    "error": "login temporarily blocked",
                    "code": "rate_limited",
                    "retry_after_seconds": int(max(1, wait_seconds)),
                },
            )
        try:
            session_payload = self._auth_session.login(
                username=username,
                password=password,
                totp_code=str(payload.get("totp_code") or ""),
                remote_addr=self._remote_addr(),
                user_agent=self._user_agent(),
            )
        except PermissionError as exc:
            self._safe_side_effect(self._record_login_failure, username)
            self._safe_side_effect(
                self._audit_event,
                "auth.login",
                "denied",
                username=username,
                remote_addr=self._remote_addr(),
                reason=str(exc),
            )
            return self._json(
                HTTPStatus.UNAUTHORIZED,
                {"ok": False, "error": str(exc), "code": "invalid_totp"},
            )
        if session_payload is None:
            self._safe_side_effect(self._record_login_failure, username)
            self._safe_side_effect(
                self._audit_event,
                "auth.login",
                "denied",
                username=username,
                remote_addr=self._remote_addr(),
            )
            return self._json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "invalid credentials"})
        self._safe_side_effect(self._record_login_success, username)
        self._safe_side_effect(
            self._audit_event,
            "auth.login",
            "success",
            username=str(session_payload.get("user", {}).get("username") or username),
            remote_addr=self._remote_addr(),
        )
        return self._json(
            HTTPStatus.OK,
            session_payload,
            extra_headers=[self._refresh_cookie_header(str(session_payload.get("refresh_token") or ""))],
        )

    def _handle_refresh(self) -> dict[str, Any]:
        if self._has_body():
            try:
                payload = self._read_json_body()
                self._validate_whitelist(payload, optional={"refresh_token"})
            except Exception as exc:
                return self._json(
                    HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"}
                )
        else:
            payload = {}
        refresh_token = str(
            payload.get("refresh_token")
            or self._read_refresh_cookie()
            or ""
        ).strip()
        if not refresh_token:
            return self._json(
                HTTPStatus.BAD_REQUEST, {"ok": False, "error": "refresh token missing"}
            )
        session_payload = self._auth_session.refresh(refresh_token)
        if session_payload is None:
            self._audit_event(
                "auth.refresh", "denied", remote_addr=self._remote_addr()
            )
            return self._json(
                HTTPStatus.UNAUTHORIZED,
                {"ok": False, "error": "invalid refresh token"},
                extra_headers=[self._clear_refresh_cookie_header()],
            )
        self._audit_event(
            "auth.refresh",
            "success",
            username=str(session_payload.get("user", {}).get("username") or ""),
            remote_addr=self._remote_addr(),
        )
        return self._json(
            HTTPStatus.OK,
            session_payload,
            extra_headers=[self._refresh_cookie_header(str(session_payload.get("refresh_token") or ""))],
        )

    def _handle_logout(self) -> dict[str, Any]:
        refresh_token = ""
        if self._has_body():
            try:
                payload = self._read_json_body()
                self._validate_whitelist(payload, optional={"refresh_token"})
                refresh_token = str(payload.get("refresh_token") or "").strip()
            except Exception as exc:
                return self._json(
                    HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"}
                )
        if not refresh_token:
            refresh_token = self._read_refresh_cookie()
        revoked = self._auth_session.revoke(
            access_token=self._bearer_token(),
            refresh_token=refresh_token,
        )
        self._audit_event(
            "auth.logout",
            "success" if revoked else "noop",
            remote_addr=self._remote_addr(),
        )
        return self._json(
            HTTPStatus.OK,
            {"ok": True, "revoked": bool(revoked)},
            extra_headers=[self._clear_refresh_cookie_header()],
        )

    def _handle_onboarding_complete(self) -> dict[str, Any]:
        try:
            payload = self._read_json_body()
            self._validate_whitelist(
                payload, required={"username", "password", "password_confirm"}
            )
            username = self._sanitize_identifier(
                payload.get("username"),
                label="username",
                pattern=r"^[A-Za-z0-9._-]{1,64}$",
            )
        except Exception as exc:
            return self._json(
                HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"}
            )
        password = str(payload.get("password") or "")
        password_confirm = str(payload.get("password_confirm") or "")
        if not password:
            return self._json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "username and password are required"},
            )
        if password != password_confirm:
            return self._json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "password confirmation mismatch"},
            )
        try:
            onboarding_state = self._auth_session.complete_onboarding(
                username=username,
                password=password,
                bootstrap_username=self._bootstrap_username,
                bootstrap_disabled=self._bootstrap_disabled,
            )
        except Exception as exc:
            message = str(exc)
            status_code = (
                HTTPStatus.CONFLICT
                if message == "onboarding already completed"
                else HTTPStatus.BAD_REQUEST
            )
            return self._json(status_code, {"ok": False, "error": message})
        self._audit_event(
            "auth.onboarding.complete",
            "success",
            username=username,
            remote_addr=self._remote_addr(),
        )
        return self._json(HTTPStatus.OK, {"ok": True, "onboarding": onboarding_state})

    def _handle_saml_callback(self) -> dict[str, Any]:
        try:
            # SAML ACS: IdP POSTs a SAMLResponse (application/x-www-form-urlencoded)
            content_length = 0
            try:
                from urllib.parse import parse_qs as _parse_qs  # noqa: PLC0415
                # Read via callable — has_body checked already
            except ImportError:
                pass
            raw_bytes = self._read_raw_body(65536)  # SAML response is always < 64 KB
            raw_body = raw_bytes.decode("utf-8", errors="replace")
        except Exception:
            raw_body = ""
        from urllib.parse import parse_qs as _parse_qs  # noqa: PLC0415
        form = _parse_qs(raw_body) if raw_body else {}
        saml_response_b64 = str((form.get("SAMLResponse") or [""])[0] or "").strip()
        if not saml_response_b64:
            self._audit_event(
                "auth.saml.assertion_rejected",
                "denied",
                reason="missing SAMLResponse",
                remote_addr=self._remote_addr(),
            )
            return self._json(
                HTTPStatus.BAD_REQUEST, {"ok": False, "error": "missing SAMLResponse"}
            )
        try:
            claims = self._saml.validate_assertion(saml_response_b64)
        except SamlAssertionError as exc:
            self._audit_event(
                "auth.saml.assertion_rejected",
                "denied",
                reason=str(exc),
                remote_addr=self._remote_addr(),
            )
            return self._json(
                HTTPStatus.UNAUTHORIZED,
                {"ok": False, "error": f"saml assertion rejected: {exc}"},
            )
        except Exception as exc:
            self._audit_event(
                "auth.saml.assertion_rejected",
                "denied",
                reason=f"internal error: {exc}",
                remote_addr=self._remote_addr(),
            )
            return self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": "saml callback failed"},
            )
        self._audit_event(
            "auth.saml.assertion_accepted",
            "success",
            name_id=str(claims.get("name_id") or ""),
            remote_addr=self._remote_addr(),
        )
        return self._json(HTTPStatus.OK, {"ok": True, "claims": claims})
