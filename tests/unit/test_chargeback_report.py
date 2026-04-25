"""Tests for Chargeback Report (GoEnterprise Plan 05, Schritt 3)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from cost_model_service import CostModelService, CostModel
from usage_tracking_service import UsageTrackingService


def make_cost_svc(tmp_path: Path) -> CostModelService:
    svc = CostModelService(state_file=tmp_path / "cost.json")
    svc.set_cost_model(CostModel(
        cpu_hour_cost=0.01,
        ram_gb_hour_cost=0.001,
        gpu_hour_cost=0.50,
        storage_gb_month_cost=0.05,
        electricity_price_per_kwh=0.30,
    ))
    return svc


def make_usage_svc(tmp_path: Path) -> UsageTrackingService:
    return UsageTrackingService(db_file=tmp_path / "usage.json")


def test_chargeback_empty_records(tmp_path):
    cost_svc = make_cost_svc(tmp_path)
    result = cost_svc.generate_chargeback_report([], "2026-04")
    assert result["total_cost"] == pytest.approx(0.0)
    assert result["entries"] == []


def test_chargeback_single_session(tmp_path):
    cost_svc = make_cost_svc(tmp_path)
    usage_svc = make_usage_svc(tmp_path)
    usage_svc.record_session(
        session_id="s-001",
        user_id="alice",
        department="marketing",
        pool_id="p1",
        vm_id=100,
        start_time="2026-04-01T08:00:00Z",
        end_time="2026-04-01T10:00:00Z",
        cpu_cores=2,
        ram_gb=4.0,
    )
    records = usage_svc.get_usage()
    result = cost_svc.generate_chargeback_report(records, "2026-04")
    assert result["total_cost"] > 0
    assert len(result["entries"]) == 1
    assert result["entries"][0]["department"] == "marketing"


def test_chargeback_multiple_departments(tmp_path):
    cost_svc = make_cost_svc(tmp_path)
    usage_svc = make_usage_svc(tmp_path)
    for dept in ("marketing", "engineering"):
        usage_svc.record_session(
            session_id=f"s-{dept}",
            user_id=f"user-{dept}",
            department=dept,
            pool_id="p1",
            vm_id=100,
            start_time="2026-04-01T08:00:00Z",
            end_time="2026-04-01T10:00:00Z",
            cpu_cores=4,
        )
    records = usage_svc.get_usage()
    result = cost_svc.generate_chargeback_report(records, "2026-04")
    depts = {e["department"] for e in result["entries"]}
    assert "marketing" in depts
    assert "engineering" in depts


def test_chargeback_filter_by_department(tmp_path):
    cost_svc = make_cost_svc(tmp_path)
    usage_svc = make_usage_svc(tmp_path)
    for dept in ("marketing", "engineering", "sales"):
        usage_svc.record_session(
            session_id=f"s-{dept}",
            user_id=f"user-{dept}",
            department=dept,
            pool_id="p1",
            vm_id=100,
            start_time="2026-04-01T08:00:00Z",
            end_time="2026-04-01T09:00:00Z",
        )
    records = usage_svc.get_usage()
    result = cost_svc.generate_chargeback_report(records, "2026-04", department="marketing")
    assert all(e["department"] == "marketing" for e in result["entries"])


def test_chargeback_csv_contains_header(tmp_path):
    cost_svc = make_cost_svc(tmp_path)
    usage_svc = make_usage_svc(tmp_path)
    usage_svc.record_session(
        session_id="s-001",
        user_id="alice",
        department="marketing",
        pool_id="p1",
        vm_id=100,
        start_time="2026-04-01T08:00:00Z",
        end_time="2026-04-01T09:00:00Z",
    )
    records = usage_svc.get_usage()
    result = cost_svc.generate_chargeback_report(records, "2026-04")
    assert "department" in result["csv"]
    assert "total_cost" in result["csv"]


def test_chargeback_wrong_month_excluded(tmp_path):
    cost_svc = make_cost_svc(tmp_path)
    usage_svc = make_usage_svc(tmp_path)
    usage_svc.record_session(
        session_id="s-may",
        user_id="alice",
        department="marketing",
        pool_id="p1",
        vm_id=100,
        start_time="2026-05-01T08:00:00Z",
        end_time="2026-05-01T09:00:00Z",
    )
    records = usage_svc.get_usage()
    result = cost_svc.generate_chargeback_report(records, "2026-04")
    assert result["entries"] == []
    assert result["total_cost"] == pytest.approx(0.0)


def test_chargeback_gpu_session_higher_cost(tmp_path):
    cost_svc = make_cost_svc(tmp_path)
    usage_svc = make_usage_svc(tmp_path)
    # CPU-only session
    usage_svc.record_session(
        session_id="s-cpu",
        user_id="alice",
        department="eng",
        pool_id="p1",
        vm_id=100,
        start_time="2026-04-01T08:00:00Z",
        end_time="2026-04-01T10:00:00Z",
        cpu_cores=2, gpu_slots=0,
    )
    # GPU session
    usage_svc.record_session(
        session_id="s-gpu",
        user_id="bob",
        department="eng",
        pool_id="p2",
        vm_id=101,
        start_time="2026-04-01T08:00:00Z",
        end_time="2026-04-01T10:00:00Z",
        cpu_cores=2, gpu_slots=1,
    )
    records = usage_svc.get_usage()
    result = cost_svc.generate_chargeback_report(records, "2026-04")
    by_user = {e["user_id"]: e["total_cost"] for e in result["entries"]}
    assert by_user["bob"] > by_user["alice"]
