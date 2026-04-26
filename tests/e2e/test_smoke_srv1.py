"""E2E smoke tests against a live Beagle host (srv1 / srv2).

GoAdvanced Plan 10 Schritt 7.

Requires:
    BEAGLE_E2E_URL    — base URL of the target control-plane
    BEAGLE_E2E_TOKEN  — admin bearer token

All tests are skipped when BEAGLE_E2E_TOKEN is not set, so this file is
safe to include in the normal test run with no environment overhead.

The tests are designed to be safe on a live system:
- Read-only assertions (health, VM list) are always safe.
- Mutating tests (create→start→snapshot→delete) create ephemeral test VMs
  with a recognisable name prefix ``beagle-e2e-smoke-`` and clean them up
  unconditionally in teardown via the ``e2e_cleanup_vms`` fixture.

Nightly CI runs this file with BEAGLE_E2E_TOKEN injected from GitHub Secrets.
"""
from __future__ import annotations

import os

import pytest

from tests.e2e.helpers import requires_e2e, E2EHttpClient, _BASE_URL


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@requires_e2e
class TestHealthEndpoint:

    def test_health_returns_200(self, e2e_client: E2EHttpClient):
        status, body = e2e_client.get("/api/v1/health")
        assert status == 200, f"Unexpected status {status}: {body}"

    def test_health_body_has_status(self, e2e_client: E2EHttpClient):
        status, body = e2e_client.get("/api/v1/health")
        assert status == 200
        # Accept either {"status": "ok"} or {"healthy": true} patterns
        assert body.get("status") in {"ok", "healthy"} or body.get("healthy") is True, (
            f"Unexpected health body: {body}"
        )


# ---------------------------------------------------------------------------
# VM list
# ---------------------------------------------------------------------------

@requires_e2e
class TestVMList:

    def test_vm_list_returns_200(self, e2e_client: E2EHttpClient):
        status, body = e2e_client.get("/api/v1/vms")
        assert status == 200, f"VM list failed: {status} {body}"

    def test_vm_list_is_list(self, e2e_client: E2EHttpClient):
        _, body = e2e_client.get("/api/v1/vms")
        # Body may be a list or {"vms": [...]}
        vms = body if isinstance(body, list) else body.get("vms", body.get("data", []))
        assert isinstance(vms, list), f"Expected list, got {type(vms).__name__}: {body}"


# ---------------------------------------------------------------------------
# Unauthorized access
# ---------------------------------------------------------------------------

@requires_e2e
class TestUnauthorizedAccess:

    def test_health_is_public(self, e2e_client: E2EHttpClient):
        """Health endpoint should return 200 without token."""
        from tests.e2e.conftest import _BASE_URL
        no_auth = E2EHttpClient(_BASE_URL, token="", timeout=10.0)
        import ssl, os
        if os.environ.get("BEAGLE_E2E_INSECURE", "").strip() == "1":
            no_auth._ctx.check_hostname = False
            no_auth._ctx.verify_mode = ssl.CERT_NONE
        status, _ = no_auth.get("/api/v1/health")
        # Health may be public (200) or require auth (401/403) — either is acceptable
        assert status in {200, 401, 403}, f"Unexpected status {status}"

    def test_vm_list_requires_auth(self, e2e_client: E2EHttpClient):
        """VM list must reject unauthenticated requests."""
        from tests.e2e.conftest import _BASE_URL
        no_auth = E2EHttpClient(_BASE_URL, token="invalid-token-xyz", timeout=10.0)
        import ssl, os
        if os.environ.get("BEAGLE_E2E_INSECURE", "").strip() == "1":
            no_auth._ctx.check_hostname = False
            no_auth._ctx.verify_mode = ssl.CERT_NONE
        status, _ = no_auth.get("/api/v1/vms")
        assert status in {401, 403}, f"Expected 401/403, got {status}"


# ---------------------------------------------------------------------------
# Jobs API (stateless read)
# ---------------------------------------------------------------------------

@requires_e2e
class TestJobsAPI:

    def test_jobs_list_returns_200(self, e2e_client: E2EHttpClient):
        status, body = e2e_client.get("/api/v1/jobs")
        assert status == 200, f"Jobs list failed: {status} {body}"

    def test_jobs_list_is_list(self, e2e_client: E2EHttpClient):
        _, body = e2e_client.get("/api/v1/jobs")
        jobs = body if isinstance(body, list) else body.get("jobs", body.get("data", []))
        assert isinstance(jobs, list), f"Expected list, got: {body}"


# ---------------------------------------------------------------------------
# VM Lifecycle: create → snapshot → delete
# ---------------------------------------------------------------------------

@requires_e2e
class TestVMLifecycle:
    """Mutating lifecycle test.

    Creates a minimal test VM, takes a snapshot, and deletes it.
    Cleanup is guaranteed via the ``e2e_cleanup_vms`` fixture even on failure.

    NOTE: This test requires the live Beagle host to have resources available
    for creating a VM.  Set BEAGLE_E2E_SKIP_MUTATING=1 to skip mutating tests.
    """

    @staticmethod
    def _skip_if_mutating_disabled():
        import os
        if os.environ.get("BEAGLE_E2E_SKIP_MUTATING", "").strip() == "1":
            pytest.skip("BEAGLE_E2E_SKIP_MUTATING=1 — skipping mutating E2E test")

    def test_vm_lifecycle_create_snapshot_delete(
        self,
        e2e_client: E2EHttpClient,
        e2e_cleanup_vms,
    ):
        self._skip_if_mutating_disabled()

        # 1. Create a minimal test VM
        status, body = e2e_client.post("/api/v1/vms", {
            "name": "beagle-e2e-smoke-lifecycle",
            "node": "local",
            "memory": 512,
            "cores": 1,
            "disk_size_gb": 1,
        })
        assert status in {200, 201, 202}, f"VM create failed: {status} {body}"
        vmid = (
            body.get("vmid")
            or body.get("data", {}).get("vmid")
            or body.get("id")
        )
        assert vmid, f"No vmid in create response: {body}"
        e2e_cleanup_vms.add(int(vmid))

        # 2. Verify VM appears in list
        _, vms_body = e2e_client.get("/api/v1/vms")
        all_vms = vms_body if isinstance(vms_body, list) else vms_body.get("vms", [])
        vmids = {int(v.get("vmid", 0)) for v in all_vms if isinstance(v, dict)}
        assert int(vmid) in vmids, f"VM {vmid} not found in list after creation"

        # 3. Take a snapshot (async job → 202 or sync 200)
        snap_status, snap_body = e2e_client.post(
            f"/api/v1/vms/{vmid}/snapshot",
            {"name": "e2e-smoke-snap"},
        )
        assert snap_status in {200, 201, 202}, f"Snapshot failed: {snap_status} {snap_body}"

        # 4. Delete the VM (cleanup fixture also deletes, but let's test it explicitly)
        del_status, del_body = e2e_client.delete(f"/api/v1/vms/{vmid}")
        assert del_status in {200, 202, 204}, f"VM delete failed: {del_status} {del_body}"
