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
            "drilldown": [{
                "department": "eng",
                "users": [{
                    "user_id": "alice",
                    "session_count": 2,
                    "total_cost_eur": 1.7,
                    "sessions": [{
                        "session_id": "sess-1",
                        "pool_id": "pool-a",
                        "vm_id": 101,
                        "start_time": "2026-04-28T10:00:00Z",
                        "total_cost_eur": 0.85,
                    }],
                }],
            }],
            "top_vms": [{"vm_id": 101, "department": "eng", "user_id": "alice", "session_count": 2, "energy_cost_eur": 0.2, "total_cost_eur": 1.0}],
            "csv": "department,total_cost\neng,1.7\n",
            "total_cost_eur": 1.7,
            "total_energy_cost_eur": 0.2,
            "forecast_total_cost_eur": 2.8,
        },
        build_cost_model_payload=lambda: {
            "model": {"cpu_hour_cost": 0.01, "electricity_price_per_kwh": 0.3},
            "budgets": [{"department": "eng", "monthly_budget": 100.0, "alert_at_percent": 80}],
        },
        build_energy_csrd_payload=lambda year, quarter: {"year": year, "quarter": quarter, "total_kwh": 12.5},
        build_energy_config_payload=lambda: {
            "carbon_config": {"co2_grams_per_kwh": 400.0, "electricity_price_per_kwh": 0.3},
            "scheduler": {"green_scheduling_enabled": True, "prewarm_minutes_ahead": 15, "green_hours": [10, 11, 12]},
            "hourly_profile": {
                "co2_grams_per_kwh": [400.0] * 24,
                "electricity_price_per_kwh": [0.3] * 24,
            },
        },
        build_energy_green_hours_payload=lambda: {
            "co2_grams_per_kwh": 400.0,
            "electricity_price_per_kwh": 0.3,
            "configured_green_hours": [10, 11, 12],
            "current_hour": 11,
            "hourly": [{"hour": 11, "is_green_hour": True, "active_now": True, "estimated_co2_grams_per_kwh": 300.0, "estimated_electricity_price_per_kwh": 0.255}],
        },
        build_energy_nodes_payload=lambda: [{"node_id": "node-a", "current_power_w": 200.0, "max_power_w": 300.0, "month_kwh": 14.2}],
        build_energy_rankings_payload=lambda: {
            "highest_nodes": [{"node_id": "node-a", "status": "high", "month_kwh": 14.2, "energy_cost_eur": 4.26}],
            "lowest_nodes": [{"node_id": "node-b", "status": "low", "month_kwh": 2.1, "energy_cost_eur": 0.63}],
            "most_intensive_vms": [{"vm_id": 101, "department": "eng", "energy_kwh": 5.0, "energy_cost_eur": 1.5}],
            "most_efficient_vms": [{"vm_id": 202, "department": "ops", "energy_kwh": 0.5, "energy_cost_eur": 0.15}],
        },
        build_energy_trend_payload=lambda months: [{"month": "2026-04", "total_kwh": 14.2, "total_co2_kg": 5.68, "total_cost_eur": 4.26}],
        build_provisioning_catalog=lambda: {"items": []},
        build_scheduler_config_payload=lambda: {"green_scheduling_enabled": True, "prewarm_minutes_ahead": 15, "green_hours": [10, 11, 12]},
        build_scheduler_insights_payload=lambda: {
            "heatmap": [{"node_id": "node-a", "vm_count": 2, "cpu_pct": 81.0, "mem_pct": 66.0}],
            "recommendations": [{"vm_id": 101, "current_node": "node-a", "recommended_node": "node-b", "reason": "rebalance"}],
            "prewarm_candidates": [{"vm_id": 101, "name": "vm-101", "node_id": "node-a", "green_window_active": True}],
            "historical_trend": [{"node_id": "node-a", "series": [{"day": "2026-04-27", "avg_cpu_pct": 70.0}]}],
            "historical_heatmap": [{"node_id": "node-a", "days": [{"day": "2026-04-27", "hours": [0.0, 10.0, 20.0]}]}],
            "forecast_24h": [{"node_id": "node-a", "hourly": [{"hour": 12, "cpu_pct": 72.0}]}],
            "config": {"green_scheduling_enabled": True, "prewarm_minutes_ahead": 15, "green_hours": [10, 11, 12]},
            "saved_cpu_hours": 1.5,
            "saved_cpu_hours_by_pool": [{"pool_id": "pool-a", "candidate_count": 1, "saved_cpu_hours": 0.25}],
            "saved_cpu_hours_by_user": [{"user_id": "alice", "candidate_count": 1, "saved_cpu_hours": 0.25}],
            "green_window_active": True,
        },
        execute_cost_model_update=lambda payload: {"model": payload, "budgets": []},
        execute_scheduler_migration=lambda vmid, target_node, requester: {"vmid": vmid, "target_node": target_node, "requester": requester},
        execute_scheduler_rebalance=lambda requester: {"executed": [{"vmid": 101}], "requester": requester},
        execute_energy_config_update=lambda payload: {
            "carbon_config": payload,
            "scheduler": payload.get("scheduler", {}),
        },
        execute_scheduler_config_update=lambda payload: payload,
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
    assert payload["prewarm_candidates"][0]["name"] == "vm-101"
    assert payload["historical_trend"][0]["node_id"] == "node-a"
    assert payload["historical_heatmap"][0]["days"][0]["day"] == "2026-04-27"
    assert payload["forecast_24h"][0]["hourly"][0]["hour"] == 12
    assert payload["config"]["green_scheduling_enabled"] is True
    assert payload["saved_cpu_hours_by_pool"][0]["pool_id"] == "pool-a"
    assert payload["saved_cpu_hours_by_user"][0]["user_id"] == "alice"
    assert payload["green_window_active"] is True


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
    green_hours = service.route_get("/api/v1/energy/green-hours")
    rankings = service.route_get("/api/v1/energy/rankings")
    trend = service.route_get("/api/v1/energy/trend?months=3")
    config = service.route_get("/api/v1/energy/config")
    assert nodes is not None and green_hours is not None and rankings is not None and trend is not None
    assert nodes["payload"]["nodes"][0]["node_id"] == "node-a"
    assert green_hours["payload"]["green_hours"]["configured_green_hours"] == [10, 11, 12]
    assert rankings["payload"]["rankings"]["most_intensive_vms"][0]["vm_id"] == 101
    assert trend["payload"]["trend"][0]["month"] == "2026-04"
    assert config is not None
    assert config["payload"]["carbon_config"]["co2_grams_per_kwh"] == 400.0
    assert len(config["payload"]["hourly_profile"]["co2_grams_per_kwh"]) == 24


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


def test_cost_model_and_scheduler_config_routes_support_get_and_put() -> None:
    service = make_service()
    chargeback = service.route_get("/api/v1/costs/chargeback?month=2026-04")
    model = service.route_get("/api/v1/costs/model")
    scheduler = service.route_get("/api/v1/scheduler/config")
    model_put = service.route_put("/api/v1/costs/model", json_payload={"cpu_hour_cost": 0.02})
    scheduler_put = service.route_put("/api/v1/scheduler/config", json_payload={"green_scheduling_enabled": False})
    assert chargeback is not None and model is not None and scheduler is not None and model_put is not None and scheduler_put is not None
    assert model["payload"]["model"]["cpu_hour_cost"] == 0.01
    assert chargeback["payload"]["top_vms"][0]["vm_id"] == 101
    assert chargeback["payload"]["drilldown"][0]["users"][0]["sessions"][0]["session_id"] == "sess-1"
    assert scheduler["payload"]["config"]["prewarm_minutes_ahead"] == 15
    assert scheduler["payload"]["config"]["green_hours"] == [10, 11, 12]
    assert model_put["payload"]["model"]["cpu_hour_cost"] == 0.02
    assert scheduler_put["payload"]["config"]["green_scheduling_enabled"] is False
