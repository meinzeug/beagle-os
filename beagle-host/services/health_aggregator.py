"""Per-component health aggregation for /api/v1/health.

GoAdvanced Plan 08 Schritt 5.

Runs a list of component checks (control_plane, libvirt, data_dir, …) with
per-check timeouts and aggregates their status to one of
``healthy | degraded | unhealthy``. Designed to wrap the existing
``HealthPayloadService.build_payload()`` output without breaking back-compat:
the flat fields stay, and ``status`` + ``components`` are added on top.

A "check" is any callable returning a ``ComponentResult``-shaped dict::

    {
        "status": "healthy" | "degraded" | "unhealthy",
        "latency_ms": 12,                # optional
        "detail": "...",                 # optional human-readable
        "error": "...",                  # optional, if degraded/unhealthy
    }

If a check raises, the aggregator records it as ``unhealthy`` with
``error=<exc>``.

Per-check timeout uses ``threading.Timer``-based watchdog; an exceeded
timeout marks the component ``unhealthy``. The check still runs to
completion in the background but its result is discarded.
"""
from __future__ import annotations

import threading
import time
from typing import Callable


_VALID_STATUSES = {"healthy", "degraded", "unhealthy"}


def _normalize(result: object) -> dict:
    if not isinstance(result, dict):
        return {"status": "unhealthy", "error": f"invalid check result: {result!r}"}
    status = str(result.get("status", "")).strip().lower()
    if status not in _VALID_STATUSES:
        return {"status": "unhealthy", "error": f"invalid status: {status!r}"}
    out: dict = {"status": status}
    if "latency_ms" in result:
        try:
            out["latency_ms"] = int(result["latency_ms"])
        except (TypeError, ValueError):
            pass
    for key in ("detail", "error"):
        if result.get(key):
            out[key] = str(result[key])
    return out


class HealthAggregatorService:
    """Runs registered component checks and aggregates the overall status."""

    def __init__(
        self,
        *,
        check_timeout_seconds: float = 2.0,
        utcnow: Callable[[], str] | None = None,
    ) -> None:
        self._checks: list[tuple[str, Callable[[], dict]]] = []
        self._timeout = float(check_timeout_seconds)
        self._utcnow = utcnow
        self._start_time = time.time()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str, check: Callable[[], dict]) -> None:
        if not name or not callable(check):
            raise ValueError("name and callable check required")
        with self._lock:
            for idx, (existing_name, _) in enumerate(self._checks):
                if existing_name == name:
                    self._checks[idx] = (name, check)
                    return
            self._checks.append((name, check))

    def names(self) -> list[str]:
        with self._lock:
            return [name for name, _ in self._checks]

    # ------------------------------------------------------------------
    # Built-in checks
    # ------------------------------------------------------------------

    def control_plane_check(self) -> dict:
        uptime = max(0, int(time.time() - self._start_time))
        return {
            "status": "healthy",
            "detail": f"uptime={uptime}s",
            "latency_ms": 0,
        }

    @staticmethod
    def writable_path_check(path) -> Callable[[], dict]:
        def _check() -> dict:
            t0 = time.time()
            try:
                if not path.exists():
                    return {"status": "unhealthy", "error": "path missing"}
                probe = path / ".beagle-health-write-probe"
                probe.write_text("ok")
                probe.unlink(missing_ok=True)
                return {
                    "status": "healthy",
                    "latency_ms": int((time.time() - t0) * 1000),
                }
            except Exception as exc:  # pragma: no cover - filesystem error path
                return {"status": "unhealthy", "error": str(exc)}
        return _check

    @staticmethod
    def provider_check(list_providers: Callable[[], list[str]]) -> Callable[[], dict]:
        def _check() -> dict:
            t0 = time.time()
            try:
                providers = list(list_providers() or [])
            except Exception as exc:
                return {"status": "unhealthy", "error": str(exc)}
            latency = int((time.time() - t0) * 1000)
            if not providers:
                return {
                    "status": "degraded",
                    "error": "no providers registered",
                    "latency_ms": latency,
                }
            return {
                "status": "healthy",
                "latency_ms": latency,
                "detail": f"providers={','.join(providers)}",
            }
        return _check

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _run_with_timeout(self, check: Callable[[], dict]) -> dict:
        result_holder: dict[str, object] = {}

        def _runner() -> None:
            try:
                t0 = time.time()
                value = check()
                if isinstance(value, dict) and "latency_ms" not in value:
                    value = {**value, "latency_ms": int((time.time() - t0) * 1000)}
                result_holder["value"] = value
            except Exception as exc:
                result_holder["error"] = exc

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join(self._timeout)
        if thread.is_alive():
            return {
                "status": "unhealthy",
                "error": f"check timed out after {self._timeout:.1f}s",
            }
        if "error" in result_holder:
            return {"status": "unhealthy", "error": str(result_holder["error"])}
        return _normalize(result_holder.get("value"))

    def run(self) -> dict:
        with self._lock:
            checks = list(self._checks)
        components: dict[str, dict] = {}
        worst = "healthy"
        for name, check in checks:
            result = self._run_with_timeout(check)
            components[name] = result
            if result["status"] == "unhealthy":
                worst = "unhealthy"
            elif result["status"] == "degraded" and worst == "healthy":
                worst = "degraded"
        return {"status": worst, "components": components}
