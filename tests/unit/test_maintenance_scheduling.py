"""Tests for Maintenance Scheduling (GoEnterprise Plan 07, Schritt 4)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from fleet_telemetry_service import FleetTelemetryService, DeviceTelemetry


def make_svc(tmp_path: Path) -> FleetTelemetryService:
    return FleetTelemetryService(
        state_dir=tmp_path,
        utcnow=lambda: "2026-04-25T12:00:00Z",
    )


def test_schedule_maintenance_returns_record(tmp_path):
    svc = make_svc(tmp_path)
    rec = svc.schedule_maintenance(
        device_id="node-1",
        reason="Disk failure predicted",
        suggested_window="2026-05-01T02:00:00Z",
    )
    assert rec["device_id"] == "node-1"
    assert rec["reason"] == "Disk failure predicted"
    assert rec["suggested_window"] == "2026-05-01T02:00:00Z"
    assert rec["status"] == "pending"


def test_get_maintenance_schedule_empty(tmp_path):
    svc = make_svc(tmp_path)
    schedule = svc.get_maintenance_schedule()
    assert schedule == []


def test_get_maintenance_schedule_returns_entries(tmp_path):
    svc = make_svc(tmp_path)
    svc.schedule_maintenance("node-1", "Disk warning", "2026-05-01T02:00:00Z")
    svc.schedule_maintenance("node-2", "CPU temp", "2026-05-02T03:00:00Z")
    schedule = svc.get_maintenance_schedule()
    assert len(schedule) == 2


def test_maintenance_scheduled_at_recorded(tmp_path):
    svc = make_svc(tmp_path)
    rec = svc.schedule_maintenance("node-1", "RAM ECC errors", "2026-05-01T02:00:00Z")
    assert rec["scheduled_at"] == "2026-04-25T12:00:00Z"


def test_maintenance_persists(tmp_path):
    svc = make_svc(tmp_path)
    svc.schedule_maintenance("node-1", "Disk warning", "2026-05-01T02:00:00Z")
    svc2 = make_svc(tmp_path)
    schedule = svc2.get_maintenance_schedule()
    assert len(schedule) == 1
    assert schedule[0]["device_id"] == "node-1"


def test_multiple_entries_for_same_device(tmp_path):
    svc = make_svc(tmp_path)
    svc.schedule_maintenance("node-1", "First warning", "2026-05-01T02:00:00Z")
    svc.schedule_maintenance("node-1", "Second warning", "2026-05-03T02:00:00Z")
    schedule = svc.get_maintenance_schedule()
    node1_entries = [e for e in schedule if e["device_id"] == "node-1"]
    assert len(node1_entries) == 2


def test_maintenance_status_defaults_to_pending(tmp_path):
    svc = make_svc(tmp_path)
    rec = svc.schedule_maintenance("node-1", "Any reason", "2026-05-01T02:00:00Z")
    assert rec["status"] == "pending"
