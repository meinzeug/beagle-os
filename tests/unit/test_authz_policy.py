import unittest

import sys
from pathlib import Path

SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from authz_policy import AuthzPolicyService


class AuthzPolicyServiceTests(unittest.TestCase):
    def test_required_permission_for_legacy_vms_post_is_provisioning_write(self):
        permission = AuthzPolicyService.required_permission("POST", "/api/v1/vms")
        self.assertEqual(permission, "provisioning:write")

    def test_pool_routes_have_pool_permissions(self):
        self.assertEqual(
            AuthzPolicyService.required_permission("GET", "/api/v1/pools"),
            "pool:read",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("POST", "/api/v1/pools"),
            "pool:write",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("POST", "/api/v1/pools/pool-a/entitlements"),
            "pool:write",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("GET", "/api/v1/pool-templates"),
            "pool:read",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("GET", "/api/v1/sessions"),
            "pool:read",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("POST", "/api/v1/sessions/stream-health"),
            "pool:write",
        )

    def test_ha_routes_require_cluster_write(self):
        self.assertEqual(
            AuthzPolicyService.required_permission("GET", "/api/v1/ha/status"),
            "cluster:read",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("POST", "/api/v1/ha/reconcile-failed-node"),
            "cluster:write",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("POST", "/api/v1/ha/maintenance/drain"),
            "cluster:write",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("POST", "/api/v1/cluster/join-existing"),
            "cluster:write",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("POST", "/api/v1/cluster/add-server-preflight"),
            "cluster:write",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("POST", "/api/v1/cluster/setup-code"),
            "cluster:write",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("POST", "/api/v1/cluster/auto-join"),
            "cluster:write",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("POST", "/api/v1/cluster/leave-local"),
            "cluster:write",
        )
        self.assertIsNone(
            AuthzPolicyService.required_permission("POST", "/api/v1/cluster/join-with-setup-code"),
        )

    def test_viewer_cannot_write_pools(self):
        permission = AuthzPolicyService.required_permission("POST", "/api/v1/pools")
        self.assertEqual(permission, "pool:write")
        allowed = AuthzPolicyService.is_allowed("viewer", permission, {"pool:read"})
        self.assertFalse(allowed)

    def test_admin_can_write_pools(self):
        permission = AuthzPolicyService.required_permission("POST", "/api/v1/pools")
        allowed = AuthzPolicyService.is_allowed("admin", permission, {"pool:write"})
        self.assertTrue(allowed)

    def test_viewer_cannot_mutate_settings(self):
        permission = AuthzPolicyService.required_permission("PUT", "/api/v1/settings/general")
        self.assertEqual(permission, "settings:write")
        allowed = AuthzPolicyService.is_allowed("viewer", permission, set())
        self.assertFalse(allowed)

    def test_admin_can_mutate_settings(self):
        permission = AuthzPolicyService.required_permission("PUT", "/api/v1/settings/general")
        allowed = AuthzPolicyService.is_allowed("admin", permission, {"settings:write"})
        self.assertTrue(allowed)

    def test_backup_routes_use_settings_permissions(self):
        self.assertEqual(
            AuthzPolicyService.required_permission("GET", "/api/v1/backups/jobs"),
            "settings:read",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("GET", "/api/v1/backups/policies/pools/default"),
            "settings:read",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("PUT", "/api/v1/backups/policies/vms/101"),
            "settings:write",
        )
        self.assertEqual(
            AuthzPolicyService.required_permission("POST", "/api/v1/backups/run"),
            "settings:write",
        )

    def test_virtualization_power_route_uses_vm_power_permission(self):
        permission = AuthzPolicyService.required_permission("POST", "/api/v1/virtualization/vms/101/power")
        self.assertEqual(permission, "vm:power")

    def test_vm_mutate_still_grants_vm_power_backwards_compat(self):
        allowed = AuthzPolicyService.is_allowed("ops", "vm:power", {"vm:mutate"})
        self.assertTrue(allowed)


if __name__ == "__main__":
    unittest.main()
