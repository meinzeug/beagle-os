"""Prometheus-compatible in-memory metrics registry.

GoAdvanced Plan 08 Schritt 1.

Provides a small, dependency-free implementation of three Prometheus metric
types (Counter, Gauge, Histogram) and a text-format exporter. No external
prometheus_client dependency is required so the control plane stays
hermetic on stripped-down installs.

Usage:
    metrics = PrometheusMetricsService()
    requests = metrics.counter(
        "beagle_http_requests_total",
        "HTTP requests handled by the control plane",
        labelnames=("method", "status"),
    )
    requests.labels(method="GET", status="200").inc()

    # Render text exposition format
    body = metrics.render()              # str
    body_bytes = metrics.render_bytes()  # bytes (utf-8)
    content_type = metrics.content_type  # for HTTP response

The implementation is intentionally simple:

- All operations are guarded by a single `threading.Lock`. The control
  plane is multi-threaded (ThreadingHTTPServer) so increments must be
  atomic for the simple int/float cases.
- Label cardinality is the caller's responsibility. To prevent runaway
  memory there is a soft cap (`max_label_combinations`) which logs a
  warning to stderr and silently drops new combinations.
"""
from __future__ import annotations

import math
import sys
import threading
import time
from typing import Iterable


_NAME_VALID = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:"
)


def _validate_name(name: str) -> None:
    if not name:
        raise ValueError("metric name must be non-empty")
    if name[0].isdigit():
        raise ValueError(f"metric name must not start with digit: {name!r}")
    for ch in name:
        if ch not in _NAME_VALID:
            raise ValueError(f"invalid character {ch!r} in metric name {name!r}")


def _validate_label_name(name: str) -> None:
    _validate_name(name)
    if name.startswith("__"):
        raise ValueError(
            f"label name must not start with __: {name!r} (reserved)"
        )


def _format_label_value(value: object) -> str:
    """Escape a label value per Prometheus text format spec."""
    text = "" if value is None else str(value)
    return (
        text.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def _format_float(value: float) -> str:
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "+Inf" if value > 0 else "-Inf"
    if value == int(value) and abs(value) < 1e16:
        return str(int(value))
    return repr(float(value))


class _LabelledMetric:
    """A single labeled time series within a parent Counter/Gauge/Histogram."""

    __slots__ = ("_parent", "_label_values")

    def __init__(self, parent: "_BaseMetric", label_values: tuple[str, ...]) -> None:
        self._parent = parent
        self._label_values = label_values


class _CounterChild(_LabelledMetric):
    def inc(self, amount: float = 1.0) -> None:
        if amount < 0:
            raise ValueError("counter increments must be non-negative")
        with self._parent._lock:
            current = self._parent._values.get(self._label_values, 0.0)
            self._parent._values[self._label_values] = current + float(amount)


class _GaugeChild(_LabelledMetric):
    def set(self, value: float) -> None:
        with self._parent._lock:
            self._parent._values[self._label_values] = float(value)

    def inc(self, amount: float = 1.0) -> None:
        with self._parent._lock:
            current = self._parent._values.get(self._label_values, 0.0)
            self._parent._values[self._label_values] = current + float(amount)

    def dec(self, amount: float = 1.0) -> None:
        self.inc(-amount)


class _HistogramChild(_LabelledMetric):
    def observe(self, amount: float) -> None:
        if amount < 0:
            # Histograms in Prometheus accept negative values, but Beagle's
            # observed values (durations, bytes) are non-negative; reject as
            # likely caller bug.
            raise ValueError("histogram observations must be non-negative")
        with self._parent._lock:
            buckets, total_sum, total_count = self._parent._values.setdefault(
                self._label_values,
                (
                    [0] * len(self._parent._upper_bounds),
                    0.0,
                    0,
                ),
            )
            for idx, upper in enumerate(self._parent._upper_bounds):
                if amount <= upper:
                    buckets[idx] += 1
            total_sum += float(amount)
            total_count += 1
            self._parent._values[self._label_values] = (
                buckets,
                total_sum,
                total_count,
            )


class _BaseMetric:
    metric_type: str = ""

    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: tuple[str, ...],
        max_label_combinations: int,
    ) -> None:
        _validate_name(name)
        for label in labelnames:
            _validate_label_name(label)
        self._name = name
        self._doc = documentation
        self._labelnames = labelnames
        self._values: dict = {}
        self._lock = threading.Lock()
        self._max_combinations = int(max_label_combinations)
        self._dropped = 0

    @property
    def name(self) -> str:
        return self._name

    def _resolve_label_values(self, **labels: object) -> tuple[str, ...]:
        if set(labels) != set(self._labelnames):
            raise ValueError(
                f"metric {self._name!r} expects labels {self._labelnames}, "
                f"got {sorted(labels)}"
            )
        return tuple(str(labels[name]) for name in self._labelnames)

    def _ensure_capacity(self, label_values: tuple[str, ...]) -> bool:
        if not self._labelnames:
            return True
        with self._lock:
            if label_values in self._values:
                return True
            if len(self._values) >= self._max_combinations:
                self._dropped += 1
                if self._dropped == 1 or self._dropped % 1000 == 0:
                    print(
                        f"[prometheus_metrics] WARN: dropping label "
                        f"combinations for metric {self._name!r} "
                        f"(cap {self._max_combinations}, total dropped "
                        f"{self._dropped})",
                        file=sys.stderr,
                        flush=True,
                    )
                return False
            return True

    def _format_labels(self, label_values: tuple[str, ...]) -> str:
        if not self._labelnames:
            return ""
        parts = [
            f'{name}="{_format_label_value(value)}"'
            for name, value in zip(self._labelnames, label_values)
        ]
        return "{" + ",".join(parts) + "}"


