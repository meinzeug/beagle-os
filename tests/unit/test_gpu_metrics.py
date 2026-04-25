"""Tests for GPU Metrics Service (GoEnterprise Plan 10, Schritt 3)."""
import sys
import json
import dataclasses
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from gpu_streaming_service import GpuMetricsService, GpuMetricSample


def make_svc(tmp_path: Path) -> GpuMetricsService:
    return GpuMetricsService(
        state_dir=tmp_path,
        utcnow=lambda: "2026-04-25T12:00:00Z",
    )


def sample(gpu_id: str = "node-1:gpu0", vm_id: str = "vm100",
           util_pct: float = 50.0, encoder_util_pct: float = 30.0,
           ts: str = "2026-04-25T12:00:00Z") -> GpuMetricSample:
    return GpuMetricSample(
        timestamp=ts,
        gpu_id=gpu_id,
        vm_id=vm_id,
        util_pct=util_pct,
        vram_used_mb=4096.0,
        temp_c=65.0,
        encoder_util_pct=encoder_util_pct,
        power_w=120.0,
    )


def test_record_creates_shard(tmp_path):
    svc = make_svc(tmp_path)
    svc.record(sample())
    shard = tmp_path / "node-1:gpu0_2026-04-25.jsonl"
    assert shard.exists()


def test_get_recent_returns_samples(tmp_path):
    svc = make_svc(tmp_path)
    # inject shard directly with recent timestamp
    shard = tmp_path / "node-1:gpu0_2026-04-25.jsonl"
    s = sample(ts="2026-04-25T11:59:00Z")
    shard.write_text(json.dumps(dataclasses.asdict(s)) + "\n")
    # get_recent looks at recent minutes from "now" (2026-04-25T12:00:00Z)
    result = svc.get_recent("node-1:gpu0", minutes=10)
    assert len(result) == 1


def test_avg_utilization(tmp_path):
    svc = make_svc(tmp_path)
    shard = tmp_path / "node-1:gpu0_2026-04-25.jsonl"
    for util in (40.0, 60.0, 80.0):
        s = sample(util_pct=util, ts="2026-04-25T11:59:00Z")
        with shard.open("a") as f:
            f.write(json.dumps(dataclasses.asdict(s)) + "\n")
    avg = svc.avg_utilization("node-1:gpu0", minutes=10)
    assert abs(avg - 60.0) < 1.0


def test_encoder_overload_not_triggered_below_threshold(tmp_path):
    svc = make_svc(tmp_path)
    shard = tmp_path / "node-1:gpu0_2026-04-25.jsonl"
    s = sample(encoder_util_pct=50.0, ts="2026-04-25T11:59:00Z")
    shard.write_text(json.dumps(dataclasses.asdict(s)) + "\n")
    assert not svc.check_encoder_overload("node-1:gpu0")


def test_encoder_overload_triggered_above_90(tmp_path):
    svc = make_svc(tmp_path)
    shard = tmp_path / "node-1:gpu0_2026-04-25.jsonl"
    s = sample(encoder_util_pct=95.0, ts="2026-04-25T11:59:00Z")
    shard.write_text(json.dumps(dataclasses.asdict(s)) + "\n")
    assert svc.check_encoder_overload("node-1:gpu0")


def test_get_recent_empty_for_unknown_gpu(tmp_path):
    svc = make_svc(tmp_path)
    assert svc.get_recent("nonexistent:gpu0") == []


def test_avg_utilization_zero_no_samples(tmp_path):
    svc = make_svc(tmp_path)
    assert svc.avg_utilization("nonexistent:gpu0") == pytest.approx(0.0)


def test_record_multiple_samples(tmp_path):
    svc = make_svc(tmp_path)
    for i in range(5):
        svc.record(sample(ts=f"2026-04-25T12:0{i}:00Z"))
    shard = tmp_path / "node-1:gpu0_2026-04-25.jsonl"
    lines = [l for l in shard.read_text().splitlines() if l.strip()]
    assert len(lines) == 5
