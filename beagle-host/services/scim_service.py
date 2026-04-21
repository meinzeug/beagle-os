from __future__ import annotations

from http import HTTPStatus
from typing import Any, Callable


class ScimService:
    """Minimal SCIM 2.0 surface for Users and Groups."""

    def __init__(
        self,
        *,
        create_user: Callable[..., dict[str, Any]],
        delete_role: Callable[[str], bool],
        delete_user: Callable[[str], bool],
        list_roles: Callable[[], list[dict[str, Any]]],
        list_users: Callable[[], list[dict[str, Any]]],
        save_role: Callable[..., dict[str, Any]],
        service_name: str,
        token_urlsafe: Callable[[int], str],
        update_user: Callable[..., dict[str, Any]],
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._create_user = create_user
        self._delete_role = delete_role
        self._delete_user = delete_user
        self._list_roles = list_roles
        self._list_users = list_users
        self._save_role = save_role
        self._service_name = str(service_name or "beagle-control-plane")
        self._token_urlsafe = token_urlsafe
        self._update_user = update_user
        self._utcnow = utcnow
        self._version = str(version or "")

    @staticmethod
    def handles_path(path: str) -> bool:
        return str(path or "").startswith("/scim/v2/")

    @staticmethod
    def _response(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"status": status, "payload": payload}

    @staticmethod
    def _resource_id_from_path(path: str) -> str:
        parts = [segment for segment in str(path or "").split("/") if segment]
        if len(parts) < 4:
            return ""
        return str(parts[3] or "").strip()

    @staticmethod
    def _is_active(value: Any, default: bool = True) -> bool:
        if value is None:
            return bool(default)
        return bool(value)

    @staticmethod
    def _extract_role(payload: dict[str, Any], default_role: str = "viewer") -> str:
        role = str(payload.get("role") or "").strip().lower()
        if role:
            return role
        roles = payload.get("roles")
        if isinstance(roles, list) and roles:
            first = roles[0]
            if isinstance(first, dict):
                return str(first.get("value") or default_role).strip().lower() or default_role
            return str(first or default_role).strip().lower() or default_role
        return str(default_role or "viewer").strip().lower() or "viewer"

    def _scim_list_payload(self, resources: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": len(resources),
            "startIndex": 1,
            "itemsPerPage": len(resources),
            "Resources": resources,
            "meta": {
                "service": self._service_name,
                "version": self._version,
                "generated_at": self._utcnow(),
            },
        }

    def _scim_user(self, user: dict[str, Any]) -> dict[str, Any]:
        username = str(user.get("username") or "").strip()
        role = str(user.get("role") or "viewer").strip().lower() or "viewer"
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "id": username,
            "userName": username,
            "active": bool(user.get("enabled", True)),
            "roles": [{"value": role, "display": role}],
            "meta": {
                "resourceType": "User",
                "created": int(user.get("created_at") or 0),
            },
        }

    def _scim_group(self, role: dict[str, Any]) -> dict[str, Any]:
        name = str(role.get("name") or "").strip().lower()
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "id": name,
            "displayName": name,
            "members": [],
            "meta": {
                "resourceType": "Group",
            },
        }

    def route_get(self, path: str) -> dict[str, Any]:
        if path == "/scim/v2/Users":
            resources = [self._scim_user(item) for item in self._list_users()]
            return self._response(HTTPStatus.OK, self._scim_list_payload(resources))

        if path == "/scim/v2/Groups":
            resources = [self._scim_group(item) for item in self._list_roles()]
            return self._response(HTTPStatus.OK, self._scim_list_payload(resources))

        if path.startswith("/scim/v2/Users/"):
            user_id = self._resource_id_from_path(path)
            for item in self._list_users():
                if str(item.get("username") or "").strip().lower() == user_id.lower():
                    return self._response(HTTPStatus.OK, self._scim_user(item))
            return self._response(HTTPStatus.NOT_FOUND, {"detail": "user not found"})

        if path.startswith("/scim/v2/Groups/"):
            group_id = self._resource_id_from_path(path)
            for item in self._list_roles():
                if str(item.get("name") or "").strip().lower() == group_id.lower():
                    return self._response(HTTPStatus.OK, self._scim_group(item))
            return self._response(HTTPStatus.NOT_FOUND, {"detail": "group not found"})

        return self._response(HTTPStatus.NOT_FOUND, {"detail": "not found"})

    def route_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if path == "/scim/v2/Users":
            user_name = str(payload.get("userName") or payload.get("username") or "").strip()
            if not user_name:
                return self._response(HTTPStatus.BAD_REQUEST, {"detail": "missing userName"})
            role_name = self._extract_role(payload)
            active = self._is_active(payload.get("active"), True)
            try:
                created = self._create_user(
                    username=user_name,
                    password=self._token_urlsafe(18),
                    role=role_name,
                    enabled=active,
                )
            except Exception as exc:
                return self._response(HTTPStatus.BAD_REQUEST, {"detail": str(exc)})
            return self._response(HTTPStatus.CREATED, self._scim_user(created))

        if path == "/scim/v2/Groups":
            display_name = str(payload.get("displayName") or payload.get("name") or "").strip().lower()
            if not display_name:
                return self._response(HTTPStatus.BAD_REQUEST, {"detail": "missing displayName"})
            try:
                saved = self._save_role(name=display_name, permissions=[])
            except Exception as exc:
                return self._response(HTTPStatus.BAD_REQUEST, {"detail": str(exc)})
            return self._response(HTTPStatus.CREATED, self._scim_group(saved))

        return self._response(HTTPStatus.NOT_FOUND, {"detail": "not found"})

    def route_put(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if path.startswith("/scim/v2/Users/"):
            user_id = self._resource_id_from_path(path)
            role_name = self._extract_role(payload)
            enabled = self._is_active(payload.get("active"), True)
            try:
                updated = self._update_user(
                    username=user_id,
                    role=role_name,
                    enabled=enabled,
                )
            except Exception as exc:
                return self._response(HTTPStatus.BAD_REQUEST, {"detail": str(exc)})
            return self._response(HTTPStatus.OK, self._scim_user(updated))

        if path.startswith("/scim/v2/Groups/"):
            group_id = self._resource_id_from_path(path)
            try:
                saved = self._save_role(name=group_id, permissions=[])
            except Exception as exc:
                return self._response(HTTPStatus.BAD_REQUEST, {"detail": str(exc)})
            return self._response(HTTPStatus.OK, self._scim_group(saved))

        return self._response(HTTPStatus.NOT_FOUND, {"detail": "not found"})

    def route_delete(self, path: str) -> dict[str, Any]:
        if path.startswith("/scim/v2/Users/"):
            user_id = self._resource_id_from_path(path)
            deleted = self._delete_user(user_id)
            if not deleted:
                return self._response(HTTPStatus.NOT_FOUND, {"detail": "user not found"})
            return self._response(HTTPStatus.NO_CONTENT, {})

        if path.startswith("/scim/v2/Groups/"):
            group_id = self._resource_id_from_path(path)
            deleted = self._delete_role(group_id)
            if not deleted:
                return self._response(HTTPStatus.NOT_FOUND, {"detail": "group not found"})
            return self._response(HTTPStatus.NO_CONTENT, {})

        return self._response(HTTPStatus.NOT_FOUND, {"detail": "not found"})