class Counter(_BaseMetric):
    metric_type = "counter"

    def labels(self, **labels: object) -> _CounterChild:
        label_values = self._resolve_label_values(**labels)
        if not self._ensure_capacity(label_values):
            return _NoopCounter()
        return _CounterChild(self, label_values)

    def inc(self, amount: float = 1.0) -> None:
        if self._labelnames:
            raise ValueError(
                f"metric {self._name!r} has labels {self._labelnames}; "
                f"use .labels(...).inc()"
            )
        if not self._ensure_capacity(()):
            return
        _CounterChild(self, ()).inc(amount)

    def render(self) -> Iterable[str]:
        yield f"# HELP {self._name} {self._doc}"
        yield f"# TYPE {self._name} counter"
        with self._lock:
            items = list(self._values.items())
        if not items and not self._labelnames:
            yield f"{self._name} 0"
            return
        for label_values, value in items:
            labels_str = self._format_labels(label_values)
            yield f"{self._name}{labels_str} {_format_float(value)}"


class Gauge(_BaseMetric):
    metric_type = "gauge"

    def labels(self, **labels: object) -> _GaugeChild:
        label_values = self._resolve_label_values(**labels)
        if not self._ensure_capacity(label_values):
            return _NoopGauge()
        return _GaugeChild(self, label_values)

    def set(self, value: float) -> None:
        if self._labelnames:
            raise ValueError(
                f"metric {self._name!r} has labels {self._labelnames}; "
                f"use .labels(...).set()"
            )
        if not self._ensure_capacity(()):
            return
        _GaugeChild(self, ()).set(value)

    def inc(self, amount: float = 1.0) -> None:
        if self._labelnames:
            raise ValueError(
                f"metric {self._name!r} has labels {self._labelnames}; "
                f"use .labels(...).inc()"
            )
        if not self._ensure_capacity(()):
            return
        _GaugeChild(self, ()).inc(amount)

    def render(self) -> Iterable[str]:
        yield f"# HELP {self._name} {self._doc}"
        yield f"# TYPE {self._name} gauge"
        with self._lock:
            items = list(self._values.items())
        if not items and not self._labelnames:
            yield f"{self._name} 0"
            return
        for label_values, value in items:
            labels_str = self._format_labels(label_values)
            yield f"{self._name}{labels_str} {_format_float(value)}"


DEFAULT_BUCKETS = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
)


class Histogram(_BaseMetric):
    metric_type = "histogram"

    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: tuple[str, ...],
        buckets: tuple[float, ...],
        max_label_combinations: int,
    ) -> None:
        super().__init__(name, documentation, labelnames, max_label_combinations)
        if not buckets:
            raise ValueError("histogram requires at least one bucket")
        bucket_list = sorted(float(b) for b in buckets)
        if bucket_list[-1] != float("inf"):
            bucket_list.append(float("inf"))
        self._upper_bounds = tuple(bucket_list)

    def labels(self, **labels: object) -> _HistogramChild:
        label_values = self._resolve_label_values(**labels)
        if not self._ensure_capacity(label_values):
            return _NoopHistogram()
        return _HistogramChild(self, label_values)

    def observe(self, amount: float) -> None:
        if self._labelnames:
            raise ValueError(
                f"metric {self._name!r} has labels {self._labelnames}; "
                f"use .labels(...).observe()"
            )
        if not self._ensure_capacity(()):
            return
        _HistogramChild(self, ()).observe(amount)

    def render(self) -> Iterable[str]:
        yield f"# HELP {self._name} {self._doc}"
        yield f"# TYPE {self._name} histogram"
        with self._lock:
            items = list(self._values.items())
        if not items and not self._labelnames:
            for upper in self._upper_bounds:
                le = "+Inf" if math.isinf(upper) else _format_float(upper)
                yield f'{self._name}_bucket{{le="{le}"}} 0'
            yield f"{self._name}_sum 0"
            yield f"{self._name}_count 0"
            return
        for label_values, (buckets, total_sum, total_count) in items:
            base_labels = self._format_labels(label_values)
            base_inner = base_labels[1:-1] if base_labels else ""
            sep = "," if base_inner else ""
            for idx, upper in enumerate(self._upper_bounds):
                le = "+Inf" if math.isinf(upper) else _format_float(upper)
                yield (
                    f'{self._name}_bucket{{{base_inner}{sep}le="{le}"}} '
                    f"{buckets[idx]}"
                )
            sum_labels = base_labels
            yield f"{self._name}_sum{sum_labels} {_format_float(total_sum)}"
            yield f"{self._name}_count{sum_labels} {total_count}"


