from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
import sys


SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from control_plane_read_surface import ControlPlaneReadSurfaceService


def make_service() -> ControlPlaneReadSurfaceService:
    return ControlPlaneReadSurfaceService(
        build_budget_alerts_payload=lambda month: [{"department": "eng", "current": 42.0, "budget": 50.0}],
        build_chargeback_payload=lambda month, department: {
            "month": month or "2026-04",
            "department": department,
            "departments": [{"department": "eng", "session_count": 2, "cpu_cost_eur": 1.2, "gpu_cost_eur": 0.5, "total_cost_eur": 1.7}],
            "entries": [],
            "csv": "department,total_cost\neng,1.7\n",
            "total_cost_eur": 1.7,
        },
        build_energy_csrd_payload=lambda year, quarter: {"year": year, "quarter": quarter, "total_kwh": 12.5},
        build_energy_nodes_payload=lambda: [{"node_id": "node-a", "current_power_w": 200.0, "max_power_w": 300.0, "month_kwh": 14.2}],
        build_energy_trend_payload=lambda months: [{"month": "2026-04", "total_kwh": 14.2, "total_co2_kg": 5.68, "total_cost_eur": 4.26}],
        build_provisioning_catalog=lambda: {"items": []},
        build_scheduler_insights_payload=lambda: {
            "heatmap": [{"node_id": "node-a", "vm_count": 2, "cpu_pct": 81.0, "mem_pct": 66.0}],
            "recommendations": [{"vm_id": 101, "current_node": "node-a", "recommended_node": "node-b", "reason": "rebalance"}],
        },
        execute_scheduler_migration=lambda vmid, target_node, requester: {"vmid": vmid, "target_node": target_node, "requester": requester},
        execute_scheduler_rebalance=lambda requester: {"executed": [{"vmid": 101}], "requester": requester},
        find_support_bundle_metadata=lambda _bundle_id: None,
        latest_ubuntu_beagle_state_for_vmid=lambda *args, **kwargs: None,
        list_endpoint_reports=lambda: [],
        list_policies=lambda: [],
        load_policy=lambda _name: None,
        service_name="beagle-control-plane",
        summarize_endpoint_report=lambda item: item,
        utcnow=lambda: "2026-04-28T12:00:00Z",
        version="8.0.0",
    )


def test_scheduler_insights_route_returns_payload() -> None:
    response = make_service().route_get("/api/v1/scheduler/insights")
    assert response is not None
    assert response["status"] == HTTPStatus.OK
    payload = response["payload"]
    assert payload["ok"] is True
    assert payload["heatmap"][0]["node_id"] == "node-a"
    assert payload["recommendations"][0]["recommended_node"] == "node-b"


def test_chargeback_csv_route_returns_bytes_download() -> None:
    response = make_service().route_get("/api/v1/costs/chargeback.csv?month=2026-04")
    assert response is not None
    assert response["kind"] == "bytes"
    assert response["status"] == HTTPStatus.OK
    assert response["content_type"] == "text/csv; charset=utf-8"
    assert b"department,total_cost" in response["body"]


def test_energy_csrd_requires_year_and_quarter() -> None:
    response = make_service().route_get("/api/v1/energy/csrd")
    assert response is not None
    assert response["status"] == HTTPStatus.BAD_REQUEST
    assert response["payload"]["ok"] is False


def test_energy_nodes_and_trend_routes_return_enveloped_payloads() -> None:
    service = make_service()
    nodes = service.route_get("/api/v1/energy/nodes")
    trend = service.route_get("/api/v1/energy/trend?months=3")
    assert nodes is not None and trend is not None
    assert nodes["payload"]["nodes"][0]["node_id"] == "node-a"
    assert trend["payload"]["trend"][0]["month"] == "2026-04"


def test_scheduler_post_routes_return_mutation_payloads() -> None:
    service = make_service()
    migrate = service.route_post(
        "/api/v1/scheduler/migrate",
        json_payload={"vm_id": 101, "target_node": "node-b"},
        requester="admin",
    )
    rebalance = service.route_post("/api/v1/scheduler/rebalance", json_payload={}, requester="admin")
    assert migrate is not None and rebalance is not None
    assert migrate["payload"]["migration"]["target_node"] == "node-b"
    assert migrate["payload"]["migration"]["requester"] == "admin"
    assert rebalance["payload"]["rebalance"]["executed"][0]["vmid"] == 101
