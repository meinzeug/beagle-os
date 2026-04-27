"""Tests for JobsHttpSurface.

GoAdvanced Plan 07 Schritt 4.
"""
from __future__ import annotations

import json
import os
import sys
from http import HTTPStatus

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "beagle-host", "services"))

from job_queue_service import JobQueueService, STATUS_COMPLETED, STATUS_CANCELLED  # noqa: E402
from jobs_http_surface import JobsHttpSurface  # noqa: E402


@pytest.fixture
def q():
    return JobQueueService()


@pytest.fixture
def surface(q):
    return JobsHttpSurface(queue=q, sse_poll_interval=0.01)


# ---------------------------------------------------------------------------
# handles_get / handles_delete
# ---------------------------------------------------------------------------

def test_handles_get_list(surface):
    assert surface.handles_get("/api/v1/jobs")


def test_handles_get_single(surface):
    assert surface.handles_get("/api/v1/jobs/" + "a" * 32)


def test_handles_get_stream(surface):
    assert surface.handles_get("/api/v1/jobs/" + "b" * 32 + "/stream")


def test_handles_get_false(surface):
    assert not surface.handles_get("/api/v1/vms")


def test_handles_delete(surface):
    assert surface.handles_delete("/api/v1/jobs/" + "c" * 32)


def test_handles_delete_false(surface):
    assert not surface.handles_delete("/api/v1/jobs")


# ---------------------------------------------------------------------------
# List jobs
# ---------------------------------------------------------------------------

def test_list_empty(surface):
    resp = surface.route_get("/api/v1/jobs")
    assert resp["status"] == HTTPStatus.OK
    assert resp["payload"]["count"] == 0
    assert resp["payload"]["jobs"] == []


def test_list_returns_jobs(q, surface):
    j1 = q.enqueue("vm.snapshot", {"vm_id": 1})
    j2 = q.enqueue("vm.backup", {"vm_id": 2})
    resp = surface.route_get("/api/v1/jobs")
    ids = {j["job_id"] for j in resp["payload"]["jobs"]}
    assert j1.job_id in ids
    assert j2.job_id in ids


def test_list_non_privileged_requester_sees_only_own_jobs(q, surface):
    mine = q.enqueue("vm.snapshot", {"vm_id": 1}, owner="alice")
    q.enqueue("vm.backup", {"vm_id": 2}, owner="bob")

    resp = surface.route_get("/api/v1/jobs", requester="alice")

    assert resp["status"] == HTTPStatus.OK
    assert resp["payload"]["count"] == 1
    assert resp["payload"]["jobs"][0]["job_id"] == mine.job_id


def test_list_legacy_api_token_can_see_all_jobs(q, surface):
    q.enqueue("vm.snapshot", {"vm_id": 1}, owner="alice")
    q.enqueue("vm.backup", {"vm_id": 2}, owner="bob")

    resp = surface.route_get("/api/v1/jobs", requester="legacy-api-token")

    assert resp["status"] == HTTPStatus.OK
    assert resp["payload"]["count"] == 2


def test_list_filter_by_status(q, surface):
    j = q.enqueue("a")
    q.claim_next_pending()  # → running
    resp = surface.route_get("/api/v1/jobs", {"status": "running"})
    assert resp["payload"]["count"] == 1
    assert resp["payload"]["jobs"][0]["job_id"] == j.job_id


def test_list_invalid_status(surface):
    resp = surface.route_get("/api/v1/jobs", {"status": "bogus"})
    assert resp["status"] == HTTPStatus.BAD_REQUEST


def test_list_invalid_limit(surface):
    resp = surface.route_get("/api/v1/jobs", {"limit": "abc"})
    assert resp["status"] == HTTPStatus.BAD_REQUEST


def test_list_invalid_since(surface):
    resp = surface.route_get("/api/v1/jobs", {"since": "not-a-float"})
    assert resp["status"] == HTTPStatus.BAD_REQUEST


def test_list_limit_respected(q, surface):
    for _ in range(10):
        q.enqueue("x")
    resp = surface.route_get("/api/v1/jobs", {"limit": "3"})
    assert resp["payload"]["count"] == 3


