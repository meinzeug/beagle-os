"""Unit tests for session cookie flag requirements.

Validates that _refresh_cookie_header returns a Set-Cookie value that
includes all required security attributes and a non-zero Max-Age.
This serves as a regression gate for the R3 cookie-flag fix.
"""
import importlib.util
import sys
import types
import unittest
from pathlib import Path

BEAGLE_HOST_DIR = Path(__file__).resolve().parents[2] / "beagle-host"
SERVICES_DIR = BEAGLE_HOST_DIR / "services"
MODULE_PATH = SERVICES_DIR / "request_handler_mixin.py"

sys.path.insert(0, str(SERVICES_DIR))
sys.path.insert(0, str(BEAGLE_HOST_DIR / "bin"))

# --- stubs required before loading the mixin module ---
service_registry_stub = types.ModuleType("service_registry")
service_registry_stub.AUTH_REFRESH_TTL_SECONDS = 604800  # 7 days
service_registry_stub.AUTH_ACCESS_TTL_SECONDS = 900
service_registry_stub.AUTH_IDLE_TIMEOUT_SECONDS = 1800
service_registry_stub.AUTH_ABSOLUTE_TIMEOUT_SECONDS = 604800
service_registry_stub.API_TOKEN = ""
service_registry_stub.__all__ = []
sys.modules["service_registry"] = service_registry_stub

for _name, _cls in {
    "audit_report_http_surface": "AuditReportHttpSurfaceService",
    "auth_session_http_surface": "AuthSessionHttpSurfaceService",
    "recording_http_surface": "RecordingHttpSurfaceService",
    "backups_http_surface": "BackupsHttpSurfaceService",
    "pools_http_surface": "PoolsHttpSurfaceService",
    "cluster_http_surface": "ClusterHttpSurfaceService",
}.items():
    _stub = types.ModuleType(_name)
    setattr(_stub, _cls, type(_cls, (), {}))
    sys.modules.setdefault(_name, _stub)

_SPEC = importlib.util.spec_from_file_location("beagle_request_handler_mixin", MODULE_PATH)
_module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_module)
HandlerMixin = _module.HandlerMixin


class _StubMixin(HandlerMixin):
    """Minimal concrete stub so we can call mixin methods directly."""
    _rate_limit_state: dict = {}
    _login_guard_state: dict = {}
    _security_state_lock = None
    headers: dict = {}
    def log_message(self, *a): pass
    def log_error(self, *a): pass


class SessionCookieFlagsTests(unittest.TestCase):
    def setUp(self):
        self.mixin = _StubMixin.__new__(_StubMixin)

    def _cookie_value(self) -> str:
        name, value = self.mixin._refresh_cookie_header("test_token_abc")
        self.assertEqual(name, "Set-Cookie")
        return value

    def test_cookie_contains_httponly(self):
        self.assertIn("HttpOnly", self._cookie_value())

    def test_cookie_contains_samesite_strict(self):
        self.assertIn("SameSite=Strict", self._cookie_value())

    def test_cookie_contains_secure(self):
        self.assertIn("Secure", self._cookie_value())

    def test_cookie_path_is_auth(self):
        self.assertIn("Path=/api/v1/auth", self._cookie_value())

    def test_cookie_contains_max_age(self):
        self.assertIn("Max-Age=", self._cookie_value())

    def test_cookie_max_age_is_positive(self):
        val = self._cookie_value()
        for part in val.split(";"):
            part = part.strip()
            if part.startswith("Max-Age="):
                age = int(part.split("=", 1)[1])
                self.assertGreater(age, 0, "Max-Age must be positive (non-zero)")
                return
        self.fail("Max-Age attribute not found in cookie")

    def test_cookie_max_age_not_exceed_seven_days(self):
        val = self._cookie_value()
        for part in val.split(";"):
            part = part.strip()
            if part.startswith("Max-Age="):
                age = int(part.split("=", 1)[1])
                self.assertLessEqual(age, 604800, "Max-Age must not exceed 7 days")
                return
        self.fail("Max-Age attribute not found in cookie")

    def test_clear_cookie_max_age_is_zero(self):
        name, val = self.mixin._clear_refresh_cookie_header()
        self.assertEqual(name, "Set-Cookie")
        self.assertIn("Max-Age=0", val)

    def test_clear_cookie_contains_httponly(self):
        _, val = self.mixin._clear_refresh_cookie_header()
        self.assertIn("HttpOnly", val)


if __name__ == "__main__":
    unittest.main()
