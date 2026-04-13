from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable


class VirtualizationReadSurfaceService:
    def __init__(
        self,
        *,
        find_vm: Callable[[int], Any | None],
        get_guest_network_interfaces: Callable[[int], list[dict[str, Any]]],
        get_vm_config: Callable[[str, int], dict[str, Any]],
        host_provider_kind: str,
        list_bridges_inventory: Callable[[str], list[dict[str, Any]]],
        list_nodes_inventory: Callable[[], list[dict[str, Any]]],
        list_storage_inventory: Callable[[], list[dict[str, Any]]],
        service_name: str,
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._find_vm = find_vm
        self._get_guest_network_interfaces = get_guest_network_interfaces
        self._get_vm_config = get_vm_config
        self._host_provider_kind = str(host_provider_kind or "")
        self._list_bridges_inventory = list_bridges_inventory
        self._list_nodes_inventory = list_nodes_inventory
        self._list_storage_inventory = list_storage_inventory
        self._service_name = str(service_name or "beagle-control-plane")
        self._utcnow = utcnow
        self._version = str(version or "")

    @staticmethod
    def _json_response(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

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
        return {
            "id": name,
            "name": name,
            "label": name,
            "status": str(item.get("status", "unknown")).strip() or "unknown",
            "cpu": float(item.get("cpu", 0) or 0),
            "mem": int(item.get("mem", 0) or 0),
            "maxmem": int(item.get("maxmem", 0) or 0),
            "maxcpu": int(item.get("maxcpu", 0) or 0),
        }

    def _hosts_payload(self) -> list[dict[str, Any]]:
        return [
            {
                "id": node["id"],
                "name": node["name"],
                "label": node["label"],
                "status": node["status"],
                "provider": self._host_provider_kind,
            }
            for node in self._nodes_payload()
        ]

    def _nodes_payload(self) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        for item in self._list_nodes_inventory():
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_node(item)
            if normalized["id"]:
                nodes.append(normalized)
        return nodes

    @staticmethod
    def _normalize_storage(item: dict[str, Any]) -> dict[str, Any]:
        storage_name = str(item.get("storage") or item.get("name") or "").strip()
        node_name = str(item.get("node") or "").strip()
        return {
            "id": storage_name,
            "name": storage_name,
            "node": node_name,
            "type": str(item.get("type", "")).strip(),
            "content": str(item.get("content", "")).strip(),
            "shared": bool(int(item.get("shared", 0) or 0)),
            "active": bool(int(item.get("active", 0) or 0)),
            "avail": int(item.get("avail", 0) or 0),
            "used": int(item.get("used", 0) or 0),
            "total": int(item.get("total", 0) or 0),
        }

    def _storage_payload(self) -> list[dict[str, Any]]:
        storage: list[dict[str, Any]] = []
        for item in self._list_storage_inventory():
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_storage(item)
            if normalized["id"]:
                storage.append(normalized)
        return storage

    @staticmethod
    def _normalize_bridge(item: dict[str, Any]) -> dict[str, Any]:
        name = str(item.get("name") or item.get("iface") or "").strip()
        return {
            "id": name,
            "name": name,
            "node": str(item.get("node", "")).strip(),
            "type": str(item.get("type", "bridge")).strip() or "bridge",
            "active": bool(item.get("active", False)),
            "address": str(item.get("address", "") or "").strip(),
            "netmask": str(item.get("netmask", "") or "").strip(),
            "cidr": str(item.get("cidr", "") or "").strip(),
            "bridge_ports": str(item.get("bridge_ports", "") or "").strip(),
            "autostart": bool(item.get("autostart", False)),
        }

    def _bridges_payload(self) -> list[dict[str, Any]]:
        bridges: list[dict[str, Any]] = []
        for item in self._list_bridges_inventory(""):
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_bridge(item)
            if normalized["id"]:
                bridges.append(normalized)
        return bridges

    def _vm_config_payload(self, vmid: int) -> dict[str, Any] | None:
        vm = self._find_vm(vmid)
        if vm is None:
            return None
        config = self._get_vm_config(vm.node, vm.vmid)
        payload = dict(config) if isinstance(config, dict) else {}
        payload.setdefault("vmid", int(vm.vmid))
        payload.setdefault("node", str(vm.node))
        payload.setdefault("name", str(getattr(vm, "name", "") or f"vm-{vm.vmid}"))
        payload.setdefault("status", str(getattr(vm, "status", "") or "unknown"))
        payload.setdefault("tags", str(getattr(vm, "tags", "") or ""))
        return payload

    def _vm_interfaces_payload(self, vmid: int) -> list[dict[str, Any]] | None:
        vm = self._find_vm(vmid)
        if vm is None:
            return None
        payload = self._get_guest_network_interfaces(vmid)
        return payload if isinstance(payload, list) else []

    def route_get(self, path: str) -> dict[str, Any] | None:
        if path == "/api/v1/virtualization/overview":
            nodes = self._nodes_payload()
            storage = self._storage_payload()
            hosts = self._hosts_payload()
            bridges = self._bridges_payload()
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(
                    hosts=hosts,
                    nodes=nodes,
                    storage=storage,
                    bridges=bridges,
                    host_count=len(hosts),
                    node_count=len(nodes),
                    storage_count=len(storage),
                    bridge_count=len(bridges),
                ),
            )

        if path == "/api/v1/virtualization/hosts":
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(hosts=self._hosts_payload()),
            )

        if path == "/api/v1/virtualization/nodes":
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(nodes=self._nodes_payload()),
            )

        if path == "/api/v1/virtualization/storage":
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(storage=self._storage_payload()),
            )

        if path == "/api/v1/virtualization/bridges":
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(bridges=self._bridges_payload()),
            )

        match = re.match(r"^/api/v1/virtualization/vms/(?P<vmid>\d+)/config$", path)
        if match:
            payload = self._vm_config_payload(int(match.group("vmid")))
            if payload is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(config=payload),
            )

        match = re.match(r"^/api/v1/virtualization/vms/(?P<vmid>\d+)/interfaces$", path)
        if match:
            payload = self._vm_interfaces_payload(int(match.group("vmid")))
            if payload is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(interfaces=payload),
            )

        return None
