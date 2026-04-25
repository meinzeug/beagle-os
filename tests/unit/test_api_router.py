"""Unit tests for beagle-host/services/api_router_service.py."""
from __future__ import annotations

import sys
from http import HTTPStatus
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "beagle-host" / "services"))

from api_router_service import ApiRouterService, Response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_handler(payload: dict, status: HTTPStatus = HTTPStatus.OK):
    """Return a simple handler that captures calls."""
    calls = []

    def handler(*, path_params, body, headers) -> Response:
        calls.append({"path_params": path_params, "body": body, "headers": headers})
        return {"kind": "json", "status": status, "payload": payload}

    handler.calls = calls  # type: ignore[attr-defined]
    return handler


# ---------------------------------------------------------------------------
# Static path match
# ---------------------------------------------------------------------------

class TestStaticPath:
    def setup_method(self):
        self.router = ApiRouterService()

    def test_exact_match_returns_handler_response(self):
        h = make_handler({"ok": True})
        self.router.register("GET", "/api/v1/health", h)
        resp = self.router.dispatch("GET", "/api/v1/health")
        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"] == {"ok": True}

    def test_path_not_registered_returns_404(self):
        h = make_handler({"ok": True})
        self.router.register("GET", "/api/v1/health", h)
        resp = self.router.dispatch("GET", "/api/v1/missing")
        assert resp["status"] == HTTPStatus.NOT_FOUND

    def test_trailing_slash_does_not_match(self):
        h = make_handler({})
        self.router.register("GET", "/api/v1/health", h)
        resp = self.router.dispatch("GET", "/api/v1/health/")
        assert resp["status"] == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Param extraction
# ---------------------------------------------------------------------------

class TestParamExtraction:
    def setup_method(self):
        self.router = ApiRouterService()

    def test_single_param_extracted(self):
        h = make_handler({})
        self.router.register("GET", "/api/v1/vms/:vmid", h)
        self.router.dispatch("GET", "/api/v1/vms/101")
        assert h.calls[0]["path_params"] == {"vmid": "101"}

    def test_multiple_params_extracted(self):
        h = make_handler({})
        self.router.register("GET", "/api/v1/pools/:pool_id/vms/:vmid", h)
        self.router.dispatch("GET", "/api/v1/pools/prod/vms/202")
        assert h.calls[0]["path_params"] == {"pool_id": "prod", "vmid": "202"}

    def test_uuid_param_matches(self):
        h = make_handler({})
        self.router.register("GET", "/api/v1/backups/:job_id/files", h)
        uid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        self.router.dispatch("GET", f"/api/v1/backups/{uid}/files")
        assert h.calls[0]["path_params"]["job_id"] == uid


# ---------------------------------------------------------------------------
# Method mismatch → 405
# ---------------------------------------------------------------------------

class TestMethodMismatch:
    def setup_method(self):
        self.router = ApiRouterService()

    def test_wrong_method_returns_405(self):
        h = make_handler({})
        self.router.register("GET", "/api/v1/vms", h)
        resp = self.router.dispatch("POST", "/api/v1/vms")
        assert resp["status"] == HTTPStatus.METHOD_NOT_ALLOWED

    def test_correct_method_returns_200(self):
        h = make_handler({})
        self.router.register("POST", "/api/v1/vms", h)
        resp = self.router.dispatch("POST", "/api/v1/vms")
        assert resp["status"] == HTTPStatus.OK


# ---------------------------------------------------------------------------
# handles() + handles_any_method()
# ---------------------------------------------------------------------------

class TestHandles:
    def setup_method(self):
        self.router = ApiRouterService()
        self.router.register("GET", "/api/v1/vms/:vmid", make_handler({}))

    def test_handles_matching_method_and_path(self):
        assert self.router.handles("GET", "/api/v1/vms/101") is True

    def test_handles_returns_false_for_wrong_method(self):
        assert self.router.handles("DELETE", "/api/v1/vms/101") is False

    def test_handles_any_method_true_if_any_method_matches(self):
        assert self.router.handles_any_method("/api/v1/vms/101") is True

    def test_handles_any_method_false_for_unknown_path(self):
        assert self.router.handles_any_method("/api/v1/unknown") is False


# ---------------------------------------------------------------------------
# Route priority — first registered wins
# ---------------------------------------------------------------------------

class TestRoutePriority:
    def setup_method(self):
        self.router = ApiRouterService()

    def test_specific_route_registered_first_takes_priority(self):
        specific = make_handler({"route": "specific"})
        generic = make_handler({"route": "generic"})
        # Register specific before generic
        self.router.register("GET", "/api/v1/vms/_search", specific)
        self.router.register("GET", "/api/v1/vms/:vmid", generic)
        resp = self.router.dispatch("GET", "/api/v1/vms/_search")
        assert resp["payload"]["route"] == "specific"

    def test_generic_route_catches_non_specific_paths(self):
        specific = make_handler({"route": "specific"})
        generic = make_handler({"route": "generic"})
        self.router.register("GET", "/api/v1/vms/_search", specific)
        self.router.register("GET", "/api/v1/vms/:vmid", generic)
        resp = self.router.dispatch("GET", "/api/v1/vms/101")
        assert resp["payload"]["route"] == "generic"


# ---------------------------------------------------------------------------
# Body + headers forwarding
# ---------------------------------------------------------------------------

class TestBodyAndHeaders:
    def setup_method(self):
        self.router = ApiRouterService()

    def test_body_forwarded_to_handler(self):
        h = make_handler({})
        self.router.register("POST", "/api/v1/vms", h)
        self.router.dispatch("POST", "/api/v1/vms", body={"name": "vm1"})
        assert h.calls[0]["body"] == {"name": "vm1"}

    def test_headers_forwarded_to_handler(self):
        h = make_handler({})
        self.router.register("GET", "/api/v1/vms", h)
        self.router.dispatch("GET", "/api/v1/vms", headers={"Authorization": "Bearer tok"})
        assert h.calls[0]["headers"]["Authorization"] == "Bearer tok"
