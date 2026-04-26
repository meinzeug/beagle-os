"""In-process async job queue.

GoAdvanced Plan 07 Schritt 1.

Provides a thread-safe ``JobQueueService`` backed by an in-memory store
(list + dict). Jobs are lightweight dataclass-like records; callers receive
a ``Job`` view-object immediately after enqueue.

Design decisions:

- No persistent storage in this first iteration — jobs survive in-process
  restarts but not full process restarts. Persistence can be layered on top
  via ``JsonStateStore`` (Plan 01) or SQLite (Plan 06) by providing an
  optional ``persistence_backend`` parameter (stub added).
- ``job_id`` is a UUID4 hex string.
- Idempotency keys (Plan 07 Schritt 5) are optional: pass
  ``idempotency_key=...``; the same key within the TTL returns the existing
  job instead of enqueuing a new one.
- ``JobWorker`` (Schritt 2) is a separate module that consumes jobs from
  this service.
- Thread-safety: a single ``threading.Lock`` guards all mutable state.

Status lifecycle:

    pending → running → completed | failed | cancelled

``cancelled`` is a terminal state. Cancelling a running job is a best-effort
signal; the worker must check ``job.cancel_requested`` and exit cleanly.
"""
from __future__ import annotations

import time
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

TERMINAL_STATUSES = frozenset({STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED})

# Default TTL for idempotency keys and finished jobs kept in memory (24 h).
DEFAULT_IDEMPOTENCY_TTL = 60 * 60 * 24
DEFAULT_JOB_RETENTION = 60 * 60 * 24 * 7  # 7 days


# ---------------------------------------------------------------------------
# Job record
# ---------------------------------------------------------------------------

@dataclass
class Job:
    """A single unit of work tracked by the queue.

    Read-only after creation except via :py:class:`JobQueueService` mutators.
    """

    job_id: str
    name: str
    payload: dict[str, Any]
    status: str = STATUS_PENDING
    progress: int = 0           # 0–100
    message: str = ""
    result: Any = None
    error: str = ""
    idempotency_key: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    heartbeat_at: float | None = None
    cancel_requested: bool = False
    owner: str = ""             # optional user / session identifier

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "payload": self.payload,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "heartbeat_at": self.heartbeat_at,
            "cancel_requested": self.cancel_requested,
            "owner": self.owner,
        }


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class JobNotFoundError(KeyError):
    pass


