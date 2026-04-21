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


if __name__ == "__main__":
    unittest.main()