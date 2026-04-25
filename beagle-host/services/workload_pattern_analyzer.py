"""Workload Pattern Analyzer — erkennt Peak-/Idle-Muster aus Metriken-History.

GoEnterprise Plan 04, Schritt 2
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkloadProfile:
    """Aggregiertes Auslastungsprofil einer VM oder eines Nodes."""
    entity_id: str          # vmid or node_id
    avg_cpu_pct: float
    avg_ram_pct: float
    peak_hours: list[int]   # hours-of-day (0-23) where avg CPU > peak_threshold
    idle_hours: list[int]   # hours-of-day where avg CPU < idle_threshold
    samples_analyzed: int
    # Raw hourly averages (index 0 = hour 0, ..., 23 = hour 23)
    hourly_avg_cpu: list[float] = field(default_factory=lambda: [0.0] * 24)


class WorkloadPatternAnalyzer:
    """
    Analyzes Metric samples (from MetricsCollector) to build WorkloadProfiles.

    Algorithm:
    1. Group samples by hour-of-day
    2. Compute per-hour average CPU
    3. Mark "peak" hours (avg > peak_threshold) and "idle" hours (avg < idle_threshold)

    Used by SmartScheduler (Plan 04, Schritt 3) for predictive placement.
    """

    DEFAULT_PEAK_THRESHOLD = 70.0   # %
    DEFAULT_IDLE_THRESHOLD = 15.0   # %

    def __init__(
        self,
        peak_threshold: float = DEFAULT_PEAK_THRESHOLD,
        idle_threshold: float = DEFAULT_IDLE_THRESHOLD,
    ) -> None:
        self._peak_threshold = peak_threshold
        self._idle_threshold = idle_threshold

    def analyze(self, entity_id: str, samples: list[Any]) -> WorkloadProfile:
        """
        Build a WorkloadProfile from a list of MetricSample-like objects.
        Accepts anything with .timestamp (ISO str) and .cpu_pct attributes.
        """
        if not samples:
            return WorkloadProfile(
                entity_id=entity_id,
                avg_cpu_pct=0.0,
                avg_ram_pct=0.0,
                peak_hours=[],
                idle_hours=[],
                samples_analyzed=0,
            )

        # Accumulate per-hour buckets
        hour_cpu: list[list[float]] = [[] for _ in range(24)]
        hour_ram: list[list[float]] = [[] for _ in range(24)]
        all_cpu: list[float] = []
        all_ram: list[float] = []

        for s in samples:
            ts = getattr(s, "timestamp", "")
            if len(ts) >= 13:
                try:
                    hour = int(ts[11:13])
                except ValueError:
                    hour = 0
            else:
                hour = 0
            cpu = getattr(s, "cpu_pct", 0.0)
            ram = getattr(s, "ram_pct", 0.0)
            hour_cpu[hour].append(cpu)
            hour_ram[hour].append(ram)
            all_cpu.append(cpu)
            all_ram.append(ram)

        hourly_avg_cpu = [
            (sum(bucket) / len(bucket)) if bucket else 0.0
            for bucket in hour_cpu
        ]
        hourly_avg_ram = [
            (sum(bucket) / len(bucket)) if bucket else 0.0
            for bucket in hour_ram
        ]

        peak_hours = [h for h, avg in enumerate(hourly_avg_cpu) if avg >= self._peak_threshold]
        idle_hours = [h for h, avg in enumerate(hourly_avg_cpu) if avg <= self._idle_threshold]

        return WorkloadProfile(
            entity_id=entity_id,
            avg_cpu_pct=sum(all_cpu) / len(all_cpu) if all_cpu else 0.0,
            avg_ram_pct=sum(all_ram) / len(all_ram) if all_ram else 0.0,
            peak_hours=peak_hours,
            idle_hours=idle_hours,
            samples_analyzed=len(samples),
            hourly_avg_cpu=hourly_avg_cpu,
        )

    def predict_load_at_hour(self, profile: WorkloadProfile, hour: int) -> float:
        """Return predicted CPU% for a given hour-of-day."""
        if not (0 <= hour <= 23):
            raise ValueError(f"hour must be 0-23, got {hour}")
        return profile.hourly_avg_cpu[hour]

    def is_peak_time(self, profile: WorkloadProfile, hour: int) -> bool:
        return hour in profile.peak_hours

    def is_idle_time(self, profile: WorkloadProfile, hour: int) -> bool:
        return hour in profile.idle_hours
