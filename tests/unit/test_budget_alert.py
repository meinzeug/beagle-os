"""Tests for Budget Alert (GoEnterprise Plan 05, Schritt 4)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from cost_model_service import CostModelService, BudgetAlert


def make_svc(tmp_path: Path) -> CostModelService:
    return CostModelService(state_file=tmp_path / "cost.json")


def test_set_and_get_budget_alert(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_budget_alert(BudgetAlert(
        department="marketing",
        monthly_budget=1000.0,
        alert_at_percent=80,
    ))
    alert = svc.get_budget_alert("marketing")
    assert alert is not None
    assert alert.monthly_budget == 1000.0
    assert alert.alert_at_percent == 80


def test_no_alert_below_threshold(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_budget_alert(BudgetAlert(department="eng", monthly_budget=1000.0, alert_at_percent=80))
    # 79% → below threshold
    triggered = svc.check_budget_alerts({"eng": 790.0})
    assert triggered == []


def test_alert_fires_at_threshold(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_budget_alert(BudgetAlert(department="eng", monthly_budget=1000.0, alert_at_percent=80))
    # exactly 80%
    triggered = svc.check_budget_alerts({"eng": 800.0})
    assert len(triggered) == 1
    assert triggered[0]["department"] == "eng"
    assert triggered[0]["percent"] == pytest.approx(80.0)


def test_alert_fires_above_threshold(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_budget_alert(BudgetAlert(department="sales", monthly_budget=500.0, alert_at_percent=80))
    triggered = svc.check_budget_alerts({"sales": 450.0})  # 90%
    assert len(triggered) == 1
    assert triggered[0]["percent"] == pytest.approx(90.0)


def test_multiple_departments_partial_trigger(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_budget_alert(BudgetAlert(department="marketing", monthly_budget=1000.0, alert_at_percent=80))
    svc.set_budget_alert(BudgetAlert(department="engineering", monthly_budget=2000.0, alert_at_percent=80))
    # marketing at 85%, engineering at 50%
    triggered = svc.check_budget_alerts({"marketing": 850.0, "engineering": 1000.0})
    depts = [t["department"] for t in triggered]
    assert "marketing" in depts
    assert "engineering" not in depts


def test_no_alert_for_unknown_department(tmp_path):
    svc = make_svc(tmp_path)
    # No budget set for "unknown"
    triggered = svc.check_budget_alerts({"unknown": 9999.0})
    assert triggered == []


def test_budget_alert_persists(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_budget_alert(BudgetAlert(department="hr", monthly_budget=300.0))
    svc2 = make_svc(tmp_path)
    alert = svc2.get_budget_alert("hr")
    assert alert is not None
    assert alert.monthly_budget == 300.0


def test_budget_alert_update(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_budget_alert(BudgetAlert(department="it", monthly_budget=500.0))
    svc.set_budget_alert(BudgetAlert(department="it", monthly_budget=800.0))
    alert = svc.get_budget_alert("it")
    assert alert.monthly_budget == 800.0
