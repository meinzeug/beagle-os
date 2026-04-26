"""Tests for JobQueueService.

GoAdvanced Plan 07 Schritt 1.
"""
from __future__ import annotations

import os
import sys
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "beagle-host", "services"))

from job_queue_service import (  # noqa: E402
    Job,
    JobAlreadyTerminalError,
    JobNotFoundError,
    JobQueueService,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
)


@pytest.fixture
def q() -> JobQueueService:
    return JobQueueService()


# ---------------------------------------------------------------------------
# Enqueue
# ---------------------------------------------------------------------------

def test_enqueue_returns_job(q):
    job = q.enqueue("vm.snapshot", {"vm_id": 42})
    assert isinstance(job, Job)
    assert job.job_id
    assert job.name == "vm.snapshot"
    assert job.payload == {"vm_id": 42}
    assert job.status == STATUS_PENDING


def test_enqueue_empty_name_rejected(q):
    with pytest.raises(ValueError):
        q.enqueue("")


def test_enqueue_increments_pending_count(q):
    q.enqueue("a")
    q.enqueue("b")
    assert q.pending_count() == 2


# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------

def test_claim_moves_to_running(q):
    q.enqueue("a")
    job = q.claim_next_pending()
    assert job is not None
    assert job.status == STATUS_RUNNING
    assert job.started_at is not None
    assert q.pending_count() == 0


def test_claim_returns_none_when_empty(q):
    assert q.claim_next_pending() is None


def test_claim_fifo_order(q):
    j1 = q.enqueue("first")
    j2 = q.enqueue("second")
    claimed1 = q.claim_next_pending()
    claimed2 = q.claim_next_pending()
    assert claimed1.job_id == j1.job_id
    assert claimed2.job_id == j2.job_id


# ---------------------------------------------------------------------------
# Progress + Complete + Fail
# ---------------------------------------------------------------------------

def test_update_progress(q):
    job = q.enqueue("a")
    q.claim_next_pending()
    q.update_progress(job.job_id, 50, "halfway")
    refreshed = q.get(job.job_id)
    assert refreshed.progress == 50
    assert refreshed.message == "halfway"


def test_update_progress_clamps(q):
    job = q.enqueue("a")
    q.claim_next_pending()
    q.update_progress(job.job_id, 999)
    assert q.get(job.job_id).progress == 100
    q.update_progress(job.job_id, -5)
    assert q.get(job.job_id).progress == 0


def test_update_progress_on_pending_rejected(q):
    job = q.enqueue("a")
    with pytest.raises(JobAlreadyTerminalError):
        q.update_progress(job.job_id, 50)


def test_complete_job(q):
    job = q.enqueue("a")
    q.claim_next_pending()
    q.complete(job.job_id, {"ok": True})
    refreshed = q.get(job.job_id)
    assert refreshed.status == STATUS_COMPLETED
    assert refreshed.progress == 100
    assert refreshed.result == {"ok": True}
    assert refreshed.finished_at is not None


def test_fail_job(q):
    job = q.enqueue("a")
    q.claim_next_pending()
    q.fail(job.job_id, "something broke")
    refreshed = q.get(job.job_id)
    assert refreshed.status == STATUS_FAILED
    assert "something broke" in refreshed.error


def test_fail_idempotent_if_already_failed(q):
    job = q.enqueue("a")
    q.claim_next_pending()
    q.fail(job.job_id, "first")
    q.fail(job.job_id, "second")  # must not raise


def test_complete_on_failed_raises(q):
    job = q.enqueue("a")
    q.claim_next_pending()
    q.fail(job.job_id, "err")
    with pytest.raises(JobAlreadyTerminalError):
        q.complete(job.job_id)


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

def test_cancel_pending_sets_terminal(q):
    job = q.enqueue("a")
    assert q.cancel(job.job_id) is True
    assert q.get(job.job_id).status == STATUS_CANCELLED
    assert q.pending_count() == 0


def test_cancel_running_sets_flag(q):
    job = q.enqueue("a")
    q.claim_next_pending()
    assert q.cancel(job.job_id) is True
    assert q.get(job.job_id).cancel_requested is True
    assert q.get(job.job_id).status == STATUS_RUNNING  # worker still running


def test_cancel_completed_returns_false(q):
    job = q.enqueue("a")
    q.claim_next_pending()
    q.complete(job.job_id)
    assert q.cancel(job.job_id) is False


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def test_get_returns_none_for_unknown(q):
    assert q.get("nope") is None


