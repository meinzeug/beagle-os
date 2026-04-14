"""Central RBAC policy mapping for control-plane routes."""

from __future__ import annotations

import re


class AuthzPolicyService:
    @staticmethod
    def required_permission(method: str, path: str) -> str | None:
        verb = str(method or "").upper()
        route = str(path or "")
        if verb == "POST":
            if route == "/api/v1/actions/bulk":
                return "actions:bulk"
            if route in {"/api/v1/ubuntu-beagle-vms", "/api/v1/provisioning/vms"}:
                return "provisioning:write"
            if route == "/api/v1/policies" or route.startswith("/api/v1/policies/"):
                return "policy:write"
            if route.startswith("/api/v1/vms/") and (
                route.endswith("/installer-prep")
                or route.endswith("/actions")
                or route.endswith("/usb/refresh")
                or route.endswith("/usb/attach")
                or route.endswith("/usb/detach")
                or route.endswith("/sunshine-access")
            ):
                return "vm:mutate"
            if route.startswith("/api/v1/virtualization/vms/") and route.endswith("/power"):
                return "vm:mutate"
            if route == "/api/v1/auth/users" or route == "/api/v1/auth/roles":
                return "auth:write"
            if re.match(r"^/api/v1/auth/users/[A-Za-z0-9._-]+/revoke-sessions$", route):
                return "auth:write"
        if verb == "PUT":
            if re.match(r"^/api/v1/provisioning/vms/\d+$", route):
                return "provisioning:write"
            if route.startswith("/api/v1/policies/"):
                return "policy:write"
            if route.startswith("/api/v1/auth/users/") or route.startswith("/api/v1/auth/roles/"):
                return "auth:write"
        if verb == "DELETE":
            if route.startswith("/api/v1/policies/"):
                return "policy:write"
            if route.startswith("/api/v1/auth/users/") or route.startswith("/api/v1/auth/roles/"):
                return "auth:write"
        if verb == "GET":
            if route in {"/api/v1/auth/users", "/api/v1/auth/roles"}:
                return "auth:read"
        return None

    @staticmethod
    def is_allowed(role: str, permission: str | None, role_permissions: set[str]) -> bool:
        role_name = str(role or "").strip().lower() or "viewer"
        if permission is None:
            return True
        if role_name == "superadmin":
            return True
        permissions = {str(value).strip() for value in role_permissions if str(value).strip()}
        return "*" in permissions or permission in permissions
