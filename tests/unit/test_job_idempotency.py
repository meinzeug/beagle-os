"""Tests for Idempotency-Key header support in HTTP surfaces.

GoAdvanced Plan 07 Schritt 5.

Covers:
- BackupsHttpSurfaceService: POST /api/v1/backups/run uses client_idempotency_key when supplied.
- VmMutationSurfaceService:  POST /api/v1/vms/{vmid}/snapshot uses client_idempotency_key.
- Expired TTL: key after TTL creates a new job (tested via JobQueueService directly).
- No key supplied: server-computed key used as fallback.
"""
from __future__ import annotations

import os
import sys
import time
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "beagle-host", "services"))

from backups_http_surface import BackupsHttpSurfaceService  # noqa: E402
from job_queue_service import JobQueueService  # noqa: E402
from vm_mutation_surface import VmMutationSurfaceService  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Vm:
    def __init__(self, vmid: int, node: str) -> None:
        self.vmid = vmid
        self.node = node


def _make_backup_svc(**overrides):
    backup_svc = MagicMock()
    backup_svc.run_backup_now.return_value = {"ok": True, "job": {"job_id": "sync-j1"}}
    quota_svc = MagicMock()
    storage_image_svc = MagicMock()
    defaults = dict(
        backup_service=backup_svc,
        storage_image_store_service=storage_image_svc,
        storage_quota_service=quota_svc,
        audit_event=MagicMock(),
        requester_identity=lambda: "testuser",
        read_binary_body=lambda n: b"x" * n,
        utcnow=lambda: "2024-01-01T00:00:00Z",
        version="test",
    )
    defaults.update(overrides)
    return BackupsHttpSurfaceService(**defaults)


def _make_vm_svc(**overrides):
    vm = _Vm(100, "node-a")
    kwargs = dict(
        attach_usb_to_guest=lambda vm, busid: {},
        build_vm_usb_state=lambda vm: {},
        find_vm=lambda vmid: vm if int(vmid) == 100 else None,
        invalidate_vm_cache=lambda vmid, node: None,
        issue_sunshine_access_token=lambda vm: ("", {}),
        migrate_vm=lambda vmid, target_node, live, copy_storage, requester_identity: {"migration": {}},
        queue_vm_action=lambda vm, action, requester_identity, params=None: {},
        reboot_vm=lambda vmid: "",
        service_name="beagle-control-plane",
        start_vm=lambda vmid: "",
        start_installer_prep=lambda vm: {},
        stop_vm=lambda vmid: "",
        summarize_action_result=lambda payload: payload or {},
        sunshine_proxy_ticket_url=lambda token: token,
        usb_action_wait_seconds=0,
        utcnow=lambda: "2026-04-23T10:00:00Z",
        version="test",
        wait_for_action_result=lambda node, vmid, action_id: None,
        detach_usb_from_guest=lambda vm, port, busid: {},
        delete_vm_snapshot=lambda vmid, snapshot_name: f"deleted {vmid} snapshot {snapshot_name}",
        reset_vm_to_snapshot=lambda vmid, snapshot_name: f"reset {vmid} to {snapshot_name}",
        clone_vm=lambda source_vmid, target_vmid, name="": f"cloned {source_vmid} to {target_vmid} as {name}",
    )
    kwargs.update(overrides)
    return VmMutationSurfaceService(**kwargs)


def _make_job(job_id: str = "idem-job-1"):
    class _Job:
        def __init__(self, jid: str) -> None:
            self.job_id = jid
    return _Job(job_id)


# ---------------------------------------------------------------------------
# BackupsHttpSurface — client_idempotency_key
# ---------------------------------------------------------------------------


