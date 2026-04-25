"""Tests for prometheus_metrics service.

GoAdvanced Plan 08 Schritt 1.
"""
from __future__ import annotations

import os
import sys
import threading

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "beagle-host", "services"))

from prometheus_metrics import (  # noqa: E402
    Counter,
    DEFAULT_BUCKETS,
    Gauge,
    Histogram,
    PrometheusMetricsService,
)


@pytest.fixture
def registry() -> PrometheusMetricsService:
    return PrometheusMetricsService()


# ---------------------------------------------------------------------------
# Counter
# ---------------------------------------------------------------------------


def test_counter_unlabelled_inc(registry):
    c = registry.counter("test_counter", "doc")
    c.inc()
    c.inc(2)
    text = registry.render()
    assert "# TYPE test_counter counter" in text
    assert "test_counter 3" in text


def test_counter_labelled(registry):
    c = registry.counter("req_total", "doc", labelnames=("method",))
    c.labels(method="GET").inc()
    c.labels(method="POST").inc(5)
    c.labels(method="GET").inc()
    text = registry.render()
    assert 'req_total{method="GET"} 2' in text
    assert 'req_total{method="POST"} 5' in text


def test_counter_negative_rejected(registry):
    c = registry.counter("c", "d")
    with pytest.raises(ValueError):
        c.inc(-1)


def test_counter_unlabelled_zero_default(registry):
    registry.counter("never_used", "doc")
    text = registry.render()
    assert "never_used 0" in text


def test_counter_inc_on_labelled_without_labels_rejected(registry):
    c = registry.counter("x", "d", labelnames=("a",))
    with pytest.raises(ValueError):
        c.inc()


# ---------------------------------------------------------------------------
# Gauge
# ---------------------------------------------------------------------------


def test_gauge_set_inc_dec(registry):
    g = registry.gauge("vm_count", "doc")
    g.set(5)
    g.inc()
    g.set(2.5)
    text = registry.render()
    assert "# TYPE vm_count gauge" in text
    assert "vm_count 2.5" in text


def test_gauge_labelled(registry):
    g = registry.gauge("disk_bytes", "doc", labelnames=("pool",))
    g.labels(pool="ssd").set(1000)
    g.labels(pool="ssd").inc(500)
    g.labels(pool="hdd").set(8000)
    text = registry.render()
    assert 'disk_bytes{pool="ssd"} 1500' in text
    assert 'disk_bytes{pool="hdd"} 8000' in text


# ---------------------------------------------------------------------------
# Histogram
# ---------------------------------------------------------------------------


def test_histogram_observe(registry):
    h = registry.histogram("latency", "doc", buckets=(0.1, 0.5, 1.0))
    h.observe(0.05)
    h.observe(0.3)
    h.observe(2.0)
    text = registry.render()
    assert "# TYPE latency histogram" in text
    assert 'latency_bucket{le="0.1"} 1' in text
    assert 'latency_bucket{le="0.5"} 2' in text
    assert 'latency_bucket{le="1"} 2' in text
    assert 'latency_bucket{le="+Inf"} 3' in text
    assert "latency_sum 2.35" in text
    assert "latency_count 3" in text


def test_histogram_negative_rejected(registry):
    h = registry.histogram("h", "d")
    with pytest.raises(ValueError):
        h.observe(-0.1)


def test_histogram_labelled(registry):
    h = registry.histogram(
        "rt", "d", labelnames=("method",), buckets=(0.1, 1.0)
    )
    h.labels(method="GET").observe(0.05)
    h.labels(method="POST").observe(0.5)
    text = registry.render()
    assert 'rt_bucket{method="GET",le="0.1"} 1' in text
    assert 'rt_bucket{method="POST",le="0.1"} 0' in text
    assert 'rt_bucket{method="POST",le="1"} 1' in text


def test_histogram_default_buckets_appended_inf(registry):
    h = registry.histogram("h", "d")
    # Last upper bound is +Inf
    assert h._upper_bounds[-1] == float("inf")
    assert h._upper_bounds[: len(DEFAULT_BUCKETS)] == DEFAULT_BUCKETS


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_invalid_metric_name(registry):
    with pytest.raises(ValueError):
        registry.counter("", "d")
    with pytest.raises(ValueError):
        registry.counter("9foo", "d")
    with pytest.raises(ValueError):
        registry.counter("foo bar", "d")


def test_invalid_label_name(registry):
    with pytest.raises(ValueError):
        registry.counter("c", "d", labelnames=("__reserved",))
    with pytest.raises(ValueError):
        registry.counter("c", "d", labelnames=("bad-name",))


def test_label_value_escaping(registry):
    c = registry.counter("c", "d", labelnames=("path",))
    c.labels(path='quote"backslash\\newline\n').inc()
    text = registry.render()
    assert 'path="quote\\"backslash\\\\newline\\n"' in text


def test_mismatched_labels_rejected(registry):
    c = registry.counter("c", "d", labelnames=("a", "b"))
    with pytest.raises(ValueError):
        c.labels(a="x").inc()
    with pytest.raises(ValueError):
        c.labels(a="x", b="y", c="z").inc()


# ---------------------------------------------------------------------------
# Re-registration
# ---------------------------------------------------------------------------


def test_re_register_same_type_returns_existing(registry):
    a = registry.counter("c", "d")
    b = registry.counter("c", "d")
    assert a is b


def test_re_register_different_type_rejected(registry):
    registry.counter("c", "d")
    with pytest.raises(ValueError):
        registry.gauge("c", "d")


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


def test_counter_thread_safe(registry):
    c = registry.counter("c", "d")
    n_threads = 20
    n_inc_per_thread = 1000

    def worker():
        for _ in range(n_inc_per_thread):
            c.inc()

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    text = registry.render()
    assert f"c {n_threads * n_inc_per_thread}" in text


# ---------------------------------------------------------------------------
# Cardinality cap
# ---------------------------------------------------------------------------


def test_cardinality_cap_drops_silently():
    reg = PrometheusMetricsService(max_label_combinations=3)
    c = reg.counter("c", "d", labelnames=("k",))
    for i in range(10):
        c.labels(k=str(i)).inc()
    # Only first 3 combinations were stored.
    text = reg.render()
    series = [line for line in text.splitlines() if line.startswith("c{")]
    assert len(series) == 3


# ---------------------------------------------------------------------------
# Defaults + service-level
# ---------------------------------------------------------------------------


def test_register_defaults():
    reg = PrometheusMetricsService()
    defaults = reg.register_defaults()
    expected = {
        "beagle_http_requests_total",
        "beagle_http_request_duration_seconds",
        "beagle_vm_count",
        "beagle_session_count",
        "beagle_auth_failures_total",
        "beagle_rate_limit_drops_total",
        "beagle_process_start_time_seconds",
    }
    assert expected.issubset(set(defaults))
    assert expected.issubset(set(reg.names()))
    text = reg.render()
    for name in expected:
        assert f"# TYPE {name}" in text


def test_render_bytes_is_utf8():
    reg = PrometheusMetricsService()
    reg.counter("c", "doc").inc()
    body = reg.render_bytes()
    assert isinstance(body, bytes)
    assert b"# TYPE c counter" in body


def test_content_type():
    reg = PrometheusMetricsService()
    assert "text/plain" in reg.content_type
    assert "0.0.4" in reg.content_type


def test_types_via_isinstance(registry):
    assert isinstance(registry.counter("c", "d"), Counter)
    assert isinstance(registry.gauge("g", "d"), Gauge)
    assert isinstance(registry.histogram("h", "d"), Histogram)
