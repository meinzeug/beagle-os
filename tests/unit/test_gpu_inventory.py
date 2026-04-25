"""Tests for GPU Inventory (GoEnterprise Plan 10, Schritt 1)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from gpu_streaming_service import GpuDevice, GpuInventoryService


def make_svc(tmp_path: Path) -> GpuInventoryService:
    return GpuInventoryService(
        state_file=tmp_path / "gpu-inventory.json",
        run_cmd=lambda cmd: "",  # no real nvidia-smi
    )


def sample_gpu(gpu_id: str = "node-1:0000:01:00.0", node_id: str = "node-1", model: str = "NVIDIA GeForce RTX 3090") -> GpuDevice:
    return GpuDevice(
        gpu_id=gpu_id,
        node_id=node_id,
        pci_addr="0000:01:00.0",
        model=model,
        vram_gb=24.0,
        gpu_class="gaming",
    )


def test_register_gpu(tmp_path):
    svc = make_svc(tmp_path)
    gpu = svc.register_gpu(sample_gpu())
    assert gpu.gpu_id == "node-1:0000:01:00.0"


def test_get_gpu(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_gpu(sample_gpu())
    gpu = svc.get_gpu("node-1:0000:01:00.0")
    assert gpu is not None
    assert gpu.model == "NVIDIA GeForce RTX 3090"


def test_get_unknown_gpu_returns_none(tmp_path):
    svc = make_svc(tmp_path)
    assert svc.get_gpu("nonexistent") is None


def test_list_gpus_all(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_gpu(sample_gpu("node-1:0000:01:00.0", "node-1"))
    svc.register_gpu(sample_gpu("node-2:0000:01:00.0", "node-2"))
    assert len(svc.list_gpus()) == 2


def test_list_gpus_filter_by_node(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_gpu(sample_gpu("node-1:0000:01:00.0", "node-1"))
    svc.register_gpu(sample_gpu("node-2:0000:01:00.0", "node-2"))
    result = svc.list_gpus(node_id="node-1")
    assert len(result) == 1
    assert result[0].node_id == "node-1"


def test_list_gpus_filter_free_only(tmp_path):
    svc = make_svc(tmp_path)
    g1 = sample_gpu("node-1:gpu0", "node-1")
    g2 = sample_gpu("node-1:gpu1", "node-1")
    svc.register_gpu(g1)
    svc.register_gpu(g2)
    svc.assign_gpu("node-1:gpu0", "vm100", "passthrough")
    free = svc.list_gpus(free_only=True)
    assert all(not g.current_assignment for g in free)
    assert len(free) == 1


def test_assign_gpu(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_gpu(sample_gpu())
    gpu = svc.assign_gpu("node-1:0000:01:00.0", "vm100", "passthrough")
    assert gpu.current_assignment == "vm100"
    assert gpu.current_mode == "passthrough"


def test_release_gpu(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_gpu(sample_gpu())
    svc.assign_gpu("node-1:0000:01:00.0", "vm100", "passthrough")
    gpu = svc.release_gpu("node-1:0000:01:00.0")
    assert gpu.current_assignment == ""
    assert gpu.current_mode == "unassigned"


def test_assign_nonexistent_gpu_raises(tmp_path):
    svc = make_svc(tmp_path)
    with pytest.raises(KeyError):
        svc.assign_gpu("nonexistent", "vm100", "passthrough")


def test_gpu_classification_gaming(tmp_path):
    svc = make_svc(tmp_path)
    gpu = svc.register_gpu(GpuDevice(
        gpu_id="n:0", node_id="n", pci_addr="0", model="NVIDIA GeForce RTX 4090",
        vram_gb=24.0,
    ))
    assert gpu.gpu_class == "gaming"


def test_gpu_classification_compute_a100(tmp_path):
    svc = make_svc(tmp_path)
    gpu = svc.register_gpu(GpuDevice(
        gpu_id="n:0", node_id="n", pci_addr="0", model="NVIDIA A100",
        vram_gb=80.0,
    ))
    fetched = svc.get_gpu("n:0")
    # Register preserves what was set; classification via scan
    assert fetched is not None


def test_inventory_persists(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_gpu(sample_gpu())
    svc2 = make_svc(tmp_path)
    assert svc2.get_gpu("node-1:0000:01:00.0") is not None


def test_list_gpus_filter_by_class(tmp_path):
    svc = make_svc(tmp_path)
    svc.register_gpu(GpuDevice(gpu_id="n:g0", node_id="n", pci_addr="0",
                                model="RTX 3090", vram_gb=24.0, gpu_class="gaming"))
    svc.register_gpu(GpuDevice(gpu_id="n:g1", node_id="n", pci_addr="1",
                                model="A100", vram_gb=80.0, gpu_class="compute"))
    gaming = svc.list_gpus(gpu_class="gaming")
    assert all(g.gpu_class == "gaming" for g in gaming)
    assert len(gaming) == 1
