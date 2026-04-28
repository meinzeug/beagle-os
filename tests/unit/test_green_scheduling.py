"""Targeted tests for green-hour scheduling behaviour."""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from smart_scheduler import NodeCapacity, SmartSchedulerService
from workload_pattern_analyzer import WorkloadProfile


def test_pick_node_applies_time_window_multiplier_for_green_hours() -> None:
    nodes = [
        NodeCapacity(
            node_id="fast-but-dirty",
            total_cpu_cores=32,
            total_ram_mib=65536,
            free_cpu_cores=28,
            free_ram_mib=60000,
            predicted_cpu_pct_4h=5.0,
            energy_price_per_kwh=0.55,
            carbon_intensity_g_per_kwh=700.0,
        ),
        NodeCapacity(
            node_id="slightly-busier-green",
            total_cpu_cores=32,
            total_ram_mib=65536,
            free_cpu_cores=24,
            free_ram_mib=52000,
            predicted_cpu_pct_4h=12.0,
            energy_price_per_kwh=0.20,
            carbon_intensity_g_per_kwh=90.0,
        ),
    ]
    svc = SmartSchedulerService(list_nodes=lambda: nodes)
    result = svc.pick_node(
        required_cpu_cores=4,
        required_ram_mib=4096,
        green_scheduling_enabled=True,
        preferred_hour=11,
        green_hours=[10, 11, 12],
    )
    assert result.node_id == "slightly-busier-green"
    assert "green_window=match" in result.reason


def test_should_prewarm_defers_non_green_target_when_green_peak_is_soon() -> None:
    profile = WorkloadProfile(
        entity_id="vm-101",
        avg_cpu_pct=75.0,
        avg_ram_pct=30.0,
        peak_hours=[9, 10],
        idle_hours=[],
        samples_analyzed=100,
        hourly_avg_cpu=[0.0] * 24,
    )
    svc = SmartSchedulerService(list_nodes=lambda: [])
    result = svc.should_prewarm(
        profile,
        minutes_ahead=0,
        green_scheduling_enabled=True,
        green_hours=[10],
        current_hour=9,
        lookahead_hours=2,
    )
    assert result is False


def test_should_prewarm_allows_non_green_target_when_no_green_peak_exists() -> None:
    profile = WorkloadProfile(
        entity_id="vm-102",
        avg_cpu_pct=65.0,
        avg_ram_pct=25.0,
        peak_hours=[9],
        idle_hours=[],
        samples_analyzed=100,
        hourly_avg_cpu=[0.0] * 24,
    )
    svc = SmartSchedulerService(list_nodes=lambda: [])
    result = svc.should_prewarm(
        profile,
        minutes_ahead=0,
        green_scheduling_enabled=True,
        green_hours=[10, 11],
        current_hour=9,
        lookahead_hours=2,
    )
    assert result is True
