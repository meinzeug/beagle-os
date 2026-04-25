"""Tests for Energy Service + CO₂ + CSRD (GoEnterprise Plan 09)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from energy_service import EnergyService, CarbonConfig, EnergySample


def make_svc(tmp_path: Path) -> EnergyService:
    return EnergyService(
        state_dir=tmp_path,
        config_file=tmp_path / "carbon.json",
        utcnow=lambda: "2026-04-25T12:00:00Z",
    )


def test_record_node_power(tmp_path):
    svc = make_svc(tmp_path)
    svc.record_node_power("node-1", node_power_w=300.0)
    # File should be written
    shard = tmp_path / "node-1_2026-04-25.jsonl"
    assert shard.exists()


def test_compute_energy_kwh_basic(tmp_path):
    """60 samples at 100W with 60s intervals (1/60 h each) = 100 Wh = 0.1 kWh."""
    svc = make_svc(tmp_path)
    import dataclasses, json
    shard = tmp_path / "node-1_2026-04-25.jsonl"
    for i in range(60):
        sample = EnergySample(
            timestamp=f"2026-04-25T12:{i:02d}:00Z",
            node_id="node-1",
            node_power_w=100.0,
            vm_allocations={},
        )
        with shard.open("a") as f:
            f.write(json.dumps(dataclasses.asdict(sample)) + "\n")
    kwh = svc.compute_energy_kwh("node-1", month="2026-04")
    # 60 samples * 100W * (1/60 h) = 100 Wh = 0.1 kWh
    assert abs(kwh - 0.1) < 0.01


def test_compute_co2_grams(tmp_path):
    svc = make_svc(tmp_path)
    # 1 kWh * 400 g/kWh = 400g
    co2 = svc.compute_co2(kwh=1.0)
    assert abs(co2 - 400.0) < 1.0


def test_co2_custom_carbon_intensity(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_carbon_config(CarbonConfig(co2_grams_per_kwh=200.0))
    co2 = svc.compute_co2(kwh=1.0)
    assert abs(co2 - 200.0) < 1.0


def test_generate_csrd_report_structure(tmp_path):
    svc = make_svc(tmp_path)
    # Inject shard with known power samples in Q2 2026
    import json, dataclasses
    shard = tmp_path / "node-1_2026-04-25.jsonl"
    for h in range(60):
        sample = EnergySample(
            timestamp=f"2026-04-25T12:{h % 60:02d}:00Z",
            node_id="node-1",
            node_power_w=200.0,
            vm_allocations={},
        )
        with shard.open("a") as f:
            f.write(json.dumps(dataclasses.asdict(sample)) + "\n")
    report = svc.generate_csrd_report(["node-1"], year=2026, quarter=2)
    assert "total_kwh" in report
    assert "total_co2_kg" in report
    assert "breakdown" in report
    assert report["total_kwh"] > 0


def test_vm_share_attribution(tmp_path):
    """VM with 50% cpu_share should get ~50% of node energy."""
    import json, dataclasses
    svc = make_svc(tmp_path)
    # Inject 60 samples at 200W with 50% for vm-100
    shard = tmp_path / "node-1_2026-04-25.jsonl"
    for i in range(60):
        sample = EnergySample(
            timestamp=f"2026-04-25T12:{i:02d}:00Z",
            node_id="node-1",
            node_power_w=200.0,
            vm_allocations={"vm-100": 0.5},
        )
        with shard.open("a") as f:
            f.write(json.dumps(dataclasses.asdict(sample)) + "\n")
    kwh = svc.compute_energy_kwh("node-1", month="2026-04", vm_id="vm-100")
    # 60 samples * 200W * 50% * (1/60 h) = 100 Wh = 0.1 kWh
    assert abs(kwh - 0.1) < 0.01


def test_carbon_config_default(tmp_path):
    svc = make_svc(tmp_path)
    cfg = svc.get_carbon_config()
    assert cfg.co2_grams_per_kwh == 400.0
    assert cfg.electricity_price_per_kwh == 0.30
