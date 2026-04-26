"""Unit tests for ClusterHttpSurfaceService."""
from __future__ import annotations

import sys
import os
from http import HTTPStatus
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "beagle-host", "services"))

from cluster_http_surface import ClusterHttpSurfaceService


def _make_svc(**overrides):
    cm = MagicMock()
    cm.status_payload.return_value = {"state": "ok", "members": []}
    ha = MagicMock()
    ha.reconcile_failed_node.return_value = {"failed_node": "n1", "handled_vm_count": 2}
    maint = MagicMock()
    maint.drain_node.return_value = {"node_name": "n1", "handled_vm_count": 1}

    defaults = dict(
        cluster_membership_service=cm,
        ha_manager_service=ha,
        maintenance_service=maint,
        build_cluster_inventory=lambda: {"nodes": [], "vms": []},
        build_ha_status_payload=lambda: {"ha_state": "ok"},
        ensure_cluster_rpc_listener=MagicMock(),
        audit_event=MagicMock(),
        requester_identity=lambda: "admin",
        cluster_node_name="node1",
        public_manager_url="https://srv1:9088",
        public_server_name="srv1.example.com",
        utcnow=lambda: "2024-01-01T00:00:00Z",
        version="test",
    )
    defaults.update(overrides)
    return ClusterHttpSurfaceService(**defaults), cm, ha, maint


class TestClusterGetRouting:
    def test_cluster_inventory(self):
        svc, cm, _, _ = _make_svc()
        resp = svc.route_get("/api/v1/cluster/inventory")
        assert resp["status"] == HTTPStatus.OK
        assert "nodes" in resp["payload"]
        cm.probe_and_update_member_statuses.assert_called_once()

    def test_cluster_nodes_alias(self):
        svc, cm, _, _ = _make_svc()
        resp = svc.route_get("/api/v1/cluster/nodes")
        assert resp["status"] == HTTPStatus.OK
        cm.probe_and_update_member_statuses.assert_called_once()

    def test_cluster_status(self):
        svc, cm, _, _ = _make_svc()
        resp = svc.route_get("/api/v1/cluster/status")
        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["ok"] is True

    def test_ha_status(self):
        svc, _, _, _ = _make_svc()
        resp = svc.route_get("/api/v1/ha/status")
        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["ha_state"] == "ok"

    def test_unknown_get_returns_none(self):
        svc, _, _, _ = _make_svc()
        assert svc.route_get("/api/v1/unknown") is None

    def test_handles_get(self):
        svc, _, _, _ = _make_svc()
        assert svc.handles_get("/api/v1/cluster/inventory")
        assert svc.handles_get("/api/v1/ha/status")
        assert not svc.handles_get("/api/v1/vms")


