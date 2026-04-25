"""Metrics Collector — sammelt VM + Node Auslastungsmetriken als Zeitreihe.

GoEnterprise Plan 04, Schritt 1
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class MetricSample:
    timestamp: str
    node_id: str
    vmid: int | None          # None for node-level samples
    cpu_pct: float
    ram_pct: float
    gpu_util_pct: float = 0.0
    gpu_vram_pct: float = 0.0


class MetricsCollector:
    """
    Lightweight time-series metrics collector.

    - Records samples to JSON shards per node per day
    - Retention: 90 days (old files pruned on collect())
    - Reads back data for workload analysis (Plan 04, Schritt 2)
    """

    RETENTION_DAYS = 90
    METRICS_DIR = Path("/var/lib/beagle/metrics")

    def __init__(
        self,
        metrics_dir: Path | None = None,
        utcnow: Callable[[], str] | None = None,
    ) -> None:
        self._dir = metrics_dir or self.METRICS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._utcnow = utcnow or self._default_utcnow

    def record(self, sample: MetricSample) -> None:
        """Append a sample to the day-shard file."""
        day = sample.timestamp[:10]  # "YYYY-MM-DD"
        shard = self._dir / f"{sample.node_id}_{day}.jsonl"
        with shard.open("a") as f:
            f.write(json.dumps(asdict(sample)) + "\n")

    def record_node(
        self,
        node_id: str,
        cpu_pct: float,
        ram_pct: float,
    ) -> MetricSample:
        s = MetricSample(
            timestamp=self._utcnow(),
            node_id=node_id,
            vmid=None,
            cpu_pct=cpu_pct,
            ram_pct=ram_pct,
        )
        self.record(s)
        return s

    def record_vm(
        self,
        node_id: str,
        vmid: int,
        cpu_pct: float,
        ram_pct: float,
        gpu_util_pct: float = 0.0,
    ) -> MetricSample:
        s = MetricSample(
            timestamp=self._utcnow(),
            node_id=node_id,
            vmid=vmid,
            cpu_pct=cpu_pct,
            ram_pct=ram_pct,
            gpu_util_pct=gpu_util_pct,
        )
        self.record(s)
        return s

    def read_samples(
        self,
        node_id: str,
        *,
        days: int = 14,
        vmid: int | None = None,
    ) -> list[MetricSample]:
        """Read back samples for a node (optionally filtered by vmid)."""
        import datetime
        cutoff = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        ).strftime("%Y-%m-%d")

        samples = []
        for shard in sorted(self._dir.glob(f"{node_id}_*.jsonl")):
            day_str = shard.stem.split("_", 1)[1]
            if day_str < cutoff:
                continue
            for line in shard.read_text().splitlines():
                if not line.strip():
                    continue
                d = json.loads(line)
                if vmid is not None and d.get("vmid") != vmid:
                    continue
                samples.append(MetricSample(**d))
        return samples

    def prune_old_shards(self) -> int:
        """Remove shards older than RETENTION_DAYS. Returns count deleted."""
        import datetime
        cutoff = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=self.RETENTION_DAYS)
        ).strftime("%Y-%m-%d")
        deleted = 0
        for shard in self._dir.glob("*.jsonl"):
            parts = shard.stem.rsplit("_", 1)
            if len(parts) == 2 and parts[1] < cutoff:
                shard.unlink()
                deleted += 1
        return deleted

    @staticmethod
    def _default_utcnow() -> str:
        import datetime
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
