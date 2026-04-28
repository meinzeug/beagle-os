"""Acceptance tests for GoEnterprise Plan 07 test obligations."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from alert_service import AlertService
from fleet_telemetry_service import DeviceTelemetry, FleetTelemetryService


def _telemetry(
    *,
    device_id: str,
    timestamp: str,
    disk_reallocated: float = 0.0,
    disk_pending: float = 0.0,
    cpu_temp: float = 55.0,
    gpu_temp: float = 60.0,
    ecc_errors: int = 0,
    reboot_count_7d: int = 0,
) -> DeviceTelemetry:
    return DeviceTelemetry(
        device_id=device_id,
        timestamp=timestamp,
        device_type="node",
        disk_reallocated_sectors=disk_reallocated,
        disk_pending_sectors=disk_pending,
        cpu_temp_c=cpu_temp,
        gpu_temp_c=gpu_temp,
        ram_ecc_errors=ecc_errors,
        reboot_count_7d=reboot_count_7d,
        uptime_hours=720.0,
    )


def test_node_smart_telemetry_is_collected_and_stored(tmp_path: Path) -> None:
    svc = FleetTelemetryService(state_dir=tmp_path, utcnow=lambda: "2026-04-25T12:00:00Z")
    svc.ingest(
        _telemetry(
            device_id="node-smart-1",
            timestamp="2026-04-25T12:00:00Z",
            disk_reallocated=3,
            disk_pending=1,
        )
    )

    history = svc.get_history("node-smart-1", days=30)
    assert len(history) == 1
    assert history[0].disk_reallocated_sectors == pytest.approx(3)
    assert history[0].disk_pending_sectors == pytest.approx(1)


def test_disk_failure_trend_detected_within_7_days(tmp_path: Path) -> None:
    svc = FleetTelemetryService(state_dir=tmp_path, utcnow=lambda: "2026-04-25T12:00:00Z")
    # Keep values below threshold but with a positive trend that projects failure in ~1 day.
    for index in range(30):
        value = 7.0 + (index * 0.005)
        svc.ingest(
            _telemetry(
                device_id="node-trend-1",
                timestamp=f"2026-04-25T{index % 24:02d}:00:00Z",
                disk_reallocated=value,
            )
        )

    anomalies = svc.detect_anomalies("node-trend-1")
    disk_anomalies = [item for item in anomalies if item.metric == "disk_reallocated_sectors"]
    assert disk_anomalies
    assert 0 < disk_anomalies[0].estimated_failure_days <= 7


def test_disk_failure_predicted_alert_triggers_web_notification(tmp_path: Path) -> None:
    webhook_calls: list[dict] = []
    alerts = AlertService(
        state_file=tmp_path / "alerts.json",
        utcnow=lambda: "2026-04-25T12:00:00Z",
        webhook_fn=lambda payload: webhook_calls.append(payload),
    )
    alerts.ensure_default_rules()

    fired = alerts.check_anomalies(
        "node-alert-1",
        [SimpleNamespace(metric="disk_reallocated_sectors", current_value=12.0)],
    )

    assert len(fired) == 1
    assert fired[0].rule_id == "disk_failure_predicted"
    assert len(webhook_calls) == 1
    assert webhook_calls[0]["rule_id"] == "disk_failure_predicted"


def test_maintenance_window_is_created_and_vms_are_migrated(tmp_path: Path) -> None:
    migrated = []

    def migrate_stub(device_id: str) -> list[dict[str, str | int]]:
        actions = [
            {"vmid": 3101, "from": device_id, "to": "node-b"},
            {"vmid": 3102, "from": device_id, "to": "node-c"},
        ]
        migrated.extend(actions)
        return actions

    svc = FleetTelemetryService(
        state_dir=tmp_path,
        utcnow=lambda: "2026-04-25T12:00:00Z",
        migrate_vms_fn=migrate_stub,
    )
    entry = svc.schedule_maintenance(
        "node-maint-1",
        "disk_failure_predicted",
        "2026-05-04T02:00:00Z",
    )

    assert entry["device_id"] == "node-maint-1"
    assert entry["drain_status"] == "completed"
    assert entry["vm_migration_count"] == 2
    assert len(entry["vm_migrations"]) == 2
    assert len(migrated) == 2

    persisted = svc.get_maintenance_schedule()
    assert len(persisted) == 1
    assert persisted[0]["vm_migration_count"] == 2