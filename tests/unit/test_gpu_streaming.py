"""Tests for GPU Inventory + GPU Metrics + GPU Pool Rebalancer (GoEnterprise Plan 10)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from gpu_streaming_service import (
    GpuDevice,
    GpuInventoryService,
    GpuMetricSample,
    GpuMetricsService,
    GpuPoolRebalancer,
)


# ------------------------------------------------------------------
# GPU Inventory
# ------------------------------------------------------------------

def make_inv_svc(tmp_path: Path) -> GpuInventoryService:
    return GpuInventoryService(
        state_file=tmp_path / "gpu-inventory.json",
        run_cmd=lambda cmd: "",  # no-op: no real GPU in CI
    )


def make_device(node_id: str = "node-1", pci: str = "0000:01:00.0", model: str = "NVIDIA GeForce RTX 3080") -> GpuDevice:
    from gpu_streaming_service import _classify_gpu
    return GpuDevice(
        gpu_id=f"{node_id}:{pci}",
        node_id=node_id,
        pci_addr=pci,
        model=model,
        vram_gb=10.0,
        gpu_class=_classify_gpu(model),
    )


def test_register_gpu(tmp_path):
    svc = make_inv_svc(tmp_path)
    dev = make_device()
    svc.register_gpu(dev)
    got = svc.get_gpu(dev.gpu_id)
    assert got is not None
    assert got.model == "NVIDIA GeForce RTX 3080"


def test_list_gpus(tmp_path):
    svc = make_inv_svc(tmp_path)
    svc.register_gpu(make_device("node-1", "0000:01:00.0", "NVIDIA GeForce RTX 3080"))
    svc.register_gpu(make_device("node-2", "0000:02:00.0", "NVIDIA GeForce RTX 3080"))
    gpus = svc.list_gpus()
    assert len(gpus) == 2


def test_list_gpus_by_node(tmp_path):
    svc = make_inv_svc(tmp_path)
    svc.register_gpu(make_device("node-1", "0000:01:00.0"))
    svc.register_gpu(make_device("node-2", "0000:01:00.0"))
    n1 = svc.list_gpus(node_id="node-1")
    assert len(n1) == 1
    assert n1[0].node_id == "node-1"


def test_assign_gpu(tmp_path):
    svc = make_inv_svc(tmp_path)
    dev = make_device()
    svc.register_gpu(dev)
    updated = svc.assign_gpu(dev.gpu_id, "vm-100", "passthrough")
    assert updated.current_assignment == "vm-100"
    assert updated.current_mode == "passthrough"


def test_release_gpu(tmp_path):
    svc = make_inv_svc(tmp_path)
    dev = make_device()
    svc.register_gpu(dev)
    svc.assign_gpu(dev.gpu_id, "vm-100", "passthrough")
    released = svc.release_gpu(dev.gpu_id)
    assert released.current_assignment == ""
    assert released.current_mode == "unassigned"


def test_free_only_filter(tmp_path):
    svc = make_inv_svc(tmp_path)
    d1 = make_device("n1", "0000:01:00.0")
    d2 = make_device("n1", "0000:02:00.0")
    svc.register_gpu(d1)
    svc.register_gpu(d2)
    svc.assign_gpu(d1.gpu_id, "vm-100", "passthrough")
    free = svc.list_gpus(free_only=True)
    assert len(free) == 1
    assert free[0].gpu_id == d2.gpu_id


def test_classify_gaming_gpu():
    from gpu_streaming_service import _classify_gpu
    assert _classify_gpu("NVIDIA GeForce RTX 3080") == "gaming"


def test_classify_compute_gpu():
    from gpu_streaming_service import _classify_gpu
    assert _classify_gpu("NVIDIA A100 SXM4") == "compute"


def test_classify_workstation_gpu():
    from gpu_streaming_service import _classify_gpu
    assert _classify_gpu("NVIDIA RTX A4000") == "workstation"


def test_persistence(tmp_path):
    svc = make_inv_svc(tmp_path)
    svc.register_gpu(make_device())
    svc2 = make_inv_svc(tmp_path)
    assert len(svc2.list_gpus()) == 1


# ------------------------------------------------------------------
# GPU Metrics
# ------------------------------------------------------------------

def make_metrics_svc(tmp_path: Path) -> GpuMetricsService:
    return GpuMetricsService(
        state_dir=tmp_path,
        utcnow=lambda: "2026-04-25T12:00:00Z",
    )


def make_sample(gpu_id: str = "node-1:0000:01:00.0", util_pct: float = 50.0, encoder: float = 30.0) -> GpuMetricSample:
    return GpuMetricSample(
        timestamp="2026-04-25T12:00:00Z",
        gpu_id=gpu_id,
        vm_id="vm-100",
        util_pct=util_pct,
        vram_used_mb=5000.0,
        temp_c=70.0,
        encoder_util_pct=encoder,
        power_w=200.0,
    )


def test_record_and_get_recent(tmp_path):
    svc = make_metrics_svc(tmp_path)
    svc.record(make_sample())
    samples = svc.get_recent("node-1:0000:01:00.0")
    assert len(samples) == 1


def test_avg_utilization(tmp_path):
    svc = make_metrics_svc(tmp_path)
    for u in [40.0, 60.0, 80.0]:
        svc.record(make_sample(util_pct=u))
    avg = svc.avg_utilization("node-1:0000:01:00.0")
    assert abs(avg - 60.0) < 1.0


def test_encoder_overload_true(tmp_path):
    svc = make_metrics_svc(tmp_path)
    svc.record(make_sample(encoder=95.0))
    assert svc.check_encoder_overload("node-1:0000:01:00.0") is True


def test_encoder_not_overloaded(tmp_path):
    svc = make_metrics_svc(tmp_path)
    svc.record(make_sample(encoder=50.0))
    assert svc.check_encoder_overload("node-1:0000:01:00.0") is False


def test_no_samples_returns_zero_avg(tmp_path):
    svc = make_metrics_svc(tmp_path)
    assert svc.avg_utilization("nonexistent-gpu") == 0.0


# ------------------------------------------------------------------
# GPU Pool Rebalancer
# ------------------------------------------------------------------

def test_rebalance_recommends_migration(tmp_path):
    inv = make_inv_svc(tmp_path / "inv")
    metrics = make_metrics_svc(tmp_path / "m")

    d1 = make_device("node-1", "0000:01:00.0")
    d2 = make_device("node-1", "0000:02:00.0")
    inv.register_gpu(d1)
    inv.register_gpu(d2)
    inv.assign_gpu(d1.gpu_id, "vm-100", "passthrough")

    # Record high utilization for d1 and low for d2
    s_high = GpuMetricSample("2026-04-25T12:00:00Z", d1.gpu_id, "vm-100", 95.0, 5000.0, 80.0, 85.0, 250.0)
    s_low = GpuMetricSample("2026-04-25T12:00:00Z", d2.gpu_id, "", 5.0, 100.0, 40.0, 2.0, 50.0)
    metrics.record(s_high)
    metrics.record(s_low)

    rebalancer = GpuPoolRebalancer(inv, metrics)
    recs = rebalancer.rebalance(node_id="node-1")
    assert len(recs) > 0
    assert recs[0].from_gpu_id == d1.gpu_id
    assert recs[0].to_gpu_id == d2.gpu_id


def test_no_rebalance_when_balanced(tmp_path):
    inv = make_inv_svc(tmp_path / "inv")
    metrics = make_metrics_svc(tmp_path / "m")
    d = make_device()
    inv.register_gpu(d)
    inv.assign_gpu(d.gpu_id, "vm-100", "passthrough")
    metrics.record(make_sample(util_pct=50.0))
    rebalancer = GpuPoolRebalancer(inv, metrics)
    recs = rebalancer.rebalance()
    assert len(recs) == 0
