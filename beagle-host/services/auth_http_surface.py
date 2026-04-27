from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable


class AuthHttpSurfaceService:
    def __init__(self, *, auth_session: Any) -> None:
        self._auth_session = auth_session

    @staticmethod
    def _json_response(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    @staticmethod
    def _auth_user_match(path: str) -> re.Match[str] | None:
        return re.match(r"^/api/v1/auth/users/(?P<username>[A-Za-z0-9._-]+)$", path)

    @staticmethod
    def _auth_role_match(path: str) -> re.Match[str] | None:
        return re.match(r"^/api/v1/auth/roles/(?P<name>[A-Za-z0-9._:-]+)$", path)

    @staticmethod
    def _auth_user_revoke_sessions_match(path: str) -> re.Match[str] | None:
        return re.match(r"^/api/v1/auth/users/(?P<username>[A-Za-z0-9._-]+)/revoke-sessions$", path)

    @staticmethod
    def handles_get(path: str) -> bool:
        return path in {"/api/v1/auth/users", "/api/v1/auth/roles", "/api/v1/auth/sessions", "/api/v1/auth/tenants"}

    @staticmethod
    def handles_post(path: str) -> bool:
        return (
            path in {"/api/v1/auth/users", "/api/v1/auth/roles"}
            or AuthHttpSurfaceService._auth_user_revoke_sessions_match(path) is not None
        )

    @staticmethod
    def handles_put(path: str) -> bool:
        return (
            AuthHttpSurfaceService._auth_user_match(path) is not None
            or AuthHttpSurfaceService._auth_role_match(path) is not None
        )

    @staticmethod
    def handles_delete(path: str) -> bool:
        return (
            AuthHttpSurfaceService._auth_user_match(path) is not None
            or AuthHttpSurfaceService._auth_role_match(path) is not None
            or bool(re.fullmatch(r"^/api/v1/auth/sessions/[A-Za-z0-9_=-]{8,128}$", path))
        )

    @staticmethod
    def requires_json_body(path: str) -> bool:
        return AuthHttpSurfaceService._auth_user_revoke_sessions_match(path) is None

    @staticmethod
    def _sanitize_identifier(raw: Any, *, label: str, pattern: str) -> str:
        text = str(raw or "").strip()
        if not text:
            raise ValueError(f"{label} is required")
        if not re.fullmatch(pattern, text):
            raise ValueError(f"invalid {label}")
        return text

    def route_get(self, path: str, *, requester_tenant_id: str | None = None, query_params: dict | None = None) -> dict[str, Any]:
        if path == "/api/v1/auth/users":
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "users": self._auth_session.list_users(
                        requester_tenant_id=requester_tenant_id
                    ),
                },
            )
        if path == "/api/v1/auth/roles":
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "roles": self._auth_session.list_roles(),
                },
            )
        if path == "/api/v1/auth/sessions":
            params = query_params or {}
            username_filter = str(params.get("username") or "").strip() or None
            tenant_filter = str(params.get("tenant_id") or "").strip() or None
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "sessions": self._auth_session.list_active_sessions(
                        username=username_filter,
                        tenant_id=tenant_filter,
                    ),
                },
            )
        if path == "/api/v1/auth/tenants":
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "tenants": self._auth_session.list_tenants(),
                },
            )
        return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def route_post(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None,
        requester_tenant_id: str | None = None,
    ) -> dict[str, Any]:
        payload = json_payload if isinstance(json_payload, dict) else {}

        if path == "/api/v1/auth/users":
            try:
                username = self._sanitize_identifier(
                    payload.get("username"),
                    label="username",
                    pattern=r"^[A-Za-z0-9._-]{1,64}$",
                )
                # Tenant-scoped requester can only create users within their own tenant
                requested_tenant = payload.get("tenant_id") or None
                if requested_tenant is not None:
                    requested_tenant = str(requested_tenant).strip() or None
                if requester_tenant_id is not None:
                    if requested_tenant is not None and requested_tenant != requester_tenant_id:
                        return self._json_response(
                            HTTPStatus.FORBIDDEN,
                            {"ok": False, "error": "cross-tenant user creation denied"},
                        )
                    requested_tenant = requester_tenant_id
                user = self._auth_session.create_user(
                    username=username,
                    password=str(payload.get("password") or ""),
                    role=str(payload.get("role") or "viewer").strip().lower() or "viewer",
                    enabled=bool(payload.get("enabled", True)),
                    tenant_id=requested_tenant,
                    session_geo_routing=payload.get("session_geo_routing") if isinstance(payload.get("session_geo_routing"), dict) else None,
                )
            except Exception as exc:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json_response(HTTPStatus.CREATED, {"ok": True, "user": user})

        if path == "/api/v1/auth/roles":
            try:
                role_name = self._sanitize_identifier(
                    payload.get("name"),
                    label="role",
                    pattern=r"^[A-Za-z0-9._:-]{1,64}$",
                ).lower()
                permissions_raw = payload.get("permissions") if isinstance(payload.get("permissions"), list) else []
                permissions = [str(value).strip() for value in permissions_raw if str(value).strip()]
                role = self._auth_session.save_role(name=role_name, permissions=permissions)
            except Exception as exc:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json_response(HTTPStatus.CREATED, {"ok": True, "role": role})

        revoke_match = self._auth_user_revoke_sessions_match(path)
        if revoke_match is not None:
            username = str(revoke_match.group("username") or "").strip()
            revoked_count = self._auth_session.revoke_user_sessions(username)
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "username": username,
                    "revoked_count": revoked_count,
                },
            )

        return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def route_put(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None,
        requester_tenant_id: str | None = None,
    ) -> dict[str, Any]:
        payload = json_payload if isinstance(json_payload, dict) else {}

        user_match = self._auth_user_match(path)
        if user_match is not None:
            username = str(user_match.group("username") or "")
            # Tenant-scoped requester cannot modify users from a different tenant
            if requester_tenant_id is not None:
                target_tid = self._auth_session.get_user_tenant_id(username)
                if target_tid != requester_tenant_id:
                    return self._json_response(
                        HTTPStatus.FORBIDDEN,
                        {"ok": False, "error": "cross-tenant user mutation denied"},
                    )
            try:
                updated = self._auth_session.update_user(
                    username=username,
                    role=str(payload.get("role")).strip().lower() if payload.get("role") is not None else None,
                    enabled=bool(payload.get("enabled")) if "enabled" in payload else None,
                    password=str(payload.get("password") or "") if payload.get("password") is not None else None,
                    tenant_id=(str(payload.get("tenant_id")).strip() or None) if "tenant_id" in payload else ...,
                    session_geo_routing=payload.get("session_geo_routing") if "session_geo_routing" in payload else ...,
                )
            except Exception as exc:
                status = HTTPStatus.NOT_FOUND if str(exc) == "user not found" else HTTPStatus.BAD_REQUEST
                return self._json_response(status, {"ok": False, "error": str(exc)})
            return self._json_response(HTTPStatus.OK, {"ok": True, "user": updated})

        role_match = self._auth_role_match(path)
        if role_match is not None:
            permissions_raw = payload.get("permissions") if isinstance(payload.get("permissions"), list) else []
            permissions = [str(value).strip() for value in permissions_raw if str(value).strip()]
            try:
                role = self._auth_session.save_role(
                    name=str(role_match.group("name") or "").strip().lower(),
                    permissions=permissions,
                )
            except Exception as exc:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json_response(HTTPStatus.OK, {"ok": True, "role": role})

        return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def route_delete(self, path: str, *, requester_tenant_id: str | None = None) -> dict[str, Any]:
        user_match = self._auth_user_match(path)
        if user_match is not None:
            username = str(user_match.group("username") or "")
            # Tenant-scoped requester cannot delete users from a different tenant
            if requester_tenant_id is not None:
                target_tid = self._auth_session.get_user_tenant_id(username)
                if target_tid != requester_tenant_id:
                    return self._json_response(
                        HTTPStatus.FORBIDDEN,
                        {"ok": False, "error": "cross-tenant user deletion denied"},
                    )
            deleted = self._auth_session.delete_user(username)
            if not deleted:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "user not found"})
            return self._json_response(HTTPStatus.OK, {"ok": True, "deleted": username})

        role_match = self._auth_role_match(path)
        if role_match is not None:
            role_name = str(role_match.group("name") or "")
            deleted = self._auth_session.delete_role(role_name)
            if not deleted:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "role not found or protected"})
            return self._json_response(HTTPStatus.OK, {"ok": True, "deleted": role_name})

        session_jti_match = re.fullmatch(r"^/api/v1/auth/sessions/(?P<jti>[A-Za-z0-9_=-]{8,128})$", path)
        if session_jti_match is not None:
            jti = session_jti_match.group("jti")
            revoked = self._auth_session.revoke_session_by_jti(jti)
            if not revoked:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "session not found or already revoked"})
            return self._json_response(HTTPStatus.OK, {"ok": True, "revoked_jti": jti})

        return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
