"""Integration test fixtures for beagle-host services.

GoAdvanced Plan 10 Schritt 1.

Provides shared pytest fixtures for integration tests:

- ``temp_state_dir``      — isolated temp directory per test
- ``mock_audit_log``      — in-memory audit event collector
- ``test_http_client``    — thin HTTP client wrapper for control-plane tests
- ``libvirt_stub``        — stub for virsh/libvirt XML responses

Import style::

    from tests.integration.conftest import *   # pytest picks up automatically

The control-plane server fixture (``cp_server``) spins up a real
ThreadingHTTPServer with the full Handler, using the temp_state_dir and
injected environment variables so tests are fully isolated.
"""
from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import threading
import time
import typing

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must set before importing service_registry
os.environ.setdefault("BEAGLE_BEAGLE_PROVIDER_STATE_DIR", "/tmp/beagle-test-integration/providers")

for _sub in ("services", "providers", "bin"):
    _p = os.path.join(ROOT, "beagle-host", _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Temp state dir
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_state_dir(tmp_path):
    """Isolated state directory for each test."""
    d = tmp_path / "state"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Audit log collector
# ---------------------------------------------------------------------------

class _AuditCollector:
    """Collects audit events in-memory for assertion in tests."""

    def __init__(self):
        self.events: list[dict] = []
        self._lock = threading.Lock()

    def write_event(self, event_type: str, outcome: str, **fields):
        with self._lock:
            self.events.append({"event_type": event_type, "outcome": outcome, **fields})

    def clear(self):
        with self._lock:
            self.events.clear()

    def by_type(self, event_type: str) -> list[dict]:
        with self._lock:
            return [e for e in self.events if e.get("event_type") == event_type]

    def __len__(self):
        with self._lock:
            return len(self.events)


@pytest.fixture
def mock_audit_log():
    """In-memory audit event collector (replaces real AuditLogService)."""
    return _AuditCollector()


# ---------------------------------------------------------------------------
# HTTP client helper
# ---------------------------------------------------------------------------

class TestHttpClient:
    """Thin synchronous HTTP client for integration tests."""

    def __init__(self, host: str, port: int, *, token: str = "", timeout: float = 5.0):
        self._host = host
        self._port = port
        self._token = token
        self._timeout = timeout

    def _conn(self) -> http.client.HTTPConnection:
        return http.client.HTTPConnection(self._host, self._port, timeout=self._timeout)

    def get(self, path: str, *, extra_headers: dict[str, str] | None = None) -> tuple[int, dict, bytes]:
        return self._request("GET", path, body=None, extra_headers=extra_headers)

    def post(self, path: str, body: dict | None = None, *, extra_headers: dict[str, str] | None = None) -> tuple[int, dict, bytes]:
        return self._request("POST", path, body=body, extra_headers=extra_headers)

    def put(self, path: str, body: dict | None = None, *, extra_headers: dict[str, str] | None = None) -> tuple[int, dict, bytes]:
        return self._request("PUT", path, body=body, extra_headers=extra_headers)

    def delete(self, path: str, *, extra_headers: dict[str, str] | None = None) -> tuple[int, dict, bytes]:
        return self._request("DELETE", path, body=None, extra_headers=extra_headers)

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None,
        extra_headers: dict[str, str] | None,
    ) -> tuple[int, dict, bytes]:
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if body is not None:
            encoded = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(encoded))
        else:
            encoded = None
        if extra_headers:
            headers.update(extra_headers)

        conn = self._conn()
        try:
            conn.request(method, path, body=encoded, headers=headers)
            resp = conn.getresponse()
            resp_body = resp.read()
            resp_headers = dict(resp.getheaders())
            return resp.status, resp_headers, resp_body
        finally:
            conn.close()

    def get_json(self, path: str, **kwargs) -> tuple[int, dict]:
        status, _, body = self.get(path, **kwargs)
        return status, json.loads(body) if body else {}

    def post_json(self, path: str, body: dict | None = None, **kwargs) -> tuple[int, dict]:
        status, _, resp_body = self.post(path, body, **kwargs)
        return status, json.loads(resp_body) if resp_body else {}

    def delete_json(self, path: str, **kwargs) -> tuple[int, dict]:
        status, _, body = self.delete(path, **kwargs)
        return status, json.loads(body) if body else {}