def test_list_jobs_filter_by_status(q):
    j1 = q.enqueue("a")
    j2 = q.enqueue("b")
    q.claim_next_pending()  # j1 → running
    pending = q.list_jobs(status=STATUS_PENDING)
    running = q.list_jobs(status=STATUS_RUNNING)
    assert len(pending) == 1 and pending[0].job_id == j2.job_id
    assert len(running) == 1 and running[0].job_id == j1.job_id


def test_list_jobs_filter_by_owner(q):
    q.enqueue("a", owner="alice")
    q.enqueue("b", owner="bob")
    assert len(q.list_jobs(owner="alice")) == 1
    assert len(q.list_jobs(owner="bob")) == 1


def test_list_jobs_limit(q):
    for i in range(10):
        q.enqueue("x")
    assert len(q.list_jobs(limit=3)) == 3


def test_job_as_dict_contains_fields(q):
    job = q.enqueue("vm.backup", {"vm_id": 1}, owner="carol")
    d = job.as_dict()
    assert d["name"] == "vm.backup"
    assert d["owner"] == "carol"
    assert "created_at" in d


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_idempotency_key_deduplicates(q):
    j1 = q.enqueue("a", idempotency_key="k1")
    j2 = q.enqueue("a", idempotency_key="k1")
    assert j1.job_id == j2.job_id
    assert q.pending_count() == 1


def test_idempotency_key_expired_allows_new_job():
    q = JobQueueService(idempotency_ttl=0.0, utcnow=time.time)
    j1 = q.enqueue("a", idempotency_key="k")
    time.sleep(0.01)
    j2 = q.enqueue("a", idempotency_key="k")
    assert j1.job_id != j2.job_id


def test_no_idempotency_key_always_new_job(q):
    j1 = q.enqueue("a")
    j2 = q.enqueue("a")
    assert j1.job_id != j2.job_id


# ---------------------------------------------------------------------------
# Stuck-job detection
# ---------------------------------------------------------------------------

def test_reap_stuck_jobs():
    t = [0.0]

    def _now():
        return t[0]

    q = JobQueueService(stuck_threshold=10.0, utcnow=_now)
    job = q.enqueue("a")
    q.claim_next_pending()
    t[0] = 30.0  # simulate 30s passing
    reaped = q.reap_stuck_jobs()
    assert job.job_id in reaped
    assert q.get(job.job_id).status == STATUS_FAILED
    assert "stuck" in q.get(job.job_id).error


def test_heartbeat_prevents_stuck():
    t = [0.0]

    def _now():
        return t[0]

    q = JobQueueService(stuck_threshold=10.0, utcnow=_now)
    job = q.enqueue("a")
    q.claim_next_pending()
    t[0] = 8.0
    q.heartbeat(job.job_id)
    t[0] = 12.0  # only 4s since last heartbeat
    reaped = q.reap_stuck_jobs()
    assert job.job_id not in reaped


# ---------------------------------------------------------------------------
# Retention cleanup
# ---------------------------------------------------------------------------

def test_purge_old_jobs():
    t = [0.0]

    def _now():
        return t[0]

    q = JobQueueService(job_retention=10.0, utcnow=_now)
    job = q.enqueue("a")
    q.claim_next_pending()
    q.complete(job.job_id)
    t[0] = 100.0
    count = q.purge_old_jobs()
    assert count == 1
    assert q.get(job.job_id) is None


def test_purge_keeps_non_terminal_jobs():
    t = [0.0]

    def _now():
        return t[0]

    q = JobQueueService(job_retention=10.0, utcnow=_now)
    q.enqueue("running")
    t[0] = 100.0
    count = q.purge_old_jobs()
    assert count == 0


# ---------------------------------------------------------------------------
# Not-found errors
# ---------------------------------------------------------------------------

def test_get_nonexistent_returns_none(q):
    assert q.get("x") is None


def test_complete_nonexistent_raises(q):
    with pytest.raises(JobNotFoundError):
        q.complete("x")


def test_fail_nonexistent_raises(q):
    with pytest.raises(JobNotFoundError):
        q.fail("x")


def test_cancel_nonexistent_raises(q):
    with pytest.raises(JobNotFoundError):
        q.cancel("x")


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

def test_concurrent_enqueue_and_claim():
    q = JobQueueService()
    n = 100
    results: list[str] = []
    lock = threading.Lock()

    def producer():
        for _ in range(n):
            q.enqueue("t")

    def consumer():
        claimed = 0
        while claimed < n:
            job = q.claim_next_pending()
            if job:
                q.complete(job.job_id)
                with lock:
                    results.append(job.job_id)
                claimed += 1
            else:
                time.sleep(0.001)

    p = threading.Thread(target=producer)
    c = threading.Thread(target=consumer)
    p.start(); c.start(); p.join(); c.join()
    assert len(results) == n
    assert len(set(results)) == n  # all unique
