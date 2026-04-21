"""Unit tests for cross-tenant isolation enforcement in auth_http_surface.

Plan 13 Step 4: Tenant-Scope in all mutating API endpoints.
Acceptance: user from tenant-A cannot read/mutate users from tenant-B.
"""
from __future__ import annotations

import sys
from http import HTTPStatus
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from auth_http_surface import AuthHttpSurfaceService


class _TenantAuthSessionStub:
    """Auth session stub that supports tenant_id on users."""

    def __init__(self) -> None:
        self._users: list[dict] = [
            {"username": "platform-admin", "role": "admin", "enabled": True, "tenant_id": None},
            {"username": "alice", "role": "viewer", "enabled": True, "tenant_id": "tenant-a"},
            {"username": "bob",   "role": "viewer", "enabled": True, "tenant_id": "tenant-b"},
        ]
        self._roles: list[dict] = [
            {"name": "viewer", "permissions": []},
            {"name": "admin",  "permissions": ["*"]},
        ]

    def list_users(self, *, requester_tenant_id=None):
        if requester_tenant_id is not None:
            return [u for u in self._users if u.get("tenant_id") == requester_tenant_id]
        return list(self._users)

    def list_roles(self):
        return list(self._roles)

    def get_user_tenant_id(self, username: str):
        for user in self._users:
            if user["username"] == username:
                return user.get("tenant_id")
        return None

    def create_user(self, *, username, password, role, enabled, tenant_id=None):
        if not password:
            raise ValueError("password is required")
        user = {"username": username, "role": role, "enabled": enabled, "tenant_id": tenant_id}
        self._users.append(user)
        return user

    def update_user(self, *, username, role=None, enabled=None, password=None, tenant_id=...):
        for user in self._users:
            if user["username"] == username:
                if role is not None:
                    user["role"] = role
                return user
        raise ValueError("user not found")

    def delete_user(self, username):
        before = len(self._users)
        self._users = [u for u in self._users if u["username"] != username]
        return len(self._users) < before

    def delete_role(self, name):
        if name in {"admin", "superadmin"}:
            return False
        before = len(self._roles)
        self._roles = [r for r in self._roles if r["name"] != name]
        return len(self._roles) < before

    def save_role(self, *, name, permissions):
        role = {"name": name, "permissions": permissions}
        self._roles = [r for r in self._roles if r["name"] != name]
        self._roles.append(role)
        return role

    def revoke_user_sessions(self, username):
        return 0


def _svc():
    return AuthHttpSurfaceService(auth_session=_TenantAuthSessionStub())


# ── list_users: tenant-scoped requester sees only own tenant ────────────────

def test_list_users_platform_admin_sees_all():
    """Platform admin (no tenant_id) sees all users."""
    svc = _svc()
    resp = svc.route_get("/api/v1/auth/users", requester_tenant_id=None)
    assert resp["status"] == HTTPStatus.OK
    usernames = {u["username"] for u in resp["payload"]["users"]}
    assert "platform-admin" in usernames
    assert "alice" in usernames
    assert "bob" in usernames


def test_list_users_tenant_a_sees_only_own_tenant():
    """Tenant-A requester only sees users in tenant-A."""
    svc = _svc()
    resp = svc.route_get("/api/v1/auth/users", requester_tenant_id="tenant-a")
    assert resp["status"] == HTTPStatus.OK
    usernames = {u["username"] for u in resp["payload"]["users"]}
    assert "alice" in usernames
    assert "bob" not in usernames
    assert "platform-admin" not in usernames


def test_list_users_tenant_b_sees_only_own_tenant():
    """Tenant-B requester only sees users in tenant-B."""
    svc = _svc()
    resp = svc.route_get("/api/v1/auth/users", requester_tenant_id="tenant-b")
    assert resp["status"] == HTTPStatus.OK
    usernames = {u["username"] for u in resp["payload"]["users"]}
    assert "bob" in usernames
    assert "alice" not in usernames


# ── create_user: cross-tenant creation is denied ───────────────────────────

def test_create_user_same_tenant_allowed():
    """Tenant-A requester can create a user in tenant-A."""
    svc = _svc()
    resp = svc.route_post(
        "/api/v1/auth/users",
        json_payload={"username": "carol", "password": "secret123", "role": "viewer"},
        requester_tenant_id="tenant-a",
    )
    assert resp["status"] == HTTPStatus.CREATED
    assert resp["payload"]["user"]["tenant_id"] == "tenant-a"


def test_create_user_cross_tenant_denied():
    """Tenant-A requester cannot create a user explicitly in tenant-B."""
    svc = _svc()
    resp = svc.route_post(
        "/api/v1/auth/users",
        json_payload={
            "username": "intruder",
            "password": "secret123",
            "role": "viewer",
            "tenant_id": "tenant-b",
        },
        requester_tenant_id="tenant-a",
    )
    assert resp["status"] == HTTPStatus.FORBIDDEN
    assert "cross-tenant" in resp["payload"]["error"]


def test_create_user_platform_admin_any_tenant():
    """Platform admin can create users in any tenant."""
    svc = _svc()
    resp = svc.route_post(
        "/api/v1/auth/users",
        json_payload={
            "username": "newuser",
            "password": "secret123",
            "role": "viewer",
            "tenant_id": "tenant-b",
        },
        requester_tenant_id=None,
    )
    assert resp["status"] == HTTPStatus.CREATED
    assert resp["payload"]["user"]["tenant_id"] == "tenant-b"


# ── update_user: cross-tenant mutation is denied ───────────────────────────

def test_update_user_same_tenant_allowed():
    """Tenant-A can update alice (also tenant-A)."""
    svc = _svc()
    resp = svc.route_put(
        "/api/v1/auth/users/alice",
        json_payload={"role": "admin"},
        requester_tenant_id="tenant-a",
    )
    assert resp["status"] == HTTPStatus.OK


def test_update_user_cross_tenant_denied():
    """Tenant-A cannot update bob (tenant-B)."""
    svc = _svc()
    resp = svc.route_put(
        "/api/v1/auth/users/bob",
        json_payload={"role": "admin"},
        requester_tenant_id="tenant-a",
    )
    assert resp["status"] == HTTPStatus.FORBIDDEN
    assert "cross-tenant" in resp["payload"]["error"]


def test_update_user_platform_admin_cross_tenant_allowed():
    """Platform admin can update any user regardless of tenant."""
    svc = _svc()
    resp = svc.route_put(
        "/api/v1/auth/users/bob",
        json_payload={"role": "admin"},
        requester_tenant_id=None,
    )
    assert resp["status"] == HTTPStatus.OK


# ── delete_user: cross-tenant deletion is denied ───────────────────────────

def test_delete_user_same_tenant_allowed():
    """Tenant-A can delete alice (also tenant-A)."""
    svc = _svc()
    resp = svc.route_delete("/api/v1/auth/users/alice", requester_tenant_id="tenant-a")
    assert resp["status"] == HTTPStatus.OK


def test_delete_user_cross_tenant_denied():
    """Tenant-A cannot delete bob (tenant-B)."""
    svc = _svc()
    resp = svc.route_delete("/api/v1/auth/users/bob", requester_tenant_id="tenant-a")
    assert resp["status"] == HTTPStatus.FORBIDDEN
    assert "cross-tenant" in resp["payload"]["error"]


def test_delete_user_platform_admin_cross_tenant_allowed():
    """Platform admin can delete any user regardless of tenant."""
    svc = _svc()
    resp = svc.route_delete("/api/v1/auth/users/bob", requester_tenant_id=None)
    assert resp["status"] == HTTPStatus.OK
