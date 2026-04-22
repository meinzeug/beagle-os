import tempfile
import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from entitlement_service import EntitlementService


class EntitlementServiceTests(unittest.TestCase):
    def _build_service(self) -> EntitlementService:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        state_file = Path(temp_dir.name) / "entitlements.json"
        return EntitlementService(state_file=state_file)

    def test_set_and_get_entitlements(self) -> None:
        service = self._build_service()
        result = service.set_entitlements(
            "pool-a",
            users=["u1", "u1", "", "u2"],
            groups=["g1", "g1", "g2"],
        )
        self.assertEqual(result["users"], ["u1", "u2"])
        self.assertEqual(result["groups"], ["g1", "g2"])

        fetched = service.get_entitlements("pool-a")
        self.assertEqual(fetched["users"], ["u1", "u2"])
        self.assertEqual(fetched["groups"], ["g1", "g2"])

    def test_add_remove_and_is_entitled(self) -> None:
        service = self._build_service()
        service.add_entitlement("pool-b", user_id="alice")
        service.add_entitlement("pool-b", group_id="ops")

        self.assertTrue(service.is_entitled("pool-b", user_id="alice"))
        self.assertTrue(service.is_entitled("pool-b", user_id="bob", groups=["ops"]))
        self.assertFalse(service.is_entitled("pool-b", user_id="bob", groups=["sales"]))

        service.remove_entitlement("pool-b", user_id="alice")
        self.assertFalse(service.is_entitled("pool-b", user_id="alice"))

    def test_can_view_pool_defaults_to_visible_when_unrestricted(self) -> None:
        service = self._build_service()

        self.assertFalse(service.has_explicit_entitlements("pool-open"))
        self.assertTrue(service.can_view_pool("pool-open", user_id="alice"))
        self.assertFalse(service.can_view_pool("pool-open", user_id="alice", allow_unrestricted=False))

    def test_can_view_pool_hides_restricted_pools_from_unentitled_users(self) -> None:
        service = self._build_service()
        service.set_entitlements("pool-c", users=["alice"], groups=["ops"])

        self.assertTrue(service.has_explicit_entitlements("pool-c"))
        self.assertTrue(service.can_view_pool("pool-c", user_id="alice"))
        self.assertTrue(service.can_view_pool("pool-c", user_id="bob", groups=["ops"]))
        self.assertFalse(service.can_view_pool("pool-c", user_id="mallory", groups=["sales"]))

    def test_rejects_empty_pool_id(self) -> None:
        service = self._build_service()
        with self.assertRaisesRegex(ValueError, "pool_id is required"):
            service.get_entitlements("  ")


if __name__ == "__main__":
    unittest.main()
