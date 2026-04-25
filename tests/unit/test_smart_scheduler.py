"""Tests for Smart Scheduler (GoEnterprise Plan 04, Schritt 3+4)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from smart_scheduler import (
    SmartSchedulerService,
    NodeCapacity,
    SmartPlacementResult,
    RebalanceRecommendation,
)
from workload_pattern_analyzer import WorkloadProfile


def make_nodes_free(specs: list[dict]) -> list[NodeCapacity]:
    nodes = []
    for s in specs:
        nodes.append(NodeCapacity(
            node_id=s["node_id"],
            total_cpu_cores=s.get("total_cpu", 32),
            total_ram_mib=s.get("total_ram", 65536),
            free_cpu_cores=s["free_cpu"],
            free_ram_mib=s["free_ram"],
            gpu_slots_free=s.get("gpu_free", 0),
            predicted_cpu_pct_4h=s.get("load_pct", 0.0),
        ))
    return nodes


def make_svc(nodes: list[NodeCapacity]) -> SmartSchedulerService:
    return SmartSchedulerService(list_nodes=lambda: nodes)


def test_picks_least_loaded_node():
    nodes = make_nodes_free([
        {"node_id": "node-1", "free_cpu": 24, "free_ram": 49152, "load_pct": 25.0},
        {"node_id": "node-2", "free_cpu": 4,  "free_ram": 5536,  "load_pct": 87.5},
        {"node_id": "node-3", "free_cpu": 30, "free_ram": 63488, "load_pct": 6.25},
    ])
    svc = make_svc(nodes)
    result = svc.pick_node(required_cpu_cores=4, required_ram_mib=4096, gpu_required=False)
    assert result.node_id == "node-3"


def test_gpu_required_filters_nodes():
    nodes = make_nodes_free([
        {"node_id": "node-1", "free_cpu": 24, "free_ram": 49152, "load_pct": 25.0, "gpu_free": 0},
        {"node_id": "node-2", "free_cpu": 4,  "free_ram": 5536,  "load_pct": 87.5, "gpu_free": 1},
    ])
    svc = make_svc(nodes)
    result = svc.pick_node(required_cpu_cores=4, required_ram_mib=4096, gpu_required=True)
    assert result.node_id == "node-2"


def test_returns_empty_node_if_no_capacity():
    nodes = make_nodes_free([
        {"node_id": "node-full", "free_cpu": 0, "free_ram": 0, "load_pct": 100.0}
    ])
    svc = make_svc(nodes)
    result = svc.pick_node(required_cpu_cores=4, required_ram_mib=4096, gpu_required=False)
    assert result.node_id == ""
    assert result.confidence == 0.0


def test_no_gpu_node_excluded_for_gpu_workload():
    nodes = make_nodes_free([
        {"node_id": "n1", "free_cpu": 32, "free_ram": 65536, "load_pct": 0.0, "gpu_free": 0},
    ])
    svc = make_svc(nodes)
    result = svc.pick_node(required_cpu_cores=4, required_ram_mib=4096, gpu_required=True)
    assert result.node_id == ""


def test_rebalance_identifies_overloaded_node():
    nodes = make_nodes_free([
        {"node_id": "node-1", "free_cpu": 24, "free_ram": 49152, "load_pct": 25.0},
        {"node_id": "node-2", "free_cpu": 4,  "free_ram": 5536,  "load_pct": 90.0},
        {"node_id": "node-3", "free_cpu": 30, "free_ram": 63488, "load_pct": 10.0},
    ])
    svc = make_svc(nodes)
    assignments = [{"vmid": 100, "node_id": "node-2", "cpu_pct": 40.0}]
    recs = svc.rebalance_cluster(assignments)
    assert any(r.from_node == "node-2" for r in recs)


def test_no_rebalance_if_balanced():
    nodes = make_nodes_free([
        {"node_id": "n1", "free_cpu": 16, "free_ram": 32768, "load_pct": 50.0},
        {"node_id": "n2", "free_cpu": 14, "free_ram": 30000, "load_pct": 45.0},
    ])
    svc = make_svc(nodes)
    recs = svc.rebalance_cluster([])
    assert len(recs) == 0


def test_should_prewarm_returns_true_all_peak():
    svc = make_svc([])
    profile = WorkloadProfile(
        entity_id="pool-1",
        avg_cpu_pct=80.0,
        avg_ram_pct=40.0,
        peak_hours=list(range(24)),  # every hour is peak
        idle_hours=[],
        samples_analyzed=100,
        hourly_avg_cpu=[80.0] * 24,
    )
    result = svc.should_prewarm(profile, minutes_ahead=30)
    assert result is True


def test_no_prewarm_with_empty_peak_hours():
    svc = make_svc([])
    profile = WorkloadProfile(
        entity_id="pool-1",
        avg_cpu_pct=5.0,
        avg_ram_pct=10.0,
        peak_hours=[],
        idle_hours=list(range(24)),
        samples_analyzed=100,
        hourly_avg_cpu=[5.0] * 24,
    )
    result = svc.should_prewarm(profile, minutes_ahead=30)
    assert result is False
