"""Tests for GPU Pool Rebalancer (GoEnterprise Plan 10, Schritt 4)."""
import sys
import json
import dataclasses
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from gpu_streaming_service import (
    GpuDevice, GpuInventoryService, GpuMetricsService, GpuMetricSample, GpuPoolRebalancer
)


def make_inventory(tmp_path: Path) -> GpuInventoryService:
    return GpuInventoryService(
        state_file=tmp_path / "gpu-inv.json",
        run_cmd=lambda cmd: "",
    )


def make_metrics(tmp_path: Path) -> GpuMetricsService:
    return GpuMetricsService(
        state_dir=tmp_path / "gpu-metrics",
        utcnow=lambda: "2026-04-25T12:00:00Z",
    )


def set_utilization(metrics_dir: Path, gpu_id: str, util_pct: float):
    """Inject a recent sample with given utilization."""
    shard = metrics_dir / f"{gpu_id}_2026-04-25.jsonl"
    sample = GpuMetricSample(
        timestamp="2026-04-25T11:59:00Z",
        gpu_id=gpu_id,
        vm_id="vm100",
        util_pct=util_pct,
        vram_used_mb=4096.0,
        temp_c=65.0,
        encoder_util_pct=30.0,
        power_w=120.0,
    )
    shard.parent.mkdir(parents=True, exist_ok=True)
    with shard.open("a") as f:
        f.write(json.dumps(dataclasses.asdict(sample)) + "\n")


def test_no_rebalance_when_all_balanced(tmp_path):
    inv = make_inventory(tmp_path)
    met = make_metrics(tmp_path)
    gpu = GpuDevice(gpu_id="n:g0", node_id="n", pci_addr="0", model="RTX 3090",
                    vram_gb=24.0, gpu_class="gaming", current_assignment="vm100")
    inv.register_gpu(gpu)
    set_utilization(tmp_path / "gpu-metrics", "n:g0", 50.0)
    rebalancer = GpuPoolRebalancer(inv, met)
    recs = rebalancer.rebalance()
    assert recs == []


def test_rebalance_recommends_migration_on_overload(tmp_path):
    inv = make_inventory(tmp_path)
    met = make_metrics(tmp_path)

    # Overloaded GPU with assignment
    gpu_hot = GpuDevice(gpu_id="n:g0", node_id="n", pci_addr="0", model="RTX 3090",
                        vram_gb=24.0, gpu_class="gaming", current_assignment="vm100")
    # Free GPU with same class
    gpu_free = GpuDevice(gpu_id="n:g1", node_id="n", pci_addr="1", model="RTX 3090",
                         vram_gb=24.0, gpu_class="gaming", current_assignment="")

    inv.register_gpu(gpu_hot)
    inv.register_gpu(gpu_free)

    metrics_dir = tmp_path / "gpu-metrics"
    set_utilization(metrics_dir, "n:g0", 95.0)  # overloaded
    set_utilization(metrics_dir, "n:g1", 5.0)   # underloaded, free

    rebalancer = GpuPoolRebalancer(inv, met)
    recs = rebalancer.rebalance()
    assert len(recs) >= 1
    assert recs[0].vm_id == "vm100"
    assert recs[0].from_gpu_id == "n:g0"
    assert recs[0].to_gpu_id == "n:g1"


def test_rebalance_auto_execute_calls_migrate(tmp_path):
    inv = make_inventory(tmp_path)
    met = make_metrics(tmp_path)

    gpu_hot = GpuDevice(gpu_id="n:g0", node_id="n", pci_addr="0", model="RTX 3090",
                        vram_gb=24.0, gpu_class="gaming", current_assignment="vm100")
    gpu_free = GpuDevice(gpu_id="n:g1", node_id="n", pci_addr="1", model="RTX 3090",
                         vram_gb=24.0, gpu_class="gaming", current_assignment="")
    inv.register_gpu(gpu_hot)
    inv.register_gpu(gpu_free)

    metrics_dir = tmp_path / "gpu-metrics"
    set_utilization(metrics_dir, "n:g0", 95.0)
    set_utilization(metrics_dir, "n:g1", 5.0)

    migrated = []
    def fake_migrate(vm_id, target_gpu):
        migrated.append((vm_id, target_gpu))

    rebalancer = GpuPoolRebalancer(inv, met, migrate_vm=fake_migrate)
    rebalancer.rebalance(auto_execute=True)
    assert len(migrated) >= 1
    assert migrated[0][0] == "vm100"


def test_no_migration_different_class(tmp_path):
    """Overloaded gaming GPU should not recommend migration to compute GPU."""
    inv = make_inventory(tmp_path)
    met = make_metrics(tmp_path)

    gpu_hot = GpuDevice(gpu_id="n:g0", node_id="n", pci_addr="0", model="RTX 3090",
                        vram_gb=24.0, gpu_class="gaming", current_assignment="vm100")
    gpu_compute = GpuDevice(gpu_id="n:g1", node_id="n", pci_addr="1", model="A100",
                             vram_gb=80.0, gpu_class="compute", current_assignment="")
    inv.register_gpu(gpu_hot)
    inv.register_gpu(gpu_compute)

    metrics_dir = tmp_path / "gpu-metrics"
    set_utilization(metrics_dir, "n:g0", 95.0)
    set_utilization(metrics_dir, "n:g1", 5.0)

    rebalancer = GpuPoolRebalancer(inv, met)
    recs = rebalancer.rebalance()
    assert recs == []
