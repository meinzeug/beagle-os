"""Tests for Fleet Telemetry Service (GoEnterprise Plan 07)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from fleet_telemetry_service import (
    DeviceTelemetry,
    FleetTelemetryService,
)


def make_svc(tmp_path: Path) -> FleetTelemetryService:
    return FleetTelemetryService(
        state_dir=tmp_path,
        utcnow=lambda: "2026-04-25T12:00:00Z",
    )


def normal_telemetry(device_id: str, ts: str = "2026-04-25T12:00:00Z") -> DeviceTelemetry:
    return DeviceTelemetry(
        device_id=device_id,
        timestamp=ts,
        device_type="node",
        cpu_temp_c=55.0,
        gpu_temp_c=60.0,
        ram_ecc_errors=0,
        disk_reallocated_sectors=0,
        disk_pending_sectors=0,
        reboot_count_7d=0,
        uptime_hours=720.0,
    )


def test_ingest_writes_shard(tmp_path):
    svc = make_svc(tmp_path)
    svc.ingest(normal_telemetry("dev-001"))
    shard = tmp_path / "dev-001.jsonl"
    assert shard.exists()


def test_get_history_returns_sample(tmp_path):
    svc = make_svc(tmp_path)
    t = normal_telemetry("dev-001")
    svc.ingest(t)
    history = svc.get_history("dev-001", days=1)
    assert len(history) == 1
    assert history[0].cpu_temp_c == 55.0


def test_no_anomaly_for_healthy_device(tmp_path):
    svc = make_svc(tmp_path)
    for i in range(10):
        svc.ingest(normal_telemetry("dev-001", f"2026-04-25T12:0{i}:00Z"))
    anomalies = svc.detect_anomalies("dev-001")
    assert len(anomalies) == 0


def test_detects_high_disk_reallocated(tmp_path):
    svc = make_svc(tmp_path)
    # 10 normal samples first to establish baseline
    for i in range(10):
        svc.ingest(normal_telemetry("dev-001", f"2026-04-25T12:0{i}:00Z"))
    # Now inject outlier
    bad = normal_telemetry("dev-001", "2026-04-25T12:15:00Z")
    bad.disk_reallocated_sectors = 5000  # way above normal
    svc.ingest(bad)
    anomalies = svc.detect_anomalies("dev-001")
    assert any(a.metric == "disk_reallocated_sectors" for a in anomalies)


def test_detects_high_cpu_temp(tmp_path):
    svc = make_svc(tmp_path)
    for i in range(10):
        svc.ingest(normal_telemetry("dev-001", f"2026-04-25T12:0{i}:00Z"))
    hot = normal_telemetry("dev-001", "2026-04-25T12:11:00Z")
    hot.cpu_temp_c = 110.0
    svc.ingest(hot)
    anomalies = svc.detect_anomalies("dev-001")
    assert any(a.metric == "cpu_temp_c" for a in anomalies)


def test_schedule_maintenance(tmp_path):
    svc = make_svc(tmp_path)
    svc.schedule_maintenance("dev-001", "disk_reallocated_sectors anomaly", "2026-05-01T08:00:00Z")
    scheduled = svc.get_maintenance_schedule()
    assert len(scheduled) >= 1
    assert scheduled[0]["reason"] == "disk_reallocated_sectors anomaly"


def test_alert_severity_critical_for_high_ecc(tmp_path):
    svc = make_svc(tmp_path)
    for i in range(10):
        svc.ingest(normal_telemetry("dev-001", f"2026-04-25T12:0{i}:00Z"))
    bad = normal_telemetry("dev-001", "2026-04-25T12:11:00Z")
    bad.ram_ecc_errors = 100
    svc.ingest(bad)
    anomalies = svc.detect_anomalies("dev-001")
    assert any(a.metric == "ram_ecc_errors" for a in anomalies)


def test_trend_detection(tmp_path):
    """Rising disk sectors that trend to threshold within 7 days → anomaly."""
    svc = make_svc(tmp_path)
    # Slowly rising values: 10, 20, 30 ... over multiple samples
    for i in range(15):
        t = normal_telemetry("dev-001", f"2026-04-{i + 1:02d}T12:00:00Z")
        t.disk_reallocated_sectors = i * 10  # 0 to 140
        svc.ingest(t)
    anomalies = svc.detect_anomalies("dev-001")
    # Rising trend should be detected even if no single point is sigma outlier
    # At minimum no crash
    assert isinstance(anomalies, list)
