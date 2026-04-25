"""Cost Model Service — Ressourcen-Preismodell + Chargeback-Reports.

GoEnterprise Plan 05, Schritte 1 + 3 + 4
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CostModel:
    cpu_hour_cost: float = 0.002        # € per vCPU per hour
    ram_gb_hour_cost: float = 0.0005    # € per GB RAM per hour
    gpu_hour_cost: float = 0.10         # € per GPU slot per hour
    storage_gb_month_cost: float = 0.05  # € per GB storage per month
    electricity_price_per_kwh: float = 0.30  # €/kWh


@dataclass
class BudgetAlert:
    department: str
    monthly_budget: float
    alert_at_percent: int = 80      # fire alert when usage reaches this %
    last_alerted_at: str = ""


@dataclass
class ChargebackEntry:
    department: str
    user_id: str
    month: str          # "YYYY-MM"
    sessions: int
    cpu_hours: float
    gpu_hours: float
    storage_gb: float
    total_cost: float
    energy_cost: float = 0.0


class CostModelService:
    """
    Computes per-VM hourly rates and generates chargeback reports.

    Reads usage data from UsageTrackingService state file.
    """

    STATE_FILE = Path("/var/lib/beagle/beagle-manager/cost-model.json")

    def __init__(self, state_file: Path | None = None) -> None:
        self._state_file = state_file or self.STATE_FILE
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    # ------------------------------------------------------------------
    # Model
    # ------------------------------------------------------------------

    def set_cost_model(self, model: CostModel) -> None:
        self._state["model"] = asdict(model)
        self._save()

    def get_cost_model(self) -> CostModel:
        d = self._state.get("model", {})
        return CostModel(
            cpu_hour_cost=d.get("cpu_hour_cost", 0.002),
            ram_gb_hour_cost=d.get("ram_gb_hour_cost", 0.0005),
            gpu_hour_cost=d.get("gpu_hour_cost", 0.10),
            storage_gb_month_cost=d.get("storage_gb_month_cost", 0.05),
            electricity_price_per_kwh=d.get("electricity_price_per_kwh", 0.30),
        )

    def hourly_rate_per_vm(
        self,
        cpu_cores: int,
        ram_gb: float,
        gpu_slots: int = 0,
        storage_gb: float = 0.0,
    ) -> float:
        m = self.get_cost_model()
        return (
            cpu_cores * m.cpu_hour_cost
            + ram_gb * m.ram_gb_hour_cost
            + gpu_slots * m.gpu_hour_cost
            + storage_gb * m.storage_gb_month_cost / 720  # hours per month
        )

    def session_cost(
        self,
        duration_seconds: float,
        cpu_cores: int,
        ram_gb: float,
        gpu_slots: int = 0,
    ) -> float:
        hours = duration_seconds / 3600.0
        return self.hourly_rate_per_vm(cpu_cores, ram_gb, gpu_slots) * hours

    # ------------------------------------------------------------------
    # Budget Alerts
    # ------------------------------------------------------------------

    def set_budget_alert(self, alert: BudgetAlert) -> None:
        self._state["budgets"][alert.department] = asdict(alert)
        self._save()

    def get_budget_alert(self, department: str) -> BudgetAlert | None:
        d = self._state["budgets"].get(department)
        if not d:
            return None
        return BudgetAlert(**d)

    def check_budget_alerts(
        self,
        usage_by_department: dict[str, float],
        utcnow: str = "",
    ) -> list[dict[str, Any]]:
        """
        Check if any department has exceeded their budget alert threshold.
        Returns list of triggered alerts.
        """
        triggered = []
        for dept, spent in usage_by_department.items():
            alert = self.get_budget_alert(dept)
            if alert is None or alert.monthly_budget <= 0:
                continue
            pct = (spent / alert.monthly_budget) * 100
            if pct >= alert.alert_at_percent:
                triggered.append({
                    "department": dept,
                    "spent": round(spent, 4),
                    "budget": alert.monthly_budget,
                    "percent": round(pct, 1),
                    "threshold": alert.alert_at_percent,
                })
        return triggered

    # ------------------------------------------------------------------
    # Chargeback Report (Plan 05, Schritt 3)
    # ------------------------------------------------------------------

    def generate_chargeback_report(
        self,
        usage_records: list[dict[str, Any]],
        month: str,
        department: str | None = None,
    ) -> dict[str, Any]:
        """
        Build chargeback report from raw usage records.
        usage_records: list of dicts from UsageTrackingService
        Returns: {"entries": [...], "csv": "<csv string>", "total_cost": float}
        """
        m = self.get_cost_model()
        agg: dict[tuple[str, str], ChargebackEntry] = {}

        for rec in usage_records:
            if rec.get("month") != month:
                continue
            dept = rec.get("department", "")
            if department and dept != department:
                continue
            user = rec.get("user_id", "")
            key = (dept, user)
            if key not in agg:
                agg[key] = ChargebackEntry(
                    department=dept,
                    user_id=user,
                    month=month,
                    sessions=0,
                    cpu_hours=0.0,
                    gpu_hours=0.0,
                    storage_gb=0.0,
                    total_cost=0.0,
                )
            entry = agg[key]
            entry.sessions += 1
            entry.cpu_hours += rec.get("cpu_hours", 0.0)
            entry.gpu_hours += rec.get("gpu_hours", 0.0)
            entry.storage_gb += rec.get("storage_gb", 0.0)
            entry.energy_cost += rec.get("energy_cost", 0.0)
            entry.total_cost += (
                rec.get("cpu_hours", 0.0) * m.cpu_hour_cost
                + rec.get("gpu_hours", 0.0) * m.gpu_hour_cost
                + rec.get("storage_gb", 0.0) * m.storage_gb_month_cost / 720
                + rec.get("energy_cost", 0.0)
            )

        entries = [asdict(e) for e in agg.values()]
        total = sum(e["total_cost"] for e in entries)

        # CSV
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=[
            "department", "user_id", "month", "sessions",
            "cpu_hours", "gpu_hours", "storage_gb", "energy_cost", "total_cost"
        ])
        w.writeheader()
        w.writerows(entries)

        return {"entries": entries, "csv": buf.getvalue(), "total_cost": round(total, 4)}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if self._state_file.exists():
            return json.loads(self._state_file.read_text())
        return {"model": {}, "budgets": {}}

    def _save(self) -> None:
        self._state_file.write_text(json.dumps(self._state, indent=2))