class TestBackupRunIdempotencyKey:
    def test_client_key_passed_to_enqueue(self):
        """When client supplies Idempotency-Key, it overrides the server-computed key."""
        enqueue = MagicMock(return_value=_make_job("client-job"))
        svc = _make_backup_svc(enqueue_job=enqueue)

        resp = svc.route_post(
            "/api/v1/backups/run",
            json_payload={"scope_type": "pool", "scope_id": "p1"},
            client_idempotency_key="my-client-key-abc",
        )

        assert resp["status"].value == 202
        assert resp["payload"]["ok"] is True
        assert resp["payload"]["job_id"] == "client-job"
        _, kwargs = enqueue.call_args
        assert kwargs["idempotency_key"] == "my-client-key-abc"

    def test_client_key_deduplicates_repeated_call(self):
        """Two POSTs with the same Idempotency-Key must return the same job_id."""
        job = _make_job("dedup-job")
        enqueue = MagicMock(return_value=job)
        svc = _make_backup_svc(enqueue_job=enqueue)

        resp1 = svc.route_post(
            "/api/v1/backups/run",
            json_payload={"scope_type": "pool", "scope_id": "p1"},
            client_idempotency_key="idempotent-key",
        )
        resp2 = svc.route_post(
            "/api/v1/backups/run",
            json_payload={"scope_type": "pool", "scope_id": "p1"},
            client_idempotency_key="idempotent-key",
        )

        # Both must carry same idempotency key to enqueue
        assert enqueue.call_count == 2
        for c in enqueue.call_args_list:
            assert c[1]["idempotency_key"] == "idempotent-key"
        # Both responses have same job_id (enqueue mock returns same job each time)
        assert resp1["payload"]["job_id"] == resp2["payload"]["job_id"] == "dedup-job"

    def test_no_client_key_uses_server_computed_key(self):
        """Without Idempotency-Key header, server computes key from scope args."""
        enqueue = MagicMock(return_value=_make_job("srv-job"))
        svc = _make_backup_svc(enqueue_job=enqueue)

        svc.route_post(
            "/api/v1/backups/run",
            json_payload={"scope_type": "vm", "scope_id": "200"},
        )

        _, kwargs = enqueue.call_args
        assert kwargs["idempotency_key"] == "backup.run.vm.200"

    def test_empty_client_key_falls_back_to_server_computed(self):
        """Empty string Idempotency-Key acts as 'not supplied'."""
        enqueue = MagicMock(return_value=_make_job("fallback-job"))
        svc = _make_backup_svc(enqueue_job=enqueue)

        svc.route_post(
            "/api/v1/backups/run",
            json_payload={"scope_type": "pool", "scope_id": "x"},
            client_idempotency_key="",
        )

        _, kwargs = enqueue.call_args
        assert kwargs["idempotency_key"] == "backup.run.pool.x"


# ---------------------------------------------------------------------------
# VmMutationSurface — client_idempotency_key
# ---------------------------------------------------------------------------


class TestVmSnapshotIdempotencyKey:
    def test_client_key_overrides_server_computed_key(self):
        enqueue_calls: list[tuple] = []

        def _enqueue(name, payload, *, idempotency_key="", owner=""):
            enqueue_calls.append((name, payload, idempotency_key, owner))
            return _make_job("snap-job-1")

        svc = _make_vm_svc(enqueue_job=_enqueue)

        resp = svc.route_post(
            "/api/v1/vms/100/snapshot",
            json_payload={"name": "mysnap"},
            requester_identity="admin",
            client_idempotency_key="client-snap-key",
        )

        assert resp["payload"]["ok"] is True
        assert len(enqueue_calls) == 1
        _, _, ikey, _ = enqueue_calls[0]
        assert ikey == "client-snap-key"

    def test_no_client_key_uses_server_computed_key(self):
        enqueue_calls: list[tuple] = []

        def _enqueue(name, payload, *, idempotency_key="", owner=""):
            enqueue_calls.append((name, payload, idempotency_key, owner))
            return _make_job("snap-job-2")

        svc = _make_vm_svc(enqueue_job=_enqueue)

        svc.route_post(
            "/api/v1/vms/100/snapshot",
            json_payload={"name": "dailysnap"},
            requester_identity="ops",
        )

        _, _, ikey, _ = enqueue_calls[0]
        assert ikey == "vm.snapshot.100.dailysnap"


# ---------------------------------------------------------------------------
# JobQueueService — TTL expiry (unit-level, no HTTP layer)
# ---------------------------------------------------------------------------


class TestIdempotencyTtlExpiry:
    def test_expired_key_creates_new_job(self):
        """A key that has exceeded the TTL must NOT deduplicate a new enqueue."""
        q = JobQueueService(idempotency_ttl=0.0, utcnow=time.time)
        j1 = q.enqueue("task.a", {}, idempotency_key="ttl-key")
        # TTL is 0, so any re-enqueue creates a new job
        time.sleep(0.01)
        j2 = q.enqueue("task.a", {}, idempotency_key="ttl-key")
        assert j1.job_id != j2.job_id

    def test_within_ttl_deduplicates(self):
        """A key within the TTL window must return the same job."""
        q = JobQueueService(idempotency_ttl=3600.0, utcnow=time.time)
        j1 = q.enqueue("task.b", {}, idempotency_key="live-key")
        j2 = q.enqueue("task.b", {}, idempotency_key="live-key")
        assert j1.job_id == j2.job_id
        assert q.pending_count() == 1

    def test_no_key_never_deduplicates(self):
        """Calls without idempotency_key always create distinct jobs."""
        q = JobQueueService(idempotency_ttl=3600.0, utcnow=time.time)
        j1 = q.enqueue("task.c", {})
        j2 = q.enqueue("task.c", {})
        assert j1.job_id != j2.job_id
        assert q.pending_count() == 2

    def test_different_keys_create_distinct_jobs(self):
        q = JobQueueService(idempotency_ttl=3600.0, utcnow=time.time)
        j1 = q.enqueue("task.d", {}, idempotency_key="key-x")
        j2 = q.enqueue("task.d", {}, idempotency_key="key-y")
        assert j1.job_id != j2.job_id