class TestClusterPostRouting:
    def test_cluster_init(self):
        svc, cm, _, _ = _make_svc()
        cm.initialize_cluster.return_value = {"initialized": True}
        resp = svc.route_post("/api/v1/cluster/init", json_payload={})
        assert resp["status"] == HTTPStatus.CREATED
        cm.initialize_cluster.assert_called_once()

    def test_cluster_join_token(self):
        svc, cm, _, _ = _make_svc()
        cm.create_join_token.return_value = {"token": "abc", "expires_at": "2025-01-01"}
        resp = svc.route_post("/api/v1/cluster/join-token", json_payload={"ttl_seconds": 900})
        assert resp["status"] == HTTPStatus.CREATED
        cm.create_join_token.assert_called_once_with(ttl_seconds=900)

    def test_cluster_setup_code(self):
        audit = MagicMock()
        svc, cm, _, _ = _make_svc(audit_event=audit)
        cm.create_setup_code.return_value = {
            "setup_code": "BGL-code",
            "expires_at": 1770000000,
            "ttl_seconds": 600,
        }
        resp = svc.route_post("/api/v1/cluster/setup-code", json_payload={"ttl_seconds": 600})
        assert resp["status"] == HTTPStatus.CREATED
        assert resp["payload"]["setup_code"] == "BGL-code"
        cm.create_setup_code.assert_called_once_with(ttl_seconds=600)
        audit.assert_called_once()
        assert "setup_code" not in audit.call_args.kwargs

    def test_cluster_add_server_preflight(self):
        svc, cm, _, _ = _make_svc()
        cm.preflight_add_server.return_value = {
            "ok": True,
            "node_name": "node-b",
            "api_url": "https://node-b.example.test/beagle-api",
            "checks": [],
        }
        resp = svc.route_post(
            "/api/v1/cluster/add-server-preflight",
            json_payload={
                "node_name": "node-b",
                "api_url": "https://node-b.example.test/beagle-api",
                "advertise_host": "node-b.example.test",
                "issue_join_token": True,
            },
        )
        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["preflight"]["ok"] is True
        cm.preflight_add_server.assert_called_once()

    def test_cluster_auto_join(self):
        audit = MagicMock()
        svc, cm, _, _ = _make_svc(audit_event=audit)
        cm.auto_join_server.return_value = {
            "ok": True,
            "preflight": {
                "node_name": "node-b",
                "api_url": "https://node-b.example.test/beagle-api/api/v1",
                "checks": [],
            },
            "target": {"member": {"name": "node-b"}},
        }
        resp = svc.route_post(
            "/api/v1/cluster/auto-join",
            json_payload={
                "setup_code": "BGL-code",
                "node_name": "node-b",
                "api_url": "https://node-b.example.test/beagle-api/api/v1",
                "advertise_host": "node-b.example.test",
            },
        )
        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["auto_join"]["ok"] is True
        cm.auto_join_server.assert_called_once()
        assert cm.auto_join_server.call_args.kwargs["setup_code"] == "BGL-code"
        audit.assert_called_once()
        assert "setup_code" not in audit.call_args.kwargs

    def test_cluster_join_existing(self):
        svc, cm, _, _ = _make_svc()
        cm.join_existing_cluster.return_value = {"member": {"name": "node-b"}}
        resp = svc.route_post(
            "/api/v1/cluster/join-existing",
            json_payload={
                "join_token": "tok",
                "leader_api_url": "https://leader.example.test/beagle-api",
                "node_name": "node-b",
                "api_url": "https://node-b.example.test/beagle-api",
                "advertise_host": "node-b.example.test",
                "rpc_url": "https://node-b.example.test:9089/rpc",
            },
        )
        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["ok"] is True
        cm.join_existing_cluster.assert_called_once_with(
            join_token="tok",
            leader_api_url="https://leader.example.test/beagle-api",
            node_name="node-b",
            api_url="https://node-b.example.test/beagle-api",
            advertise_host="node-b.example.test",
            rpc_url="https://node-b.example.test:9089/rpc",
        )

    def test_cluster_join_with_setup_code(self):
        ensure_rpc = MagicMock()
        audit = MagicMock()
        svc, cm, _, _ = _make_svc(ensure_cluster_rpc_listener=ensure_rpc, audit_event=audit)
        cm.join_with_setup_code.return_value = {"member": {"name": "node-b"}}
        resp = svc.route_post(
            "/api/v1/cluster/join-with-setup-code",
            json_payload={
                "setup_code": "BGL-code",
                "join_token": "tok",
                "leader_api_url": "https://leader.example.test/beagle-api",
                "node_name": "node-b",
                "api_url": "https://node-b.example.test/beagle-api",
                "advertise_host": "node-b.example.test",
                "rpc_url": "https://node-b.example.test:9089/rpc",
            },
        )
        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["ok"] is True
        ensure_rpc.assert_called_once()
        cm.join_with_setup_code.assert_called_once_with(
            setup_code="BGL-code",
            join_token="tok",
            leader_api_url="https://leader.example.test/beagle-api",
            node_name="node-b",
            api_url="https://node-b.example.test/beagle-api",
            advertise_host="node-b.example.test",
            rpc_url="https://node-b.example.test:9089/rpc",
        )
        audit.assert_called_once()
        assert "setup_code" not in audit.call_args.kwargs
        assert "join_token" not in audit.call_args.kwargs

    def test_cluster_leave_local(self):
        audit = MagicMock()
        svc, cm, _, _ = _make_svc(audit_event=audit)
        cm.leave_local_cluster.return_value = {
            "ok": True,
            "detached_node": "node-b",
            "former_leader_node": "leader-node",
        }
        resp = svc.route_post("/api/v1/cluster/leave-local", json_payload={})
        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["ok"] is True
        cm.leave_local_cluster.assert_called_once_with()
        audit.assert_called_once()

    def test_cluster_apply_join(self):
        svc, cm, _, _ = _make_svc()
        cm.apply_join_response.return_value = {"joined": True}
        resp = svc.route_post("/api/v1/cluster/apply-join", json_payload={"join_response": {}})
        assert resp["status"] == HTTPStatus.OK

    def test_cluster_join(self):
        svc, cm, _, _ = _make_svc()
        cm.accept_join_request.return_value = {"joined": True}
        resp = svc.route_post(
            "/api/v1/cluster/join",
            json_payload={
                "join_token": "tok",
                "node_name": "n2",
                "api_url": "https://n2:9088",
                "advertise_host": "n2.example.com",
                "rpc_url": "https://n2:9089",
            },
        )
        assert resp["status"] == HTTPStatus.OK

    def test_ha_reconcile(self):
        svc, _, ha, _ = _make_svc()
        resp = svc.route_post(
            "/api/v1/ha/reconcile-failed-node",
            json_payload={"failed_node": "n1"},
        )
        assert resp["status"] == HTTPStatus.OK
        ha.reconcile_failed_node.assert_called_once_with(failed_node="n1", requester_identity="admin")

    def test_ha_maintenance_drain(self):
        svc, _, _, maint = _make_svc()
        resp = svc.route_post(
            "/api/v1/ha/maintenance/drain",
            json_payload={"node_name": "n1"},
        )
        assert resp["status"] == HTTPStatus.OK
        maint.drain_node.assert_called_once_with(node_name="n1", requester_identity="admin")

    def test_unknown_post_returns_none(self):
        svc, _, _, _ = _make_svc()
        assert svc.route_post("/api/v1/unknown") is None

    def test_handles_post(self):
        svc, _, _, _ = _make_svc()
        assert svc.handles_post("/api/v1/cluster/init")
        assert svc.handles_post("/api/v1/cluster/setup-code")
        assert svc.handles_post("/api/v1/cluster/add-server-preflight")
        assert svc.handles_post("/api/v1/cluster/auto-join")
        assert svc.handles_post("/api/v1/cluster/join-existing")
        assert svc.handles_post("/api/v1/cluster/leave-local")
        assert svc.handles_post("/api/v1/cluster/join-with-setup-code")
        assert svc.handles_post("/api/v1/ha/maintenance/drain")
        assert svc.handles_post("/api/v1/cluster/migrate")
        assert not svc.handles_post("/api/v1/vms")