# ---------------------------------------------------------------------------
# Control plane server fixture
# ---------------------------------------------------------------------------

def _make_cp_server(state_dir: str, token: str = "test-token-integration"):
    """Start a real ThreadingHTTPServer with the control-plane Handler.

    Injects BEAGLE_* environment variables before the first import of
    service_registry — or patches module-level globals if already imported.
    """
    from http.server import ThreadingHTTPServer
    import service_registry as reg

    # Patch module-level globals that control auth + paths
    reg.API_TOKEN = token
    reg.AUTH_ADMIN_USERNAME = "admin"
    reg.AUTH_BOOTSTRAP_PASSWORD = "test-bootstrap-pw"

    # Override data dir to temp path
    import runtime_paths as rp_mod
    if hasattr(rp_mod, "RuntimePathsService"):
        # Re-point the singleton's data dir
        rts = reg.runtime_paths_service()
        original_data_dir = rts.data_dir
        rts.data_dir = lambda: state_dir

    from control_plane_handler import Handler

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    return srv, thread


@pytest.fixture(scope="function")
def cp_server(tmp_path):
    """Real control-plane HTTP server bound to an ephemeral port.

    Yields a ``TestHttpClient`` pre-configured with the test bearer token.
    Server is shut down after the test.
    """
    state_dir = str(tmp_path / "state")
    os.makedirs(state_dir, exist_ok=True)
    token = "test-integration-token"

    from http.server import ThreadingHTTPServer
    import service_registry as reg

    # Reset singletons that might have been populated by previous tests
    reg.JOB_QUEUE_SERVICE = None
    reg.JOB_WORKER = None
    reg.JOBS_HTTP_SURFACE = None
    reg.PROMETHEUS_METRICS_SERVICE = None
    reg.HEALTH_AGGREGATOR_SERVICE = None

    reg.API_TOKEN = token
    reg.AUTH_ADMIN_USERNAME = "admin"
    reg.AUTH_BOOTSTRAP_PASSWORD = "test-bootstrap-pw"

    # Override data dir
    rts = reg.runtime_paths_service()
    rts.data_dir = lambda: state_dir

    from control_plane_handler import Handler
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()

    host, port = srv.server_address
    client = TestHttpClient(host, port, token=token)
    try:
        yield client
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Virsh / libvirt stub helpers
# ---------------------------------------------------------------------------

class LibvirtStub:
    """Stub for libvirt-based operations used in integration tests.

    Instead of calling a real libvirt daemon, responses are pre-configured
    via ``set_domain_list`` / ``set_domain_state`` etc.
    """

    def __init__(self):
        self._domains: dict[str, dict] = {}  # name → state dict

    def add_domain(
        self,
        name: str,
        *,
        state: str = "running",
        uuid: str = "",
        vcpus: int = 2,
        memory_mb: int = 2048,
    ) -> None:
        import uuid as _uuid_mod
        self._domains[name] = {
            "name": name,
            "state": state,
            "uuid": uuid or str(_uuid_mod.uuid4()),
            "vcpus": vcpus,
            "memory_mb": memory_mb,
        }

    def list_domains(self) -> list[dict]:
        return list(self._domains.values())

    def domain_state(self, name: str) -> str | None:
        d = self._domains.get(name)
        return d["state"] if d else None

    def start_domain(self, name: str) -> bool:
        if name in self._domains:
            self._domains[name]["state"] = "running"
            return True
        return False

    def stop_domain(self, name: str) -> bool:
        if name in self._domains:
            self._domains[name]["state"] = "shut off"
            return True
        return False


@pytest.fixture
def libvirt_stub():
    """A fresh LibvirtStub for each test."""
    return LibvirtStub()
