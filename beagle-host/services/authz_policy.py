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
        "group": "Cluster",
        "tags": [
            {"tag": "cluster:read",  "label": "Cluster-Status lesen"},
            {"tag": "cluster:write", "label": "Cluster initialisieren / Join verwalten"},
        ],
    },
    {
        "group": "Aktionen",
        "tags": [
            {"tag": "actions:bulk", "label": "Bulk-VM-Aktionen ausfuehren"},
        ],
    },
    {
        "group": "VDI Pools",
        "tags": [
            {"tag": "pool:read",  "label": "Desktop-Pools & Templates lesen"},
            {"tag": "pool:scale", "label": "Desktop-Pool skalieren (pool-operator)"},
            {"tag": "pool:write", "label": "Desktop-Pools & Templates verwalten (erstellen, loeschen)"},
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
        "group": "Kiosk",
        "tags": [
            {"tag": "kiosk:operate", "label": "Kiosk-Sessions lesen, beenden und Betreiber-Ansichten nutzen"},
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
            if route == "/api/v1/audit/failures/replay" or re.match(r"^/api/v1/audit/export-targets/[A-Za-z0-9_-]+/test$", route):
                return "auth:write"
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
                or route.endswith("/migrate")
                or route.endswith("/sunshine-access")
            ):
                return "vm:mutate"
            if route.startswith("/api/v1/virtualization/vms/") and route.endswith("/power"):
                return "vm:power"
            if route == "/api/v1/auth/users" or route == "/api/v1/auth/roles":
                return "auth:write"
            if re.match(r"^/api/v1/auth/users/[A-Za-z0-9._-]+/revoke-sessions$", route):
                return "auth:write"
            if re.match(r"^/api/v1/auth/sessions/[A-Za-z0-9_=-]{8,128}$", route):
                return "auth:write"
            if route.startswith("/api/v1/settings/"):
                return "settings:write"
            if route == "/api/v1/backups/run":
                return "settings:write"
            if route == "/api/v1/backups/prune":
                return "settings:write"
            if re.match(r"^/api/v1/backups/[0-9a-f-]{36}/(restore|replicate)$", route):
                return "settings:write"
            if route == "/api/v1/backups/ingest":
                return "settings:write"
            if re.match(r"^/api/v1/storage/pools/[A-Za-z0-9._-]+/upload$", route):
                return "settings:write"
            if route == "/api/v1/fleet/devices/register":
                return "settings:write"
            if route in {"/api/v1/fleet/policies", "/api/v1/fleet/policies/assignments", "/api/v1/fleet/policies/assignments/bulk", "/api/v1/fleet/devices/actions/bulk"}:
                return "settings:write"
            if re.match(r"^/api/v1/fleet/devices/[A-Za-z0-9._:-]+/(heartbeat|lock|unlock|wipe|confirm-wiped)$", route):
                return "settings:write"
            if route in {"/api/v1/cluster/init", "/api/v1/cluster/setup-code", "/api/v1/cluster/add-server-preflight", "/api/v1/cluster/auto-join", "/api/v1/cluster/join-token", "/api/v1/cluster/join-existing", "/api/v1/cluster/leave-local", "/api/v1/cluster/apply-join", "/api/v1/cluster/reconcile-membership"}:
                return "cluster:write"
            if route == "/api/v1/ha/reconcile-failed-node":
                return "cluster:write"
            if route in {"/api/v1/ha/maintenance/preview", "/api/v1/ha/maintenance/drain", "/api/v1/ha/maintenance/drain-async"}:
                return "cluster:write"
            if re.match(r"^/api/v1/sessions/[A-Za-z0-9._:-]+/recording/(start|stop)$", route):
                return "session:manage_recording"
            if re.match(r"^/api/v1/pools/kiosk/sessions/\d+/end$", route):
                return "kiosk:operate"
            if re.match(r"^/api/v1/pools/kiosk/sessions/\d+/extend$", route):
                return "kiosk:operate"
            if re.match(r"^/api/v1/pools/[A-Za-z0-9._-]+/scale$", route):
                return "pool:scale"
            if route == "/api/v1/pools" or re.match(r"^/api/v1/pools/[A-Za-z0-9._-]+/(vms|entitlements|allocate|release|recycle)$", route):
                return "pool:write"
            if route == "/api/v1/pool-templates":
                return "pool:write"
            if route == "/api/v1/sessions/stream-health":
                return "pool:write"
        if verb == "PUT":
            if re.match(r"^/api/v1/fleet/policies/[A-Za-z0-9._:-]+$", route):
                return "settings:write"
            if re.match(r"^/api/v1/fleet/devices/[A-Za-z0-9._:-]+$", route):
                return "settings:write"
            if re.match(r"^/api/v1/provisioning/vms/\d+$", route):
                return "provisioning:write"
            if route.startswith("/api/v1/policies/"):
                return "policy:write"
            if route.startswith("/api/v1/auth/users/") or route.startswith("/api/v1/auth/roles/"):
                return "auth:write"
            if re.match(r"^/api/v1/storage/pools/[A-Za-z0-9._-]+/quota$", route):
                return "settings:write"
            if route.startswith("/api/v1/settings/"):
                return "settings:write"
            if re.match(r"^/api/v1/backups/policies/(pools/[A-Za-z0-9._-]+|vms/\d+)$", route):
                return "settings:write"
            if route == "/api/v1/backups/replication/config":
                return "settings:write"
            if re.match(r"^/api/v1/pools/[A-Za-z0-9._-]+$", route):
                return "pool:write"
        if verb == "DELETE":
            if re.match(r"^/api/v1/fleet/policies/[A-Za-z0-9._:-]+$", route):
                return "settings:write"
            if re.match(r"^/api/v1/provisioning/vms/\d+$", route):
                return "provisioning:write"
            if route.startswith("/api/v1/policies/"):
                return "policy:write"
            if route.startswith("/api/v1/auth/users/") or route.startswith("/api/v1/auth/roles/"):
                return "auth:write"
            if re.match(r"^/api/v1/pools/[A-Za-z0-9._-]+$", route):
                return "pool:write"
            if re.match(r"^/api/v1/pool-templates/[A-Za-z0-9._-]+$", route):
                return "pool:write"
        if verb == "GET":
            if route in {"/api/v1/fleet/policies", "/api/v1/fleet/policies/assignments"}:
                return "settings:read"
            if re.match(r"^/api/v1/fleet/policies/[A-Za-z0-9._:-]+$", route):
                return "settings:read"
            if re.match(r"^/api/v1/fleet/devices/[A-Za-z0-9._:-]+/effective-policy$", route):
                return "settings:read"
            if route in {"/api/v1/fleet/devices", "/api/v1/fleet/devices/groups"}:
                return "settings:read"
            if re.match(r"^/api/v1/fleet/devices/[A-Za-z0-9._:-]+$", route):
                return "settings:read"
            if route in {"/api/v1/audit/report", "/api/v1/audit/export-targets", "/api/v1/audit/failures"}:
                return "auth:read"
            if route == "/api/v1/installer-logs" or re.match(r"^/api/v1/installer-logs/[A-Za-z0-9._-]{8,96}$", route):
                return "settings:read"
            if route in {"/api/v1/auth/users", "/api/v1/auth/roles"}:
                return "auth:read"
            if route in {"/api/v1/auth/sessions", "/api/v1/auth/tenants"}:
                return "auth:read"
            if re.match(r"^/api/v1/storage/pools/[A-Za-z0-9._-]+/quota$", route):
                return "settings:read"
            if re.match(r"^/api/v1/storage/pools/[A-Za-z0-9._-]+/files$", route):
                return "settings:read"
            if route.startswith("/api/v1/settings/"):
                return "settings:read"
            if route == "/api/v1/backups/jobs":
                return "settings:read"
            if route == "/api/v1/backups/snapshots":
                return "settings:read"
            if re.match(r"^/api/v1/backups/[0-9a-f-]{36}/files$", route):
                return "settings:read"
            if route == "/api/v1/backups/replication/config":
                return "settings:read"
            if re.match(r"^/api/v1/backups/policies/(pools/[A-Za-z0-9._-]+|vms/\d+)$", route):
                return "settings:read"
            if route == "/api/v1/cluster/status":
                return "cluster:read"
            if route == "/api/v1/nodes/install-checks":
                return "cluster:read"
            if route == "/api/v1/ha/status":
                return "cluster:read"
            if re.match(r"^/api/v1/sessions/[A-Za-z0-9._:-]+/recording$", route):
                return "session:download_recording"
            if route == "/api/v1/pools/kiosk/sessions":
                return "kiosk:operate"
            if route == "/api/v1/gaming/metrics":
                return "vm:read"
            if route == "/api/v1/pools" or re.match(r"^/api/v1/pools/[A-Za-z0-9._-]+(/.*)?$", route):
                return "pool:read"
            if route == "/api/v1/pool-templates" or re.match(r"^/api/v1/pool-templates/[A-Za-z0-9._-]+$", route):
                return "pool:read"
            if route in {"/api/v1/sessions", "/api/v1/sessions/handover"}:
                return "pool:read"
        return None

    @staticmethod
    def is_allowed(role: str, permission: str | None, role_permissions: set[str]) -> bool:
        role_name = str(role or "").strip().lower() or "viewer"
        if permission is None:
            return True
        if role_name == "superadmin":
            return True
        permissions = {str(value).strip() for value in role_permissions if str(value).strip()}
        if "*" in permissions or permission in permissions:
            return True
        if permission == "vm:power" and "vm:mutate" in permissions:
            return True
        # pool:write implicitly grants pool:scale (backwards compat)
        if permission == "pool:scale" and "pool:write" in permissions:
            return True
        return False