# ---------------------------------------------------------------------------
# Cap-exceeded sentinels — silently swallow ops to avoid breaking callers.
# ---------------------------------------------------------------------------


class _NoopCounter:
    def inc(self, amount: float = 1.0) -> None:
        pass


class _NoopGauge:
    def set(self, value: float) -> None:
        pass

    def inc(self, amount: float = 1.0) -> None:
        pass

    def dec(self, amount: float = 1.0) -> None:
        pass


class _NoopHistogram:
    def observe(self, amount: float) -> None:
        pass


# ---------------------------------------------------------------------------
# Service / registry
# ---------------------------------------------------------------------------


class PrometheusMetricsService:
    """In-memory metrics registry + text exporter.

    Standard Beagle metrics are pre-declared via :py:meth:`register_defaults`.
    Surfaces obtain the singleton via ``service_registry.prometheus_metrics()``.
    """

    content_type: str = "text/plain; version=0.0.4; charset=utf-8"

    def __init__(self, *, max_label_combinations: int = 10_000) -> None:
        self._metrics: dict[str, _BaseMetric] = {}
        self._lock = threading.Lock()
        self._max_combinations = int(max_label_combinations)
        self._start_time = time.time()

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------

    def counter(
        self,
        name: str,
        documentation: str,
        labelnames: tuple[str, ...] = (),
    ) -> Counter:
        return self._register(
            Counter(name, documentation, labelnames, self._max_combinations)
        )

    def gauge(
        self,
        name: str,
        documentation: str,
        labelnames: tuple[str, ...] = (),
    ) -> Gauge:
        return self._register(
            Gauge(name, documentation, labelnames, self._max_combinations)
        )

    def histogram(
        self,
        name: str,
        documentation: str,
        labelnames: tuple[str, ...] = (),
        buckets: tuple[float, ...] = DEFAULT_BUCKETS,
    ) -> Histogram:
        return self._register(
            Histogram(
                name,
                documentation,
                labelnames,
                buckets,
                self._max_combinations,
            )
        )

    def _register(self, metric: _BaseMetric):
        with self._lock:
            if metric.name in self._metrics:
                existing = self._metrics[metric.name]
                if existing.metric_type != metric.metric_type:
                    raise ValueError(
                        f"metric {metric.name!r} already registered with "
                        f"type {existing.metric_type!r}, cannot re-register "
                        f"as {metric.metric_type!r}"
                    )
                return existing
            self._metrics[metric.name] = metric
            return metric

    def get(self, name: str) -> _BaseMetric | None:
        return self._metrics.get(name)

    def names(self) -> list[str]:
        with self._lock:
            return sorted(self._metrics)

    # ------------------------------------------------------------------
    # Default metrics — see Plan 08 Schritt 1.
    # ------------------------------------------------------------------

    def register_defaults(self) -> dict[str, _BaseMetric]:
        defaults = {
            "beagle_http_requests_total": self.counter(
                "beagle_http_requests_total",
                "Total HTTP requests handled by the control plane.",
                labelnames=("method", "status"),
            ),
            "beagle_http_request_duration_seconds": self.histogram(
                "beagle_http_request_duration_seconds",
                "HTTP request duration in seconds.",
                labelnames=("method",),
            ),
            "beagle_vm_count": self.gauge(
                "beagle_vm_count",
                "Number of VMs known to the control plane.",
            ),
            "beagle_session_count": self.gauge(
                "beagle_session_count",
                "Active streaming sessions.",
            ),
            "beagle_auth_failures_total": self.counter(
                "beagle_auth_failures_total",
                "Failed authentication attempts.",
                labelnames=("kind",),
            ),
            "beagle_rate_limit_drops_total": self.counter(
                "beagle_rate_limit_drops_total",
                "Requests dropped due to rate limiting.",
                labelnames=("path",),
            ),
            "beagle_process_start_time_seconds": self.gauge(
                "beagle_process_start_time_seconds",
                "Unix epoch second the control plane process started.",
            ),
        }
        # Process start time is constant for the lifetime of the registry.
        defaults["beagle_process_start_time_seconds"].set(self._start_time)
        return defaults

    # ------------------------------------------------------------------
    # Exposition
    # ------------------------------------------------------------------

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            metrics = list(self._metrics.values())
        for metric in metrics:
            lines.extend(metric.render())
            lines.append("")  # blank line between metric families
        return "\n".join(lines).rstrip("\n") + "\n"

    def render_bytes(self) -> bytes:
        return self.render().encode("utf-8")
