import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


AUTH_SESSION_PATH = Path(__file__).resolve().parents[2] / "beagle-host" / "services" / "auth_session.py"
SPEC = importlib.util.spec_from_file_location("beagle_auth_session", AUTH_SESSION_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
AuthSessionService = MODULE.AuthSessionService


def load_json_file(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class AuthSessionOnboardingTests(unittest.TestCase):
    def make_service(self, root: Path) -> AuthSessionService:
        return AuthSessionService(
            data_dir=root,
            load_json_file=load_json_file,
            write_json_file=write_json_file,
            now=lambda: 1_700_000_000,
            token_urlsafe=lambda length: "token",
        )

    def test_bootstrap_only_admin_keeps_onboarding_pending(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = self.make_service(Path(temp_dir))
            service.ensure_bootstrap_admin(username="admin", password="bootstrap-secret")

            status = service.onboarding_status(bootstrap_username="admin", bootstrap_disabled=False)

            self.assertTrue(status["pending"])
            self.assertFalse(status["completed"])
            self.assertEqual(status["user_count"], 1)

    def test_completing_onboarding_with_bootstrap_username_promotes_user(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = self.make_service(root)
            service.ensure_bootstrap_admin(username="admin", password="bootstrap-secret")

            status = service.complete_onboarding(
                username="admin",
                password="real-admin-secret",
                bootstrap_username="admin",
                bootstrap_disabled=False,
            )

            self.assertFalse(status["pending"])
            self.assertTrue(status["completed"])
            users_doc = load_json_file(root / "auth" / "users.json", {"users": []})
            self.assertEqual(len(users_doc["users"]), 1)
            self.assertNotIn("bootstrap_only", users_doc["users"][0])
            onboarding_doc = load_json_file(root / "auth" / "onboarding.json", {})
            self.assertEqual(onboarding_doc.get("completed_by"), "admin")

    def test_create_user_rejects_invalid_username(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = self.make_service(Path(temp_dir))
            with self.assertRaises(ValueError):
                service.create_user(username="bad user", password="secret123", role="viewer", enabled=True)

    def test_save_role_rejects_invalid_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = self.make_service(Path(temp_dir))
            with self.assertRaises(ValueError):
                service.save_role(name="bad role", permissions=["auth:read"])

    def test_default_roles_include_kiosk_operator(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = self.make_service(Path(temp_dir))
            roles = {item["name"]: item for item in service.list_roles()}
            self.assertIn("kiosk_operator", roles)
            self.assertEqual(set(roles["kiosk_operator"].get("permissions", [])), {"vm:read", "vm:power", "kiosk:operate"})
            self.assertTrue(roles["kiosk_operator"]["protected"])

    def test_create_and_update_user_with_session_geo_routing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = self.make_service(Path(temp_dir))

            created = service.create_user(
                username="alice",
                password="secret123",
                role="viewer",
                enabled=True,
                session_geo_routing={
                    "enabled": True,
                    "sites": {
                        "berlin": {"target_node": "srv1", "cidrs": ["10.0.0.0/16"]},
                        "munich": {"target_node": "srv2", "cidrs": ["10.2.0.0/16"]},
                    },
                },
            )
            self.assertTrue(created["session_geo_routing"]["enabled"])
            self.assertEqual(created["session_geo_routing"]["sites"]["munich"]["target_node"], "srv2")

            updated = service.update_user(
                username="alice",
                session_geo_routing={
                    "enabled": True,
                    "sites": {"berlin": {"target_node": "srv3", "cidrs": ["10.0.0.0/16"]}},
                },
            )
            self.assertEqual(updated["session_geo_routing"]["sites"]["berlin"]["target_node"], "srv3")
            self.assertEqual(service.get_user_session_geo_routing("alice")["sites"]["berlin"]["target_node"], "srv3")

    def test_builtin_roles_cannot_be_modified_or_deleted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = self.make_service(Path(temp_dir))

            with self.assertRaises(ValueError):
                service.save_role(name="admin", permissions=["auth:read"])

            self.assertFalse(service.delete_role("viewer"))

    def test_list_roles_backfills_missing_builtin_roles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            roles_path = root / "auth" / "roles.json"
            roles_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"roles": [{"name": "viewer", "permissions": []}]}
            roles_path.write_text(json.dumps(payload), encoding="utf-8")
            writes: list[Path] = []

            service = AuthSessionService(
                data_dir=root,
                load_json_file=load_json_file,
                write_json_file=lambda path, doc: writes.append(path),
                now=lambda: 1_700_000_000,
                token_urlsafe=lambda length: "token",
            )

            roles = service.list_roles()

            role_names = [item["name"] for item in roles]
            self.assertIn("viewer", role_names)
            self.assertIn("kiosk_operator", role_names)
            self.assertEqual(writes, [roles_path])


if __name__ == "__main__":
    unittest.main()
