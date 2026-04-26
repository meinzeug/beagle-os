"""Backups HTTP Surface — Plan 05 Schritt 3a.

Handles /api/v1/backups/* and /api/v1/storage/pools/*/quota endpoints,
extracted from beagle-control-plane.py to keep that file slim.

Usage in the control plane:
    from backups_http_surface import BackupsHttpSurfaceService
    ...
    svc = BackupsHttpSurfaceService(backup_service=backup_service, ...)
    response = svc.route_get(path, query=query)
    if response is not None:
        self._write_json(response["status"], response["payload"])
        return
"""
from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable


class BackupsHttpSurfaceService:
    # Patterns for paths with variable segments.
    _BACKUP_SNAPSHOT_FILES = re.compile(r"^/api/v1/backups/(?P<job_id>[0-9a-f-]{36})/files$")
    _BACKUP_RESTORE = re.compile(r"^/api/v1/backups/(?P<job_id>[0-9a-f-]{36})/restore$")
    _BACKUP_REPLICATE = re.compile(r"^/api/v1/backups/(?P<job_id>[0-9a-f-]{36})/replicate$")
    _BACKUP_POOL_POLICY = re.compile(r"^/api/v1/backups/policies/pools/(?P<pool_id>[A-Za-z0-9._-]+)$")
    _BACKUP_VM_POLICY = re.compile(r"^/api/v1/backups/policies/vms/(?P<vmid>\d+)$")
    _STORAGE_POOL_QUOTA = re.compile(r"^/api/v1/storage/pools/(?P<pool>[A-Za-z0-9._-]+)/quota$")

    # All static GET paths handled here.
    _GET_PATHS = {
        "/api/v1/backups/jobs",
        "/api/v1/backups/snapshots",
        "/api/v1/backups/replication/config",
    }
    # All static POST paths handled here.
    _POST_PATHS = {
        "/api/v1/backups/run",
        "/api/v1/backups/prune",
        "/api/v1/backups/ingest",
    }

    def __init__(
        self,
        *,
        backup_service: Any,
        storage_quota_service: Any,
        audit_event: Callable[..., None],
        requester_identity: Callable[[], str],
        read_binary_body: Callable[[int], bytes],
        service_name: str = "beagle-control-plane",
        utcnow: Callable[[], str],
        version: str = "",
        enqueue_job: Callable[..., Any] | None = None,
    ) -> None:
        self._backup = backup_service
        self._storage_quota = storage_quota_service
        self._audit_event = audit_event
        self._requester_identity = requester_identity
        self._read_binary_body = read_binary_body
        self._service_name = str(service_name or "beagle-control-plane")
        self._utcnow = utcnow
        self._version = str(version or "")
        self._enqueue_job = enqueue_job

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _json(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    @staticmethod
    def _bytes(status: HTTPStatus, body: bytes, content_type: str, filename: str = "") -> dict[str, Any]:
        return {"kind": "bytes", "status": status, "body": body, "content_type": content_type, "filename": filename}

    # ------------------------------------------------------------------
    # GET routing
    # ------------------------------------------------------------------

    def handles_get(self, path: str) -> bool:
        if path in self._GET_PATHS:
            return True
        if self._BACKUP_SNAPSHOT_FILES.match(path):
            return True
        if self._BACKUP_POOL_POLICY.match(path):
            return True
        if self._BACKUP_VM_POLICY.match(path):
            return True
        if self._STORAGE_POOL_QUOTA.match(path):
            return True
        return False

    def route_get(
        self,
        path: str,
        *,
        query: dict[str, list[str]] | None = None,
        accept_header: str = "",
    ) -> dict[str, Any] | None:
        q = query or {}

        if path == "/api/v1/backups/jobs":
            scope_type = str(q.get("scope_type", [""])[0] or "").strip().lower()
            scope_id = str(q.get("scope_id", [""])[0] or "").strip()
            jobs = self._backup.list_jobs(scope_type=scope_type, scope_id=scope_id)
            return self._json(HTTPStatus.OK, {"ok": True, "jobs": jobs})

        if path == "/api/v1/backups/snapshots":
            scope_type = str(q.get("scope_type", [""])[0] or "").strip().lower()
            scope_id = str(q.get("scope_id", [""])[0] or "").strip()
            snapshots = self._backup.list_snapshots(scope_type=scope_type, scope_id=scope_id)
            return self._json(HTTPStatus.OK, {"ok": True, "snapshots": snapshots})

        m = self._BACKUP_SNAPSHOT_FILES.match(path)
        if m:
            job_id = m.group("job_id")
            file_path = str(q.get("path", [""])[0] or "").strip()
            if file_path:
                try:
                    data = self._backup.read_snapshot_file(job_id, file_path)
                except (ValueError, FileNotFoundError) as exc:
                    return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                filename = file_path.split("/")[-1] or "file"
                return self._bytes(HTTPStatus.OK, data, "application/octet-stream", filename)
            else:
                try:
                    result = self._backup.list_snapshot_files(job_id)
                except ValueError as exc:
                    return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return self._json(HTTPStatus.OK, result)

        if path == "/api/v1/backups/replication/config":
            return self._json(HTTPStatus.OK, {"ok": True, **self._backup.get_replication_config()})

        m = self._BACKUP_POOL_POLICY.match(path)
        if m:
            pool_id = str(m.group("pool_id") or "").strip()
            try:
                payload = self._backup.get_pool_policy(pool_id)
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json(HTTPStatus.OK, {"ok": True, **payload})

        m = self._BACKUP_VM_POLICY.match(path)
        if m:
            vmid = int(m.group("vmid") or 0)
            payload = self._backup.get_vm_policy(vmid)
            return self._json(HTTPStatus.OK, {"ok": True, **payload})

        m = self._STORAGE_POOL_QUOTA.match(path)
        if m:
            pool_name = str(m.group("pool") or "").strip()
            try:
                payload = self._storage_quota.get_pool_quota(pool_name)
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return self._json(HTTPStatus.OK, {"ok": True, **payload})

        return None

    # ------------------------------------------------------------------
    # POST routing
    # ------------------------------------------------------------------

    def handles_post(self, path: str) -> bool:
        if path in self._POST_PATHS:
            return True
        if self._BACKUP_RESTORE.match(path):
            return True
        if self._BACKUP_REPLICATE.match(path):
            return True
        return False

    def route_post(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
        raw_body: bytes | None = None,
        raw_headers: dict[str, str] | None = None,
        client_idempotency_key: str = "",
    ) -> dict[str, Any] | None:
        p = json_payload or {}
        requester = self._requester_identity()

        if path == "/api/v1/backups/run":
            scope_type = str(p.get("scope_type") or "").strip().lower()
            scope_id = str(p.get("scope_id") or "").strip()
            if self._enqueue_job is not None:
                # Async path: enqueue and return 202 Accepted immediately.
                ikey = client_idempotency_key or f"backup.run.{scope_type}.{scope_id}"
                try:
                    job = self._enqueue_job(
                        "backup.run",
                        {"scope_type": scope_type, "scope_id": scope_id},
                        idempotency_key=ikey,
                        owner=requester,
                    )
                except Exception as exc:
                    return self._json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {"ok": False, "error": f"failed to enqueue backup job: {exc}"},
                    )
                self._audit_event(
                    "backup.run.enqueued",
                    "success",
                    scope_type=scope_type,
                    scope_id=scope_id,
                    job_id=str(job.job_id),
                    username=requester,
                )
                return self._json(
                    HTTPStatus.ACCEPTED,
                    {
                        "ok": True,
                        "job_id": str(job.job_id),
                        "scope_type": scope_type,
                        "scope_id": scope_id,
                    },
                )
            # Synchronous fallback (no job queue): run inline and return 200.
            try:
                result = self._backup.run_backup_now(scope_type=scope_type, scope_id=scope_id)
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            outcome = "success" if result.get("ok") else "error"
            self._audit_event(
                "backup.run",
                outcome,
                scope_type=scope_type,
                scope_id=scope_id,
                job_id=str((result.get("job") or {}).get("job_id") or ""),
                username=requester,
            )
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR
            return self._json(status, result)

        m = self._BACKUP_RESTORE.match(path)
        if m:
            job_id = m.group("job_id")
            restore_path = str(p.get("restore_path") or "").strip() or None
            try:
                result = self._backup.restore_snapshot(job_id, restore_path=restore_path)
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event(
                "backup.restore",
                "success" if result.get("ok") else "error",
                job_id=job_id,
                restore_path=str(result.get("restored_to") or ""),
                username=requester,
            )
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR
            return self._json(status, result)

        m = self._BACKUP_REPLICATE.match(path)
        if m:
            job_id = m.group("job_id")
            try:
                result = self._backup.replicate_to_remote(job_id)
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event(
                "backup.replicate",
                "success" if result.get("ok") else "error",
                job_id=job_id,
                username=requester,
            )
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR
            return self._json(status, result)

        if path == "/api/v1/backups/prune":
            scope_type = str(p.get("scope_type") or "").strip()
            scope_id = str(p.get("scope_id") or "").strip()
            try:
                pruned = self._backup.prune_old_snapshots(
                    scope_type=scope_type,
                    scope_id=scope_id,
                )
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            for pjob in pruned:
                self._audit_event(
                    "backup.snapshot_pruned",
                    "success",
                    job_id=str(pjob.get("job_id") or ""),
                    scope_type=str(pjob.get("scope_type") or ""),
                    scope_id=str(pjob.get("scope_id") or ""),
                    created_at=str(pjob.get("created_at") or ""),
                    username=requester,
                )
            return self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "pruned_count": len(pruned),
                    "pruned_jobs": [j.get("job_id") for j in pruned],
                },
            )

        if path == "/api/v1/backups/ingest":
            # raw_body must be provided by the caller (large binary upload)
            if raw_body is None:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "missing request body"})
            meta_raw = str((raw_headers or {}).get("X-Beagle-Backup-Meta") or "{}").strip()
            try:
                import json as _json
                meta = _json.loads(meta_raw)
            except Exception:
                meta = {}
            try:
                result = self._backup.ingest_replicated_backup(archive_bytes=raw_body, meta=meta)
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event(
                "backup.ingest",
                "success",
                job_id=str(result.get("job_id") or ""),
                origin_job_id=str(meta.get("job_id") or ""),
                username=requester,
            )
            return self._json(HTTPStatus.OK, result)

        return None

    # ------------------------------------------------------------------
    # PUT routing
    # ------------------------------------------------------------------

    def handles_put(self, path: str) -> bool:
        if path == "/api/v1/backups/replication/config":
            return True
        if self._BACKUP_POOL_POLICY.match(path):
            return True
        if self._BACKUP_VM_POLICY.match(path):
            return True
        if self._STORAGE_POOL_QUOTA.match(path):
            return True
        return False

    def route_put(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        p = json_payload or {}
        requester = self._requester_identity()

        m = self._BACKUP_POOL_POLICY.match(path)
        if m:
            pool_id = str(m.group("pool_id") or "").strip()
            try:
                result = self._backup.update_pool_policy(pool_id, p)
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event(
                "backup.policy.update",
                "success",
                scope_type="pool",
                scope_id=pool_id,
                username=requester,
            )
            return self._json(HTTPStatus.OK, {"ok": True, **result})

        m = self._BACKUP_VM_POLICY.match(path)
        if m:
            vmid = int(m.group("vmid") or 0)
            result = self._backup.update_vm_policy(vmid, p)
            self._audit_event(
                "backup.policy.update",
                "success",
                scope_type="vm",
                scope_id=str(vmid),
                username=requester,
            )
            return self._json(HTTPStatus.OK, {"ok": True, **result})

        if path == "/api/v1/backups/replication/config":
            try:
                result = self._backup.update_replication_config(p)
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event("backup.replication.config.update", "success", username=requester)
            return self._json(HTTPStatus.OK, {"ok": True, **result})

        m = self._STORAGE_POOL_QUOTA.match(path)
        if m:
            pool_name = str(m.group("pool") or "").strip()
            quota_bytes = int(p.get("quota_bytes", 0) or 0)
            try:
                payload = self._storage_quota.set_pool_quota(pool_name, quota_bytes)
            except ValueError as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            self._audit_event(
                "storage.quota.update",
                "success",
                pool=pool_name,
                quota_bytes=quota_bytes,
                username=requester,
            )
            return self._json(HTTPStatus.OK, {"ok": True, **payload})

        return None
