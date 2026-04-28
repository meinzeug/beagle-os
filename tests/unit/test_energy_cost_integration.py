from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from cost_model_service import CostModel, CostModelService
from usage_tracking_service import UsageTrackingService


def test_chargeback_keeps_energy_cost_as_separate_component(tmp_path: Path) -> None:
    cost_service = CostModelService(state_file=tmp_path / "cost.json")
    usage_service = UsageTrackingService(db_file=tmp_path / "usage.json")
    cost_service.set_cost_model(
        CostModel(
            cpu_hour_cost=0.01,
            ram_gb_hour_cost=0.001,
            gpu_hour_cost=0.50,
            storage_gb_month_cost=0.05,
            electricity_price_per_kwh=0.30,
        )
    )

    usage_service.record_session(
        session_id="energy-session",
        user_id="alice",
        department="engineering",
        pool_id="pool-a",
        vm_id=201,
        start_time="2026-04-01T08:00:00Z",
        end_time="2026-04-01T10:00:00Z",
        cpu_cores=2,
        gpu_slots=1,
        energy_kwh=1.5,
        energy_cost=0.45,
    )

    report = cost_service.generate_chargeback_report(usage_service.get_usage(), "2026-04")
    assert len(report["entries"]) == 1
    entry = report["entries"][0]
    assert entry["energy_cost"] == 0.45
    # Includes RAM component: 2h * 4GB * 0.001 €/GBh = 0.008
    expected_total = (4.0 * 0.01) + (8.0 * 0.001) + (2.0 * 0.50) + 0.45
    assert round(entry["total_cost"], 4) == round(expected_total, 4)
