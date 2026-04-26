"""Unit tests for BackupsHttpSurfaceService."""
from __future__ import annotations

import sys
import os
from http import HTTPStatus
from unittest.mock import MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "beagle-host", "services"))

from backups_http_surface import BackupsHttpSurfaceService


def _make_svc(**overrides):
    backup_svc = MagicMock()
    backup_svc.list_jobs.return_value = [{"job_id": "abc"}]
    backup_svc.list_snapshots.return_value = []
    backup_svc.get_replication_config.return_value = {"remote": ""}
    backup_svc.get_pool_policy.return_value = {"policy": "daily"}
    backup_svc.get_vm_policy.return_value = {"policy": "weekly"}
    backup_svc.list_snapshot_files.return_value = {"ok": True, "files": []}
    backup_svc.read_snapshot_file.return_value = b"data"
    backup_svc.run_backup_now.return_value = {"ok": True, "job": {"job_id": "j1"}}
    backup_svc.restore_snapshot.return_value = {"ok": True, "restored_to": "/tmp/x"}
    backup_svc.replicate_to_remote.return_value = {"ok": True}
    backup_svc.prune_old_snapshots.return_value = [{"job_id": "j2", "scope_type": "pool", "scope_id": "p1", "created_at": "t"}]
    backup_svc.ingest_replicated_backup.return_value = {"ok": True, "job_id": "j3"}
    backup_svc.update_pool_policy.return_value = {"policy": "updated"}
    backup_svc.update_vm_policy.return_value = {"policy": "updated"}
    backup_svc.update_replication_config.return_value = {"remote": "updated"}

    quota_svc = MagicMock()
    quota_svc.get_pool_quota.return_value = {"quota_bytes": 1024}
    quota_svc.set_pool_quota.return_value = {"quota_bytes": 2048}

    defaults = dict(
        backup_service=backup_svc,
        storage_quota_service=quota_svc,
        audit_event=MagicMock(),
        requester_identity=lambda: "testuser",
        read_binary_body=lambda n: b"x" * n,
        utcnow=lambda: "2024-01-01T00:00:00Z",
        version="test",
    )
    defaults.update(overrides)
    return BackupsHttpSurfaceService(**defaults), backup_svc, quota_svc


class TestBackupsGetRouting:
    def test_list_jobs(self):
        svc, bk, _ = _make_svc()
        resp = svc.route_get("/api/v1/backups/jobs", query={"scope_type": ["pool"], "scope_id": ["p1"]})
        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["ok"] is True
        assert "jobs" in resp["payload"]
        bk.list_jobs.assert_called_once_with(scope_type="pool", scope_id="p1")

    def test_list_snapshots(self):
        svc, bk, _ = _make_svc()
        resp = svc.route_get("/api/v1/backups/snapshots")
        assert resp["payload"]["ok"] is True
        bk.list_snapshots.assert_called_once()

    def test_replication_config(self):
        svc, bk, _ = _make_svc()
        resp = svc.route_get("/api/v1/backups/replication/config")
        assert resp["status"] == HTTPStatus.OK
        bk.get_replication_config.assert_called_once()

    def test_snapshot_files_list(self):
        svc, bk, _ = _make_svc()
        job_id = "12345678-1234-1234-1234-123456789abc"
        resp = svc.route_get(f"/api/v1/backups/{job_id}/files")
        assert resp["status"] == HTTPStatus.OK
        bk.list_snapshot_files.assert_called_once_with(job_id)

    def test_snapshot_files_download(self):
        svc, bk, _ = _make_svc()
        job_id = "12345678-1234-1234-1234-123456789abc"
        resp = svc.route_get(f"/api/v1/backups/{job_id}/files", query={"path": ["/etc/hosts"]})
        assert resp["kind"] == "bytes"
        bk.read_snapshot_file.assert_called_once_with(job_id, "/etc/hosts")

    def test_pool_policy(self):
        svc, bk, _ = _make_svc()
        resp = svc.route_get("/api/v1/backups/policies/pools/mypool")
        assert resp["status"] == HTTPStatus.OK
        bk.get_pool_policy.assert_called_once_with("mypool")

    def test_vm_policy(self):
        svc, bk, _ = _make_svc()
        resp = svc.route_get("/api/v1/backups/policies/vms/101")
        assert resp["status"] == HTTPStatus.OK
        bk.get_vm_policy.assert_called_once_with(101)

    def test_storage_quota(self):
        svc, _, qsvc = _make_svc()
        resp = svc.route_get("/api/v1/storage/pools/local/quota")
        assert resp["payload"]["quota_bytes"] == 1024
        qsvc.get_pool_quota.assert_called_once_with("local")

    def test_unknown_path_returns_none(self):
        svc, _, _ = _make_svc()
        assert svc.route_get("/api/v1/unknown") is None

    def test_handles_get(self):
        svc, _, _ = _make_svc()
        assert svc.handles_get("/api/v1/backups/jobs")
        assert not svc.handles_get("/api/v1/vms")


