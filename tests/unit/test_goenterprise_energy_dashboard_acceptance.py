"""Acceptance tests for GoEnterprise Plan 09 test obligations."""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

import energy_service as energy_service_module
from cost_model_service import CostModel, CostModelService
from energy_service import CarbonConfig, EnergySample, EnergyService
from usage_tracking_service import UsageTrackingService


def _make_energy_service(tmp_path: Path) -> EnergyService:
    return EnergyService(
        state_dir=tmp_path,
        config_file=tmp_path / "energy-config.json",
        utcnow=lambda: "2026-04-25T12:00:00Z",
    )


def _append_samples(tmp_path: Path, node_id: str, day: str, samples: list[EnergySample]) -> None:
    shard = tmp_path / f"{node_id}_{day}.jsonl"
    with shard.open("a") as handle:
        for sample in samples:
            handle.write(json.dumps(dataclasses.asdict(sample)) + "\n")


def test_rapl_power_read_and_vm_share_allocation_are_correct(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Simulate RAPL counter delta in 100ms: 6,000,000 uJ -> 60.0W
    class _FakeRaplDir:
        def __init__(self) -> None:
            self._values = ["1000000", "7000000"]

        def __truediv__(self, _name: str) -> "_FakeRaplDir":
            return self

        def read_text(self) -> str:
            return self._values.pop(0)

    fake_rapl = _FakeRaplDir()
    monkeypatch.setattr(energy_service_module, "Path", lambda _path: fake_rapl)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    rapl_power = EnergyService.read_rapl_power_w(0)
    assert rapl_power == pytest.approx(60.0)

    # Node power is split by CPU share: vm-a gets 1/4, vm-b gets 3/4.
    svc = _make_energy_service(tmp_path)
    svc.record_node_power("node-1", node_power_w=120.0, vm_cpu_shares={"vm-a": 1.0, "vm-b": 3.0})
    samples = svc.get_samples("node-1", days=365)
    assert len(samples) == 1
    assert samples[0].vm_allocations["vm-a"] == pytest.approx(0.25)
    assert samples[0].vm_allocations["vm-b"] == pytest.approx(0.75)


def test_co2_calculation_100w_for_1h_equals_40g_at_400g_per_kwh(tmp_path: Path) -> None:
    svc = _make_energy_service(tmp_path)
    svc.set_carbon_config(CarbonConfig(co2_grams_per_kwh=400.0, electricity_price_per_kwh=0.30))

    # 60 samples @ 100W with 60s interval = 0.1 kWh for the month.
    samples = [
        EnergySample(
            timestamp=f"2026-04-25T12:{minute:02d}:00Z",
            node_id="node-2",
            node_power_w=100.0,
            vm_allocations={},
        )
        for minute in range(60)
    ]
    _append_samples(tmp_path, "node-2", "2026-04-25", samples)

    kwh = svc.compute_energy_kwh("node-2", month="2026-04")
    co2_grams = svc.compute_co2(kwh)

    assert kwh == pytest.approx(0.1, abs=0.01)
    assert co2_grams == pytest.approx(40.0, abs=1.0)


def test_chargeback_contains_energy_cost_breakdown(tmp_path: Path) -> None:
    usage = UsageTrackingService(db_file=tmp_path / "usage.json")
    costs = CostModelService(state_file=tmp_path / "cost-model.json")
    costs.set_cost_model(
        CostModel(
            cpu_hour_cost=0.01,
            ram_gb_hour_cost=0.001,
            gpu_hour_cost=0.50,
            storage_gb_month_cost=0.05,
            electricity_price_per_kwh=0.30,
        )
    )

    usage.record_session(
        session_id="sess-energy",
        user_id="alice",
        department="marketing",
        pool_id="pool-a",
        vm_id=300,
        start_time="2026-04-01T10:00:00Z",
        end_time="2026-04-01T11:00:00Z",
        cpu_cores=2,
        ram_gb=4.0,
        gpu_slots=1,
        energy_kwh=1.5,
        energy_cost=0.45,
    )

    report = costs.generate_chargeback_report(usage.get_usage(), "2026-04")
    assert len(report["entries"]) == 1
    entry = report["entries"][0]
    assert entry["energy_cost"] == pytest.approx(0.45)
    assert entry["total_cost"] >= entry["energy_cost"]


def test_csrd_export_contains_correct_scope2_value_for_quarter(tmp_path: Path) -> None:
    svc = _make_energy_service(tmp_path)
    svc.set_carbon_config(CarbonConfig(co2_grams_per_kwh=400.0, electricity_price_per_kwh=0.30))

    # Q2: April has 0.1 kWh (100W for 60 minutes), May/June are 0.0.
    april_samples = [
        EnergySample(
            timestamp=f"2026-04-01T08:{minute:02d}:00Z",
            node_id="node-3",
            node_power_w=100.0,
            vm_allocations={},
        )
        for minute in range(60)
    ]
    _append_samples(tmp_path, "node-3", "2026-04-01", april_samples)

    report = svc.generate_csrd_report(["node-3"], year=2026, quarter=2)

    assert report["scope"] == "Scope-2 (location-based)"
    assert report["total_kwh"] == pytest.approx(0.1, abs=0.01)
    # 0.1 kWh * 400 g/kWh = 40 g = 0.04 kg
    assert report["total_co2_kg"] == pytest.approx(0.04, abs=0.005)