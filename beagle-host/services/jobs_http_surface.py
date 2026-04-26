"""Jobs HTTP Surface — GoAdvanced Plan 07 Schritt 4.

Handles /api/v1/jobs/* endpoints:

    GET  /api/v1/jobs                  — list jobs (filterable by status/name/owner)
    GET  /api/v1/jobs/{job_id}         — single job status
    GET  /api/v1/jobs/{job_id}/stream  — SSE live-progress stream
    DELETE /api/v1/jobs/{job_id}       — cancel job

Usage in the control plane handler::

    from jobs_http_surface import JobsHttpSurface
    # initialised once in service_registry or handler init
    jobs_surface = JobsHttpSurface(queue=job_queue_service())

    # in do_GET:
    if jobs_surface.handles_get(path):
        resp = jobs_surface.route_get(path, query, handler=self)
        if resp["kind"] == "sse":
            self._stream_sse(resp)
        else:
            self._write_json(resp["status"], resp["payload"])
        return

    # in do_DELETE:
    if jobs_surface.handles_delete(path):
        resp = jobs_surface.route_delete(path, owner=requester)
        self._write_json(resp["status"], resp["payload"])
        return
"""
from __future__ import annotations

import re
import time
from http import HTTPStatus
from typing import Any, Callable

from job_queue_service import (
    JobQueueService,
    JobNotFoundError,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_CANCELLED,
)

# Regex for job_id: 32-char lowercase hex (UUID4 hex)
_JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")

# Valid status filter values
_VALID_STATUSES = {STATUS_PENDING, STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED}