class TestClusterMigrateAsync:
    def _make_job(self, job_id: str = "migrate-job-1"):
        class _Job:
            def __init__(self, jid: str) -> None:
                self.job_id = jid
        return _Job(job_id)

    def test_migrate_enqueues_job_and_returns_202(self):
        enqueue = MagicMock(return_value=self._make_job("mig-1"))
        svc, _, _, _ = _make_svc(enqueue_job=enqueue)

        resp = svc.route_post(
            "/api/v1/cluster/migrate",
            json_payload={"source_node": "node-a", "target_node": "node-b"},
        )

        assert resp["status"] == HTTPStatus.ACCEPTED
        assert resp["payload"]["ok"] is True
        assert resp["payload"]["job_id"] == "mig-1"
        assert resp["payload"]["source_node"] == "node-a"
        assert resp["payload"]["target_node"] == "node-b"
        enqueue.assert_called_once()
        _, ekw = enqueue.call_args
        assert ekw["idempotency_key"] == "cluster.migrate.node-a.node-b"

    def test_migrate_missing_source_returns_400(self):
        enqueue = MagicMock(return_value=self._make_job())
        svc, _, _, _ = _make_svc(enqueue_job=enqueue)

        resp = svc.route_post(
            "/api/v1/cluster/migrate",
            json_payload={"target_node": "node-b"},
        )

        assert resp["status"] == HTTPStatus.BAD_REQUEST
        assert resp["payload"]["ok"] is False
        enqueue.assert_not_called()

    def test_migrate_no_job_queue_returns_503(self):
        svc, _, _, _ = _make_svc()  # no enqueue_job

        resp = svc.route_post(
            "/api/v1/cluster/migrate",
            json_payload={"source_node": "node-a", "target_node": "node-b"},
        )

        assert resp["status"] == HTTPStatus.SERVICE_UNAVAILABLE
        assert resp["payload"]["ok"] is False

    def test_migrate_enqueue_failure_returns_500(self):
        enqueue = MagicMock(side_effect=RuntimeError("queue full"))
        svc, _, _, _ = _make_svc(enqueue_job=enqueue)

        resp = svc.route_post(
            "/api/v1/cluster/migrate",
            json_payload={"source_node": "node-a", "target_node": "node-b"},
        )

        assert resp["status"] == HTTPStatus.INTERNAL_SERVER_ERROR
        assert resp["payload"]["ok"] is False
        assert "queue full" in resp["payload"]["error"]

    def test_migrate_client_idempotency_key_in_payload(self):
        """Client-supplied idempotency_key in JSON payload overrides server-computed key."""
        enqueue = MagicMock(return_value=self._make_job("custom-mig"))
        svc, _, _, _ = _make_svc(enqueue_job=enqueue)

        svc.route_post(
            "/api/v1/cluster/migrate",
            json_payload={
                "source_node": "node-a",
                "target_node": "node-b",
                "idempotency_key": "my-migration-key",
            },
        )

        _, ekw = enqueue.call_args
        assert ekw["idempotency_key"] == "my-migration-key"


