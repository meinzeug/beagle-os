"""Fleet Telemetry Service — Health-Monitoring + Predictive Maintenance.

GoEnterprise Plan 07, Schritte 1 + 2 + 3
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class DeviceTelemetry:
    device_id: str
    timestamp: str
    device_type: str    # "node" | "thin_client"
    # Health metrics
    disk_smart_ok: bool = True
    disk_reallocated_sectors: int = 0
    disk_pending_sectors: int = 0
    cpu_temp_c: float = 0.0
    gpu_temp_c: float = 0.0
    ram_ecc_errors: int = 0
    network_errors: int = 0
    reboot_count_7d: int = 0
    uptime_hours: float = 0.0


@dataclass
class AnomalyReport:
    device_id: str
    metric: str
    current_value: float
    baseline_mean: float
    baseline_std: float
    trend_slope: float          # units per day
    estimated_failure_days: int  # -1 if unknown
    severity: str               # "warning" | "critical"


class FleetTelemetryService:
    """
    Collects device health telemetry and runs anomaly detection.

    Anomaly detection algorithm:
    - Maintain 30-day baseline (mean + std-dev) per metric per device
    - Flag if: current > mean + 3*std OR linear trend hits critical threshold in <7 days
    """

    STATE_DIR = Path("/var/lib/beagle/fleet-telemetry")
    RETENTION_DAYS = 30
    ANOMALY_SIGMA = 3.0

    # Critical thresholds for trend-based prediction
    CRITICAL_THRESHOLDS = {
        "disk_reallocated_sectors": 10,
        "disk_pending_sectors": 5,
        "cpu_temp_c": 90.0,
        "gpu_temp_c": 90.0,
        "ram_ecc_errors": 50,
        "reboot_count_7d": 5,
    }

    def __init__(
        self,
        state_dir: Path | None = None,
        utcnow: Callable[[], str] | None = None,
        migrate_vms_fn: Callable[[str], list[dict[str, Any]]] | None = None,
    ) -> None:
        self._dir = state_dir or self.STATE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._utcnow = utcnow or self._default_utcnow
        self._migrate_vms_fn = migrate_vms_fn

    # ------------------------------------------------------------------
    # Telemetry ingestion
    # ------------------------------------------------------------------

    def ingest(self, telemetry: DeviceTelemetry) -> None:
        """Store a telemetry record."""
        shard = self._dir / f"{telemetry.device_id}.jsonl"
        with shard.open("a") as f:
            f.write(json.dumps(asdict(telemetry)) + "\n")
        self._prune(telemetry.device_id)

    def get_history(self, device_id: str, *, days: int = 30) -> list[DeviceTelemetry]:
        """Return telemetry history for a device (last N days)."""
        import datetime
        cutoff = (self._current_datetime() - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")

        shard = self._dir / f"{device_id}.jsonl"
        if not shard.exists():
            return []
        records = []
        for line in shard.read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("timestamp", "") >= cutoff:
                records.append(DeviceTelemetry(**d))
        return records

    # ------------------------------------------------------------------
    # Anomaly detection (Plan 07, Schritt 2)
    # ------------------------------------------------------------------

    def detect_anomalies(self, device_id: str) -> list[AnomalyReport]:
        """Run anomaly detection on recent telemetry. Returns list of reports."""
        history = self.get_history(device_id, days=self.RETENTION_DAYS)
        if len(history) < 3:
            return []

        latest = history[-1]
        anomalies = []

        for metric, threshold in self.CRITICAL_THRESHOLDS.items():
            values = [getattr(h, metric, 0.0) for h in history]
            current = getattr(latest, metric, 0.0)

            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            std = math.sqrt(variance) if variance > 0 else 0.001

            # Sigma check
            sigma_exceeded = current > mean + self.ANOMALY_SIGMA * std

            # Linear trend: estimate days to threshold
            trend_slope, failure_days = self._estimate_trend(values, float(threshold))

            if sigma_exceeded or (trend_slope > 0 and 0 < failure_days <= 7):
                severity = "critical" if failure_days <= 3 else "warning"
                anomalies.append(AnomalyReport(
                    device_id=device_id,
                    metric=metric,
                    current_value=float(current),
                    baseline_mean=round(mean, 3),
                    baseline_std=round(std, 3),
                    trend_slope=round(trend_slope, 4),
                    estimated_failure_days=failure_days,
                    severity=severity,
                ))

        return anomalies

    def detect_all_anomalies(self) -> dict[str, list[AnomalyReport]]:
        """Run anomaly detection for all devices that have telemetry."""
        result = {}
        for shard in self._dir.glob("*.jsonl"):
            device_id = shard.stem
            anomalies = self.detect_anomalies(device_id)
            if anomalies:
                result[device_id] = anomalies
        return result

    # ------------------------------------------------------------------
    # Maintenance scheduling (Plan 07, Schritt 4)
    # ------------------------------------------------------------------

    def schedule_maintenance(
        self,
        device_id: str,
        reason: str,
        suggested_window: str,
    ) -> dict[str, Any]:
        """Record a maintenance schedule entry."""
        vm_migrations: list[dict[str, Any]] = []
        drain_status = "not_configured"
        drain_error = ""
        if self._migrate_vms_fn is not None:
            try:
                payload = self._migrate_vms_fn(device_id)
                if isinstance(payload, list):
                    vm_migrations = [item for item in payload if isinstance(item, dict)]
                drain_status = "completed"
            except Exception as exc:
                drain_status = "failed"
                drain_error = str(exc)

        rec = {
            "device_id": device_id,
            "reason": reason,
            "suggested_window": suggested_window,
            "scheduled_at": self._utcnow(),
            "status": "pending",
            "drain_status": drain_status,
            "vm_migration_count": len(vm_migrations),
            "vm_migrations": vm_migrations,
        }
        if drain_error:
            rec["drain_error"] = drain_error
        maint_file = self._dir / "maintenance_schedule.json"
        schedule = []
        if maint_file.exists():
            schedule = json.loads(maint_file.read_text())
        schedule.append(rec)
        maint_file.write_text(json.dumps(schedule, indent=2))
        return rec

    def get_maintenance_schedule(self) -> list[dict[str, Any]]:
        maint_file = self._dir / "maintenance_schedule.json"
        if not maint_file.exists():
            return []
        return json.loads(maint_file.read_text())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _estimate_trend(self, values: list[float], threshold: float) -> tuple[float, int]:
        """
        Fit a linear regression to values. Return (slope_per_sample, days_to_threshold).
        days_to_threshold = -1 if trend is flat or decreasing.
        """
        n = len(values)
        if n < 2:
            return 0.0, -1
        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n
        num = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0.0
        if slope <= 0 or values[-1] >= threshold:
            return slope, -1
        steps_left = (threshold - values[-1]) / slope
        # Assume one sample per 5 minutes → steps_left * 5 / 1440 days
        days = int(steps_left * 5 / 1440)
        return slope, max(0, days)

    def _prune(self, device_id: str) -> None:
        """Remove telemetry older than RETENTION_DAYS."""
        import datetime
        cutoff = (self._current_datetime() - datetime.timedelta(days=self.RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
        shard = self._dir / f"{device_id}.jsonl"
        if not shard.exists():
            return
        lines = [
            line for line in shard.read_text().splitlines()
            if line.strip() and json.loads(line).get("timestamp", "") >= cutoff
        ]
        shard.write_text("\n".join(lines) + ("\n" if lines else ""))

    @staticmethod
    def _default_utcnow() -> str:
        import datetime
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _current_datetime(self):
        import datetime
        raw = str(self._utcnow() or "").strip()
        if raw:
            try:
                parsed = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=datetime.timezone.utc)
                return parsed.astimezone(datetime.timezone.utc)
            except ValueError:
                pass
        return datetime.datetime.now(datetime.timezone.utc)
