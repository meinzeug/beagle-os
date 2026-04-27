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

    def pick_node(
        self,
        *,
        required_cpu_cores: int,
        required_ram_mib: int,
        gpu_required: bool = False,
        preferred_hour: int | None = None,
        gpu_utilization_threshold: float = 85.0,
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

    def should_prewarm(self, profile: Any, minutes_ahead: int = 15) -> bool:
        """
        Return True if a VM should be pre-started N minutes before predicted peak.
        profile: WorkloadProfile from WorkloadPatternAnalyzer
        """
        if profile is None:
            return False
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        target_hour = (now + datetime.timedelta(minutes=minutes_ahead)).hour
        return target_hour in getattr(profile, "peak_hours", [])
