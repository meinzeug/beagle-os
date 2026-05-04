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
service_registry_stub.__all__ = ["API_V1_DEPRECATED_ENDPOINTS", "API_V1_DEPRECATION_SUNSET", "AUTH_REFRESH_TTL_SECONDS", "API_TOKEN", "SCIM_BEARER_TOKEN", "extract_bearer_token", "is_scim_bearer_token_valid", "load_endpoint_token"]
service_registry_stub.normalized_origin = lambda v: v
service_registry_stub.cors_allowed_origins = lambda: []
service_registry_stub.API_TOKEN = None
service_registry_stub.SCIM_BEARER_TOKEN = None
service_registry_stub.extract_bearer_token = lambda value: str(value).split(" ", 1)[1] if str(value).startswith("Bearer ") else ""
service_registry_stub.is_scim_bearer_token_valid = lambda token: token == "scim-secret"
service_registry_stub.load_endpoint_token = lambda token: {"endpoint_id": "ep-1", "vmid": 100} if token == "endpoint-secret" else None
service_registry_stub.API_V1_DEPRECATED_ENDPOINTS = set()
service_registry_stub.API_V1_DEPRECATION_SUNSET = ""
service_registry_stub.AUTH_REFRESH_TTL_SECONDS = 300
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
        self.path = "/api/v1/health"
        self.response_status = None
        self.response_headers = []
        self.logged_status = None
        self.close_connection = False
        self.wfile = types.SimpleNamespace(write=lambda _body: None)

    def send_response(self, status):
        self.response_status = int(status)

    def send_header(self, name, value):
        self.response_headers.append((name, value))

    def end_headers(self):
        return None

    def _log_response_event(self, status: int):
        self.logged_status = int(status)


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


def test_write_json_treats_broken_pipe_as_client_disconnect() -> None:
    handler = DummyHandler("127.0.0.1")

    def raise_broken_pipe(_body):
        raise BrokenPipeError(32, "broken pipe")

    handler.wfile = types.SimpleNamespace(write=raise_broken_pipe)

    handler._write_json(module.HTTPStatus.OK, {"ok": True})

    assert handler.response_status == 200
    assert handler.close_connection is True
    assert handler.logged_status is None


def test_scim_auth_uses_service_registry_validator() -> None:
    handler = DummyHandler("127.0.0.1", {"Authorization": "Bearer scim-secret"})

    assert handler._is_scim_authenticated() is True


def test_endpoint_identity_accepts_x_beagle_token_header() -> None:
    handler = DummyHandler("127.0.0.1", {"X-Beagle-Token": "endpoint-secret"})

    assert handler._endpoint_identity() == {"endpoint_id": "ep-1", "vmid": 100}


def test_endpoint_identity_accepts_query_access_token() -> None:
    handler = DummyHandler("127.0.0.1")
    handler.path = "/api/v1/streams/100/config?access_token=endpoint-secret"

    assert handler._endpoint_identity_from_query() == {"endpoint_id": "ep-1", "vmid": 100}
