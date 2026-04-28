"""Acceptance tests for GoEnterprise Plan 05 test obligations."""

import csv
import io
import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from cost_model_service import BudgetAlert, CostModel, CostModelService
from usage_tracking_service import UsageTrackingService


def make_cost_service(tmp_path: Path) -> CostModelService:
    svc = CostModelService(state_file=tmp_path / "cost-model.json")
    svc.set_cost_model(
        CostModel(
            cpu_hour_cost=0.01,
            ram_gb_hour_cost=0.001,
            gpu_hour_cost=0.50,
            storage_gb_month_cost=0.05,
            electricity_price_per_kwh=0.30,
        )
    )
    return svc


def make_usage_service(tmp_path: Path) -> UsageTrackingService:
    return UsageTrackingService(db_file=tmp_path / "usage.json")


def test_gpu_vm_cost_model_calculation_is_correct(tmp_path: Path) -> None:
    cost_svc = make_cost_service(tmp_path)

    rate = cost_svc.hourly_rate_per_vm(cpu_cores=2, ram_gb=8.0, gpu_slots=1)

    # 2*0.01 + 8*0.001 + 1*0.50 = 0.528 €/h
    assert rate == pytest.approx(0.528)


def test_five_alice_marketing_sessions_are_reported_with_correct_sum(tmp_path: Path) -> None:
    usage_svc = make_usage_service(tmp_path)
    cost_svc = make_cost_service(tmp_path)

    for i in range(5):
        usage_svc.record_session(
            session_id=f"alice-{i}",
            user_id="alice",
            department="marketing",
            pool_id="pool-desktop",
            vm_id=100,
            start_time=f"2026-04-0{i + 1}T08:00:00Z",
            end_time=f"2026-04-0{i + 1}T10:00:00Z",
            cpu_cores=2,
            ram_gb=4.0,
            gpu_slots=0,
        )

    report = cost_svc.generate_chargeback_report(usage_svc.get_usage(), "2026-04", department="marketing")

    assert len(report["entries"]) == 1
    entry = report["entries"][0]
    assert entry["department"] == "marketing"
    assert entry["user_id"] == "alice"
    assert entry["sessions"] == 5
    assert entry["cpu_hours"] == pytest.approx(20.0)
    # 5 sessions * 2h * (2*0.01 + 4*0.001)
    assert entry["total_cost"] == pytest.approx(0.24)
    assert report["total_cost"] == pytest.approx(0.24)


def test_chargeback_csv_contains_all_sessions_and_correctly_summed_costs(tmp_path: Path) -> None:
    usage_svc = make_usage_service(tmp_path)
    cost_svc = make_cost_service(tmp_path)

    usage_svc.record_session(
        session_id="s-1",
        user_id="alice",
        department="marketing",
        pool_id="p1",
        vm_id=100,
        start_time="2026-04-01T08:00:00Z",
        end_time="2026-04-01T10:00:00Z",
        cpu_cores=2,
        ram_gb=4.0,
    )
    usage_svc.record_session(
        session_id="s-2",
        user_id="bob",
        department="engineering",
        pool_id="p2",
        vm_id=101,
        start_time="2026-04-01T08:00:00Z",
        end_time="2026-04-01T09:00:00Z",
        cpu_cores=4,
        ram_gb=8.0,
        gpu_slots=1,
    )

    report = cost_svc.generate_chargeback_report(usage_svc.get_usage(), "2026-04")

    rows = list(csv.DictReader(io.StringIO(report["csv"])))
    assert len(rows) == 2
    csv_total = sum(float(row["total_cost"]) for row in rows)
    assert csv_total == pytest.approx(report["total_cost"])
    assert {row["department"] for row in rows} == {"marketing", "engineering"}


def test_budget_alert_is_triggered_at_85_percent(tmp_path: Path) -> None:
    cost_svc = make_cost_service(tmp_path)
    cost_svc.set_budget_alert(
        BudgetAlert(department="marketing", monthly_budget=1000.0, alert_at_percent=85)
    )

    triggered = cost_svc.check_budget_alerts({"marketing": 850.0})

    assert len(triggered) == 1
    assert triggered[0]["department"] == "marketing"
    assert triggered[0]["percent"] == pytest.approx(85.0)