class TestBackupsPostRouting:
    def test_run_backup(self):
        svc, bk, _ = _make_svc()
        resp = svc.route_post("/api/v1/backups/run", json_payload={"scope_type": "pool", "scope_id": "p1"})
        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["ok"] is True
        bk.run_backup_now.assert_called_once_with(scope_type="pool", scope_id="p1")

    def test_restore(self):
        svc, bk, _ = _make_svc()
        job_id = "12345678-1234-1234-1234-123456789abc"
        resp = svc.route_post(f"/api/v1/backups/{job_id}/restore", json_payload={"restore_path": "/tmp"})
        assert resp["status"] == HTTPStatus.OK
        bk.restore_snapshot.assert_called_once_with(job_id, restore_path="/tmp")

    def test_replicate(self):
        svc, bk, _ = _make_svc()
        job_id = "12345678-1234-1234-1234-123456789abc"
        resp = svc.route_post(f"/api/v1/backups/{job_id}/replicate")
        assert resp["status"] == HTTPStatus.OK
        bk.replicate_to_remote.assert_called_once_with(job_id)

    def test_prune(self):
        svc, bk, _ = _make_svc()
        resp = svc.route_post("/api/v1/backups/prune", json_payload={"scope_type": "pool", "scope_id": "p1"})
        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["pruned_count"] == 1

    def test_ingest(self):
        svc, bk, _ = _make_svc()
        resp = svc.route_post(
            "/api/v1/backups/ingest",
            raw_body=b"archivedata",
            raw_headers={"X-Beagle-Backup-Meta": '{"job_id": "orig1"}'},
        )
        assert resp["status"] == HTTPStatus.OK
        bk.ingest_replicated_backup.assert_called_once()

    def test_ingest_no_body_returns_error(self):
        svc, _, _ = _make_svc()
        resp = svc.route_post("/api/v1/backups/ingest")
        assert resp["status"] == HTTPStatus.BAD_REQUEST

    def test_unknown_post_returns_none(self):
        svc, _, _ = _make_svc()
        assert svc.route_post("/api/v1/unknown") is None


class TestBackupsPutRouting:
    def test_update_pool_policy(self):
        svc, bk, _ = _make_svc()
        resp = svc.route_put(
            "/api/v1/backups/policies/pools/mypool",
            json_payload={"retention_days": 14},
        )
        assert resp["status"] == HTTPStatus.OK
        bk.update_pool_policy.assert_called_once_with("mypool", {"retention_days": 14})

    def test_update_vm_policy(self):
        svc, bk, _ = _make_svc()
        resp = svc.route_put(
            "/api/v1/backups/policies/vms/200",
            json_payload={"enabled": False},
        )
        assert resp["status"] == HTTPStatus.OK
        bk.update_vm_policy.assert_called_once_with(200, {"enabled": False})

    def test_update_replication_config(self):
        svc, bk, _ = _make_svc()
        resp = svc.route_put(
            "/api/v1/backups/replication/config",
            json_payload={"remote": "https://backup.example.com"},
        )
        assert resp["status"] == HTTPStatus.OK
        bk.update_replication_config.assert_called_once()

    def test_set_storage_quota(self):
        svc, _, qsvc = _make_svc()
        resp = svc.route_put(
            "/api/v1/storage/pools/local/quota",
            json_payload={"quota_bytes": 2048},
        )
        assert resp["status"] == HTTPStatus.OK
        qsvc.set_pool_quota.assert_called_once_with("local", 2048)


class TestBackupRunAsync:
    def _make_job(self, job_id: str = "cafebabe1234"):
        class _Job:
            def __init__(self, jid: str) -> None:
                self.job_id = jid
        return _Job(job_id)

    def test_run_backup_enqueues_job_and_returns_202(self):
        job = self._make_job("abc123")
        enqueue = MagicMock(return_value=job)
        svc, bk, _ = _make_svc(enqueue_job=enqueue)

        resp = svc.route_post("/api/v1/backups/run", json_payload={"scope_type": "pool", "scope_id": "p1"})

        assert resp["status"] == HTTPStatus.ACCEPTED
        assert resp["payload"]["ok"] is True
        assert resp["payload"]["job_id"] == "abc123"
        assert resp["payload"]["scope_type"] == "pool"
        assert resp["payload"]["scope_id"] == "p1"
        bk.run_backup_now.assert_not_called()
        enqueue.assert_called_once_with(
            "backup.run",
            {"scope_type": "pool", "scope_id": "p1"},
            idempotency_key="backup.run.pool.p1",
            owner="testuser",
        )

    def test_run_backup_enqueue_failure_returns_500(self):
        enqueue = MagicMock(side_effect=RuntimeError("queue full"))
        svc, bk, _ = _make_svc(enqueue_job=enqueue)

        resp = svc.route_post("/api/v1/backups/run", json_payload={"scope_type": "pool", "scope_id": "p1"})

        assert resp["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
        assert resp["payload"]["ok"] is False
        assert "queue full" in resp["payload"]["error"]
        bk.run_backup_now.assert_not_called()

    def test_run_backup_sync_fallback_without_enqueue_job(self):
        svc, bk, _ = _make_svc()  # no enqueue_job
        resp = svc.route_post("/api/v1/backups/run", json_payload={"scope_type": "vm", "scope_id": "200"})

        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["ok"] is True
        bk.run_backup_now.assert_called_once_with(scope_type="vm", scope_id="200")
