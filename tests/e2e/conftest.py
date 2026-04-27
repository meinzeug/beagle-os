"""E2E test fixtures for tests against a live Beagle host (srv1/srv2).

GoAdvanced Plan 10 Schritt 7.

Environment variables (set in CI as secrets or locally — NEVER committed):
    BEAGLE_E2E_URL    — e.g. https://srv1.beagle-os.com
    BEAGLE_E2E_TOKEN  — Bearer token for an admin account on the target host

All E2E tests are automatically skipped when BEAGLE_E2E_TOKEN is not set.
"""
from __future__ import annotations

import os

import pytest

from tests.e2e.helpers import E2EHttpClient, _BASE_URL, _TOKEN


@pytest.fixture(scope="session")
def e2e_client():
    """Live E2E HTTP client.  Tests are skipped when BEAGLE_E2E_TOKEN is missing."""
    if not _TOKEN:
        pytest.skip("BEAGLE_E2E_TOKEN not set")
    return E2EHttpClient(_BASE_URL, _TOKEN)


@pytest.fixture
def e2e_cleanup_vms(e2e_client):
    """Collect VMIDs created during a test and delete them in teardown."""
    vmids_to_delete: list[int] = []

    class _Collector:
        def add(self, vmid: int):
            vmids_to_delete.append(vmid)

    collector = _Collector()
    yield collector
    for vmid in vmids_to_delete:
        try:
            e2e_client.delete(f"/api/v1/vms/{vmid}")
        except Exception:  # noqa: BLE001
            pass  # Best-effort cleanup
