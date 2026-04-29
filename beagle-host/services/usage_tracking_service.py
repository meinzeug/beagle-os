"""Usage Tracking Service — per-session Nutzungsdaten für Chargeback.

GoEnterprise Plan 05, Schritt 2
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.persistence.json_state_store import JsonStateStore


@dataclass
class UsageRecord:
    session_id: str
    user_id: str
    department: str
    pool_id: str
    vm_id: int
    month: str          # "YYYY-MM"
    start_time: str
    end_time: str
    duration_seconds: float
    cpu_cores: int
    ram_gb: float
    gpu_slots: int
    storage_gb: float
    cpu_hours: float    # cpu_cores * duration_hours
    gpu_hours: float    # gpu_slots * duration_hours
    energy_kwh: float = 0.0
    energy_cost: float = 0.0


class UsageTrackingService:
    """Records session usage for Chargeback and Cost-Transparency."""

    DB_FILE = Path("/var/lib/beagle/usage/usage.db.json")

    def __init__(self, db_file: Path | None = None) -> None:
        self._db_file = db_file or self.DB_FILE
        self._db_file.parent.mkdir(parents=True, exist_ok=True)
        self._db = self._load()

    def record_session(
        self,
        *,
        session_id: str,
        user_id: str,
        department: str,
        pool_id: str,
        vm_id: int,
        start_time: str,
        end_time: str,
        cpu_cores: int = 1,
        ram_gb: float = 4.0,
        gpu_slots: int = 0,
        storage_gb: float = 0.0,
        energy_kwh: float = 0.0,
        energy_cost: float = 0.0,
    ) -> UsageRecord:
        """Record a completed session and append to the usage database."""
        import datetime

        def parse_ts(ts: str) -> datetime.datetime:
            for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.datetime.strptime(ts, fmt).replace(
                        tzinfo=datetime.timezone.utc
                    )
                except ValueError:
                    continue
            raise ValueError(f"Cannot parse timestamp: {ts!r}")

        t0 = parse_ts(start_time)
        t1 = parse_ts(end_time)
        dur = max(0.0, (t1 - t0).total_seconds())
        hours = dur / 3600.0
        month = t0.strftime("%Y-%m")

        rec = UsageRecord(
            session_id=session_id,
            user_id=user_id,
            department=department,
            pool_id=pool_id,
            vm_id=vm_id,
            month=month,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=dur,
            cpu_cores=cpu_cores,
            ram_gb=ram_gb,
            gpu_slots=gpu_slots,
            storage_gb=storage_gb,
            cpu_hours=round(cpu_cores * hours, 4),
            gpu_hours=round(gpu_slots * hours, 4),
            energy_kwh=energy_kwh,
            energy_cost=energy_cost,
        )
        self._db.append(asdict(rec))
        self._save()
        return rec

    def get_usage(
        self,
        *,
        month: str | None = None,
        user_id: str | None = None,
        department: str | None = None,
    ) -> list[dict[str, Any]]:
        records = self._db
        if month:
            records = [r for r in records if r.get("month") == month]
        if user_id:
            records = [r for r in records if r.get("user_id") == user_id]
        if department:
            records = [r for r in records if r.get("department") == department]
        return records

    def total_cost_by_department(self, month: str) -> dict[str, float]:
        """
        Sum up total_cost per department for a given month.
        Requires cost_model_service to calculate — returns cpu+gpu hours as proxy.
        """
        agg: dict[str, float] = {}
        for rec in self.get_usage(month=month):
            dept = rec.get("department", "")
            # Use cpu_hours as simple proxy (caller multiplies by rate)
            agg[dept] = agg.get(dept, 0.0) + rec.get("cpu_hours", 0.0) + rec.get("gpu_hours", 0.0)
        return agg

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load(self) -> list[dict[str, Any]]:
        return JsonStateStore(self._db_file, default_factory=list).load()

    def _save(self) -> None:
        JsonStateStore(self._db_file, default_factory=list).save(self._db)
