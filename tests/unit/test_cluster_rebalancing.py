"""Acceptance tests for GoEnterprise Plan 04 rebalancing checklist."""

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from smart_scheduler import NodeCapacity, SmartSchedulerService
from workload_pattern_analyzer import WorkloadPatternAnalyzer, WorkloadProfile


def _make_14day_hourly_samples(peak_hours: list[int], idle_hours: list[int]) -> list[SimpleNamespace]:
    samples: list[SimpleNamespace] = []
    for day in range(14):
        for hour in range(24):
            if hour in peak_hours:
                cpu_pct = 90.0
            elif hour in idle_hours:
                cpu_pct = 5.0
            else:
                cpu_pct = 35.0
            samples.append(
                SimpleNamespace(
                    timestamp=f"2026-04-{day + 1:02d}T{hour:02d}:00:00Z",
                    cpu_pct=cpu_pct,
                    ram_pct=50.0,
                )
            )
    return samples


def test_pattern_analyzer_detects_peak_hours_after_14_days() -> None:
    analyzer = WorkloadPatternAnalyzer()
    samples = _make_14day_hourly_samples(peak_hours=[8, 9, 10], idle_hours=[1, 2, 3])

    profile = analyzer.analyze("vm-peak", samples)

    assert 8 in profile.peak_hours
    assert 9 in profile.peak_hours
    assert 10 in profile.peak_hours


def test_predictive_scheduler_prewarms_vm_10_minutes_before_peak() -> None:
    svc = SmartSchedulerService(list_nodes=lambda: [])
    profile = WorkloadProfile(
        entity_id="vm-morning-peak",
        avg_cpu_pct=70.0,
        avg_ram_pct=40.0,
        peak_hours=[10],
        idle_hours=[0, 1, 2, 3],
        samples_analyzed=336,
        hourly_avg_cpu=[25.0] * 24,
    )

    should_prewarm = svc.should_prewarm(
        profile,
        minutes_ahead=10,
        current_hour=9,
    )

    assert should_prewarm is True


def test_rebalancing_recommends_migration_from_node_above_85_percent() -> None:
    nodes = [
        NodeCapacity(
            node_id="node-overloaded",
            total_cpu_cores=32,
            total_ram_mib=65536,
            free_cpu_cores=2,
            free_ram_mib=4096,
            predicted_cpu_pct_4h=92.0,
        ),
        NodeCapacity(
            node_id="node-free",
            total_cpu_cores=32,
            total_ram_mib=65536,
            free_cpu_cores=24,
            free_ram_mib=48000,
            predicted_cpu_pct_4h=18.0,
        ),
    ]
    svc = SmartSchedulerService(list_nodes=lambda: nodes)
    assignments = [
        {"vmid": 2101, "node_id": "node-overloaded", "cpu_pct": 55.0},
        {"vmid": 2102, "node_id": "node-overloaded", "cpu_pct": 30.0},
    ]

    recommendations = svc.rebalance_cluster(assignments)

    assert len(recommendations) >= 1
    assert recommendations[0].from_node == "node-overloaded"
    assert recommendations[0].to_node == "node-free"
    assert recommendations[0].vm_id == 2101