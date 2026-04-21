"""Central RBAC policy mapping for control-plane routes."""

from __future__ import annotations

import re

# Structured catalog of all known permission tags, grouped by category.
# Used by GET /api/v1/auth/permission-tags so the Web Console can render
# a checkbox-based role editor instead of a raw freeform textarea.
PERMISSION_CATALOG: list[dict] = [
    {
        "group": "VMs",
        "tags": [
            {"tag": "vm:read",   "label": "VMs lesen (list / get)"},
            {"tag": "vm:power",  "label": "VMs starten / stoppen (power)"},
            {"tag": "vm:mutate", "label": "VMs erstellen, aendern, loeschen"},
        ],
    },
    {
        "group": "Provisioning",
        "tags": [
            {"tag": "provisioning:read",  "label": "Provisioning-Eintraege lesen"},
            {"tag": "provisioning:write", "label": "Provisioning schreiben / loeschen"},
        ],
    },
    {
        "group": "Policies",
        "tags": [
            {"tag": "policy:read",  "label": "Policies lesen"},
            {"tag": "policy:write", "label": "Policies schreiben / loeschen"},
        ],
    },
    {
        "group": "Benutzer & Rollen",
        "tags": [
            {"tag": "auth:read",  "label": "Benutzer & Rollen lesen"},
            {"tag": "auth:write", "label": "Benutzer & Rollen schreiben / loeschen"},
        ],
    },
    {
        "group": "Einstellungen",
        "tags": [
            {"tag": "settings:read",  "label": "Einstellungen lesen"},
            {"tag": "settings:write", "label": "Einstellungen schreiben"},
        ],
    },
    {
        "group": "Aktionen",
        "tags": [
            {"tag": "actions:bulk", "label": "Bulk-VM-Aktionen ausfuehren"},
        ],
    },
    {
        "group": "Session Recording",
        "tags": [
            {"tag": "session:download_recording", "label": "Session-Recording herunterladen"},
            {"tag": "session:manage_recording", "label": "Session-Recording starten/stoppen"},
        ],
    },
    {
        "group": "Superadmin",
        "tags": [
            {"tag": "*", "label": "Alle Berechtigungen (Superadmin / Wildcard)"},
        ],
    },
]


class AuthzPolicyService:
    @staticmethod
    def required_permission(method: str, path: str) -> str | None:
        verb = str(method or "").upper()
        route = str(path or "")
        if verb == "POST":
            if route == "/api/v1/actions/bulk":
                return "actions:bulk"
            if route in {"/api/v1/ubuntu-beagle-vms", "/api/v1/provisioning/vms", "/api/v1/vms"}:
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
            if route.startswith("/api/v1/settings/"):
                return "settings:write"
            if re.match(r"^/api/v1/sessions/[A-Za-z0-9._:-]+/recording/(start|stop)$", route):
                return "session:manage_recording"
        if verb == "PUT":
            if re.match(r"^/api/v1/provisioning/vms/\d+$", route):
                return "provisioning:write"
            if route.startswith("/api/v1/policies/"):
                return "policy:write"
            if route.startswith("/api/v1/auth/users/") or route.startswith("/api/v1/auth/roles/"):
                return "auth:write"
            if route.startswith("/api/v1/settings/"):
                return "settings:write"
        if verb == "DELETE":
            if re.match(r"^/api/v1/provisioning/vms/\d+$", route):
                return "provisioning:write"
            if route.startswith("/api/v1/policies/"):
                return "policy:write"
            if route.startswith("/api/v1/auth/users/") or route.startswith("/api/v1/auth/roles/"):
                return "auth:write"
        if verb == "GET":
            if route == "/api/v1/audit/report":
                return "auth:read"
            if route in {"/api/v1/auth/users", "/api/v1/auth/roles"}:
                return "auth:read"
            if route.startswith("/api/v1/settings/"):
                return "settings:read"
            if re.match(r"^/api/v1/sessions/[A-Za-z0-9._:-]+/recording$", route):
                return "session:download_recording"
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
