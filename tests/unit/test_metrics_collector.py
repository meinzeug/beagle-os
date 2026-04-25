"""Tests for Metrics Collector (GoEnterprise Plan 04, Schritt 1)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from metrics_collector import MetricsCollector


def make_svc(tmp_path: Path) -> MetricsCollector:
    return MetricsCollector(
        metrics_dir=tmp_path,
        utcnow=lambda: "2026-04-25T12:00:00Z",
    )


def test_record_and_read_node_sample(tmp_path):
    svc = make_svc(tmp_path)
    svc.record_node("node-1", cpu_pct=45.0, ram_pct=60.0)
    samples = svc.read_samples("node-1", days=1)
    assert len(samples) == 1
    assert samples[0].cpu_pct == 45.0


def test_record_and_read_vm_sample(tmp_path):
    svc = make_svc(tmp_path)
    svc.record_vm("node-1", vmid=100, cpu_pct=30.0, ram_pct=40.0, gpu_util_pct=80.0)
    samples = svc.read_samples("node-1", days=1)
    assert any(s.vmid == 100 for s in samples)


def test_multiple_samples_appended(tmp_path):
    times = ["2026-04-25T12:00:00Z", "2026-04-25T12:01:00Z", "2026-04-25T12:02:00Z"]
    idx = [0]
    def tick():
        t = times[idx[0]]
        idx[0] = min(idx[0] + 1, len(times) - 1)
        return t

    svc = MetricsCollector(metrics_dir=tmp_path, utcnow=tick)
    svc.record_node("node-1", cpu_pct=10.0, ram_pct=20.0)
    svc.record_node("node-1", cpu_pct=20.0, ram_pct=25.0)
    samples = svc.read_samples("node-1", days=1)
    assert len(samples) == 2


def test_shard_file_created(tmp_path):
    svc = make_svc(tmp_path)
    svc.record_node("node-1", cpu_pct=50.0, ram_pct=70.0)
    shard_file = tmp_path / "node-1_2026-04-25.jsonl"
    assert shard_file.exists()


def test_prune_old_shards(tmp_path):
    import json
    # Create shard from 100 days ago
    old_shard = tmp_path / "node-1_2026-01-15.jsonl"
    old_shard.write_text(json.dumps({"ts": "2026-01-15T00:00:00Z", "cpu_pct": 50.0}) + "\n")
    svc = make_svc(tmp_path)
    svc.prune_old_shards()
    assert not old_shard.exists()


def test_prune_keeps_recent(tmp_path):
    import json
    recent_shard = tmp_path / "node-1_2026-04-24.jsonl"
    recent_shard.write_text(json.dumps({"ts": "2026-04-24T00:00:00Z", "cpu_pct": 40.0}) + "\n")
    svc = make_svc(tmp_path)
    svc.prune_old_shards()
    assert recent_shard.exists()


def test_read_multiple_days(tmp_path):
    import json
    from metrics_collector import MetricSample
    # Create two days of data
    for day in ["2026-04-24", "2026-04-25"]:
        shard = tmp_path / f"node-1_{day}.jsonl"
        sample = MetricSample(timestamp=f"{day}T12:00:00Z", node_id="node-1", vmid=None, cpu_pct=55.0, ram_pct=50.0)
        import dataclasses
        shard.write_text(json.dumps(dataclasses.asdict(sample)) + "\n")
    svc = make_svc(tmp_path)
    samples = svc.read_samples("node-1", days=2)
    assert len(samples) == 2
