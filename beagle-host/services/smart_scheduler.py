"""Smart Scheduler — prädiktiver, kostenbewusster VM-Placement-Algorithmus.

GoEnterprise Plan 04, Schritt 3 + 4
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class NodeCapacity:
    node_id: str
    total_cpu_cores: int
    total_ram_mib: int
    free_cpu_cores: int
    free_ram_mib: int
    gpu_slots_free: int = 0
    predicted_cpu_pct_4h: float = 0.0   # predicted load over next 4 hours
    gpu_utilization_pct: float = 0.0    # current average GPU utilization (Plan 10)
    predicted_gpu_utilization_pct_4h: float = 0.0  # predicted GPU load over next 4 hours
    energy_price_per_kwh: float = 0.0
    carbon_intensity_g_per_kwh: float = 0.0


@dataclass
class SmartPlacementResult:
    node_id: str
    reason: str
    confidence: float            # 0.0 - 1.0
    alternative_nodes: list[str] = field(default_factory=list)


@dataclass
class RebalanceRecommendation:
    vm_id: int
    from_node: str
    to_node: str
    reason: str
    auto_execute: bool = False


class SmartSchedulerService:
    """
    Prädiktiver Scheduler für VM-Placement und Cluster-Rebalancing.

    - Berücksichtigt aktuelle + prognostizierte Node-Last (aus WorkloadPatternAnalyzer)
    - GPU-Klassen-Matching (Plan 03 gaming pools)
    - Kostenbewusst: bevorzugt Nodes mit niedrigstem Energie-Preis (Plan 09 Green Scheduling)
    - Rebalancing: erkennt ungleichmäßige Verteilung und empfiehlt Migrationen
    """

    OVERLOAD_THRESHOLD_PCT = 85.0
    UNDERLOAD_THRESHOLD_PCT = 20.0

    def __init__(
        self,
        *,
        list_nodes: Callable[[], list[NodeCapacity]] | None = None,
        migrate_vm: Callable[[int, str], None] | None = None,
        get_profile: Callable[[str], Any] | None = None,  # WorkloadProfile lookup
    ) -> None:
        self._list_nodes = list_nodes or (lambda: [])
        self._migrate_vm = migrate_vm
        self._get_profile = get_profile or (lambda _: None)

    # ------------------------------------------------------------------
    # Placement
    # ------------------------------------------------------------------

    @staticmethod
    def _effective_gpu_utilization(node: NodeCapacity) -> float:
        current = float(node.gpu_utilization_pct or 0.0)
        predicted = float(node.predicted_gpu_utilization_pct_4h or 0.0)
        return max(current, predicted)

    @staticmethod
    def _normalize_green_hours(green_hours: list[int] | None) -> list[int]:
        values: list[int] = []
        for item in list(green_hours or []):
            try:
                hour = int(item)
            except (TypeError, ValueError):
                continue
            if 0 <= hour <= 23 and hour not in values:
                values.append(hour)
        return sorted(values)

    @classmethod
    def is_green_hour(cls, hour: int | None, green_hours: list[int] | None) -> bool:
        if hour is None:
            return False
        return int(hour) in cls._normalize_green_hours(green_hours)

    @classmethod
    def _green_window_multiplier(cls, preferred_hour: int | None, green_hours: list[int] | None) -> float:
        hours = cls._normalize_green_hours(green_hours)
        if preferred_hour is None or not hours:
            return 1.0
        if cls.is_green_hour(preferred_hour, hours):
            return 1.6
        return 0.45

    @classmethod
    def _has_nearby_green_peak(
        cls,
        *,
        target_hour: int,
        peak_hours: list[int] | None,
        green_hours: list[int] | None,
        lookahead_hours: int,
    ) -> bool:
        peaks = cls._normalize_green_hours(peak_hours)
        greens = cls._normalize_green_hours(green_hours)
        if not peaks or not greens:
            return False
        for offset in range(1, max(1, int(lookahead_hours)) + 1):
            candidate_hour = (int(target_hour) + offset) % 24
            if candidate_hour in peaks and candidate_hour in greens:
                return True
        return False

    def pick_node(
        self,
        *,
        required_cpu_cores: int,
        required_ram_mib: int,
        gpu_required: bool = False,
        preferred_hour: int | None = None,
        green_hours: list[int] | None = None,
        gpu_utilization_threshold: float = 85.0,
        green_scheduling_enabled: bool = False,
    ) -> SmartPlacementResult:
        """
        Pick best node for a new VM.

        Scoring:
        - Must have free_cpu_cores >= required and free_ram_mib >= required
        - GPU slot required if gpu_required=True
        - For GPU-required VMs: prefer nodes with lower effective GPU utilization
          (current vs. predicted 4h load, whichever is worse)
        - Prefer lower predicted_cpu_pct_4h (pre-warming aware)
        - Tie-break: most free RAM
        """
        nodes = self._list_nodes()
        candidates = []
        green_multiplier = self._green_window_multiplier(preferred_hour, green_hours) if green_scheduling_enabled else 1.0
        green_window_state = (
            "match"
            if green_scheduling_enabled and self.is_green_hour(preferred_hour, green_hours)
            else "outside"
            if green_scheduling_enabled and preferred_hour is not None
            else "disabled"
        )
        for node in nodes:
            if node.free_cpu_cores < required_cpu_cores:
                continue
            if node.free_ram_mib < required_ram_mib:
                continue
            if gpu_required and node.gpu_slots_free < 1:
                continue
            effective_gpu_util = self._effective_gpu_utilization(node)
            # Exclude nodes whose GPU is already over the threshold (Plan 10)
            if gpu_required and effective_gpu_util >= gpu_utilization_threshold:
                continue
            score = 100.0 - node.predicted_cpu_pct_4h
            # GPU-aware scoring: penalise nodes with high GPU utilization
            if gpu_required:
                score -= effective_gpu_util * 0.5
            if green_scheduling_enabled:
                score -= float(node.energy_price_per_kwh or 0.0) * 20.0 * green_multiplier
                score -= float(node.carbon_intensity_g_per_kwh or 0.0) / 100.0 * green_multiplier
                if preferred_hour is not None and not self.is_green_hour(preferred_hour, green_hours):
                    score -= 2.5
            candidates.append((score, node.free_ram_mib, node))

        if not candidates:
            return SmartPlacementResult(
                node_id="",
                reason="no_suitable_node: insufficient resources",
                confidence=0.0,
            )

        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        best = candidates[0][2]
        alternatives = [c[2].node_id for c in candidates[1:3]]

        return SmartPlacementResult(
            node_id=best.node_id,
            reason=(
                f"best_score: free_cpu={best.free_cpu_cores},"
                f" predicted_load={best.predicted_cpu_pct_4h:.1f}%"
                + (
                    f", gpu_util={best.gpu_utilization_pct:.1f}%"
                    f", predicted_gpu_util={best.predicted_gpu_utilization_pct_4h:.1f}%"
                    if gpu_required else ""
                )
                + (
                    f", green_cost={best.energy_price_per_kwh:.3f}eur/kWh"
                    f", green_co2={best.carbon_intensity_g_per_kwh:.1f}g/kWh"
                    f", green_window={green_window_state}"
                    f", green_multiplier={green_multiplier:.2f}"
                    if green_scheduling_enabled else ""
                )
            ),
            confidence=min(1.0, candidates[0][0] / 100.0),
            alternative_nodes=alternatives,
        )

    # ------------------------------------------------------------------
    # Rebalancing (Plan 04, Schritt 4)
    # ------------------------------------------------------------------

    def rebalance_cluster(
        self,
        vm_assignments: list[dict[str, Any]],  # [{"vmid": int, "node_id": str, "cpu_pct": float}]
    ) -> list[RebalanceRecommendation]:
        """
        Identify overloaded nodes and recommend VM migrations.

        Returns a list of recommendations (not executed unless auto_execute=True and
        migrate_vm callable is provided).
        """
        nodes = {n.node_id: n for n in self._list_nodes()}
        if not nodes:
            return []

        # Compute per-node load
        node_load: dict[str, float] = {nid: n.predicted_cpu_pct_4h for nid, n in nodes.items()}

        overloaded = [nid for nid, load in node_load.items() if load > self.OVERLOAD_THRESHOLD_PCT]
        underloaded = [nid for nid, load in node_load.items() if load < self.UNDERLOAD_THRESHOLD_PCT]

        recommendations = []
        for src_node in overloaded:
            # Find VMs on this node, pick highest CPU consumer
            vms_on_node = [v for v in vm_assignments if v["node_id"] == src_node]
            vms_on_node.sort(key=lambda v: v.get("cpu_pct", 0.0), reverse=True)
            for vm in vms_on_node[:1]:   # recommend migrating top CPU consumer
                for dst_node in underloaded:
                    dst = nodes[dst_node]
                    if dst.free_cpu_cores >= 1 and dst.free_ram_mib >= 512:
                        rec = RebalanceRecommendation(
                            vm_id=vm["vmid"],
                            from_node=src_node,
                            to_node=dst_node,
                            reason=f"source_load={node_load[src_node]:.1f}% > {self.OVERLOAD_THRESHOLD_PCT}%",
                        )
                        recommendations.append(rec)
                        if self._migrate_vm:
                            self._migrate_vm(vm["vmid"], dst_node)
                        break

        return recommendations

    # ------------------------------------------------------------------
    # Pre-warming helper
    # ------------------------------------------------------------------

    def should_prewarm(
        self,
        profile: Any,
        minutes_ahead: int = 15,
        *,
        green_scheduling_enabled: bool = False,
        green_hours: list[int] | None = None,
        current_hour: int | None = None,
        lookahead_hours: int = 4,
    ) -> bool:
        """
        Return True if a VM should be pre-started N minutes before predicted peak.
        profile: WorkloadProfile from WorkloadPatternAnalyzer
        """
        if profile is None:
            return False
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        base_hour = int(current_hour) if current_hour is not None else now.hour
        target_hour = (base_hour + max(0, int(minutes_ahead)) // 60) % 24 if minutes_ahead >= 60 else (now + datetime.timedelta(minutes=minutes_ahead)).hour
        peak_hours = list(getattr(profile, "peak_hours", []) or [])
        if target_hour not in peak_hours:
            return False
        if not green_scheduling_enabled:
            return True
        normalized_green_hours = self._normalize_green_hours(green_hours)
        if not normalized_green_hours:
            return True
        if self.is_green_hour(target_hour, normalized_green_hours):
            return True
        return not self._has_nearby_green_peak(
            target_hour=target_hour,
            peak_hours=peak_hours,
            green_hours=normalized_green_hours,
            lookahead_hours=lookahead_hours,
        )