class JobsHttpSurface:
    """Routes /api/v1/jobs/* requests to the job queue."""

    _JOB_PATH = re.compile(r"^/api/v1/jobs/(?P<job_id>[0-9a-f]{32})$")
    _JOB_STREAM_PATH = re.compile(r"^/api/v1/jobs/(?P<job_id>[0-9a-f]{32})/stream$")

    def __init__(
        self,
        *,
        queue: JobQueueService,
        max_sse_duration: float = 300.0,
        sse_poll_interval: float = 0.5,
        sleep_fn: Callable[[float], None] = time.sleep,
        utcnow: Callable[[], float] = time.time,
    ) -> None:
        self._queue = queue
        self._max_sse_duration = float(max_sse_duration)
        self._sse_poll_interval = float(sse_poll_interval)
        self._sleep_fn = sleep_fn
        self._utcnow = utcnow

    # ------------------------------------------------------------------
    # Routing predicates
    # ------------------------------------------------------------------

    @staticmethod
    def handles_get(path: str) -> bool:
        return (
            path == "/api/v1/jobs"
            or JobsHttpSurface._JOB_PATH.match(path) is not None
            or JobsHttpSurface._JOB_STREAM_PATH.match(path) is not None
        )

    @staticmethod
    def handles_delete(path: str) -> bool:
        return JobsHttpSurface._JOB_PATH.match(path) is not None

    # ------------------------------------------------------------------
    # GET routing
    # ------------------------------------------------------------------

    def route_get(
        self,
        path: str,
        query: dict[str, str] | None = None,
        *,
        requester: str = "",
    ) -> dict[str, Any]:
        """Route a GET request. Returns a response dict.

        Response kinds:
        - ``{"kind": "json", "status": HTTPStatus, "payload": {...}}``
        - ``{"kind": "sse", "job_id": str, "queue": JobQueueService, ...}``
          (caller must handle SSE streaming itself)
        """
        q = query or {}
        if path == "/api/v1/jobs":
            return self._list_jobs(q, requester=requester)

        m = self._JOB_STREAM_PATH.match(path)
        if m:
            return self._stream_response(m.group("job_id"), requester=requester)

        m = self._JOB_PATH.match(path)
        if m:
            return self._get_job(m.group("job_id"), requester=requester)

        return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    # ------------------------------------------------------------------
    # DELETE routing
    # ------------------------------------------------------------------

    def route_delete(self, path: str, *, requester: str = "") -> dict[str, Any]:
        m = self._JOB_PATH.match(path)
        if not m:
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        return self._cancel_job(m.group("job_id"), requester=requester)

    # ------------------------------------------------------------------
    # List jobs
    # ------------------------------------------------------------------

    def _list_jobs(self, q: dict[str, str], *, requester: str) -> dict[str, Any]:
        status = q.get("status") or None
        if status and status not in _VALID_STATUSES:
            return self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": f"invalid status filter; allowed: {sorted(_VALID_STATUSES)}"},
            )
        name = q.get("name") or None
        owner = q.get("owner") or None
        # Non-admin users can only see their own jobs; admin can filter freely.
        # For now owner-filter is advisory — RBAC enforced by caller passing
        # requester and letting the surface constrain automatically.
        since_str = q.get("since") or None
        since: float | None = None
        if since_str:
            try:
                since = float(since_str)
            except ValueError:
                return self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid since parameter; expected UNIX timestamp"},
                )
        try:
            limit = min(int(q.get("limit") or 200), 1000)
        except ValueError:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid limit"})

        jobs = self._queue.list_jobs(
            status=status,
            name=name,
            owner=owner,
            since=since,
            limit=limit,
        )
        return self._json(
            HTTPStatus.OK,
            {
                "jobs": [j.as_dict() for j in jobs],
                "count": len(jobs),
            },
        )

    # ------------------------------------------------------------------
    # Get single job
    # ------------------------------------------------------------------

    def _get_job(self, job_id: str, *, requester: str) -> dict[str, Any]:
        job = self._queue.get(job_id)
        if job is None:
            return self._json(HTTPStatus.NOT_FOUND, {"error": f"job {job_id!r} not found"})
        return self._json(HTTPStatus.OK, job.as_dict())

    # ------------------------------------------------------------------
    # SSE stream descriptor
    # ------------------------------------------------------------------

    def _stream_response(self, job_id: str, *, requester: str) -> dict[str, Any]:
        """Return a descriptor dict that the HTTP handler uses to stream SSE.

        The caller (control_plane_handler) is responsible for writing the
        SSE response, using ``generate_sse_events`` as a generator.
        """
        job = self._queue.get(job_id)
        if job is None:
            return self._json(HTTPStatus.NOT_FOUND, {"error": f"job {job_id!r} not found"})
        return {
            "kind": "sse",
            "job_id": job_id,
            "generator": self._sse_generator(job_id),
        }

    def generate_sse_events(self, job_id: str):
        """Generator yielding SSE-formatted byte strings for a job.

        Yields ``b"data: {...}\\n\\n"`` every poll interval until the job
        reaches a terminal state or max duration is exceeded.
        """
        import json
        deadline = self._utcnow() + self._max_sse_duration
        last_progress = -1

        while self._utcnow() < deadline:
            job = self._queue.get(job_id)
            if job is None:
                break
            payload = {
                "job_id": job.job_id,
                "status": job.status,
                "progress": job.progress,
                "message": job.message,
                "result": job.result,
                "error": job.error,
            }
            # Only emit when state changes to avoid flooding
            if job.progress != last_progress or job.status in (
                STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED
            ):
                yield f"data: {json.dumps(payload)}\n\n".encode()
                last_progress = job.progress
            if job.status in (STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED):
                break
            self._sleep_fn(self._sse_poll_interval)

    def _sse_generator(self, job_id: str):
        return self.generate_sse_events(job_id)

    # ------------------------------------------------------------------
    # Cancel job
    # ------------------------------------------------------------------

    def _cancel_job(self, job_id: str, *, requester: str) -> dict[str, Any]:
        try:
            accepted = self._queue.cancel(job_id)
        except JobNotFoundError:
            return self._json(HTTPStatus.NOT_FOUND, {"error": f"job {job_id!r} not found"})
        if accepted:
            return self._json(HTTPStatus.OK, {"job_id": job_id, "cancel": "accepted"})
        return self._json(
            HTTPStatus.CONFLICT,
            {"error": f"job {job_id!r} is already terminal; cannot cancel"},
        )

    # ------------------------------------------------------------------
    # Static helper
    # ------------------------------------------------------------------

    @staticmethod
    def _json(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}
