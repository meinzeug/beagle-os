"""Request handler helper methods mixin for beagle-control-plane.

All helper methods for the HTTP handler are defined here.  The ``Handler``
class in ``beagle-control-plane.py`` inherits from this mixin so that the
main entry-point file stays focused on the HTTP dispatch logic.
"""
from __future__ import annotations

import json
import ipaddress
import re
import secrets
import time
import threading
import traceback
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, urlparse

import service_registry as _svc_registry  # for mutable bootstrapped values
from service_registry import *  # noqa: F401,F403
from audit_report_http_surface import AuditReportHttpSurfaceService
from auth_session_http_surface import AuthSessionHttpSurfaceService
from recording_http_surface import RecordingHttpSurfaceService
from backups_http_surface import BackupsHttpSurfaceService
from pools_http_surface import PoolsHttpSurfaceService
from cluster_http_surface import ClusterHttpSurfaceService


class HandlerMixin:
    """Mixin providing all helper methods for the Beagle control-plane request handler."""

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

    @staticmethod
    def _json_default(value: Any) -> Any:
        if isinstance(value, (set, frozenset, tuple)):
            return list(value)
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return value.hex()
        return repr(value)

    @staticmethod
    def _valid_ip_address(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            return str(ipaddress.ip_address(raw))
        except ValueError:
            return ""

    @classmethod
    def _is_trusted_forwarding_peer(cls, value: str) -> bool:
        addr = cls._valid_ip_address(value)
        if not addr:
            return False
        parsed = ipaddress.ip_address(addr)
        return parsed.is_loopback

    def _forwarded_client_addr(self) -> str:
        if not self._is_trusted_forwarding_peer(self.client_address[0] if self.client_address else ""):
            return ""
        forwarded_for = str(self.headers.get("X-Forwarded-For") or "")
        for part in forwarded_for.split(","):
            addr = self._valid_ip_address(part)
            if addr:
                return addr
        return self._valid_ip_address(str(self.headers.get("X-Real-IP") or ""))

    def _client_addr(self) -> str:
        forwarded = self._forwarded_client_addr()
        if forwarded:
            return forwarded
        return self._valid_ip_address(self.client_address[0] if self.client_address else "")

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
            structured_logger().info(
                "api.response",
                method=str(getattr(self, "command", "")),
                path=path,
                action=action,
                status=int(status),
                user=self._requester_identity(),
                remote_addr=self._client_addr(),
                resource_type=resource_type,
                resource_id=resource_id,
            )
        except Exception:
            pass

    def _handle_unexpected_error(self, error: Exception) -> None:
        try:
            structured_logger().error(
                "request.unhandled_exception.traceback",
                method=str(getattr(self, "command", "")),
                path=str(urlparse(getattr(self, "path", "") or "").path),
                username=self._requester_identity(),
                remote_addr=self._client_addr(),
                error_type=type(error).__name__,
                error_message=str(error),
                traceback=traceback.format_exc(),
            )
        except Exception:
            pass
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
            remote_addr=self._client_addr,
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
            audit_export_service=audit_export_service(),
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
            storage_image_store_service=storage_image_store_service(),
            storage_quota_service=storage_quota_service(),
            audit_event=self._audit_event,
            requester_identity=self._requester_identity,
            read_binary_body=lambda n: self.rfile.read(n),
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
            enqueue_job=job_queue_service().enqueue,
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
            enqueue_job=job_queue_service().enqueue,
        )

    def _pools_surface(self) -> PoolsHttpSurfaceService:
        return PoolsHttpSurfaceService(
            pool_manager_service=pool_manager_service(),
            gaming_metrics_service=gaming_metrics_service(),
            entitlement_service=entitlement_service(),
            desktop_template_builder_service=desktop_template_builder_service(),
            recording_service=recording_service(),
            session_manager_service=session_manager_service(),
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
            return
        session_jti_match = re.fullmatch(r"^/api/v1/auth/sessions/(?P<jti>[A-Za-z0-9_=-]{8,128})$", path)
        if method == "DELETE" and session_jti_match is not None:
            self._audit_event(
                "auth.session.revoke_by_jti",
                outcome,
                jti=session_jti_match.group("jti"),
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
            if _svc_registry.API_TOKEN and secrets.compare_digest(bearer, _svc_registry.API_TOKEN):
                principal = {"username": "legacy-api-token", "role": "superadmin", "auth_type": "api_token"}
                setattr(self, "_cached_auth_principal", principal)
                return principal
        api_token = self.headers.get("X-Beagle-Api-Token", "").strip()
        if api_token and _svc_registry.API_TOKEN and secrets.compare_digest(api_token, _svc_registry.API_TOKEN):
            principal = {"username": "legacy-api-token", "role": "superadmin", "auth_type": "api_token"}
            setattr(self, "_cached_auth_principal", principal)
            return principal
        setattr(self, "_cached_auth_principal", None)
        return None

    def _is_authenticated(self) -> bool:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/healthz":
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
        if not _svc_registry.SCIM_BEARER_TOKEN:
            return False
        token = extract_bearer_token(self.headers.get("Authorization", ""))
        if not token:
            return False
        return secrets.compare_digest(token, _svc_registry.SCIM_BEARER_TOKEN)

    def _stream_principal(self, parsed) -> dict[str, Any] | None:
        # EventSource cannot send custom Authorization headers, so accept
        # access_token query parameter for this dedicated stream endpoint.
        query = parse_qs(parsed.query or "")
        candidate = str((query.get("access_token") or query.get("token") or [""])[0] or "").strip()
        if candidate:
            session_principal = auth_session_service().resolve_access_token(candidate)
            if session_principal is not None:
                return session_principal
            if _svc_registry.API_TOKEN and secrets.compare_digest(candidate, _svc_registry.API_TOKEN):
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

    def _stream_sse_job(self, generator) -> None:
        """Stream SSE events from a job-progress generator (Plan 07 Schritt 4)."""
        try:
            self.send_response(HTTPStatus.OK)
            self._write_common_security_headers()
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            for chunk in generator:
                self.wfile.write(chunk)
                self.wfile.flush()
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
        request_id = getattr(self, "_beagle_request_id", "") or ""
        if request_id:
            self.send_header("X-Request-Id", request_id)
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
        body = json.dumps(payload, indent=2, default=self._json_default).encode("utf-8") + b"\n"
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
