"""Tests for HealthAggregatorService.

GoAdvanced Plan 08 Schritt 5.
"""
from __future__ import annotations

import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "beagle-host", "services"))

from health_aggregator import HealthAggregatorService  # noqa: E402


def test_no_checks_is_healthy():
    agg = HealthAggregatorService()
    result = agg.run()
    assert result == {"status": "healthy", "components": {}}


def test_all_healthy():
    agg = HealthAggregatorService()
    agg.register("a", lambda: {"status": "healthy"})
    agg.register("b", lambda: {"status": "healthy", "latency_ms": 5})
    result = agg.run()
    assert result["status"] == "healthy"
    assert result["components"]["a"]["status"] == "healthy"
    assert result["components"]["b"]["latency_ms"] == 5


def test_one_degraded_yields_degraded():
    agg = HealthAggregatorService()
    agg.register("a", lambda: {"status": "healthy"})
    agg.register("b", lambda: {"status": "degraded", "error": "slow"})
    result = agg.run()
    assert result["status"] == "degraded"
    assert result["components"]["b"]["error"] == "slow"


def test_one_unhealthy_yields_unhealthy():
    agg = HealthAggregatorService()
    agg.register("a", lambda: {"status": "healthy"})
    agg.register("b", lambda: {"status": "degraded"})
    agg.register("c", lambda: {"status": "unhealthy", "error": "down"})
    result = agg.run()
    assert result["status"] == "unhealthy"
    assert result["components"]["c"]["status"] == "unhealthy"


def test_check_raising_marks_unhealthy():
    agg = HealthAggregatorService()

    def boom():
        raise RuntimeError("nope")

    agg.register("a", boom)
    result = agg.run()
    assert result["status"] == "unhealthy"
    assert "nope" in result["components"]["a"]["error"]


def test_check_timeout_marks_unhealthy():
    agg = HealthAggregatorService(check_timeout_seconds=0.05)

    def slow():
        time.sleep(0.5)
        return {"status": "healthy"}

    agg.register("slow", slow)
    t0 = time.time()
    result = agg.run()
    elapsed = time.time() - t0
    assert elapsed < 0.4  # didn't wait for the slow check to finish
    assert result["components"]["slow"]["status"] == "unhealthy"
    assert "timed out" in result["components"]["slow"]["error"]


def test_invalid_status_treated_as_unhealthy():
    agg = HealthAggregatorService()
    agg.register("a", lambda: {"status": "weird"})
    result = agg.run()
    assert result["components"]["a"]["status"] == "unhealthy"


def test_non_dict_result_treated_as_unhealthy():
    agg = HealthAggregatorService()
    agg.register("a", lambda: "not a dict")  # type: ignore[arg-type]
    result = agg.run()
    assert result["components"]["a"]["status"] == "unhealthy"


def test_register_replaces_same_name():
    agg = HealthAggregatorService()
    agg.register("a", lambda: {"status": "unhealthy"})
    agg.register("a", lambda: {"status": "healthy"})
    result = agg.run()
    assert result["status"] == "healthy"
    assert agg.names() == ["a"]


def test_register_invalid_inputs():
    agg = HealthAggregatorService()
    with pytest.raises(ValueError):
        agg.register("", lambda: {"status": "healthy"})
    with pytest.raises(ValueError):
        agg.register("x", "not callable")  # type: ignore[arg-type]


def test_control_plane_check_reports_uptime():
    agg = HealthAggregatorService()
    agg.register("control_plane", agg.control_plane_check)
    result = agg.run()
    assert result["components"]["control_plane"]["status"] == "healthy"
    assert "uptime=" in result["components"]["control_plane"]["detail"]


def test_provider_check_no_providers_is_degraded():
    check = HealthAggregatorService.provider_check(lambda: [])
    result = check()
    assert result["status"] == "degraded"


def test_provider_check_with_providers_is_healthy():
    check = HealthAggregatorService.provider_check(lambda: ["beagle"])
    result = check()
    assert result["status"] == "healthy"
    assert "beagle" in result["detail"]


def test_provider_check_raising_is_unhealthy():
    def boom() -> list:
        raise RuntimeError("listing failed")

    check = HealthAggregatorService.provider_check(boom)
    result = check()
    assert result["status"] == "unhealthy"
    assert "listing failed" in result["error"]


def test_writable_path_check_missing(tmp_path):
    check = HealthAggregatorService.writable_path_check(tmp_path / "nope")
    result = check()
    assert result["status"] == "unhealthy"


def test_writable_path_check_ok(tmp_path):
    check = HealthAggregatorService.writable_path_check(tmp_path)
    result = check()
    assert result["status"] == "healthy"
    assert "latency_ms" in result


def test_latency_ms_auto_filled():
    agg = HealthAggregatorService()
    agg.register("a", lambda: {"status": "healthy"})
    result = agg.run()
    assert "latency_ms" in result["components"]["a"]
