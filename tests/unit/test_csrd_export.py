"""Tests for CSRD Export (GoEnterprise Plan 09, Schritt 5)."""
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


def inject_month(tmp_path: Path, node_id: str, month: str, n: int, power_w: float):
    day = f"{month}-01"
    shard = tmp_path / f"{node_id}_{day}.jsonl"
    for i in range(n):
        s = EnergySample(
            timestamp=f"{month}-01T{i:02d}:00:00Z",
            node_id=node_id,
            node_power_w=power_w,
            vm_allocations={},
        )
        with shard.open("a") as f:
            f.write(json.dumps(dataclasses.asdict(s)) + "\n")


def test_csrd_report_has_required_fields(tmp_path):
    svc = make_svc(tmp_path)
    inject_month(tmp_path, "node-1", "2026-01", 60, 200.0)
    report = svc.generate_csrd_report(["node-1"], 2026, 1)
    assert "total_kwh" in report
    assert "total_co2_kg" in report
    assert "by_month" in report
    assert "period" in report


def test_csrd_report_q1_covers_three_months(tmp_path):
    svc = make_svc(tmp_path)
    report = svc.generate_csrd_report(["node-1"], 2026, 1)
    assert set(report["by_month"].keys()) == {"2026-01", "2026-02", "2026-03"}


def test_csrd_report_q2_covers_apr_to_jun(tmp_path):
    svc = make_svc(tmp_path)
    report = svc.generate_csrd_report(["node-1"], 2026, 2)
    assert set(report["by_month"].keys()) == {"2026-04", "2026-05", "2026-06"}


def test_csrd_report_total_kwh_aggregates(tmp_path):
    svc = make_svc(tmp_path)
    # inject 60 × 100W samples per month of Q1
    for month in ("2026-01", "2026-02", "2026-03"):
        inject_month(tmp_path, "node-1", month, 60, 100.0)
    report = svc.generate_csrd_report(["node-1"], 2026, 1)
    # Each month: 60 × 100W × (1/60h) = 100 Wh = 0.1 kWh
    assert abs(report["total_kwh"] - 0.3) < 0.05


def test_csrd_report_co2_kg_computed(tmp_path):
    svc = make_svc(tmp_path)
    svc.set_carbon_config(CarbonConfig(co2_grams_per_kwh=400.0))
    inject_month(tmp_path, "node-1", "2026-01", 60, 100.0)
    report = svc.generate_csrd_report(["node-1"], 2026, 1)
    # 0.1 kWh × 400 g/kWh = 40 g = 0.040 kg
    jan = report["by_month"]["2026-01"]
    assert abs(jan["co2_kg"] - 0.040) < 0.005


def test_csrd_report_invalid_quarter_raises(tmp_path):
    svc = make_svc(tmp_path)
    with pytest.raises(ValueError):
        svc.generate_csrd_report(["node-1"], 2026, 5)


def test_csrd_report_multiple_nodes(tmp_path):
    svc = make_svc(tmp_path)
    inject_month(tmp_path, "node-1", "2026-01", 60, 100.0)
    inject_month(tmp_path, "node-2", "2026-01", 60, 100.0)
    report = svc.generate_csrd_report(["node-1", "node-2"], 2026, 1)
    # Both nodes: 0.1 + 0.1 = 0.2 kWh in Jan
    jan = report["by_month"]["2026-01"]
    assert abs(jan["kwh"] - 0.2) < 0.02


def test_csrd_report_period_label(tmp_path):
    svc = make_svc(tmp_path)
    report = svc.generate_csrd_report(["node-1"], 2026, 3)
    assert "2026" in report["period"]
    assert "Q3" in report["period"]
