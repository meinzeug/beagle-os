"""Tests for CO₂ / Carbon calculations (GoEnterprise Plan 09, Schritt 2)."""
import sys
import json
import dataclasses
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from energy_service import EnergyService, CarbonConfig, EnergySample


def make_svc(tmp_path: Path) -> EnergyService:
    return EnergyService(
        state_dir=tmp_path,
        config_file=tmp_path / "carbon.json",
        utcnow=lambda: "2026-04-25T12:00:00Z",
    )


def inject_samples(tmp_path: Path, node_id: str, n: int, power_w: float, month: str = "2026-04"):
    shard = tmp_path / f"{node_id}_{month}-25.jsonl"
    for i in range(n):
        s = EnergySample(
            timestamp=f"{month}-25T{i:02d}:00:00Z",
            node_id=node_id,
            node_power_w=power_w,
            vm_allocations={},
        )
        with shard.open("a") as f:
            f.write(json.dumps(dataclasses.asdict(s)) + "\n")


def test_co2_default_config(tmp_path):
    svc = make_svc(tmp_path)
    # 1 kWh × 400 g/kWh = 400 g
    assert svc.compute_co2(1.0) == pytest.approx(400.0)


def test_co2_custom_intensity(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_carbon_config(CarbonConfig(co2_grams_per_kwh=200.0))
    assert svc.compute_co2(1.0) == pytest.approx(200.0)


def test_co2_zero_for_zero_kwh(tmp_path):
    svc = make_svc(tmp_path)
    assert svc.compute_co2(0.0) == pytest.approx(0.0)


def test_co2_proportional(tmp_path):
    svc = make_svc(tmp_path)
    assert svc.compute_co2(2.0) == pytest.approx(svc.compute_co2(1.0) * 2)


def test_energy_cost_calculation(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_carbon_config(CarbonConfig(electricity_price_per_kwh=0.30))
    # 1 kWh × 0.30 €/kWh = 0.30 €
    assert svc.compute_energy_cost(1.0) == pytest.approx(0.30)


def test_energy_kwh_from_100w_60_samples(tmp_path):
    """60 × 100W × (1/60 h) = 100 Wh = 0.1 kWh."""
    svc = make_svc(tmp_path)
    inject_samples(tmp_path, "node-1", 60, 100.0)
    kwh = svc.compute_energy_kwh("node-1", month="2026-04")
    assert abs(kwh - 0.1) < 0.01


def test_energy_kwh_vm_allocation(tmp_path):
    """VM with 50% share of 200W node for 60 samples = 0.1 kWh for that VM."""
    svc = make_svc(tmp_path)
    shard = tmp_path / "node-2_2026-04-25.jsonl"
    for i in range(60):
        s = EnergySample(
            timestamp=f"2026-04-25T{i:02d}:00:00Z",
            node_id="node-2",
            node_power_w=200.0,
            vm_allocations={"vm100": 0.5},
        )
        with shard.open("a") as f:
            f.write(json.dumps(dataclasses.asdict(s)) + "\n")
    kwh = svc.compute_energy_kwh("node-2", month="2026-04", vm_id="vm100")
    assert abs(kwh - 0.1) < 0.01


def test_carbon_config_persists(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_carbon_config(CarbonConfig(co2_grams_per_kwh=350.0))
    svc2 = make_svc(tmp_path)
    cfg = svc2.get_carbon_config()
    assert cfg.co2_grams_per_kwh == pytest.approx(350.0)


def test_100w_1h_equals_400g_co2(tmp_path):
    """100W for 1 hour = 0.1 kWh × 400 g/kWh = 40g CO₂."""
    svc = make_svc(tmp_path)
    inject_samples(tmp_path, "node-3", 60, 100.0)
    kwh = svc.compute_energy_kwh("node-3", month="2026-04")
    co2 = svc.compute_co2(kwh)
    assert abs(co2 - 40.0) < 2.0
