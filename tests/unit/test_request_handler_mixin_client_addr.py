import importlib.util
import sys
import types
from pathlib import Path


BEAGLE_HOST_DIR = Path(__file__).resolve().parents[2] / "beagle-host"
SERVICES_DIR = BEAGLE_HOST_DIR / "services"
MODULE_PATH = SERVICES_DIR / "request_handler_mixin.py"
sys.path.insert(0, str(SERVICES_DIR))
sys.path.insert(0, str(BEAGLE_HOST_DIR / "bin"))

service_registry_stub = types.ModuleType("service_registry")
service_registry_stub.__all__ = []
sys.modules.setdefault("service_registry", service_registry_stub)

for module_name, class_name in {
    "audit_report_http_surface": "AuditReportHttpSurfaceService",
    "auth_session_http_surface": "AuthSessionHttpSurfaceService",
    "recording_http_surface": "RecordingHttpSurfaceService",
    "backups_http_surface": "BackupsHttpSurfaceService",
    "pools_http_surface": "PoolsHttpSurfaceService",
    "cluster_http_surface": "ClusterHttpSurfaceService",
}.items():
    stub = types.ModuleType(module_name)
    setattr(stub, class_name, type(class_name, (), {}))
    sys.modules.setdefault(module_name, stub)

SPEC = importlib.util.spec_from_file_location("beagle_request_handler_mixin", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class DummyHandler(module.HandlerMixin):
    _rate_limit_state = {}
    _login_guard_state = {}
    _security_state_lock = None

    def __init__(self, peer_addr: str, headers: dict[str, str] | None = None) -> None:
        self.client_address = (peer_addr, 12345)
        self.headers = headers or {}


def test_client_addr_uses_forwarded_for_from_loopback_proxy() -> None:
    handler = DummyHandler("127.0.0.1", {"X-Forwarded-For": "203.0.113.10, 127.0.0.1"})

    assert handler._client_addr() == "203.0.113.10"


def test_client_addr_ignores_forwarded_for_from_untrusted_peer() -> None:
    handler = DummyHandler("198.51.100.7", {"X-Forwarded-For": "203.0.113.10"})

    assert handler._client_addr() == "198.51.100.7"


def test_client_addr_falls_back_to_peer_on_invalid_forwarded_for() -> None:
    handler = DummyHandler("127.0.0.1", {"X-Forwarded-For": "unknown"})

    assert handler._client_addr() == "127.0.0.1"


def test_login_guard_keys_are_scoped_to_forwarded_client_addr() -> None:
    first = DummyHandler("127.0.0.1", {"X-Forwarded-For": "203.0.113.10"})
    second = DummyHandler("127.0.0.1", {"X-Forwarded-For": "203.0.113.11"})

    assert first._login_guard_key("admin") == "203.0.113.10::admin"
    assert second._login_guard_key("admin") == "203.0.113.11::admin"
    assert first._login_guard_key("admin") != second._login_guard_key("admin")