# ---------------------------------------------------------------------------
# Get single job
# ---------------------------------------------------------------------------

def test_get_existing_job(q, surface):
    j = q.enqueue("vm.snapshot", {"x": 1})
    resp = surface.route_get(f"/api/v1/jobs/{j.job_id}")
    assert resp["status"] == HTTPStatus.OK
    assert resp["payload"]["job_id"] == j.job_id
    assert resp["payload"]["name"] == "vm.snapshot"


def test_get_foreign_job_forbidden(q, surface):
    j = q.enqueue("vm.snapshot", {"x": 1}, owner="alice")
    resp = surface.route_get(f"/api/v1/jobs/{j.job_id}", requester="bob")
    assert resp["status"] == HTTPStatus.FORBIDDEN


def test_get_nonexistent_job(surface):
    resp = surface.route_get("/api/v1/jobs/" + "0" * 32)
    assert resp["status"] == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Cancel job
# ---------------------------------------------------------------------------

def test_cancel_pending_job(q, surface):
    j = q.enqueue("a")
    resp = surface.route_delete(f"/api/v1/jobs/{j.job_id}")
    assert resp["status"] == HTTPStatus.OK
    assert "accepted" in resp["payload"]["cancel"]
    assert q.get(j.job_id).status == STATUS_CANCELLED


def test_cancel_foreign_job_forbidden(q, surface):
    j = q.enqueue("a", owner="alice")
    resp = surface.route_delete(f"/api/v1/jobs/{j.job_id}", requester="bob")
    assert resp["status"] == HTTPStatus.FORBIDDEN
    assert q.get(j.job_id).status != STATUS_CANCELLED


def test_cancel_completed_job(q, surface):
    j = q.enqueue("a")
    q.claim_next_pending()
    q.complete(j.job_id)
    resp = surface.route_delete(f"/api/v1/jobs/{j.job_id}")
    assert resp["status"] == HTTPStatus.CONFLICT


def test_cancel_nonexistent_job(surface):
    resp = surface.route_delete("/api/v1/jobs/" + "f" * 32)
    assert resp["status"] == HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------

def test_sse_stream_nonexistent_job(surface):
    resp = surface.route_get("/api/v1/jobs/" + "e" * 32 + "/stream")
    assert resp["status"] == HTTPStatus.NOT_FOUND


def test_sse_stream_returns_sse_kind(q, surface):
    j = q.enqueue("a")
    resp = surface.route_get(f"/api/v1/jobs/{j.job_id}/stream")
    assert resp["kind"] == "sse"
    assert "generator" in resp


def test_sse_stream_foreign_job_forbidden(q, surface):
    j = q.enqueue("a", owner="alice")
    resp = surface.route_get(f"/api/v1/jobs/{j.job_id}/stream", requester="bob")
    assert resp["status"] == HTTPStatus.FORBIDDEN


def test_sse_generator_yields_terminal_event(q):
    surface = JobsHttpSurface(queue=q, sse_poll_interval=0.001, max_sse_duration=5.0)
    j = q.enqueue("a")
    q.claim_next_pending()
    q.complete(j.job_id, {"ok": True})

    events = list(surface.generate_sse_events(j.job_id))
    assert len(events) >= 1
    last = json.loads(events[-1].decode().lstrip("data: ").strip())
    assert last["status"] == STATUS_COMPLETED
    assert last["job_id"] == j.job_id


def test_sse_generator_yields_progress_updates(q):
    calls = []
    import threading

    surface = JobsHttpSurface(queue=q, sse_poll_interval=0.01, max_sse_duration=2.0)
    j = q.enqueue("a")
    q.claim_next_pending()

    stop = threading.Event()

    def advance():
        import time
        time.sleep(0.05)
        q.update_progress(j.job_id, 50, "half")
        time.sleep(0.05)
        q.complete(j.job_id)

    t = threading.Thread(target=advance, daemon=True)
    t.start()

    events = list(surface.generate_sse_events(j.job_id))
    t.join(timeout=2.0)
    statuses = [json.loads(e.decode().lstrip("data: ").strip())["status"] for e in events]
    assert STATUS_COMPLETED in statuses
