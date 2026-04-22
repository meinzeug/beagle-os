from __future__ import annotations

from typing import Any, Callable


class ClusterInventoryService:
    def __init__(
        self,
        *,
        build_vm_inventory: Callable[[], dict[str, Any]],
        host_provider_kind: str,
        list_nodes_inventory: Callable[[], list[dict[str, Any]]],
        service_name: str,
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._build_vm_inventory = build_vm_inventory
        self._host_provider_kind = str(host_provider_kind or "")
        self._list_nodes_inventory = list_nodes_inventory
        self._service_name = str(service_name or "beagle-control-plane")
        self._utcnow = utcnow
        self._version = str(version or "")

    def _envelope(self, **payload: Any) -> dict[str, Any]:
        return {
            "service": self._service_name,
            "version": self._version,
            "generated_at": self._utcnow(),
            "provider": self._host_provider_kind,
            **payload,
        }

    @staticmethod
    def _normalize_node(item: dict[str, Any]) -> dict[str, Any]:
        name = str(item.get("name") or item.get("node") or "").strip()
        status = str(item.get("status") or "unknown").strip().lower() or "unknown"
        return {
            "name": name,
            "status": status,
            "cpu": float(item.get("cpu") or 0),
            "mem": int(item.get("mem") or 0),
            "maxmem": int(item.get("maxmem") or 0),
            "maxcpu": int(item.get("maxcpu") or 0),
        }

    def build_inventory(self) -> dict[str, Any]:
        vm_inventory = self._build_vm_inventory()
        vms = vm_inventory.get("vms") if isinstance(vm_inventory, dict) else []
        vm_list = vms if isinstance(vms, list) else []

        vm_count_by_node: dict[str, int] = {}
        for vm in vm_list:
            if not isinstance(vm, dict):
                continue
            node_name = str(vm.get("node") or "").strip()
            if not node_name:
                continue
            vm_count_by_node[node_name] = int(vm_count_by_node.get(node_name, 0)) + 1

        nodes_by_name: dict[str, dict[str, Any]] = {}
        for item in self._list_nodes_inventory():
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_node(item)
            if not normalized["name"]:
                continue
            nodes_by_name[normalized["name"]] = normalized

        # Keep VMs visible even if their node is temporarily unreachable.
        for node_name in vm_count_by_node:
            if node_name not in nodes_by_name:
                nodes_by_name[node_name] = {
                    "name": node_name,
                    "status": "unreachable",
                    "cpu": 0.0,
                    "mem": 0,
                    "maxmem": 0,
                    "maxcpu": 0,
                }

        nodes = []
        for node_name in sorted(nodes_by_name.keys()):
            node = nodes_by_name[node_name]
            nodes.append(
                {
                    "name": node_name,
                    "status": str(node.get("status") or "unknown"),
                    "cpu": float(node.get("cpu") or 0),
                    "mem": int(node.get("mem") or 0),
                    "maxmem": int(node.get("maxmem") or 0),
                    "maxcpu": int(node.get("maxcpu") or 0),
                    "vm_count": int(vm_count_by_node.get(node_name, 0)),
                }
            )

        online = sum(1 for node in nodes if str(node.get("status") or "") == "online")
        unreachable = sum(1 for node in nodes if str(node.get("status") or "") in {"offline", "unreachable"})

        return self._envelope(
            nodes=nodes,
            node_count=len(nodes),
            node_online_count=online,
            node_unreachable_count=unreachable,
            vm_count=len(vm_list),
        )
