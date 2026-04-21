from __future__ import annotations

import sys
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from auth_http_surface import AuthHttpSurfaceService


class _AuthSessionStub:
    def __init__(self) -> None:
        self._users = [{"username": "admin", "role": "superadmin", "enabled": True}]
        self._roles = [{"name": "viewer", "permissions": ["inventory:read"]}]

    def list_users(self):
        return list(self._users)

    def list_roles(self):
        return list(self._roles)

    def create_user(self, *, username: str, password: str, role: str, enabled: bool):
        if not password:
            raise ValueError("password is required")
        user = {"username": username, "role": role, "enabled": bool(enabled)}
        self._users.append(user)
        return user

    def save_role(self, *, name: str, permissions: list[str]):
        role = {"name": name, "permissions": permissions}
        self._roles = [item for item in self._roles if item["name"] != name]
        self._roles.append(role)
        return role

    def revoke_user_sessions(self, username: str):
        return 2 if username == "admin" else 0

    def update_user(self, *, username: str, role, enabled, password):
        for user in self._users:
            if user["username"] == username:
                if role is not None:
                    user["role"] = role
                if enabled is not None:
                    user["enabled"] = bool(enabled)
                if password is not None and not password:
                    raise ValueError("password cannot be empty")
                return user
        raise ValueError("user not found")

    def delete_user(self, username: str):
        before = len(self._users)
        self._users = [item for item in self._users if item["username"] != username]
        return len(self._users) < before

    def delete_role(self, name: str):
        if name == "superadmin":
            return False
        before = len(self._roles)
        self._roles = [item for item in self._roles if item["name"] != name]
        return len(self._roles) < before


def _service() -> AuthHttpSurfaceService:
    return AuthHttpSurfaceService(auth_session=_AuthSessionStub())


def test_route_get_users_and_roles() -> None:
    service = _service()
    users_response = service.route_get("/api/v1/auth/users")
    roles_response = service.route_get("/api/v1/auth/roles")

    assert int(users_response["status"]) == 200
    assert users_response["payload"]["ok"] is True
    assert users_response["payload"]["users"][0]["username"] == "admin"

    assert int(roles_response["status"]) == 200
    assert roles_response["payload"]["ok"] is True
    assert roles_response["payload"]["roles"][0]["name"] == "viewer"


def test_route_post_create_user_and_role() -> None:
    service = _service()

    user_response = service.route_post(
        "/api/v1/auth/users",
        json_payload={"username": "ops", "password": "secret123", "role": "admin", "enabled": True},
    )
    role_response = service.route_post(
        "/api/v1/auth/roles",
        json_payload={"name": "pool-operator", "permissions": ["pool:read", "pool:scale"]},
    )

    assert int(user_response["status"]) == 201
    assert user_response["payload"]["user"]["username"] == "ops"

    assert int(role_response["status"]) == 201
    assert role_response["payload"]["role"]["name"] == "pool-operator"


def test_route_post_revoke_sessions() -> None:
    service = _service()

    response = service.route_post(
        "/api/v1/auth/users/admin/revoke-sessions",
        json_payload=None,
    )

    assert int(response["status"]) == 200
    assert response["payload"]["username"] == "admin"
    assert response["payload"]["revoked_count"] == 2


def test_route_put_not_found_user_maps_to_404() -> None:
    service = _service()

    response = service.route_put(
        "/api/v1/auth/users/missing",
        json_payload={"role": "viewer"},
    )

    assert int(response["status"]) == 404
    assert response["payload"]["error"] == "user not found"


def test_route_delete_role_protected_maps_to_not_found_shape() -> None:
    service = _service()

    response = service.route_delete("/api/v1/auth/roles/superadmin")

    assert int(response["status"]) == 404
    assert response["payload"]["error"] == "role not found or protected"
