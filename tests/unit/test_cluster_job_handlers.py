from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "beagle-host", "services"))

from cluster_job_handlers import make_cluster_auto_join_handler, make_cluster_maintenance_drain_handler


def test_cluster_auto_join_handler_reports_progress_and_returns_result():
    membership = MagicMock()
    membership.preflight_add_server.return_value = {"ok": True, "checks": [{"name": "dns", "status": "pass"}]}
    membership.create_join_token.return_value = {"join_token": "join-token"}
    membership.local_member.return_value = {"name": "srv1", "api_url": "https://srv1.example.test/beagle-api/api/v1"}
    membership._api_v1_url.return_value = "https://srv2.example.test/beagle-api/api/v1/cluster/join-with-setup-code"
    membership._post_json.return_value = {
        "cluster": {"cluster_id": "cluster-1"},
        "member": {"name": "srv2"},
        "members": [{"name": "srv1"}, {"name": "srv2"}],
    }
    membership.list_members.side_effect = [
        [{"name": "srv1"}, {"name": "srv2", "rpc_url": "https://srv2.example.test:9089/rpc"}],
        [{"name": "srv1"}, {"name": "srv2", "rpc_url": "https://srv2.example.test:9089/rpc"}],
    ]
    audit = MagicMock()
    worker = MagicMock()
    job = SimpleNamespace(
        job_id="job-1",
        payload={
            "setup_code": "BGL-code",
            "node_name": "srv2",
            "api_url": "https://srv2.example.test/beagle-api/api/v1",
            "advertise_host": "srv2.example.test",
            "rpc_url": "https://srv2.example.test:9089/rpc",
            "ssh_port": 22,
            "timeout": 5.0,
            "token_ttl_seconds": 900,
        },
        owner="admin",
    )

    handler = make_cluster_auto_join_handler(membership, audit)
    result = handler(job, worker)

    assert result["ok"] is True
    assert result["target"]["cluster_id"] == "cluster-1"
    assert result["target"]["member"]["name"] == "srv2"
    messages = [call.args[2] for call in worker.update_progress.call_args_list]
    assert any("Preflight" in message for message in messages)
    assert any("Token" in message for message in messages)
    assert any("Remote-Join" in message for message in messages)
    assert any("RPC-Check" in message for message in messages)
    assert any("Inventory-Refresh" in message for message in messages)
    assert any("Finale Validierung" in message for message in messages)
    assert messages[-1].startswith("Abgeschlossen")
    audit.assert_called_once()


def test_cluster_auto_join_handler_raises_on_failed_preflight():
    membership = MagicMock()
    membership.preflight_add_server.return_value = {"ok": False, "checks": [{"name": "dns", "status": "fail"}]}
    audit = MagicMock()
    worker = MagicMock()
    job = SimpleNamespace(
        job_id="job-2",
        payload={
            "setup_code": "BGL-code",
            "node_name": "srv2",
            "api_url": "https://srv2.example.test/beagle-api/api/v1",
            "advertise_host": "srv2.example.test",
        },
        owner="admin",
    )

    handler = make_cluster_auto_join_handler(membership, audit)

    try:
        handler(job, worker)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "Preflight" in str(exc)

    assert worker.update_progress.call_args_list[-1].args[2].startswith("Fehler:")
    audit.assert_called_once()


def test_cluster_maintenance_drain_handler_reports_progress_and_returns_result():
    maintenance = MagicMock()
    maintenance.preview_drain_node.return_value = {
        "node_name": "srv1",
        "actions": [
            {"vmid": 101, "handled": True, "result": "live_migration"},
            {"vmid": 102, "handled": False, "result": "skipped"},
        ],
    }
    maintenance.drain_node.return_value = {
        "node_name": "srv1",
        "handled_vm_count": 1,
        "actions": [{"vmid": 101, "handled": True, "result": "live_migration"}],
    }
    audit = MagicMock()
    worker = MagicMock()
    job = SimpleNamespace(job_id="job-3", payload={"node_name": "srv1"}, owner="admin")

    handler = make_cluster_maintenance_drain_handler(maintenance, audit)
    result = handler(job, worker)

    assert result["ok"] is True
    assert result["handled_vm_count"] == 1
    assert any("Preflight" in call.args[2] for call in worker.update_progress.call_args_list)
    assert any("Analyse" in call.args[2] for call in worker.update_progress.call_args_list)
    assert worker.update_progress.call_args_list[-1].args[2].startswith("Abgeschlossen")
    maintenance.preview_drain_node.assert_called_once_with(node_name="srv1")
    maintenance.drain_node.assert_called_once_with(node_name="srv1", requester_identity="admin")
    audit.assert_called_once()
