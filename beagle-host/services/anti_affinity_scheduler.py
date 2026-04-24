"""Anti-affinity placement scheduler.

When a VM is a member of an anti-affinity group, pick_node() ensures that
no two VMs in the same group are placed on the same node.

Usage
-----
scheduler = AntiAffinityScheduler(
    list_vms=...,              # () -> list[vm-like objects with .vmid, .node, .name]
    get_vm_config=...,         # (node, vmid) -> dict  (must contain "anti_affinity_group" key)
    list_nodes=...,            # () -> list[dict with "name"/"node" and "status"]
    is_node_in_maintenance=...,# (node_name) -> bool
)

node = scheduler.pick_node(vmid=200, group="gpu-pool")
# → raises RuntimeError if all non-maintenance nodes already host a group member
"""
from __future__ import annotations

from typing import Any, Callable


class AntiAffinityScheduler:
    def __init__(
        self,
        *,
        list_vms: Callable[[], list[Any]],
        get_vm_config: Callable[[str, int], dict[str, Any]],
        list_nodes: Callable[[], list[dict[str, Any]]],
        is_node_in_maintenance: Callable[[str], bool],
    ) -> None:
        self._list_vms = list_vms
        self._get_vm_config = get_vm_config
        self._list_nodes = list_nodes
        self._is_node_in_maintenance = is_node_in_maintenance

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _online_nodes(self) -> list[str]:
        """Return sorted list of online, non-maintenance node names."""
        result: list[str] = []
        for item in self._list_nodes():
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("node") or "").strip()
            status = str(item.get("status") or "unknown").strip().lower()
            if not name:
                continue
            if status not in {"online", "active"}:
                continue
            if self._is_node_in_maintenance(name):
                continue
            result.append(name)
        return sorted(result)

    def _occupied_nodes_for_group(self, group: str, exclude_vmid: int | None = None) -> set[str]:
        """Return nodes that already host a VM in *group* (excluding *exclude_vmid*)."""
        occupied: set[str] = set()
        group = str(group or "").strip()
        if not group:
            return occupied
        for vm in self._list_vms():
            vmid = int(getattr(vm, "vmid", 0) or 0)
            if exclude_vmid is not None and vmid == exclude_vmid:
                continue
            node = str(getattr(vm, "node", "") or "").strip()
            if not node:
                continue
            try:
                config = self._get_vm_config(node, vmid)
            except Exception:
                continue
            vm_group = str((config or {}).get("anti_affinity_group") or "").strip()
            if vm_group == group:
                occupied.add(node)
        return occupied

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def pick_node(self, *, vmid: int, group: str) -> str:
        """Return the best node for *vmid* respecting anti-affinity *group*.

        Raises
        ------
        ValueError
            If *group* is empty.
        RuntimeError
            If no eligible node is available (all occupied or in maintenance).
        """
        group = str(group or "").strip()
        if not group:
            raise ValueError("anti_affinity_group must not be empty")

        online = self._online_nodes()
        if not online:
            raise RuntimeError("no online nodes available")

        occupied = self._occupied_nodes_for_group(group, exclude_vmid=int(vmid))
        free = [n for n in online if n not in occupied]
        if not free:
            raise RuntimeError(
                f"anti-affinity constraint violated: all online nodes already host "
                f"a member of group '{group}'"
            )
        # Deterministic: pick lexicographically first free node
        return free[0]

    def check_placement(self, *, vmid: int, node: str, group: str) -> dict[str, Any]:
        """Check whether placing *vmid* on *node* respects the anti-affinity *group*.

        Returns a dict:
          ok (bool)           – True if placement is allowed
          node (str)          – requested node
          group (str)         – anti-affinity group
          occupied_nodes (list[str]) – nodes that already host a group member
          conflict (bool)     – True if *node* is already occupied
        """
        group = str(group or "").strip()
        node = str(node or "").strip()
        occupied = self._occupied_nodes_for_group(group, exclude_vmid=int(vmid))
        conflict = node in occupied
        return {
            "ok": not conflict,
            "node": node,
            "group": group,
            "occupied_nodes": sorted(occupied),
            "conflict": conflict,
        }