class TestClusterMemberPatchRoute:
    def test_patch_member_calls_update_member(self):
        svc, cm, _, _ = _make_svc()
        cm.update_member.return_value = {"ok": True, "member": {"name": "node-b", "display_name": "Node B"}}

        resp = svc.route_patch(
            "/api/v1/cluster/members/node-b",
            json_payload={"display_name": "Node B"},
        )

        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["ok"] is True
        cm.update_member.assert_called_once()
        kw = cm.update_member.call_args.kwargs
        assert kw["node_name"] == "node-b"
        assert kw["display_name"] == "Node B"

    def test_patch_member_empty_name_returns_400(self):
        svc, cm, _, _ = _make_svc()
        resp = svc.route_patch("/api/v1/cluster/members/", json_payload={})
        assert resp["status"] == HTTPStatus.BAD_REQUEST
        assert resp["payload"]["ok"] is False

    def test_patch_member_service_error_returns_400(self):
        svc, cm, _, _ = _make_svc()
        cm.update_member.side_effect = RuntimeError("not found")

        resp = svc.route_patch(
            "/api/v1/cluster/members/ghost",
            json_payload={"api_url": "https://x.example.com"},
        )

        assert resp["status"] == HTTPStatus.BAD_REQUEST
        assert "not found" in resp["payload"]["error"]

    def test_handles_patch(self):
        svc, _, _, _ = _make_svc()
        assert svc.handles_patch("/api/v1/cluster/members/node-a")
        assert not svc.handles_patch("/api/v1/cluster/init")

    def test_non_member_path_patch_returns_none(self):
        svc, _, _, _ = _make_svc()
        assert svc.route_patch("/api/v1/cluster/init", json_payload={}) is None


class TestClusterMemberDeleteRoute:
    def test_delete_member_calls_remove_member(self):
        svc, cm, _, _ = _make_svc()
        cm.remove_member.return_value = {"ok": True, "removed_node": "node-b", "remaining_member_count": 1}

        resp = svc.route_delete("/api/v1/cluster/members/node-b")

        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["ok"] is True
        cm.remove_member.assert_called_once()
        kw = cm.remove_member.call_args.kwargs
        assert kw["node_name"] == "node-b"

    def test_delete_member_empty_name_returns_400(self):
        svc, _, _, _ = _make_svc()
        resp = svc.route_delete("/api/v1/cluster/members/")
        assert resp["status"] == HTTPStatus.BAD_REQUEST

    def test_delete_member_service_error_returns_400(self):
        svc, cm, _, _ = _make_svc()
        cm.remove_member.side_effect = RuntimeError("leader cannot be removed")

        resp = svc.route_delete("/api/v1/cluster/members/leader")
        assert resp["status"] == HTTPStatus.BAD_REQUEST
        assert "leader" in resp["payload"]["error"]

    def test_handles_delete(self):
        svc, _, _, _ = _make_svc()
        assert svc.handles_delete("/api/v1/cluster/members/node-a")
        assert not svc.handles_delete("/api/v1/cluster/init")

    def test_non_member_path_delete_returns_none(self):
        svc, _, _, _ = _make_svc()
        assert svc.route_delete("/api/v1/cluster/other") is None


class TestClusterLocalPreflight:
    def test_local_preflight_returns_checks(self):
        svc, cm, _, _ = _make_svc()
        cm.local_preflight_kvm_libvirt.return_value = {
            "ok": True,
            "checks": [{"name": "kvm_device", "status": "pass", "message": "ok", "required": True}],
            "summary": {"passed": 1, "failed": 0, "warnings": 0, "skipped": 0},
        }

        resp = svc.route_get("/api/v1/cluster/local-preflight")
        assert resp["status"] == HTTPStatus.OK
        assert resp["payload"]["ok"] is True
        assert len(resp["payload"]["checks"]) == 1

    def test_handles_get_local_preflight(self):
        svc, _, _, _ = _make_svc()
        assert svc.handles_get("/api/v1/cluster/local-preflight")
