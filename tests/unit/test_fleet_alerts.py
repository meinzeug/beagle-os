"""Tests for Fleet Alerts (GoEnterprise Plan 07, Schritt 3)."""
import sys
from pathlib import Path
import pytest
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from alert_service import AlertService, AlertRule, AlertEvent


def make_svc(tmp_path: Path, **kwargs) -> AlertService:
    return AlertService(
        state_file=tmp_path / "alerts.json",
        utcnow=lambda: "2026-04-25T12:00:00Z",
        **kwargs,
    )


def make_rule(metric: str = "disk_reallocated_sectors", threshold: float = 10.0) -> AlertRule:
    return AlertRule(
        rule_id=f"rule-{metric}",
        name=f"Alert for {metric}",
        metric=metric,
        threshold=threshold,
        severity="warning",
        channels=["console"],
    )


def fake_anomaly(metric: str, value: float):
    return SimpleNamespace(metric=metric, current_value=value)


def test_add_and_get_rule(tmp_path):
    svc = make_svc(tmp_path)
    rule = svc.add_rule(make_rule())
    fetched = svc.get_rule(rule.rule_id)
    assert fetched is not None
    assert fetched.metric == "disk_reallocated_sectors"


def test_list_rules(tmp_path):
    svc = make_svc(tmp_path)
    svc.add_rule(make_rule("disk_reallocated_sectors"))
    svc.add_rule(make_rule("cpu_temp_c", threshold=90.0))
    assert len(svc.list_rules()) == 2


def test_delete_rule(tmp_path):
    svc = make_svc(tmp_path)
    svc.add_rule(make_rule())
    deleted = svc.delete_rule("rule-disk_reallocated_sectors")
    assert deleted
    assert svc.get_rule("rule-disk_reallocated_sectors") is None


def test_check_anomalies_fires_alert(tmp_path):
    svc = make_svc(tmp_path)
    svc.add_rule(make_rule("disk_reallocated_sectors", threshold=5.0))
    anomalies = [fake_anomaly("disk_reallocated_sectors", 20.0)]
    fired = svc.check_anomalies("node-1", anomalies)
    assert len(fired) == 1
    assert fired[0].device_id == "node-1"
    assert fired[0].metric == "disk_reallocated_sectors"


def test_check_anomalies_no_fire_below_threshold(tmp_path):
    svc = make_svc(tmp_path)
    svc.add_rule(make_rule("disk_reallocated_sectors", threshold=50.0))
    anomalies = [fake_anomaly("disk_reallocated_sectors", 10.0)]
    fired = svc.check_anomalies("node-1", anomalies)
    assert fired == []


def test_no_duplicate_alert_for_same_rule_and_device(tmp_path):
    svc = make_svc(tmp_path)
    svc.add_rule(make_rule("disk_reallocated_sectors", threshold=5.0))
    anomalies = [fake_anomaly("disk_reallocated_sectors", 20.0)]
    fired1 = svc.check_anomalies("node-1", anomalies)
    fired2 = svc.check_anomalies("node-1", anomalies)
    assert len(fired1) == 1
    assert len(fired2) == 0  # duplicate suppressed


def test_resolve_alert(tmp_path):
    svc = make_svc(tmp_path)
    svc.add_rule(make_rule("disk_reallocated_sectors", threshold=5.0))
    fired = svc.check_anomalies("node-1", [fake_anomaly("disk_reallocated_sectors", 20.0)])
    alert_id = fired[0].alert_id
    resolved = svc.resolve_alert(alert_id)
    assert resolved is not None
    assert resolved.resolved
    open_alerts = svc.get_open_alerts("node-1")
    assert all(a.alert_id != alert_id for a in open_alerts)


def test_get_open_alerts(tmp_path):
    svc = make_svc(tmp_path)
    svc.add_rule(make_rule("disk_reallocated_sectors", threshold=5.0))
    svc.check_anomalies("node-1", [fake_anomaly("disk_reallocated_sectors", 20.0)])
    open_alerts = svc.get_open_alerts()
    assert len(open_alerts) == 1


def test_fire_alert_manually(tmp_path):
    svc = make_svc(tmp_path)
    rule = svc.add_rule(make_rule("cpu_temp_c", threshold=90.0))
    event = svc.fire_alert(
        rule_id=rule.rule_id,
        device_id="node-2",
        metric="cpu_temp_c",
        current_value=95.0,
        message="CPU temperature critical",
    )
    assert event.device_id == "node-2"
    assert event.current_value == pytest.approx(95.0)


def test_webhook_called_on_alert(tmp_path):
    webhook_calls = []
    svc = make_svc(tmp_path, webhook_fn=lambda payload: webhook_calls.append(payload))
    svc.add_rule(AlertRule(
        rule_id="rule-disk",
        name="Disk alert",
        metric="disk_reallocated_sectors",
        threshold=5.0,
        severity="critical",
        channels=["webhook"],
    ))
    svc.check_anomalies("node-1", [fake_anomaly("disk_reallocated_sectors", 20.0)])
    assert len(webhook_calls) == 1
    assert webhook_calls[0]["device_id"] == "node-1"


def test_email_called_on_alert(tmp_path):
    email_calls = []
    svc = make_svc(tmp_path, email_fn=lambda subj, body: email_calls.append(subj))
    svc.add_rule(AlertRule(
        rule_id="rule-email",
        name="Email test",
        metric="ram_ecc_errors",
        threshold=10.0,
        severity="warning",
        channels=["email"],
    ))
    svc.check_anomalies("node-1", [fake_anomaly("ram_ecc_errors", 50.0)])
    assert len(email_calls) == 1


def test_disabled_rule_not_fired(tmp_path):
    svc = make_svc(tmp_path)
    svc.add_rule(AlertRule(
        rule_id="rule-disabled",
        name="Disabled rule",
        metric="disk_reallocated_sectors",
        threshold=5.0,
        severity="warning",
        channels=["console"],
        enabled=False,
    ))
    fired = svc.check_anomalies("node-1", [fake_anomaly("disk_reallocated_sectors", 20.0)])
    assert fired == []


def test_alert_persists(tmp_path):
    svc = make_svc(tmp_path)
    svc.add_rule(make_rule("disk_reallocated_sectors", threshold=5.0))
    svc.check_anomalies("node-1", [fake_anomaly("disk_reallocated_sectors", 20.0)])
    svc2 = make_svc(tmp_path)
    open_alerts = svc2.get_open_alerts()
    assert len(open_alerts) == 1
