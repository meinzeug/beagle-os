"""End-to-end test for request-ID middleware + /metrics.

GoAdvanced Plan 08 Schritt 4 (verifies request-id echo) + Schritt 2 (/metrics).

Spins up the real Handler against ThreadingHTTPServer on an ephemeral port,
issues two requests with stdlib http.client, and asserts:

- /metrics returns 200 with prometheus content-type and HELP/TYPE lines.
- A response always carries an X-Request-Id header.
- An incoming X-Request-Id is echoed back unchanged (when syntactically safe).
"""
from __future__ import annotations

import http.client
import os
import sys
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Provide a writable provider state dir BEFORE importing the registry.
os.environ.setdefault(
    "BEAGLE_BEAGLE_PROVIDER_STATE_DIR", "/tmp/beagle-test/providers"
)

for sub in ("services", "providers", "bin"):
    sys.path.insert(0, os.path.join(ROOT, "beagle-host", sub))

from http.server import ThreadingHTTPServer  # noqa: E402

from control_plane_handler import Handler  # noqa: E402


@pytest.fixture(scope="module")
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


def _get(server, path: str, *, headers: dict[str, str] | None = None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    try:
        conn.request("GET", path, headers=headers or {})
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, dict(resp.getheaders()), body
    finally:
        conn.close()


def test_metrics_endpoint_returns_prometheus_text(server):
    status, headers, body = _get(server, "/metrics")
    assert status == 200
    assert "text/plain" in headers.get("Content-Type", "")
    assert "version=0.0.4" in headers.get("Content-Type", "")
    text = body.decode("utf-8")
    assert "# HELP beagle_http_requests_total" in text
    assert "# TYPE beagle_http_requests_total counter" in text


def test_response_always_has_request_id(server):
    _, headers, _ = _get(server, "/metrics")
    rid = headers.get("X-Request-Id", "")
    assert rid, "expected generated X-Request-Id"
    assert len(rid) >= 8


def test_incoming_request_id_is_echoed(server):
    incoming = "test-rid-abc.123_xyz"
    _, headers, _ = _get(server, "/metrics", headers={"X-Request-Id": incoming})
    assert headers.get("X-Request-Id") == incoming


def test_unsafe_request_id_is_replaced(server):
    # Contains characters outside [A-Za-z0-9._-] => must be replaced
    _, headers, _ = _get(server, "/metrics", headers={"X-Request-Id": "bad rid!@#"})
    rid = headers.get("X-Request-Id", "")
    assert rid and rid != "bad rid!@#"


def test_each_request_gets_unique_id(server):
    _, h1, _ = _get(server, "/metrics")
    _, h2, _ = _get(server, "/metrics")
    assert h1["X-Request-Id"] != h2["X-Request-Id"]
