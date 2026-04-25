#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
PROVIDERS_DIR = Path(__file__).resolve().parents[1] / "providers"
SERVICES_DIR = Path(__file__).resolve().parents[1] / "services"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(PROVIDERS_DIR) not in sys.path:
    sys.path.insert(0, str(PROVIDERS_DIR))
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from service_registry import *  # noqa: F401,F403
from service_registry import (  # private helpers used in main()
    _bootstrap_secret,
    _secret_store,
    _start_recording_retention_thread,
    _start_backup_scheduler_thread,
)
import service_registry as _svc_registry  # needed to update module-level secrets in main()

class Handler(BaseHTTPRequestHandler):
    server_version = f"BeagleControlPlane/{VERSION}"
    _rate_limit_state: dict[str, list[float]] = {}
    _login_guard_state: dict[str, dict[str, float]] = {}
    _security_state_lock = None

    @classmethod
    def _state_lock(cls):
        if cls._security_state_lock is None:
            import threading
            cls._security_state_lock = threading.RLock()
        return cls._security_state_lock

    @staticmethod
    def _error_code_for_status(status: int) -> str:
        mapping = {
            int(HTTPStatus.BAD_REQUEST): "bad_request",
            int(HTTPStatus.UNAUTHORIZED): "unauthorized",
            int(HTTPStatus.FORBIDDEN): "forbidden",
            int(HTTPStatus.NOT_FOUND): "not_found",
            int(HTTPStatus.CONFLICT): "conflict",
            int(HTTPStatus.TOO_MANY_REQUESTS): "rate_limited",
            int(HTTPStatus.BAD_GATEWAY): "bad_gateway",
            int(HTTPStatus.INTERNAL_SERVER_ERROR): "internal_error",
        }
        return mapping.get(int(status), "request_error")

    def _client_addr(self) -> str:
        return self.client_address[0] if self.client_address else ""

    def _login_guard_key(self, username: str) -> str:
        return f"{self._client_addr()}::{str(username or '').strip().lower()}"

    def _check_login_guard(self, username: str) -> tuple[bool, int]:
        now_ts = time.time()
        key = self._login_guard_key(username)
        with self._state_lock():
            state = self._login_guard_state.get(key)
            if not isinstance(state, dict):
                return True, 0
            locked_until = float(state.get("locked_until") or 0.0)
            next_allowed = float(state.get("next_allowed") or 0.0)
            if locked_until > now_ts:
                return False, int(max(1, locked_until - now_ts))
            if next_allowed > now_ts:
                return False, int(max(1, next_allowed - now_ts))
        return True, 0

    def _record_login_success(self, username: str) -> None:
        key = self._login_guard_key(username)
        with self._state_lock():
            self._login_guard_state.pop(key, None)

    def _record_login_failure(self, username: str) -> None:
        now_ts = time.time()
        key = self._login_guard_key(username)
        with self._state_lock():
            state = self._login_guard_state.get(key)
            if not isinstance(state, dict):
                state = {"failures": 0.0, "locked_until": 0.0, "next_allowed": 0.0}
            failures = int(float(state.get("failures") or 0.0)) + 1
            backoff_seconds = min(2 ** max(0, failures - 1), AUTH_LOGIN_BACKOFF_MAX_SECONDS)
            state["failures"] = float(failures)
            state["next_allowed"] = now_ts + float(backoff_seconds)
            if failures >= max(1, AUTH_LOGIN_LOCKOUT_THRESHOLD):
                state["locked_until"] = now_ts + float(max(1, AUTH_LOGIN_LOCKOUT_SECONDS))
            self._login_guard_state[key] = state

    def _rate_limit_key(self) -> str:
        return self._client_addr() or "unknown"

    def _enforce_api_rate_limit(self, path: str) -> bool:
        if not str(path or "").startswith("/api/"):
            return True
        now_ts = time.time()
        window = float(max(1, API_RATE_LIMIT_WINDOW_SECONDS))
        max_requests = int(max(1, API_RATE_LIMIT_MAX_REQUESTS))
        key = self._rate_limit_key()
        with self._state_lock():
            entries = self._rate_limit_state.get(key, [])
            entries = [ts for ts in entries if now_ts - ts <= window]
            if len(entries) >= max_requests:
                self._rate_limit_state[key] = entries
                self._write_json(
                    HTTPStatus.TOO_MANY_REQUESTS,
                    {
                        "ok": False,
                        "error": "rate limit exceeded",
                        "code": "rate_limited",
                        "retry_after_seconds": int(window),
                    },
                )
                return False
            entries.append(now_ts)
            self._rate_limit_state[key] = entries
        return True

    def _log_response_event(self, status: int) -> None:
        try:
            path = str(urlparse(getattr(self, "path", "") or "").path)
            action = f"{str(getattr(self, 'command', '')).upper()} {path}"
            resource_type = ""
            resource_id: str | int = ""
            vm_match = re.search(r"/vms/(\d+)", path)
            auth_user_match = re.search(r"/auth/users/([A-Za-z0-9._-]+)", path)
            auth_role_match = re.search(r"/auth/roles/([A-Za-z0-9._:-]+)", path)
            if vm_match is not None:
                resource_type = "vm"
                resource_id = int(vm_match.group(1))
            elif auth_user_match is not None:
                resource_type = "user"
                resource_id = auth_user_match.group(1)
            elif auth_role_match is not None:
                resource_type = "role"
                resource_id = auth_role_match.group(1)
            print(
                json.dumps(
                    {
                        "event": "api.response",
                        "timestamp": utcnow(),
                        "method": str(getattr(self, "command", "")),
                        "path": path,
                        "action": action,
                        "status": int(status),
                        "user": self._requester_identity(),
                        "remote_addr": self._client_addr(),
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                ),
                flush=True,
            )
        except Exception:
            pass

    def _handle_unexpected_error(self, error: Exception) -> None:
        self._audit_event(
            "request.unhandled_exception",
            "error",
            method=str(getattr(self, "command", "")),
            path=str(urlparse(getattr(self, "path", "") or "").path),
            username=self._requester_identity(),
            remote_addr=self._client_addr(),
            error_type=type(error).__name__,
            error_message=str(error),
        )
        try:
            self._write_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "ok": False,
                    "error": "internal server error",
                    "code": "internal_error",
                },
            )
        except Exception:
            pass

    @staticmethod
    def _auth_user_match(path: str) -> re.Match[str] | None:
        return re.match(r"^/api/v1/auth/users/(?P<username>[A-Za-z0-9._-]+)$", path)

    @staticmethod
    def _auth_role_match(path: str) -> re.Match[str] | None:
        return re.match(r"^/api/v1/auth/roles/(?P<name>[A-Za-z0-9._:-]+)$", path)

    @staticmethod
    def _auth_user_revoke_sessions_match(path: str) -> re.Match[str] | None:
        return re.match(r"^/api/v1/auth/users/(?P<username>[A-Za-z0-9._-]+)/revoke-sessions$", path)

    def _active_session_by_id(self, session_id: str) -> dict[str, Any] | None:
        sid = str(session_id or "").strip()
        if not sid:
            return None
        for session in pool_manager_service().list_active_sessions():
            if str(session.get("session_id") or "").strip() == sid:
                return session
        return None

    def _pool_recording_policy(self, pool_id: str) -> str:
        pool_info = pool_manager_service().get_pool(str(pool_id or "").strip())
        if pool_info is None:
            return SessionRecordingPolicy.DISABLED.value
        policy = pool_info.session_recording.value if hasattr(pool_info.session_recording, "value") else str(pool_info.session_recording)
        return str(policy or SessionRecordingPolicy.DISABLED.value).strip().lower() or SessionRecordingPolicy.DISABLED.value

    def _pool_recording_watermark(self, pool_id: str) -> dict[str, Any]:
        return pool_manager_service().get_pool_recording_watermark(str(pool_id or "").strip())

    def _auth_session_surface(self) -> AuthSessionHttpSurfaceService:
        return AuthSessionHttpSurfaceService(
            auth_session=auth_session_service(),
            identity_provider_registry=identity_provider_registry_service(),
            oidc_service=oidc_service(),
            saml_service=saml_service(),
            permission_catalog=PERMISSION_CATALOG,
            auth_bootstrap_username=AUTH_BOOTSTRAP_USERNAME,
            auth_bootstrap_disabled=AUTH_BOOTSTRAP_DISABLE,
            auth_principal=self._auth_principal,
            remote_addr=lambda: self.client_address[0] if self.client_address else "",
            user_agent=lambda: str(self.headers.get("User-Agent") or "")[:256],
            read_json_body=self._read_json_body,
            has_body=lambda: int(self.headers.get("Content-Length", "0") or "0") > 0,
            check_login_guard=self._check_login_guard,
            record_login_success=self._record_login_success,
            record_login_failure=self._record_login_failure,
            refresh_cookie_header=self._refresh_cookie_header,
            clear_refresh_cookie_header=self._clear_refresh_cookie_header,
            read_refresh_cookie=self._read_refresh_cookie,
            bearer_token=lambda: extract_bearer_token(self.headers.get("Authorization", "")),
            read_raw_body=lambda n: self.rfile.read(n),
            audit_event=self._audit_event,
        )

    def _audit_report_surface(self) -> AuditReportHttpSurfaceService:
        return AuditReportHttpSurfaceService(
            audit_report_service=audit_report_service(),
            audit_event=self._audit_event,
            requester_identity=self._requester_identity,
            accept_header=lambda: str(self.headers.get("Accept") or ""),
        )

    def _recording_surface(self) -> RecordingHttpSurfaceService:
        return RecordingHttpSurfaceService(
            recording_service=recording_service(),
            audit_event=self._audit_event,
            requester_identity=self._requester_identity,
            remote_addr=lambda: self.client_address[0] if self.client_address else "",
            active_session_by_id=self._active_session_by_id,
            pool_recording_watermark=self._pool_recording_watermark,
            read_json_body=self._read_json_body,
            has_body=lambda: int(self.headers.get("Content-Length", "0") or "0") > 0,
        )

    def _backups_surface(self) -> BackupsHttpSurfaceService:
        return BackupsHttpSurfaceService(
            backup_service=backup_service(),
            storage_quota_service=storage_quota_service(),
            audit_event=self._audit_event,
            requester_identity=self._requester_identity,
            read_binary_body=lambda n: self.rfile.read(n),
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )

    def _cluster_surface(self) -> ClusterHttpSurfaceService:
        return ClusterHttpSurfaceService(
            cluster_membership_service=cluster_membership_service(),
            ha_manager_service=ha_manager_service(),
            maintenance_service=maintenance_service(),
            build_cluster_inventory=build_cluster_inventory,
            build_ha_status_payload=build_ha_status_payload,
            ensure_cluster_rpc_listener=ensure_cluster_rpc_listener,
            audit_event=self._audit_event,
            requester_identity=self._requester_identity,
            cluster_node_name=CLUSTER_NODE_NAME,
            public_manager_url=PUBLIC_MANAGER_URL,
            public_server_name=PUBLIC_SERVER_NAME,
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )

    def _pools_surface(self) -> PoolsHttpSurfaceService:
        return PoolsHttpSurfaceService(
            pool_manager_service=pool_manager_service(),
            entitlement_service=entitlement_service(),
            desktop_template_builder_service=desktop_template_builder_service(),
            recording_service=recording_service(),
            audit_event=self._audit_event,
            requester_identity=self._requester_identity,
            requester_tenant_id=self._requester_tenant_id,
            can_bypass_pool_visibility=self._can_bypass_pool_visibility,
            can_view_pool=self._can_view_pool,
            pool_recording_policy=self._pool_recording_policy,
            pool_recording_watermark=self._pool_recording_watermark,
            remote_addr=lambda: self.client_address[0] if self.client_address else "",
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )

    def _audit_auth_surface_response(self, method: str, path: str, response: dict[str, Any]) -> None:
        status = int(response.get("status") or 500)
        outcome = "success" if status < 400 else "error"
        payload = response.get("payload") if isinstance(response.get("payload"), dict) else {}
        if method == "POST" and path == "/api/v1/auth/users":
            created_username = str((payload or {}).get("user", {}).get("username", "")).strip()
            if created_username:
                self._audit_event(
                    "auth.user.create",
                    outcome,
                    username=created_username,
                    requested_by=self._requester_identity(),
                    resource_type="user",
                    resource_id=created_username,
                    remote_addr=self.client_address[0] if self.client_address else "",
                )
            return
        if method == "POST" and path == "/api/v1/auth/roles":
            self._audit_event(
                "auth.role.save",
                outcome,
                role=(payload or {}).get("role", {}).get("name", ""),
                requested_by=self._requester_identity(),
            )
            return
        revoke_match = self._auth_user_revoke_sessions_match(path)
        if method == "POST" and revoke_match is not None:
            self._audit_event(
                "auth.user.revoke_sessions",
                outcome,
                username=str(revoke_match.group("username") or "").strip(),
                revoked_count=(payload or {}).get("revoked_count", 0),
                requested_by=self._requester_identity(),
            )
            return
        user_match = self._auth_user_match(path)
        if method == "PUT" and user_match is not None:
            self._audit_event(
                "auth.user.update",
                outcome,
                username=(payload or {}).get("user", {}).get("username", "") or str(user_match.group("username") or ""),
                requested_by=self._requester_identity(),
            )
            return
        role_match = self._auth_role_match(path)
        if method == "PUT" and role_match is not None:
            self._audit_event(
                "auth.role.update",
                outcome,
                role=(payload or {}).get("role", {}).get("name", "") or str(role_match.group("name") or ""),
                requested_by=self._requester_identity(),
            )
            return
        if method == "DELETE" and user_match is not None:
            self._audit_event(
                "auth.user.delete",
                outcome,
                username=str(user_match.group("username") or ""),
                requested_by=self._requester_identity(),
            )
            return
        if method == "DELETE" and role_match is not None:
            self._audit_event(
                "auth.role.delete",
                outcome,
                role=str(role_match.group("name") or ""),
                requested_by=self._requester_identity(),
            )

    def _audit_event(self, event_type: str, outcome: str, **details: Any) -> None:
        try:
            audit_log_service().write_event(event_type, outcome, details)
        except Exception:
            pass

    def _authorize_or_respond(self, method: str, path: str) -> bool:
        permission = authz_policy_service().required_permission(method, path)
        if permission is None:
            return True
        principal = self._auth_principal()
        if principal is None:
            return False
        role = str(principal.get("role") or "viewer").strip().lower() or "viewer"
        allowed = authz_policy_service().is_allowed(
            role,
            permission,
            auth_session_service().role_permissions(role),
        )
        if allowed:
            return True
        self._audit_event(
            "mutation.authorization",
            "denied",
            method=method,
            path=path,
            permission=permission,
            role=role,
            username=str(principal.get("username") or ""),
            remote_addr=self.client_address[0] if self.client_address else "",
        )
        self._write_json(
            HTTPStatus.FORBIDDEN,
            {
                "ok": False,
                "error": "forbidden",
                "permission": permission,
                "role": role,
            },
        )
        return False

    def _auth_principal(self) -> dict[str, Any] | None:
        cached = getattr(self, "_cached_auth_principal", None)
        if cached is not None:
            return cached
        if ALLOW_LOCALHOST_NOAUTH and self.client_address[0] in {"127.0.0.1", "::1"}:
            principal = {"username": "localhost", "role": "superadmin", "auth_type": "localhost"}
            setattr(self, "_cached_auth_principal", principal)
            return principal
        header = self.headers.get("Authorization", "")
        bearer = header[7:].strip() if header.startswith("Bearer ") else ""
        if bearer:
            session_principal = auth_session_service().resolve_access_token(bearer)
            if session_principal is not None:
                setattr(self, "_cached_auth_principal", session_principal)
                return session_principal
            if API_TOKEN and secrets.compare_digest(bearer, API_TOKEN):
                principal = {"username": "legacy-api-token", "role": "superadmin", "auth_type": "api_token"}
                setattr(self, "_cached_auth_principal", principal)
                return principal
        api_token = self.headers.get("X-Beagle-Api-Token", "").strip()
        if api_token and API_TOKEN and secrets.compare_digest(api_token, API_TOKEN):
            principal = {"username": "legacy-api-token", "role": "superadmin", "auth_type": "api_token"}
            setattr(self, "_cached_auth_principal", principal)
            return principal
        setattr(self, "_cached_auth_principal", None)
        return None

    def _is_authenticated(self) -> bool:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in {"/healthz", "/api/v1/health"}:
            return True
        return self._auth_principal() is not None

    def _endpoint_identity(self) -> dict[str, Any] | None:
        token = extract_bearer_token(self.headers.get("Authorization", ""))
        if not token:
            token = self.headers.get("X-Beagle-Endpoint-Token", "").strip()
        if not token:
            return None
        payload = load_endpoint_token(token)
        return payload if isinstance(payload, dict) else None

    def _is_endpoint_authenticated(self) -> bool:
        if ALLOW_LOCALHOST_NOAUTH and self.client_address[0] in {"127.0.0.1", "::1"}:
            return True
        return self._endpoint_identity() is not None

    def _is_scim_authenticated(self) -> bool:
        if not SCIM_BEARER_TOKEN:
            return False
        token = extract_bearer_token(self.headers.get("Authorization", ""))
        if not token:
            return False
        return secrets.compare_digest(token, SCIM_BEARER_TOKEN)

    def _stream_principal(self, parsed) -> dict[str, Any] | None:
        # EventSource cannot send custom Authorization headers, so accept
        # access_token query parameter for this dedicated stream endpoint.
        query = parse_qs(parsed.query or "")
        candidate = str((query.get("access_token") or query.get("token") or [""])[0] or "").strip()
        if candidate:
            session_principal = auth_session_service().resolve_access_token(candidate)
            if session_principal is not None:
                return session_principal
            if API_TOKEN and secrets.compare_digest(candidate, API_TOKEN):
                return {"username": "legacy-api-token", "role": "superadmin", "auth_type": "api_token"}
        return self._auth_principal()

    def _write_sse_event(self, event_name: str, payload: dict[str, Any]) -> None:
        body = (
            f"event: {str(event_name or 'message')}\n"
            f"data: {json.dumps(payload, ensure_ascii=True, separators=(',', ':'))}\n\n"
        ).encode("utf-8")
        self.wfile.write(body)
        self.wfile.flush()

    def _stream_live_events(self, principal: dict[str, Any]) -> None:
        try:
            self.send_response(HTTPStatus.OK)
            self._write_common_security_headers()
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            self._write_sse_event(
                "hello",
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "user": str((principal or {}).get("username") or ""),
                    "ts": utcnow(),
                },
            )

            # Keep stream bounded so EventSource reconnects and refreshes auth state.
            for _ in range(0, 180):
                time.sleep(5)
                self._write_sse_event(
                    "tick",
                    {
                        "ok": True,
                        "ts": utcnow(),
                        "manager_status": "online",
                    },
                )
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            return

    def _stream_auth_error(self, status: HTTPStatus, code: str = "unauthorized", message: str = "unauthorized") -> None:
        """Return an SSE-framed auth error so EventSource does not fail with MIME mismatch."""
        try:
            self.send_response(status)
            self._write_common_security_headers()
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            self._write_sse_event(
                "error",
                {
                    "ok": False,
                    "error": str(message or "unauthorized"),
                    "code": str(code or "unauthorized"),
                    "ts": utcnow(),
                },
            )
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            return

    def _cors_origin(self) -> str:
        origin = normalized_origin(self.headers.get("Origin", ""))
        if origin and origin in cors_allowed_origins():
            return origin
        return ""

    def _write_common_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; worker-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
        )
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")

    def _deprecation_headers_for_request(self) -> list[tuple[str, str]]:
        path = str(urlparse(getattr(self, "path", "") or "").path or "").rstrip("/") or "/"
        if not path.startswith("/api/v1/"):
            return []
        if path not in API_V1_DEPRECATED_ENDPOINTS:
            return []
        return [
            ("Deprecation", "true"),
            ("Sunset", API_V1_DEPRECATION_SUNSET),
            ("Link", f'<{API_V1_DEPRECATION_DOC_URL}>; rel="deprecation"'),
        ]

    def _write_json(self, status: HTTPStatus, payload: Any, *, extra_headers: list[tuple[str, str]] | None = None) -> None:
        if isinstance(payload, dict) and payload.get("ok") is False and payload.get("error") and not payload.get("code"):
            payload = dict(payload)
            payload["code"] = self._error_code_for_status(int(status))
        body = json.dumps(payload, indent=2).encode("utf-8") + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self._write_common_security_headers()
        merged_headers = list(extra_headers or []) + self._deprecation_headers_for_request()
        for header_name, header_value in merged_headers:
            self.send_header(header_name, header_value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self._log_response_event(int(status))

    def _refresh_cookie_header(self, refresh_token: str) -> tuple[str, str]:
        """Return a Set-Cookie header tuple for the refresh token (HttpOnly, SameSite=Strict)."""
        return (
            "Set-Cookie",
            f"beagle_refresh_token={refresh_token}; HttpOnly; SameSite=Strict; Path=/api/v1/auth; Secure",
        )

    def _clear_refresh_cookie_header(self) -> tuple[str, str]:
        """Return a Set-Cookie header tuple that expires the refresh token cookie."""
        return (
            "Set-Cookie",
            "beagle_refresh_token=; HttpOnly; SameSite=Strict; Path=/api/v1/auth; Secure; Max-Age=0",
        )

    def _read_refresh_cookie(self) -> str:
        """Read the beagle_refresh_token value from the Cookie header, or return empty string."""
        cookie_header = str(self.headers.get("Cookie") or "")
        for part in cookie_header.split(";"):
            name, _, value = part.strip().partition("=")
            if name.strip() == "beagle_refresh_token":
                return value.strip()
        return ""

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > 256 * 1024:
            raise ValueError("invalid content length")
        body = self.rfile.read(length)
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid payload")
        return payload

    @staticmethod
    def _sanitize_identifier(value: Any, *, label: str, pattern: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{label} is required")
        if not re.fullmatch(pattern, text):
            raise ValueError(f"invalid {label}")
        return text

    @staticmethod
    def _validate_payload_whitelist(
        payload: dict[str, Any],
        *,
        required: set[str] | None = None,
        optional: set[str] | None = None,
    ) -> None:
        required_keys = set(required or set())
        optional_keys = set(optional or set())
        allowed = required_keys | optional_keys
        missing = [key for key in sorted(required_keys) if key not in payload]
        if missing:
            raise ValueError(f"missing keys: {', '.join(missing)}")
        extras = [key for key in sorted(payload.keys()) if key not in allowed]
        if extras:
            raise ValueError(f"unexpected keys: {', '.join(extras)}")

    def _read_binary_body(self, *, max_bytes: int) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > max_bytes:
            raise ValueError("invalid content length")
        return self.rfile.read(length)

    def _write_bytes(self, status: HTTPStatus, body: bytes, *, content_type: str, filename: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self._write_common_security_headers()
        for header_name, header_value in self._deprecation_headers_for_request():
            self.send_header(header_name, header_value)
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_redirect(self, location: str, *, status: HTTPStatus = HTTPStatus.FOUND) -> None:
        self.send_response(status)
        self._write_common_security_headers()
        self.send_header("Location", str(location or "/"))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _requester_identity(self) -> str:
        principal = self._auth_principal()
        if principal and principal.get("username"):
            return str(principal.get("username"))
        if self.client_address and self.client_address[0]:
            return self.client_address[0]
        return "unknown"

    def _requester_groups(self) -> list[str]:
        principal = self._auth_principal() or {}
        raw_groups = principal.get("groups", [])
        if isinstance(raw_groups, str):
            raw_groups = [raw_groups]
        groups: list[str] = []
        seen: set[str] = set()
        for item in raw_groups if isinstance(raw_groups, list) else []:
            value = str(item or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            groups.append(value)
        return groups

    def _requester_permissions(self) -> set[str]:
        principal = self._auth_principal()
        if principal is None:
            return set()
        role = str(principal.get("role") or "viewer").strip().lower() or "viewer"
        return auth_session_service().role_permissions(role)

    def _requester_tenant_id(self) -> str:
        principal = self._auth_principal() or {}
        return str(principal.get("tenant_id") or "").strip()

    def _can_bypass_pool_visibility(self) -> bool:
        permissions = self._requester_permissions()
        return "*" in permissions or "pool:write" in permissions

    def _can_view_pool(self, pool_id: str) -> bool:
        if self._can_bypass_pool_visibility():
            return True
        # Tenant isolation: non-admin users can only see pools in their own tenant.
        requester_tid = self._requester_tenant_id()
        if requester_tid:
            pool_info = pool_manager_service().get_pool(pool_id)
            if pool_info is not None and pool_info.tenant_id and pool_info.tenant_id != requester_tid:
                return False
        return entitlement_service().can_view_pool(
            pool_id,
            user_id=self._requester_identity(),
            groups=self._requester_groups(),
        )

    def _write_proxy_response(self, status_code: int, headers: dict[str, str], body: bytes) -> None:
        self.send_response(status_code)
        for key, value in headers.items():
            lower = key.lower()
            if lower in {"transfer-encoding", "connection", "content-length", "content-encoding"}:
                continue
            self.send_header(key, value)
        self.send_header("Cache-Control", "no-store")
        self._write_common_security_headers()
        for header_name, header_value in self._deprecation_headers_for_request():
            self.send_header(header_name, header_value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._write_common_security_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Beagle-Api-Token, X-Beagle-Endpoint-Token, X-Beagle-Refresh-Token")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if not self._enforce_api_rate_limit(urlparse(self.path).path.rstrip("/") or "/"):
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query_text = parsed.query
        query = parse_qs(parsed.query or "")

        response = public_sunshine_surface_service().route_request(
            parsed.path,
            query=query_text,
            method="GET",
            body=None,
            request_headers={"Accept": self.headers.get("Accept", "")},
        )
        if response is not None:
            if response["kind"] == "proxy":
                self._write_proxy_response(response["status"], response["headers"], response["body"])
            else:
                self._write_json(response["status"], response["payload"])
            return

        response = public_http_surface_service().route_get(path)
        if response is not None:
            self._write_json(response["status"], response["payload"])
            return

        if path == "/api/v1/endpoints/update-feed":
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            response = public_http_surface_service().endpoint_update_feed(
                query_text=query_text,
                endpoint_identity=self._endpoint_identity(),
            )
            self._write_json(response["status"], response["payload"])
            return

        if self._auth_session_surface().handles_get(path):
            response = self._auth_session_surface().route_get(path, query=query)
            if response["kind"] == "redirect":
                self._write_redirect(response["location"])
            elif response["kind"] == "bytes":
                self._write_bytes(response["status"], response["body"], content_type=response["content_type"])
            else:
                self._write_json(
                    response["status"],
                    response["payload"],
                    extra_headers=response.get("extra_headers"),
                )
            return

        if path == "/api/v1/events/stream":
            principal = self._stream_principal(parsed)
            if principal is None:
                self._stream_auth_error(HTTPStatus.UNAUTHORIZED, code="unauthorized", message="unauthorized")
                return
            self._stream_live_events(principal)
            return

        if AuditReportHttpSurfaceService.handles_get(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("GET", path):
                return
            response = self._audit_report_surface().route_get(path, query=query)
            if response["kind"] == "bytes":
                self._write_bytes(response["status"], response["body"], content_type=response["content_type"], filename=response.get("filename", ""))
            else:
                self._write_json(response["status"], response["payload"])
            return

        if scim_service().handles_path(path):
            if not SCIM_BEARER_TOKEN:
                self._write_json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": "scim disabled"})
                return
            if not self._is_scim_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            response = scim_service().route_get(path)
            self._write_json(response["status"], response["payload"])
            return

        if API_V2_PREPARATION_ENABLED and path in {"/api/v2", "/api/v2/health"}:
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "api": {
                        "current": "v1",
                        "next": "v2",
                        "status": "preparation",
                        "deprecated_v1_endpoints": sorted(API_V1_DEPRECATED_ENDPOINTS),
                        "deprecation_doc": API_V1_DEPRECATION_DOC_URL,
                        "sunset": API_V1_DEPRECATION_SUNSET,
                    },
                },
            )
            return

        if auth_http_surface_service().handles_get(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("GET", path):
                return
            principal = self._auth_principal()
            requester_tenant = (principal or {}).get("tenant_id") or None
            response = auth_http_surface_service().route_get(
                path, requester_tenant_id=requester_tenant
            )
            self._write_json(response["status"], response["payload"])
            return

        if self._recording_surface().handles_get(path):
            if not self._authorize_or_respond("GET", path):
                return
            response = self._recording_surface().route_get(path)
            if response["kind"] == "bytes":
                self._write_bytes(response["status"], response["body"], content_type=response["content_type"], filename=response.get("filename", ""))
            else:
                self._write_json(response["status"], response["payload"])
            return

        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return

        if self._backups_surface().handles_get(path):
            if not self._authorize_or_respond("GET", path):
                return
            response = self._backups_surface().route_get(path, query=query)
            if response is not None:
                if response.get("kind") == "bytes":
                    self._write_bytes(response["status"], response["body"], content_type=response["content_type"], filename=response.get("filename", ""))
                else:
                    self._write_json(response["status"], response["payload"])
            return

        if self._pools_surface().handles_get(path):
            if not self._authorize_or_respond("GET", path):
                return
            response = self._pools_surface().route_get(path)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        if path == "/healthz":
            self._write_json(HTTPStatus.OK, {"ok": True, "service": "beagle-control-plane", "version": VERSION})
            return
        response = control_plane_read_surface_service().route_get(path)
        if response is not None:
            if response["kind"] == "bytes":
                self._write_bytes(
                    response["status"],
                    response["body"],
                    content_type=response["content_type"],
                    filename=response["filename"],
                )
            else:
                self._write_json(response["status"], response["payload"])
            return
        response = virtualization_read_surface_service().route_get(path)
        if response is not None:
            self._write_json(response["status"], response["payload"])
            return
        if vgpu_surface_service().handles_path_get(path):
            if not self._authorize_or_respond("GET", path):
                return
            response = vgpu_surface_service().route_get(path)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return
        if path == "/api/v1/health":
            self._write_json(HTTPStatus.OK, build_health_payload())
            return
        if path == "/api/v1/vms":
            self._write_json(HTTPStatus.OK, build_vm_inventory())
            return
        if self._cluster_surface().handles_get(path):
            if not self._authorize_or_respond("GET", path):
                return
            response = self._cluster_surface().route_get(path)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return
        if path.startswith("/api/v1/vms/"):
            response = vm_http_surface_service().route_get(path)
            if response["kind"] == "bytes":
                self._write_bytes(
                    response["status"],
                    response["body"],
                    content_type=response["content_type"],
                    filename=response["filename"],
                )
            else:
                self._write_json(response["status"], response["payload"])
            return

        if path.startswith("/api/v1/settings/"):
            if not self._authorize_or_respond("GET", path):
                return
            response = server_settings_service().route_get(path)
            if response is not None:
                self._write_json(response["status"], response["payload"])
                return

        if network_http_surface_service().handles_get(path):
            if not self._authorize_or_respond("GET", path):
                return
            response = network_http_surface_service().route_get(path)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._enforce_api_rate_limit(urlparse(self.path).path.rstrip("/") or "/"):
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query or "")

        if self._backups_surface().handles_post(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            if path == "/api/v1/backups/ingest":
                content_length = int(self.headers.get("Content-Length") or 0)
                if content_length <= 0 or content_length > 10 * 1024 * 1024 * 1024:  # max 10 GB
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid Content-Length"})
                    return
                raw_body = self.rfile.read(content_length)
                raw_headers = {"X-Beagle-Backup-Meta": str(self.headers.get("X-Beagle-Backup-Meta") or "{}")}
                response = self._backups_surface().route_post(path, raw_body=raw_body, raw_headers=raw_headers)
            else:
                try:
                    json_payload = self._read_json_body() if int(self.headers.get("Content-Length", "0") or "0") > 0 else {}
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
                response = self._backups_surface().route_post(path, json_payload=json_payload)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        if self._cluster_surface().handles_post(path):
            if path != "/api/v1/cluster/join":
                if not self._is_authenticated():
                    self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                    return
                if not self._authorize_or_respond("POST", path):
                    return
            try:
                json_payload = self._read_json_body() if int(self.headers.get("Content-Length", "0") or "0") > 0 else {}
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = self._cluster_surface().route_post(path, json_payload=json_payload)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        if self._auth_session_surface().handles_post(path):
            response = self._auth_session_surface().route_post(path)
            if response["kind"] == "redirect":
                self._write_redirect(response["location"])
            elif response["kind"] == "bytes":
                self._write_bytes(response["status"], response["body"], content_type=response["content_type"])
            else:
                self._write_json(
                    response["status"],
                    response["payload"],
                    extra_headers=response.get("extra_headers"),
                )
            return

        if scim_service().handles_path(path):
            if not SCIM_BEARER_TOKEN:
                self._write_json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": "scim disabled"})
                return
            if not self._is_scim_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = scim_service().route_post(path, json_payload)
            self._write_json(response["status"], response["payload"])
            return

        if auth_http_surface_service().handles_post(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            json_payload: dict[str, Any] | None = None
            if auth_http_surface_service().requires_json_body(path):
                try:
                    json_payload = self._read_json_body()
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
            principal = self._auth_principal()
            requester_tenant = (principal or {}).get("tenant_id") or None
            response = auth_http_surface_service().route_post(
                path, json_payload=json_payload, requester_tenant_id=requester_tenant
            )
            self._audit_auth_surface_response("POST", path, response)
            self._write_json(response["status"], response["payload"])
            return

        if self._recording_surface().handles_post(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            response = self._recording_surface().route_post(path)
            if response["kind"] == "bytes":
                self._write_bytes(response["status"], response["body"], content_type=response["content_type"])
            else:
                self._write_json(response["status"], response["payload"])
            return

        sunshine_body: bytes | None = None
        if path.startswith("/api/v1/public/sunshine/"):
            try:
                sunshine_body = self._read_binary_body(max_bytes=16 * 1024 * 1024)
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid content length: {exc}"})
                return
            response = public_sunshine_surface_service().route_request(
                parsed.path,
                query=parsed.query,
                method="POST",
                body=sunshine_body,
                request_headers={
                    "Content-Type": self.headers.get("Content-Type", ""),
                    "Accept": self.headers.get("Accept", ""),
                },
            )
            if response is not None:
                if response["kind"] == "proxy":
                    self._write_proxy_response(response["status"], response["headers"], response["body"])
                else:
                    self._write_json(response["status"], response["payload"])
                return
            return

        public_install_payload: dict[str, Any] | None = None
        if path.endswith("/failed") and int(self.headers.get("Content-Length", "0") or "0") > 0:
            try:
                public_install_payload = self._read_json_body()
            except Exception:
                public_install_payload = {}
        response = public_ubuntu_install_surface_service().route_post(
            path,
            query=query,
            payload=public_install_payload,
        )
        if response is not None:
            self._write_json(response["status"], response["payload"])
            return

        if endpoint_http_surface_service().handles_path(path):
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            json_payload: dict[str, Any] | None = None
            binary_payload: bytes | None = None
            if endpoint_http_surface_service().requires_json_body(path):
                try:
                    json_payload = self._read_json_body()
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
            if endpoint_http_surface_service().requires_binary_body(path):
                try:
                    binary_payload = self._read_binary_body(max_bytes=128 * 1024 * 1024)
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid upload: {exc}"})
                    return
            response = endpoint_http_surface_service().route_post(
                path,
                endpoint_identity=self._endpoint_identity(),
                query=query,
                json_payload=json_payload,
                binary_payload=binary_payload,
            )
            self._write_json(response["status"], response["payload"])
            return

        if endpoint_lifecycle_surface_service().handles_post(path):
            if endpoint_lifecycle_surface_service().requires_endpoint_auth(path) and not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = endpoint_lifecycle_surface_service().route_post(
                path,
                endpoint_identity=self._endpoint_identity(),
                json_payload=json_payload,
                remote_addr=self.client_address[0],
            )
            self._audit_event(
                "endpoint.lifecycle",
                "success" if int(response["status"]) < 400 else "error",
                method="POST",
                path=path,
                status=int(response["status"]),
            )
            self._write_json(response["status"], response["payload"])
            return

        if vm_mutation_surface_service().handles_path(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            json_payload: dict[str, Any] | None = None
            if vm_mutation_surface_service().requires_json_body(path):
                try:
                    json_payload = self._read_json_body()
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
            elif vm_mutation_surface_service().accepts_optional_json_body(path) and int(self.headers.get("Content-Length", "0") or "0") > 0:
                try:
                    json_payload = self._read_json_body()
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
            response = vm_mutation_surface_service().route_post(
                path,
                json_payload=json_payload,
                requester_identity=self._requester_identity(),
            )
            self._audit_event(
                "mutation.request",
                "success" if int(response["status"]) < 400 else "error",
                method="POST",
                path=path,
                permission=authz_policy_service().required_permission("POST", path),
                username=self._requester_identity(),
                status=int(response["status"]),
            )
            vm_power_event = build_vm_power_audit_event(response, requester_identity=self._requester_identity())
            if isinstance(vm_power_event, dict):
                self._audit_event(
                    str(vm_power_event.get("event_type") or "vm.unknown"),
                    str(vm_power_event.get("outcome") or "unknown"),
                    **(vm_power_event.get("details") if isinstance(vm_power_event.get("details"), dict) else {}),
                )
                if str(vm_power_event.get("outcome") or "") == "success":
                    event_type = str(vm_power_event.get("event_type") or "")
                    event_details = vm_power_event.get("details") if isinstance(vm_power_event.get("details"), dict) else {}
                    try:
                        webhook_service().dispatch_event(
                            event_type=event_type,
                            event_payload={
                                "vm": event_details,
                                "requested_by": self._requester_identity(),
                            },
                        )
                    except Exception:
                        pass
            self._write_json(response["status"], response["payload"])
            return

        if gpu_passthrough_surface_service().handles_path(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = gpu_passthrough_surface_service().route_post(
                path,
                json_payload=json_payload,
            )
            self._audit_event(
                "gpu.passthrough.request",
                "success" if int(response["status"]) < 400 else "error",
                method="POST",
                path=path,
                username=self._requester_identity(),
                status=int(response["status"]),
            )
            self._write_json(response["status"], response["payload"])
            return

        if vgpu_surface_service().handles_path_post(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = vgpu_surface_service().route_post(path, json_payload=json_payload)
            self._audit_event(
                "gpu.vgpu.request",
                "success" if int(response["status"]) < 400 else "error",
                method="POST",
                path=path,
                username=self._requester_identity(),
                status=int(response["status"]),
            )
            self._write_json(response["status"], response["payload"])
            return

        if self._pools_surface().handles_post(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            try:
                json_payload = self._read_json_body() if int(self.headers.get("Content-Length", "0") or "0") > 0 else {}
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = self._pools_surface().route_post(path, json_payload=json_payload)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        admin_post_path = "/api/v1/provisioning/vms" if path == "/api/v1/vms" else path
        if admin_http_surface_service().handles_post(admin_post_path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", admin_post_path):
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                response = admin_http_surface_service().read_error_response("POST", admin_post_path, exc)
                self._write_json(response["status"], response["payload"])
                return
            response = admin_http_surface_service().route_post(
                admin_post_path,
                json_payload=json_payload,
                requester_identity=self._requester_identity(),
            )
            self._audit_event(
                "mutation.request",
                "success" if int(response["status"]) < 400 else "error",
                method="POST",
                path=path,
                effective_path=admin_post_path,
                permission=authz_policy_service().required_permission("POST", admin_post_path),
                username=self._requester_identity(),
                status=int(response["status"]),
            )
            self._write_json(response["status"], response["payload"])
            return

        if path.startswith("/api/v1/settings/"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = server_settings_service().route_post(path, json_payload or {})
            if response is not None:
                self._audit_event(
                    "settings.mutation",
                    "success" if int(response["status"]) < 400 else "error",
                    method="POST",
                    path=path,
                    username=self._requester_identity(),
                )
                self._write_json(response["status"], response["payload"])
                return

        if network_http_surface_service().handles_post(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            try:
                json_payload = self._read_json_body() if int(self.headers.get("Content-Length", "0") or "0") > 0 else {}
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = network_http_surface_service().route_post(path, json_payload=json_payload)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_PUT(self) -> None:  # noqa: N802
        if not self._enforce_api_rate_limit(urlparse(self.path).path.rstrip("/") or "/"):
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if scim_service().handles_path(path):
            if not SCIM_BEARER_TOKEN:
                self._write_json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": "scim disabled"})
                return
            if not self._is_scim_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = scim_service().route_put(path, payload)
            self._write_json(response["status"], response["payload"])
            return

        if auth_http_surface_service().handles_put(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("PUT", path):
                return
            try:
                payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            principal = self._auth_principal()
            requester_tenant = (principal or {}).get("tenant_id") or None
            response = auth_http_surface_service().route_put(
                path, json_payload=payload, requester_tenant_id=requester_tenant
            )
            self._audit_auth_surface_response("PUT", path, response)
            self._write_json(response["status"], response["payload"])
            return

        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        if not self._authorize_or_respond("PUT", path):
            return

        if self._backups_surface().handles_put(path):
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = self._backups_surface().route_put(path, json_payload=json_payload)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        if self._pools_surface().handles_put(path):
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = self._pools_surface().route_put(path, json_payload=json_payload)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        if path.startswith("/api/v1/settings/"):
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = server_settings_service().route_put(path, json_payload or {})
            if response is not None:
                self._audit_event(
                    "settings.mutation",
                    "success" if int(response["status"]) < 400 else "error",
                    method="PUT",
                    path=path,
                    username=self._requester_identity(),
                )
                self._write_json(response["status"], response["payload"])
                return

        if not admin_http_surface_service().handles_put(path):
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        try:
            json_payload = self._read_json_body()
        except Exception as exc:
            response = admin_http_surface_service().read_error_response("PUT", path, exc)
            self._write_json(response["status"], response["payload"])
            return
        response = admin_http_surface_service().route_put(path, json_payload=json_payload)
        self._audit_event(
            "mutation.request",
            "success" if int(response["status"]) < 400 else "error",
            method="PUT",
            path=path,
            permission=authz_policy_service().required_permission("PUT", path),
            username=self._requester_identity(),
            status=int(response["status"]),
        )
        self._write_json(response["status"], response["payload"])

    def do_DELETE(self) -> None:  # noqa: N802
        if not self._enforce_api_rate_limit(urlparse(self.path).path.rstrip("/") or "/"):
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if scim_service().handles_path(path):
            if not SCIM_BEARER_TOKEN:
                self._write_json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": "scim disabled"})
                return
            if not self._is_scim_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            response = scim_service().route_delete(path)
            if int(response["status"]) == int(HTTPStatus.NO_CONTENT):
                self.send_response(HTTPStatus.NO_CONTENT)
                self._write_common_security_headers()
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._write_json(response["status"], response["payload"])
            return

        if auth_http_surface_service().handles_delete(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("DELETE", path):
                return
            principal = self._auth_principal()
            requester_tenant = (principal or {}).get("tenant_id") or None
            response = auth_http_surface_service().route_delete(
                path, requester_tenant_id=requester_tenant
            )
            self._audit_auth_surface_response("DELETE", path, response)
            self._write_json(response["status"], response["payload"])
            return

        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        if not self._authorize_or_respond("DELETE", path):
            return
        if self._pools_surface().handles_delete(path):
            response = self._pools_surface().route_delete(path)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        if not admin_http_surface_service().handles_delete(path):
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        response = admin_http_surface_service().route_delete(path)
        self._audit_event(
            "mutation.request",
            "success" if int(response["status"]) < 400 else "error",
            method="DELETE",
            path=path,
            permission=authz_policy_service().required_permission("DELETE", path),
            username=self._requester_identity(),
            status=int(response["status"]),
        )
        self._write_json(response["status"], response["payload"])

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{utcnow()}] {self.address_string()} {fmt % args}", flush=True)

    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        except Exception as error:
            self._handle_unexpected_error(error)


def main() -> int:
    global API_TOKEN, SCIM_BEARER_TOKEN, PAIRING_TOKEN_SECRET  # noqa: PLW0603
    # Auto-bootstrap: if secrets not set via env, load or generate from SecretStore.
    # Must update BOTH service_registry module globals (used by factory functions)
    # and control-plane.py module globals (used by Handler class at request time).
    _svc_registry.API_TOKEN = _bootstrap_secret("manager-api-token", _svc_registry.API_TOKEN, generate=True)
    _svc_registry.SCIM_BEARER_TOKEN = _bootstrap_secret("scim-bearer-token", _svc_registry.SCIM_BEARER_TOKEN, generate=False)
    _svc_registry.PAIRING_TOKEN_SECRET = _bootstrap_secret("pairing-token-secret", _svc_registry.PAIRING_TOKEN_SECRET, generate=True)
    API_TOKEN = _svc_registry.API_TOKEN
    SCIM_BEARER_TOKEN = _svc_registry.SCIM_BEARER_TOKEN
    PAIRING_TOKEN_SECRET = _svc_registry.PAIRING_TOKEN_SECRET
    # Wire AuditLogService into SecretStoreService (audit fn must be set after audit log is ready)
    def _audit_secret_event(event: str, details: dict) -> None:
        # Never include secret values in audit events
        safe_details = {k: v for k, v in details.items() if k != "value"}
        audit_log_service().write_event(event, "ok", details=safe_details)
    _secret_store()._audit_fn = _audit_secret_event
    effective_data_dir = ensure_data_dir()
    ensure_cluster_rpc_listener()
    _start_recording_retention_thread()
    _start_backup_scheduler_thread()
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(
        json.dumps(
            {
                "service": "beagle-control-plane",
                "version": VERSION,
                "listen_host": LISTEN_HOST,
                "listen_port": LISTEN_PORT,
                "allow_localhost_noauth": ALLOW_LOCALHOST_NOAUTH,
                "data_dir": str(effective_data_dir),
            }
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if _svc_registry.RECORDING_RETENTION_STOP_EVENT is not None:
            _svc_registry.RECORDING_RETENTION_STOP_EVENT.set()
        if _svc_registry.RECORDING_RETENTION_THREAD is not None:
            _svc_registry.RECORDING_RETENTION_THREAD.join(timeout=5)
        if _svc_registry.BACKUP_SCHEDULER_STOP_EVENT is not None:
            _svc_registry.BACKUP_SCHEDULER_STOP_EVENT.set()
        if _svc_registry.BACKUP_SCHEDULER_THREAD is not None:
            _svc_registry.BACKUP_SCHEDULER_THREAD.join(timeout=5)
        if _svc_registry.CLUSTER_RPC_SERVER is not None:
            _svc_registry.CLUSTER_RPC_SERVER.shutdown()
            _svc_registry.CLUSTER_RPC_SERVER.server_close()
        if _svc_registry.CLUSTER_RPC_THREAD is not None:
            _svc_registry.CLUSTER_RPC_THREAD.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
