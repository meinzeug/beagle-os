from __future__ import annotations

from urllib.parse import urlparse
from typing import Any, Callable


class ClusterInventoryService:
    def __init__(
        self,
        *,
        build_vm_inventory: Callable[[], dict[str, Any]],
        host_provider_kind: str,
        list_remote_inventories: Callable[[], list[dict[str, Any]]] | None = None,
        list_cluster_members: Callable[[], list[dict[str, Any]]] | None = None,
        list_nodes_inventory: Callable[[], list[dict[str, Any]]],
        service_name: str,
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._build_vm_inventory = build_vm_inventory
        self._host_provider_kind = str(host_provider_kind or "")
        self._list_remote_inventories = list_remote_inventories or (lambda: [])
        self._list_cluster_members = list_cluster_members or (lambda: [])
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
            "label": str(item.get("label") or "").strip(),
            "provider_node_name": str(item.get("provider_node_name") or "").strip(),
            "status": status,
            "cpu": float(item.get("cpu") or 0),
            "mem": int(item.get("mem") or 0),
            "maxmem": int(item.get("maxmem") or 0),
            "maxcpu": int(item.get("maxcpu") or 0),
        }

    @staticmethod
    def _canonical_member_name(member_name: str, nodes: list[dict[str, Any]]) -> dict[str, str]:
        normalized_member = str(member_name or "").strip()
        if not normalized_member or len(nodes) != 1:
            return {}
        only_name = str(nodes[0].get("name") or nodes[0].get("node") or "").strip()
        if not only_name or only_name == normalized_member:
            return {}
        return {only_name: normalized_member}

    @staticmethod
    def _canonicalize_vm_node(vm: dict[str, Any], alias_map: dict[str, str]) -> dict[str, Any]:
        if not isinstance(vm, dict):
            return {}
        payload = dict(vm)
        node_name = str(payload.get("node") or "").strip()
        if node_name and node_name in alias_map:
            payload["node"] = alias_map[node_name]
        return payload

    @staticmethod
    def _canonicalize_node_item(item: dict[str, Any], alias_map: dict[str, str]) -> dict[str, Any]:
        if not isinstance(item, dict):
            return {}
        payload = dict(item)
        original_name = str(payload.get("name") or payload.get("node") or "").strip()
        canonical_name = alias_map.get(original_name, original_name)
        if canonical_name and canonical_name != original_name:
            payload["name"] = canonical_name
            payload["label"] = canonical_name
            payload["provider_node_name"] = original_name
        elif canonical_name and not str(payload.get("label") or "").strip():
            payload["label"] = canonical_name
        return payload

    @staticmethod
    def _member_name_from_snapshot(snapshot: dict[str, Any]) -> str:
        if not isinstance(snapshot, dict):
            return ""
        return str(snapshot.get("local_member_name") or snapshot.get("member_name") or "").strip()

    @staticmethod
    def _hostname_from_url(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            parsed = urlparse(raw)
            return str(parsed.hostname or "").strip().lower()
        except ValueError:
            return ""

    def build_inventory(self) -> dict[str, Any]:
        vm_inventory = self._build_vm_inventory()
        vms = vm_inventory.get("vms") if isinstance(vm_inventory, dict) else []
        vm_list = vms if isinstance(vms, list) else []
        remote_snapshots = list(self._list_remote_inventories())
        cluster_members = [item for item in self._list_cluster_members() if isinstance(item, dict)]
        local_member_name = ""
        local_member_hostnames: set[str] = set()
        for member in cluster_members:
            if not bool(member.get("local")):
                continue
            local_member_name = str(member.get("name") or "").strip()
            api_hostname = self._hostname_from_url(str(member.get("api_url") or ""))
            if api_hostname:
                local_member_hostnames.add(api_hostname)
            rpc_hostname = self._hostname_from_url(str(member.get("rpc_url") or ""))
            if rpc_hostname:
                local_member_hostnames.add(rpc_hostname)
            break

        local_nodes_raw = [item for item in self._list_nodes_inventory() if isinstance(item, dict)]
        local_alias_map = self._canonical_member_name(local_member_name, local_nodes_raw)
        vm_list = [
            self._canonicalize_vm_node(item, local_alias_map)
            for item in vm_list
            if isinstance(item, dict)
        ]

        for snapshot in remote_snapshots:
            if not isinstance(snapshot, dict):
                continue
            remote_vms = snapshot.get("vms") if isinstance(snapshot.get("vms"), list) else []
            remote_nodes = snapshot.get("nodes") if isinstance(snapshot.get("nodes"), list) else []
            remote_alias_map = self._canonical_member_name(self._member_name_from_snapshot(snapshot), remote_nodes)
            for item in remote_vms:
                if isinstance(item, dict):
                    vm_list.append(self._canonicalize_vm_node(item, remote_alias_map))

        vm_count_by_node: dict[str, int] = {}
        for vm in vm_list:
            if not isinstance(vm, dict):
                continue
            node_name = str(vm.get("node") or "").strip()
            if not node_name:
                continue
            vm_count_by_node[node_name] = int(vm_count_by_node.get(node_name, 0)) + 1

        nodes_by_name: dict[str, dict[str, Any]] = {}
        for item in local_nodes_raw:
            normalized = self._normalize_node(self._canonicalize_node_item(item, local_alias_map))
            if not normalized["name"]:
                continue
            nodes_by_name[normalized["name"]] = normalized

        # Merge cluster members so every known cluster node appears even if
        # the local libvirt provider has no knowledge of remote nodes.
        for member in cluster_members:
            member_name = str(member.get("name") or "").strip()
            if not member_name:
                continue
            if member_name in nodes_by_name:
                # Update status from membership (health-checked) if provider
                # doesn't know about this node's current liveness.
                member_status = str(member.get("status") or "unknown").lower()
                if member_status in {"online", "unreachable", "offline"}:
                    nodes_by_name[member_name]["status"] = member_status
                if not str(nodes_by_name[member_name].get("label") or "").strip():
                    nodes_by_name[member_name]["label"] = member_name
            else:
                member_status = str(member.get("status") or "unknown").lower()
                nodes_by_name[member_name] = {
                    "name": member_name,
                    "label": member_name,
                    "provider_node_name": "",
                    "status": member_status,
                    "cpu": 0.0,
                    "mem": 0,
                    "maxmem": 0,
                    "maxcpu": 0,
                }

        for snapshot in remote_snapshots:
            if not isinstance(snapshot, dict):
                continue
            remote_nodes = snapshot.get("nodes") if isinstance(snapshot.get("nodes"), list) else []
            remote_alias_map = self._canonical_member_name(self._member_name_from_snapshot(snapshot), remote_nodes)
            for item in remote_nodes:
                if not isinstance(item, dict):
                    continue
                normalized = self._normalize_node(self._canonicalize_node_item(item, remote_alias_map))
                if not normalized["name"]:
                    continue
                nodes_by_name[normalized["name"]] = normalized

        # Keep VMs visible even if their node is temporarily unreachable.
        for node_name in vm_count_by_node:
            if node_name not in nodes_by_name:
                nodes_by_name[node_name] = {
                    "name": node_name,
                    "label": node_name,
                    "provider_node_name": "",
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
                    "label": str(node.get("label") or node_name),
                    "provider_node_name": str(node.get("provider_node_name") or ""),
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
            local_member_name=local_member_name,
            local_member_hostnames=sorted(local_member_hostnames),
        )
