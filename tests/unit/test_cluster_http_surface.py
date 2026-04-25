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
        assert svc.handles_post("/api/v1/ha/maintenance/drain")
        assert not svc.handles_post("/api/v1/vms")
