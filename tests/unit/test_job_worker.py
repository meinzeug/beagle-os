"""Tests for JobWorker.

GoAdvanced Plan 07 Schritt 2.
"""
from __future__ import annotations

import os
import sys
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "beagle-host", "services"))

from job_queue_service import JobQueueService, STATUS_COMPLETED, STATUS_FAILED  # noqa: E402
from job_worker import JobWorker, check_cancelled  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_pair(max_workers: int = 1) -> tuple[JobQueueService, JobWorker]:
    q = JobQueueService()
    w = JobWorker(q, max_workers=max_workers, poll_interval=0.01, heartbeat_interval=0.05)
    return q, w


def wait_for(cond, timeout: float = 2.0, interval: float = 0.01) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return True
        time.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_stores_handler():
    _, w = make_pair()
    w.register("vm.snapshot", lambda job, worker: None)
    assert "vm.snapshot" in w.registered_names()


def test_register_non_callable_raises():
    _, w = make_pair()
    with pytest.raises(TypeError):
        w.register("bad", "not_a_callable")


# ---------------------------------------------------------------------------
# Basic dispatch
# ---------------------------------------------------------------------------

def test_job_runs_and_completes():
    q, w = make_pair()
    results = []

    def handler(job, worker):
        results.append(job.payload["x"])
        return {"done": True}

    w.register("t", handler)
    w.start()
    try:
        job = q.enqueue("t", {"x": 42})
        assert wait_for(lambda: q.get(job.job_id).status == STATUS_COMPLETED)
        assert q.get(job.job_id).result == {"done": True}
        assert results == [42]
    finally:
        w.stop()


def test_failed_handler_marks_job_failed():
    q, w = make_pair()

    def handler(job, worker):
        raise RuntimeError("boom")

    w.register("err", handler)
    w.start()
    try:
        job = q.enqueue("err")
        assert wait_for(lambda: q.get(job.job_id).status == STATUS_FAILED)
        assert "boom" in q.get(job.job_id).error
    finally:
        w.stop()


def test_no_handler_fails_job():
    q, w = make_pair()
    w.start()
    try:
        job = q.enqueue("unknown_name")
        assert wait_for(lambda: q.get(job.job_id).status == STATUS_FAILED)
        assert "no handler" in q.get(job.job_id).error
    finally:
        w.stop()


# ---------------------------------------------------------------------------
# Progress updates
# ---------------------------------------------------------------------------

def test_handler_can_report_progress():
    q, w = make_pair()
    progresses = []

    def handler(job, worker):
        worker.update_progress(job.job_id, 50, "halfway")
        progresses.append(q.get(job.job_id).progress)
        return None

    w.register("prog", handler)
    w.start()
    try:
        job = q.enqueue("prog")
        assert wait_for(lambda: q.get(job.job_id).status == STATUS_COMPLETED)
        assert 50 in progresses
    finally:
        w.stop()


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

def test_check_cancelled_raises_when_flagged():
    q, w = make_pair()

    was_cancelled = threading.Event()

    def handler(job, worker):
        # Simulate long op
        for _ in range(100):
            check_cancelled(job)
            time.sleep(0.001)

    w.register("can", handler)
    w.start()
    try:
        job = q.enqueue("can")
        # Wait for it to start running, then cancel
        assert wait_for(lambda: q.get(job.job_id).status == "running")
        q.cancel(job.job_id)
        assert wait_for(lambda: q.get(job.job_id).status == STATUS_FAILED)
        assert "cancelled" in q.get(job.job_id).error
    finally:
        w.stop()


# ---------------------------------------------------------------------------
# Parallel workers
# ---------------------------------------------------------------------------

def test_parallel_workers_process_multiple_jobs():
    q, w = make_pair(max_workers=4)
    done = threading.Event()
    count = [0]
    lock = threading.Lock()

    def handler(job, worker):
        time.sleep(0.05)
        with lock:
            count[0] += 1
        return None

    w.register("par", handler)
    w.start()
    try:
        jobs = [q.enqueue("par") for _ in range(8)]
        assert wait_for(
            lambda: all(q.get(j.job_id).status == STATUS_COMPLETED for j in jobs),
            timeout=4.0,
        ), f"not all completed, count={count[0]}"
        assert count[0] == 8
    finally:
        w.stop()


# ---------------------------------------------------------------------------
# Start/stop idempotency
# ---------------------------------------------------------------------------

def test_start_idempotent():
    q, w = make_pair()
    w.start()
    n_threads_1 = len(w._threads)
    w.start()  # second call should be no-op
    n_threads_2 = len(w._threads)
    w.stop()
    assert n_threads_1 == n_threads_2


def test_stop_clears_threads():
    q, w = make_pair()
    w.start()
    assert w.is_running
    w.stop()
    assert not w.is_running
    assert w._threads == []


# ---------------------------------------------------------------------------
# Heartbeat keeps jobs alive
# ---------------------------------------------------------------------------

def test_worker_heartbeat_updates_heartbeat_at():
    q = JobQueueService()
    w = JobWorker(q, max_workers=1, poll_interval=0.01, heartbeat_interval=0.02)

    started = threading.Event()

    def handler(job, worker):
        started.set()
        time.sleep(0.15)  # long enough for heartbeats
        return None

    w.register("hb", handler)
    w.start()
    try:
        job = q.enqueue("hb")
        started.wait(timeout=1.0)
        t0 = q.get(job.job_id).heartbeat_at
        time.sleep(0.1)
        t1 = q.get(job.job_id).heartbeat_at
        assert wait_for(lambda: q.get(job.job_id).status == STATUS_COMPLETED)
        assert t1 is not None
        # heartbeat_at should have advanced
        assert t1 >= t0
    finally:
        w.stop()
