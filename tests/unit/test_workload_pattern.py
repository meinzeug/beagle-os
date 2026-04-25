"""Tests for Workload Pattern Analyzer (GoEnterprise Plan 04, Schritt 2)."""
import sys
from pathlib import Path
import pytest
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from workload_pattern_analyzer import WorkloadPatternAnalyzer


def make_samples(peak_hours: list[int], idle_hours: list[int]) -> list:
    """Build a 14-day hourly sample list with given cpu_pct for peak/idle hours."""
    samples = []
    for day in range(14):
        for hour in range(24):
            ts = f"2026-04-{day + 1:02d}T{hour:02d}:00:00Z"
            if hour in peak_hours:
                cpu_pct = 80.0
            elif hour in idle_hours:
                cpu_pct = 5.0
            else:
                cpu_pct = 40.0
            samples.append(SimpleNamespace(timestamp=ts, cpu_pct=cpu_pct, ram_pct=50.0))
    return samples


def test_peak_hours_identified():
    samples = make_samples(peak_hours=[9, 10, 11, 14, 15], idle_hours=[2, 3, 4])
    analyzer = WorkloadPatternAnalyzer()
    profile = analyzer.analyze("vm-100", samples)
    assert 9 in profile.peak_hours
    assert 10 in profile.peak_hours
    assert 11 in profile.peak_hours


def test_idle_hours_identified():
    samples = make_samples(peak_hours=[9, 10], idle_hours=[2, 3, 4])
    analyzer = WorkloadPatternAnalyzer()
    profile = analyzer.analyze("vm-100", samples)
    assert 2 in profile.idle_hours
    assert 3 in profile.idle_hours


def test_hourly_avg_has_24_entries():
    samples = make_samples(peak_hours=[9], idle_hours=[3])
    analyzer = WorkloadPatternAnalyzer()
    profile = analyzer.analyze("vm-100", samples)
    assert len(profile.hourly_avg_cpu) == 24


def test_predict_load():
    samples = make_samples(peak_hours=[9], idle_hours=[3])
    analyzer = WorkloadPatternAnalyzer()
    profile = analyzer.analyze("vm-100", samples)
    assert analyzer.predict_load_at_hour(profile, 9) > 70.0
    assert analyzer.predict_load_at_hour(profile, 3) < 20.0


def test_empty_samples_returns_safe_defaults():
    analyzer = WorkloadPatternAnalyzer()
    profile = analyzer.analyze("vm-100", [])
    assert len(profile.hourly_avg_cpu) == 24
    assert profile.peak_hours == []
    assert profile.idle_hours == []


def test_entity_id_stored():
    analyzer = WorkloadPatternAnalyzer()
    profile = analyzer.analyze("srv-42", [])
    assert profile.entity_id == "srv-42"
