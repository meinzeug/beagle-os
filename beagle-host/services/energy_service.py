"""Energy Service — Energie-Verbrauch + CO₂-Tracking für CSRD-Compliance.

GoEnterprise Plan 09, Schritte 1 + 2 + 3 + 5
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class EnergySample:
    timestamp: str
    node_id: str
    node_power_w: float       # Watt, from RAPL or PDU
    vm_allocations: dict[str, float]  # vmid → share (0.0..1.0) of node power


@dataclass
class CarbonConfig:
    co2_grams_per_kwh: float = 400.0        # German grid average 2024
    electricity_price_per_kwh: float = 0.30  # €/kWh


@dataclass
class EnergyUsageSummary:
    entity_id: str          # vmid, pool_id, or department
    period: str             # "YYYY-MM" or "YYYY-QN"
    total_kwh: float
    total_co2_grams: float
    energy_cost_eur: float


class EnergyService:
    """
    Tracks energy consumption per VM/node and computes CO₂ footprint.

    Data sources:
    - RAPL:    /sys/class/powercap/intel-rapl:0/energy_uj
    - NVML:    nvidia-smi --query-gpu=power.draw
    - Proxy:   if neither available → CPU% × TDP estimate

    GoEnterprise Plan 09
    """

    STATE_DIR = Path("/var/lib/beagle/energy")
    CONFIG_FILE = Path("/var/lib/beagle/beagle-manager/energy-config.json")
    RETENTION_DAYS = 365

    def __init__(
        self,
        state_dir: Path | None = None,
        config_file: Path | None = None,
        utcnow: Callable[[], str] | None = None,
    ) -> None:
        self._dir = state_dir or self.STATE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cfg_file = config_file or self.CONFIG_FILE
        self._cfg_file.parent.mkdir(parents=True, exist_ok=True)
        self._utcnow = utcnow or self._default_utcnow

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_carbon_config(self, config: CarbonConfig) -> None:
        self._cfg_file.write_text(json.dumps(asdict(config), indent=2))

    def get_carbon_config(self) -> CarbonConfig:
        if self._cfg_file.exists():
            d = json.loads(self._cfg_file.read_text())
            return CarbonConfig(
                co2_grams_per_kwh=d.get("co2_grams_per_kwh", 400.0),
                electricity_price_per_kwh=d.get("electricity_price_per_kwh", 0.30),
            )
        return CarbonConfig()

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def record_sample(self, sample: EnergySample) -> None:
        day = sample.timestamp[:10]
        shard = self._dir / f"{sample.node_id}_{day}.jsonl"
        with shard.open("a") as f:
            f.write(json.dumps(asdict(sample)) + "\n")

    def record_node_power(
        self,
        node_id: str,
        node_power_w: float,
        vm_cpu_shares: dict[str, float] | None = None,
    ) -> EnergySample:
        """Record node power and distribute among VMs by CPU share."""
        if vm_cpu_shares:
            total = sum(vm_cpu_shares.values()) or 1.0
            alloc = {vid: share / total for vid, share in vm_cpu_shares.items()}
        else:
            alloc = {}
        sample = EnergySample(
            timestamp=self._utcnow(),
            node_id=node_id,
            node_power_w=node_power_w,
            vm_allocations=alloc,
        )
        self.record_sample(sample)
        return sample

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def get_samples(self, node_id: str, *, days: int = 30) -> list[EnergySample]:
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
                if line.strip():
                    d = json.loads(line)
                    samples.append(EnergySample(**d))
        return samples

    def compute_energy_kwh(
        self,
        node_id: str,
        *,
        month: str,                  # "YYYY-MM"
        vm_id: str | None = None,
    ) -> float:
        """
        Compute kWh consumed by a node (or specific VM) in a given month.
        Assumes samples are taken every ~60 seconds.
        """
        samples = self.get_samples(node_id, days=62)
        total_wh = 0.0
        SAMPLE_INTERVAL_H = 1 / 60.0  # ~60s samples → 1/60 hour each

        for s in samples:
            if not s.timestamp.startswith(month):
                continue
            if vm_id is not None:
                share = s.vm_allocations.get(str(vm_id), 0.0)
                power = s.node_power_w * share
            else:
                power = s.node_power_w
            total_wh += power * SAMPLE_INTERVAL_H

        return round(total_wh / 1000.0, 4)  # Wh → kWh

    # ------------------------------------------------------------------
    # CO₂ + Cost computation
    # ------------------------------------------------------------------

    def compute_co2(self, kwh: float) -> float:
        """Return CO₂ in grams."""
        cfg = self.get_carbon_config()
        return round(kwh * cfg.co2_grams_per_kwh, 2)

    def compute_energy_cost(self, kwh: float) -> float:
        cfg = self.get_carbon_config()
        return round(kwh * cfg.electricity_price_per_kwh, 4)

    # ------------------------------------------------------------------
    # CSRD Export (Plan 09, Schritt 5)
    # ------------------------------------------------------------------

    def generate_csrd_report(
        self,
        node_ids: list[str],
        year: int,
        quarter: int,
    ) -> dict[str, Any]:
        """
        Generate CSRD Scope-2 report for a quarter.
        Returns dict with total_kwh, total_co2_kg, breakdown by month.
        """
        if quarter not in (1, 2, 3, 4):
            raise ValueError(f"quarter must be 1-4, got {quarter}")
        start_month = (quarter - 1) * 3 + 1
        months = [f"{year}-{str(m).zfill(2)}" for m in range(start_month, start_month + 3)]

        total_kwh = 0.0
        by_month = {}
        for month in months:
            month_kwh = 0.0
            for nid in node_ids:
                month_kwh += self.compute_energy_kwh(nid, month=month)
            by_month[month] = {
                "kwh": month_kwh,
                "co2_kg": round(self.compute_co2(month_kwh) / 1000.0, 3),
                "cost_eur": self.compute_energy_cost(month_kwh),
            }
            total_kwh += month_kwh

        cfg = self.get_carbon_config()
        return {
            "year": year,
            "quarter": quarter,
            "months": months,
            "total_kwh": round(total_kwh, 3),
            "total_co2_kg": round(self.compute_co2(total_kwh) / 1000.0, 3),
            "total_cost_eur": self.compute_energy_cost(total_kwh),
            "co2_grams_per_kwh_used": cfg.co2_grams_per_kwh,
            "breakdown": by_month,
            "scope": "Scope-2 (location-based)",
        }

    # ------------------------------------------------------------------
    # RAPL reader (best-effort)
    # ------------------------------------------------------------------

    @staticmethod
    def read_rapl_power_w(package: int = 0) -> float | None:
        """
        Read CPU package power from RAPL (Linux, requires root or relaxed permissions).
        Returns Watts or None if unavailable.
        """
        try:
            import time
            rapl = Path(f"/sys/class/powercap/intel-rapl:{package}")
            e1 = int((rapl / "energy_uj").read_text().strip())
            time.sleep(0.1)
            e2 = int((rapl / "energy_uj").read_text().strip())
            uj = e2 - e1
            if uj < 0:
                # Counter wrapped — ignore
                return None
            return round(uj / 100_000.0, 2)  # uJ in 100ms → W
        except Exception:
            return None

    @staticmethod
    def _default_utcnow() -> str:
        import datetime
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
