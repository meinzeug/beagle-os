"""Tests for Cost Model Service (GoEnterprise Plan 05)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from cost_model_service import CostModel, CostModelService, BudgetAlert
from usage_tracking_service import UsageTrackingService


# ------------------------------------------------------------------
# CostModel tests
# ------------------------------------------------------------------

def make_model() -> CostModel:
    return CostModel(
        cpu_hour_cost=0.002,
        ram_gb_hour_cost=0.0005,
        gpu_hour_cost=0.10,
        storage_gb_month_cost=0.05,
        electricity_price_per_kwh=0.30,
    )


def make_svc(tmp_path: Path) -> CostModelService:
    return CostModelService(state_file=tmp_path / "cost-model.json")


def test_default_model(tmp_path):
    svc = make_svc(tmp_path)
    model = svc.get_cost_model()
    assert model.cpu_hour_cost > 0
    assert model.gpu_hour_cost > 0


def test_hourly_rate_calculation(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_cost_model(make_model())
    rate = svc.hourly_rate_per_vm(cpu_cores=4, ram_gb=8.0, gpu_slots=1)
    # 4 * 0.002 + 8 * 0.0005 + 1 * 0.10 = 0.008 + 0.004 + 0.10 = 0.112
    assert abs(rate - 0.112) < 0.001


def test_hourly_rate_no_gpu(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_cost_model(make_model())
    rate = svc.hourly_rate_per_vm(cpu_cores=2, ram_gb=4.0, gpu_slots=0)
    # 2 * 0.002 + 4 * 0.0005 = 0.004 + 0.002 = 0.006
    assert abs(rate - 0.006) < 0.001


def test_session_cost(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_cost_model(make_model())
    # 7200s = 2h session, 4 cpu, 8GB RAM, 1 GPU
    cost = svc.session_cost(duration_seconds=7200, cpu_cores=4, ram_gb=8.0, gpu_slots=1)
    assert abs(cost - 0.224) < 0.001


def test_chargeback_report(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_cost_model(make_model())
    records = [
        {
            "session_id": "s1",
            "user_id": "alice",
            "department": "engineering",
            "pool_id": "p1",
            "cpu_hours": 4.0,
            "gpu_hours": 2.0,
            "storage_gb": 100.0,
            "month": "2026-04",
            "energy_cost": 0.0,
        },
        {
            "session_id": "s2",
            "user_id": "bob",
            "department": "design",
            "pool_id": "p1",
            "cpu_hours": 2.0,
            "gpu_hours": 0.0,
            "storage_gb": 50.0,
            "month": "2026-04",
            "energy_cost": 0.0,
        },
    ]
    report = svc.generate_chargeback_report(records, "2026-04")
    assert report["total_cost"] > 0
    assert "csv" in report
    assert "alice" in report["csv"]
    assert len(report["entries"]) == 2


def test_budget_alert_triggered(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_budget_alert(BudgetAlert(department="engineering", monthly_budget=100.0))
    alerts = svc.check_budget_alerts({"engineering": 150.0, "design": 30.0})
    assert any(a["department"] == "engineering" for a in alerts)
    assert not any(a["department"] == "design" for a in alerts)


def test_budget_not_triggered_below_limit(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_budget_alert(BudgetAlert(department="engineering", monthly_budget=100.0))
    alerts = svc.check_budget_alerts({"engineering": 79.0})
    assert len(alerts) == 0


# ------------------------------------------------------------------
# UsageTracking tests
# ------------------------------------------------------------------

def make_usage_svc(tmp_path: Path) -> UsageTrackingService:
    return UsageTrackingService(db_file=tmp_path / "usage.json")


def test_record_session(tmp_path):
    svc = make_usage_svc(tmp_path)
    rec = svc.record_session(
        session_id="s1",
        user_id="alice",
        department="eng",
        pool_id="p1",
        vm_id=100,
        cpu_cores=4,
        ram_gb=8.0,
        gpu_slots=1,
        start_time="2026-04-25T13:00:00Z",
        end_time="2026-04-25T14:00:00Z",
    )
    assert rec.session_id == "s1"
    assert abs(rec.cpu_hours - 4.0) < 0.01
    assert abs(rec.gpu_hours - 1.0) < 0.01
    assert rec.month == "2026-04"


def test_get_usage_by_month(tmp_path):
    svc = make_usage_svc(tmp_path)
    svc.record_session(session_id="s1", user_id="alice", department="eng", pool_id="p1", vm_id=1, cpu_cores=4, ram_gb=8.0, gpu_slots=1, start_time="2026-04-25T13:00:00Z", end_time="2026-04-25T14:00:00Z")
    svc.record_session(session_id="s2", user_id="bob", department="eng", pool_id="p1", vm_id=2, cpu_cores=2, ram_gb=4.0, gpu_slots=0, start_time="2026-04-25T13:00:00Z", end_time="2026-04-25T13:30:00Z")
    records = svc.get_usage(month="2026-04")
    assert len(records) == 2


def test_get_usage_filter_user(tmp_path):
    svc = make_usage_svc(tmp_path)
    svc.record_session(session_id="s1", user_id="alice", department="eng", pool_id="p1", vm_id=1, cpu_cores=4, ram_gb=8.0, gpu_slots=1, start_time="2026-04-25T13:00:00Z", end_time="2026-04-25T14:00:00Z")
    svc.record_session(session_id="s2", user_id="bob", department="eng", pool_id="p1", vm_id=2, cpu_cores=2, ram_gb=4.0, gpu_slots=0, start_time="2026-04-25T13:00:00Z", end_time="2026-04-25T13:30:00Z")
    alice = svc.get_usage(month="2026-04", user_id="alice")
    assert len(alice) == 1
    assert alice[0]["user_id"] == "alice"


def test_get_usage_filter_department(tmp_path):
    svc = make_usage_svc(tmp_path)
    svc.record_session(session_id="s1", user_id="alice", department="eng", pool_id="p1", vm_id=1, cpu_cores=4, ram_gb=8.0, gpu_slots=1, start_time="2026-04-25T13:00:00Z", end_time="2026-04-25T14:00:00Z")
    svc.record_session(session_id="s2", user_id="charlie", department="finance", pool_id="p2", vm_id=2, cpu_cores=2, ram_gb=4.0, gpu_slots=0, start_time="2026-04-25T13:00:00Z", end_time="2026-04-25T13:30:00Z")
    fin = svc.get_usage(month="2026-04", department="finance")
    assert len(fin) == 1
    assert fin[0]["user_id"] == "charlie"
