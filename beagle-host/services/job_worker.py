"""Background worker that drains the JobQueueService.

GoAdvanced Plan 07 Schritt 2.

The ``JobWorker`` runs a configurable number of daemon threads that
continuously claim pending jobs, dispatch to registered handler functions,
and mark jobs as completed or failed.

Handler interface::

    def my_handler(job: Job, worker: JobWorker) -> Any:
        # May call worker.update_progress(job.job_id, percent, msg)
        # Must check job.cancel_requested periodically for cancellable ops
        return result   # stored in job.result; None is fine

Handlers must be synchronous Python callables.  Async handlers are not
supported — run sync wrappers if needed.

Registration::

    worker.register("vm.snapshot", snapshot_handler)
    worker.register("vm.migrate",  migrate_handler)
    worker.register("backup.create", backup_handler)

Lifecycle::

    worker.start()   # starts N daemon threads + heartbeat/reap thread
    # ... process runs ...
    worker.stop()    # signals threads; join with timeout

Thread model:

- ``_max_workers`` daemon threads (default 4) poll and run jobs.
- 1 maintenance thread (heartbeat sender + stuck-job reaper) runs every
  ``_maintenance_interval`` seconds.

Heartbeat:

  Each worker sends a heartbeat to the queue every ``_heartbeat_interval``
  seconds while a job is running, keeping the job alive.  The maintenance
  thread reaps jobs whose heartbeat has been silent for longer than the queue's
  ``stuck_threshold``.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from job_queue_service import Job, JobQueueService

logger = logging.getLogger(__name__)

# Type alias for handler callables
HandlerFn = Callable[["Job", "JobWorker"], Any]


class JobWorker:
    """Runs background threads to process jobs from a :py:class:`JobQueueService`.

    Parameters
    ----------
    queue:
        The shared ``JobQueueService`` instance.
    max_workers:
        Number of parallel worker threads (default 4).
    poll_interval:
        Seconds to sleep between poll attempts when queue is empty (default 0.2).
    heartbeat_interval:
        Seconds between heartbeats while a job is running (default 5.0).
    maintenance_interval:
        Seconds between maintenance cycles (stuck-reap + purge) (default 30.0).
    """

    def __init__(
        self,
        queue: JobQueueService,
        *,
        max_workers: int = 4,
        poll_interval: float = 0.2,
        heartbeat_interval: float = 5.0,
        maintenance_interval: float = 30.0,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._queue = queue
        self._max_workers = max(1, int(max_workers))
        self._poll_interval = float(poll_interval)
        self._heartbeat_interval = float(heartbeat_interval)
        self._maintenance_interval = float(maintenance_interval)
        self._sleep_fn = sleep_fn
        self._handlers: dict[str, HandlerFn] = {}
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    # ------------------------------------------------------------------
    # Handler registry
    # ------------------------------------------------------------------

    def register(self, name: str, handler: HandlerFn) -> None:
        """Register a handler for jobs with the given ``name``."""
        if not callable(handler):
            raise TypeError(f"handler for {name!r} must be callable")
        self._handlers[name] = handler

    def registered_names(self) -> list[str]:
        return list(self._handlers)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start worker threads. Idempotent if already running."""
        if self._threads:
            return
        self._stop_event.clear()
        for i in range(self._max_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"beagle-job-worker-{i}",
                daemon=True,
            )
            t.start()
            self._threads.append(t)
        mt = threading.Thread(
            target=self._maintenance_loop,
            name="beagle-job-maintenance",
            daemon=True,
        )
        mt.start()
        self._threads.append(mt)
        logger.info(
            "JobWorker started max_workers=%d handlers=%s",
            self._max_workers,
            list(self._handlers),
        )

    def stop(self, timeout: float = 5.0) -> None:
        """Signal all threads to stop and wait up to ``timeout`` seconds."""
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=timeout)
        self._threads.clear()
        logger.info("JobWorker stopped")

    @property
    def is_running(self) -> bool:
        return bool(self._threads) and not self._stop_event.is_set()

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            job = self._queue.claim_next_pending()
            if job is None:
                self._stop_event.wait(timeout=self._poll_interval)
                continue
            self._run_job(job)

    def _run_job(self, job: Job) -> None:
        handler = self._handlers.get(job.name)
        if handler is None:
            self._queue.fail(job.job_id, f"no handler registered for {job.name!r}")
            logger.warning("no handler for job %s name=%r", job.job_id, job.name)
            return

        # Start heartbeat sender
        hb_stop = threading.Event()
        hb_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(job.job_id, hb_stop),
            daemon=True,
        )
        hb_thread.start()

        try:
            result = handler(job, self)
            # Check if job was cancelled mid-run by worker
            if job.cancel_requested:
                # Worker chose not to cancel, but we still complete.
                # If the handler raised CancelledJobError, it will be caught below.
                pass
            self._queue.complete(job.job_id, result)
        except _CancelledJobError:
            # Handler signalled explicit cancellation
            self._queue.fail(job.job_id, "cancelled by handler")
            logger.info("job %s cancelled by handler", job.job_id)
        except Exception as exc:  # noqa: BLE001
            self._queue.fail(job.job_id, str(exc))
            logger.exception("job %s failed: %s", job.job_id, exc)
        finally:
            hb_stop.set()
            hb_thread.join(timeout=1.0)

    # ------------------------------------------------------------------
    # Convenience method for handlers
    # ------------------------------------------------------------------

    def update_progress(self, job_id: str, percent: int, message: str = "") -> None:
        """Convenience proxy for handlers to report progress."""
        self._queue.update_progress(job_id, percent, message)

    # ------------------------------------------------------------------
    # Heartbeat loop
    # ------------------------------------------------------------------

    def _heartbeat_loop(self, job_id: str, stop: threading.Event) -> None:
        while not stop.wait(timeout=self._heartbeat_interval):
            try:
                self._queue.heartbeat(job_id)
            except Exception:  # noqa: BLE001
                break

    # ------------------------------------------------------------------
    # Maintenance loop
    # ------------------------------------------------------------------

    def _maintenance_loop(self) -> None:
        while not self._stop_event.wait(timeout=self._maintenance_interval):
            try:
                reaped = self._queue.reap_stuck_jobs()
                if reaped:
                    logger.warning("reaped stuck jobs: %s", reaped)
            except Exception:  # noqa: BLE001
                logger.exception("maintenance: reap_stuck_jobs failed")
            try:
                purged = self._queue.purge_old_jobs()
                if purged:
                    logger.debug("purged %d old jobs", purged)
            except Exception:  # noqa: BLE001
                logger.exception("maintenance: purge_old_jobs failed")


# ---------------------------------------------------------------------------
# Exception sentinel for handler-requested cancellation
# ---------------------------------------------------------------------------

class _CancelledJobError(Exception):
    """Raised by :py:func:`check_cancelled` inside handlers."""


def check_cancelled(job: Job) -> None:
    """Raise ``_CancelledJobError`` if the job has been cancelled.

    Call this periodically inside long-running handlers::

        for chunk in large_operation():
            check_cancelled(job)
            process(chunk)
    """
    if job.cancel_requested:
        raise _CancelledJobError(f"job {job.job_id} was cancelled")
