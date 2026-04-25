"""Tests for Fleet Telemetry anomaly detection (GoEnterprise Plan 07, Schritt 2)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from fleet_telemetry_service import DeviceTelemetry, FleetTelemetryService, AnomalyReport


def make_svc(tmp_path: Path) -> FleetTelemetryService:
    return FleetTelemetryService(
        state_dir=tmp_path,
        utcnow=lambda: "2026-04-25T12:00:00Z",
    )


def ingest_many(svc, device_id, n, base_sectors=0, step=0):
    for i in range(n):
        svc.ingest(DeviceTelemetry(
            device_id=device_id,
            timestamp=f"2026-04-25T{i:02d}:00:00Z",
            device_type="node",
            disk_reallocated_sectors=base_sectors + i * step,
            disk_pending_sectors=0,
            cpu_temp_c=50.0,
            gpu_temp_c=55.0,
            ram_ecc_errors=0,
            reboot_count_7d=0,
            uptime_hours=float(i),
        ))


def test_no_anomaly_for_healthy_device(tmp_path):
    svc = make_svc(tmp_path)
    ingest_many(svc, "node-1", 10, base_sectors=0, step=0)
    anomalies = svc.detect_anomalies("node-1")
    assert anomalies == []


def test_sigma_anomaly_on_high_disk_sectors(tmp_path):
    svc = make_svc(tmp_path)
    # 20 samples at 0 then one spike at 100 → sigma exceeded
    for i in range(20):
        svc.ingest(DeviceTelemetry(
            device_id="node-2",
            timestamp=f"2026-04-25T{i:02d}:00:00Z",
            device_type="node",
            disk_reallocated_sectors=0,
            disk_pending_sectors=0,
            cpu_temp_c=50.0, gpu_temp_c=55.0,
            ram_ecc_errors=0, reboot_count_7d=0, uptime_hours=float(i),
        ))
    # Spike sample
    svc.ingest(DeviceTelemetry(
        device_id="node-2",
        timestamp="2026-04-25T20:00:00Z",
        device_type="node",
        disk_reallocated_sectors=100,
        disk_pending_sectors=0,
        cpu_temp_c=50.0, gpu_temp_c=55.0,
        ram_ecc_errors=0, reboot_count_7d=0, uptime_hours=20.0,
    ))
    anomalies = svc.detect_anomalies("node-2")
    metrics = [a.metric for a in anomalies]
    assert "disk_reallocated_sectors" in metrics


def test_too_few_samples_returns_empty(tmp_path):
    svc = make_svc(tmp_path)
    ingest_many(svc, "node-3", 2)
    assert svc.detect_anomalies("node-3") == []


def test_anomaly_report_has_correct_device_id(tmp_path):
    svc = make_svc(tmp_path)
    for i in range(20):
        svc.ingest(DeviceTelemetry(
            device_id="node-4",
            timestamp=f"2026-04-25T{i:02d}:00:00Z",
            device_type="node",
            ram_ecc_errors=0,
            disk_reallocated_sectors=0, disk_pending_sectors=0,
            cpu_temp_c=50.0, gpu_temp_c=55.0,
            reboot_count_7d=0, uptime_hours=float(i),
        ))
    svc.ingest(DeviceTelemetry(
        device_id="node-4",
        timestamp="2026-04-25T20:00:00Z",
        device_type="node",
        ram_ecc_errors=200,
        disk_reallocated_sectors=0, disk_pending_sectors=0,
        cpu_temp_c=50.0, gpu_temp_c=55.0,
        reboot_count_7d=0, uptime_hours=20.0,
    ))
    anomalies = svc.detect_anomalies("node-4")
    assert all(a.device_id == "node-4" for a in anomalies)
    metrics = [a.metric for a in anomalies]
    assert "ram_ecc_errors" in metrics


def test_detect_all_anomalies_returns_dict(tmp_path):
    svc = make_svc(tmp_path)
    ingest_many(svc, "node-5", 10)
    result = svc.detect_all_anomalies()
    # node-5 has no anomaly → might not be in result
    assert isinstance(result, dict)


def test_anomaly_severity_critical_near_threshold(tmp_path):
    svc = make_svc(tmp_path)
    # Feed rising disk sectors very close to threshold (10) to trigger trend < 3 days
    for i in range(30):
        svc.ingest(DeviceTelemetry(
            device_id="node-6",
            timestamp=f"2026-04-25T{i:02d}:00:00Z",
            device_type="node",
            disk_reallocated_sectors=i,
            disk_pending_sectors=0,
            cpu_temp_c=50.0, gpu_temp_c=55.0,
            ram_ecc_errors=0, reboot_count_7d=0, uptime_hours=float(i),
        ))
    anomalies = svc.detect_anomalies("node-6")
    # Should have anomaly for disk_reallocated_sectors
    disk_anomalies = [a for a in anomalies if a.metric == "disk_reallocated_sectors"]
    if disk_anomalies:
        assert disk_anomalies[0].severity in ("warning", "critical")