class JobAlreadyTerminalError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class JobQueueService:
    """Thread-safe in-memory job queue.

    Instantiate once (via ``service_registry.job_queue_service()``) and share
    across threads. The ``JobWorker`` uses :py:meth:`claim_next_pending` to
    dequeue and :py:meth:`heartbeat` to keep jobs alive.
    """

    def __init__(
        self,
        *,
        idempotency_ttl: float = DEFAULT_IDEMPOTENCY_TTL,
        job_retention: float = DEFAULT_JOB_RETENTION,
        stuck_threshold: float = 60 * 30,  # 30 min without heartbeat → stuck
        utcnow: callable = time.time,
    ) -> None:
        self._idempotency_ttl = float(idempotency_ttl)
        self._job_retention = float(job_retention)
        self._stuck_threshold = float(stuck_threshold)
        self._utcnow = utcnow
        self._lock = threading.Lock()
        # ordered pending queue
        self._queue: list[str] = []
        # all jobs by id
        self._jobs: dict[str, Job] = {}
        # idempotency key → (job_id, created_at)
        self._idem: dict[str, tuple[str, float]] = {}

    # ------------------------------------------------------------------
    # Enqueue
    # ------------------------------------------------------------------

    def enqueue(
        self,
        name: str,
        payload: dict[str, Any] | None = None,
        *,
        idempotency_key: str = "",
        owner: str = "",
    ) -> Job:
        if not name:
            raise ValueError("job name is required")
        payload = dict(payload or {})
        now = self._utcnow()

        with self._lock:
            # Idempotency check
            if idempotency_key:
                existing = self._idem.get(idempotency_key)
                if existing is not None:
                    job_id_idem, created = existing
                    if now - created < self._idempotency_ttl:
                        job = self._jobs.get(job_id_idem)
                        if job is not None:
                            return job
                    else:
                        del self._idem[idempotency_key]

            job_id = uuid.uuid4().hex
            job = Job(
                job_id=job_id,
                name=name,
                payload=payload,
                idempotency_key=idempotency_key,
                created_at=now,
                owner=owner,
            )
            self._jobs[job_id] = job
            self._queue.append(job_id)
            if idempotency_key:
                self._idem[idempotency_key] = (job_id, now)

        return job

    # ------------------------------------------------------------------
    # Worker interface
    # ------------------------------------------------------------------

    def claim_next_pending(self) -> Job | None:
        """Atomically move the first pending job to ``running``.

        Returns ``None`` if the queue is empty. Called by the worker thread.
        """
        with self._lock:
            for idx, job_id in enumerate(self._queue):
                job = self._jobs.get(job_id)
                if job is None:
                    continue
                if job.status == STATUS_PENDING:
                    job.status = STATUS_RUNNING
                    job.started_at = self._utcnow()
                    job.heartbeat_at = job.started_at
                    self._queue.pop(idx)
                    return job
        return None

    def heartbeat(self, job_id: str) -> None:
        with self._lock:
            job = self._require(job_id)
            job.heartbeat_at = self._utcnow()

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def update_progress(self, job_id: str, percent: int, message: str = "") -> None:
        with self._lock:
            job = self._require(job_id)
            self._assert_running(job)
            job.progress = max(0, min(100, int(percent)))
            job.message = str(message)
            job.heartbeat_at = self._utcnow()

    def complete(self, job_id: str, result: Any = None) -> None:
        with self._lock:
            job = self._require(job_id)
            self._assert_running(job)
            job.status = STATUS_COMPLETED
            job.progress = 100
            job.result = result
            job.finished_at = self._utcnow()

    def fail(self, job_id: str, error: str = "") -> None:
        with self._lock:
            job = self._require(job_id)
            if job.status in TERMINAL_STATUSES:
                return  # idempotent — don't raise if already failed
            job.status = STATUS_FAILED
            job.error = str(error or "")
            job.finished_at = self._utcnow()

    def cancel(self, job_id: str) -> bool:
        """Request cancellation. Returns True if the cancel was accepted."""
        with self._lock:
            job = self._require(job_id)
            if job.status in TERMINAL_STATUSES:
                return False
            if job.status == STATUS_PENDING:
                job.status = STATUS_CANCELLED
                job.finished_at = self._utcnow()
                # Remove from pending queue
                try:
                    self._queue.remove(job_id)
                except ValueError:
                    pass
                return True
            # Running — signal worker
            job.cancel_requested = True
            return True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(
        self,
        *,
        status: str | None = None,
        name: str | None = None,
        owner: str | None = None,
        since: float | None = None,
        limit: int = 200,
    ) -> list[Job]:
        with self._lock:
            jobs = list(self._jobs.values())
        result = []
        for job in jobs:
            if status is not None and job.status != status:
                continue
            if name is not None and job.name != name:
                continue
            if owner is not None and job.owner != owner:
                continue
            if since is not None and job.created_at < since:
                continue
            result.append(job)
        result.sort(key=lambda j: j.created_at, reverse=True)
        return result[:limit]

    def pending_count(self) -> int:
        with self._lock:
            return len(self._queue)

    def running_jobs(self) -> list[Job]:
        return self.list_jobs(status=STATUS_RUNNING)

    # ------------------------------------------------------------------
    # Stuck-job detection
    # ------------------------------------------------------------------

    def reap_stuck_jobs(self) -> list[str]:
        """Mark running jobs without a recent heartbeat as failed.

        Returns a list of job_ids that were reaped.
        """
        now = self._utcnow()
        reaped: list[str] = []
        with self._lock:
            for job in self._jobs.values():
                if job.status != STATUS_RUNNING:
                    continue
                last_heartbeat = (
                    job.heartbeat_at
                    if job.heartbeat_at is not None
                    else (job.started_at if job.started_at is not None else now)
                )
                if now - last_heartbeat > self._stuck_threshold:
                    job.status = STATUS_FAILED
                    job.error = f"stuck: no heartbeat for {int(now - last_heartbeat)}s"
                    job.finished_at = now
                    reaped.append(job.job_id)
        return reaped

    # ------------------------------------------------------------------
    # Retention cleanup
    # ------------------------------------------------------------------

    def purge_old_jobs(self) -> int:
        """Remove terminal jobs older than ``job_retention`` seconds.

        Returns number of jobs purged.
        """
        now = self._utcnow()
        to_delete: list[str] = []
        with self._lock:
            for job_id, job in self._jobs.items():
                if job.status not in TERMINAL_STATUSES:
                    continue
                finished = job.finished_at or job.created_at
                if now - finished > self._job_retention:
                    to_delete.append(job_id)
            for job_id in to_delete:
                del self._jobs[job_id]
        return len(to_delete)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(f"job not found: {job_id!r}")
        return job

    @staticmethod
    def _assert_running(job: Job) -> None:
        if job.status != STATUS_RUNNING:
            raise JobAlreadyTerminalError(
                f"job {job.job_id!r} is not running (status={job.status!r})"
            )
