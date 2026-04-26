from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable


class VirtualizationReadSurfaceService:
    def __init__(
        self,
        *,
        build_cluster_inventory: Callable[[], dict[str, Any]] | None = None,
        find_vm: Callable[[int], Any | None],
        get_guest_network_interfaces: Callable[[int], list[dict[str, Any]]],
        get_ipam_zone_leases: Callable[[str], list[dict[str, Any]]],
        get_ipam_zones: Callable[[], dict[str, Any] | list[dict[str, Any]]],
        get_local_preflight: Callable[[], dict[str, Any]],
        get_storage_quota: Callable[[str], dict[str, Any]],
        get_vm_config: Callable[[str, int], dict[str, Any]],
        get_vm_firewall_profile: Callable[[str], Any | None],
        host_provider_kind: str,
        list_cluster_members: Callable[[], list[dict[str, Any]]],
        list_bridges_inventory: Callable[[str], list[dict[str, Any]]],
        list_firewall_profiles: Callable[[], list[dict[str, Any]]],
        list_gpu_inventory: Callable[[], list[dict[str, Any]]],
        list_nodes_inventory: Callable[[], list[dict[str, Any]]],
        list_storage_inventory: Callable[[], list[dict[str, Any]]],
        list_vms: Callable[[], list[Any]],
        service_name: str,
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._find_vm = find_vm
        self._build_cluster_inventory = build_cluster_inventory or (lambda: {})
        self._get_guest_network_interfaces = get_guest_network_interfaces
        self._get_ipam_zone_leases = get_ipam_zone_leases
        self._get_ipam_zones = get_ipam_zones
        self._get_local_preflight = get_local_preflight
        self._get_storage_quota = get_storage_quota
        self._get_vm_config = get_vm_config
        self._get_vm_firewall_profile = get_vm_firewall_profile
        self._host_provider_kind = str(host_provider_kind or "")
        self._list_cluster_members = list_cluster_members
        self._list_bridges_inventory = list_bridges_inventory
        self._list_firewall_profiles = list_firewall_profiles
        self._list_gpu_inventory = list_gpu_inventory
        self._list_nodes_inventory = list_nodes_inventory
        self._list_storage_inventory = list_storage_inventory
        self._list_vms = list_vms
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
            "label": str(item.get("label") or name).strip() or name,
            "provider_node_name": str(item.get("provider_node_name") or "").strip(),
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
                "provider_node_name": node["provider_node_name"],
                "status": node["status"],
                "provider": self._host_provider_kind,
            }
            for node in self._nodes_payload()
        ]

    def _nodes_payload(self) -> list[dict[str, Any]]:
        try:
            cluster_inventory = self._build_cluster_inventory()
        except Exception:
            cluster_inventory = {}
        cluster_nodes = cluster_inventory.get("nodes") if isinstance(cluster_inventory, dict) else []
        if isinstance(cluster_nodes, list) and cluster_nodes:
            nodes: list[dict[str, Any]] = []
            for item in cluster_nodes:
                if not isinstance(item, dict):
                    continue
                normalized = self._normalize_node(item)
                if normalized["id"]:
                    nodes.append(normalized)
            if nodes:
                return nodes

        nodes: list[dict[str, Any]] = []
        try:
            raw_nodes = self._list_nodes_inventory()
        except Exception:
            return nodes
        for item in raw_nodes:
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_node(item)
            if normalized["id"]:
                nodes.append(normalized)
        return nodes

    def _normalize_storage(self, item: dict[str, Any]) -> dict[str, Any]:
        storage_name = str(item.get("storage") or item.get("name") or "").strip()
        node_name = str(item.get("node") or "").strip()
        quota = {}
        if storage_name:
            try:
                quota = self._get_storage_quota(storage_name)
            except Exception:
                quota = {}
        quota_bytes = int((quota or {}).get("quota_bytes", 0) or 0)
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
            "quota_bytes": quota_bytes,
        }

    def _storage_payload(self) -> list[dict[str, Any]]:
        storage: list[dict[str, Any]] = []
        try:
            raw_storage = self._list_storage_inventory()
        except Exception:
            return storage
        for item in raw_storage:
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
        try:
            raw_bridges = self._list_bridges_inventory("")
        except Exception:
            return bridges
        for item in raw_bridges:
            if not isinstance(item, dict):
                continue
            normalized = self._normalize_bridge(item)
            if normalized["id"]:
                bridges.append(normalized)
        return bridges

    def _normalize_ipam_zone(self, zone_id: str, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "zone_id": str(zone_id or item.get("zone_id") or "").strip(),
            "subnet": str(item.get("subnet") or "").strip(),
            "dhcp_start": str(item.get("dhcp_start") or "").strip(),
            "dhcp_end": str(item.get("dhcp_end") or "").strip(),
            "bridge_name": str(item.get("bridge_name") or "").strip(),
        }

    def _ipam_zones_payload(self) -> list[dict[str, Any]]:
        try:
            raw = self._get_ipam_zones()
        except Exception:
            return []
        zones: list[dict[str, Any]] = []
        if isinstance(raw, dict):
            for zone_id, item in raw.items():
                if isinstance(item, dict):
                    normalized = self._normalize_ipam_zone(str(zone_id), item)
                    if normalized["zone_id"]:
                        zones.append(normalized)
            return zones
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                normalized = self._normalize_ipam_zone(str(item.get("zone_id") or ""), item)
                if normalized["zone_id"]:
                    zones.append(normalized)
        return zones

    def _zone_leases_payload(self, zone_id: str) -> list[dict[str, Any]]:
        normalized_zone = str(zone_id or "").strip()
        if not normalized_zone:
            return []
        try:
            raw_leases = self._get_ipam_zone_leases(normalized_zone)
        except Exception:
            return []
        leases: list[dict[str, Any]] = []
        for item in raw_leases if isinstance(raw_leases, list) else []:
            if isinstance(item, dict):
                payload = item
            else:
                payload = getattr(item, "__dict__", {}) or {}
            if not isinstance(payload, dict):
                continue
            leases.append(
                {
                    "ip_address": str(payload.get("ip_address") or "").strip(),
                    "mac_address": str(payload.get("mac_address") or "").strip(),
                    "vm_id": str(payload.get("vm_id") or "").strip(),
                    "zone_id": str(payload.get("zone_id") or normalized_zone).strip(),
                    "hostname": str(payload.get("hostname") or "").strip(),
                    "static": bool(payload.get("static")),
                    "issued_at": str(payload.get("issued_at") or "").strip(),
                    "expires_at": str(payload.get("expires_at") or "").strip(),
                }
            )
        return leases

    def _firewall_profiles_payload(self) -> list[dict[str, Any]]:
        try:
            raw_profiles = self._list_firewall_profiles()
        except Exception:
            return []
        profiles: list[dict[str, Any]] = []
        for item in raw_profiles if isinstance(raw_profiles, list) else []:
            if not isinstance(item, dict):
                continue
            profiles.append(
                {
                    "profile_id": str(item.get("profile_id") or "").strip(),
                    "name": str(item.get("name") or item.get("profile_id") or "").strip(),
                    "rule_count": int(item.get("rule_count") or 0),
                }
            )
        return profiles

    def _vms_payload(self) -> list[dict[str, Any]]:
        try:
            raw_vms = self._list_vms()
        except Exception:
            return []
        vms: list[dict[str, Any]] = []
        for item in raw_vms if isinstance(raw_vms, list) else []:
            vmid = int(getattr(item, "vmid", 0) or 0)
            node = str(getattr(item, "node", "") or "").strip()
            if vmid <= 0 or not node:
                continue
            vms.append(
                {
                    "vmid": vmid,
                    "node": node,
                    "name": str(getattr(item, "name", "") or f"vm-{vmid}"),
                    "status": str(getattr(item, "status", "") or "unknown"),
                }
            )
        return vms

    def _bridge_vm_usage(self) -> dict[str, list[dict[str, Any]]]:
        usage: dict[str, list[dict[str, Any]]] = {}
        for vm in self._vms_payload():
            try:
                config = self._get_vm_config(vm["node"], int(vm["vmid"]))
            except Exception:
                config = {}
            if not isinstance(config, dict):
                continue
            firewall_profile = None
            try:
                firewall_profile = self._get_vm_firewall_profile(str(vm["vmid"]))
            except Exception:
                firewall_profile = None
            firewall_profile_id = str(getattr(firewall_profile, "profile_id", "") or "").strip()
            firewall_profile_name = str(getattr(firewall_profile, "name", "") or firewall_profile_id).strip()
            for key, value in config.items():
                if not str(key).startswith("net"):
                    continue
                match = re.search(r"(?:^|,)bridge=([^,]+)", str(value or ""))
                if not match:
                    continue
                bridge_name = str(match.group(1) or "").strip()
                if not bridge_name:
                    continue
                usage.setdefault(bridge_name, []).append(
                    {
                        **vm,
                        "interface": str(key),
                        "firewall_profile_id": firewall_profile_id,
                        "firewall_profile_name": firewall_profile_name,
                    }
                )
        return usage

    def _bridge_zones_map(self) -> dict[str, list[dict[str, Any]]]:
        zones_by_bridge: dict[str, list[dict[str, Any]]] = {}
        for zone in self._ipam_zones_payload():
            bridge_name = str(zone.get("bridge_name") or zone.get("zone_id") or "").strip()
            if not bridge_name:
                continue
            zones_by_bridge.setdefault(bridge_name, []).append(zone)
        return zones_by_bridge

    def _gpus_payload(self) -> list[dict[str, Any]]:
        gpus: list[dict[str, Any]] = []
        try:
            raw_gpus = self._list_gpu_inventory()
        except Exception:
            return gpus
        for item in raw_gpus if isinstance(raw_gpus, list) else []:
            if not isinstance(item, dict):
                continue
            gpus.append(
                {
                    "node": str(item.get("node") or "").strip(),
                    "pci_address": str(item.get("pci_address") or "").strip(),
                    "model": str(item.get("model") or "").strip(),
                    "vendor": str(item.get("vendor") or "").strip(),
                    "driver": str(item.get("driver") or "").strip(),
                    "iommu_group": str(item.get("iommu_group") or "").strip(),
                    "iommu_group_size": int(item.get("iommu_group_size") or 0),
                    "passthrough_ready": bool(item.get("passthrough_ready")),
                    "status": str(item.get("status") or "unknown").strip() or "unknown",
                }
            )
        return gpus

    def _cluster_members_payload(self) -> list[dict[str, Any]]:
        members: list[dict[str, Any]] = []
        try:
            raw_members = self._list_cluster_members()
        except Exception:
            return members
        for item in raw_members if isinstance(raw_members, list) else []:
            if not isinstance(item, dict):
                continue
            members.append(
                {
                    "name": str(item.get("name") or "").strip(),
                    "api_url": str(item.get("api_url") or "").strip(),
                    "rpc_url": str(item.get("rpc_url") or "").strip(),
                    "status": str(item.get("status") or "unknown").strip(),
                    "enabled": item.get("enabled") is not False,
                    "local": bool(item.get("local")),
                    "display_name": str(item.get("display_name") or "").strip(),
                }
            )
        return members

    @staticmethod
    def _node_matches(node_name: str, *, candidates: list[str]) -> bool:
        normalized = str(node_name or "").strip()
        if not normalized:
            return False
        return normalized in {str(item or "").strip() for item in candidates if str(item or "").strip()}

    def _node_detail_payload(self, node_name: str) -> dict[str, Any] | None:
        target = str(node_name or "").strip()
        if not target:
            return None
        nodes = self._nodes_payload()
        node = next(
            (
                item for item in nodes
                if self._node_matches(
                    target,
                    candidates=[
                        item.get("name"),
                        item.get("label"),
                        item.get("id"),
                        item.get("provider_node_name"),
                    ],
                )
            ),
            None,
        )
        if node is None:
            return None

        members = self._cluster_members_payload()
        member = next(
            (
                item for item in members
                if self._node_matches(
                    target,
                    candidates=[
                        item.get("name"),
                        item.get("display_name"),
                    ],
                )
            ),
            None,
        )
        local_member = next((item for item in members if bool(item.get("local"))), None)
        is_local = bool(
            local_member
            and self._node_matches(
                str(local_member.get("name") or local_member.get("display_name") or "").strip(),
                candidates=[
                    node.get("name"),
                    node.get("label"),
                    node.get("id"),
                    node.get("provider_node_name"),
                ],
            )
        )

        storage = [
            item for item in self._storage_payload()
            if self._node_matches(target, candidates=[item.get("node")])
        ]
        bridges = [
            item for item in self._bridges_payload()
            if self._node_matches(target, candidates=[item.get("node")])
        ]
        gpus = [
            item for item in self._gpus_payload()
            if self._node_matches(target, candidates=[item.get("node")])
        ]

        preflight_checks = []
        if is_local:
            try:
                preflight_payload = self._get_local_preflight()
            except Exception:
                preflight_payload = {}
            preflight_checks = preflight_payload.get("checks") if isinstance(preflight_payload, dict) and isinstance(preflight_payload.get("checks"), list) else []

        services = {
            "kvm": "unknown",
            "libvirt": "unknown",
            "virsh": "unknown",
            "control_plane": "unknown",
            "ssh": "unknown",
            "rpc": str(member.get("status") or node.get("status") or "unknown") if member else str(node.get("status") or "unknown"),
        }
        service_messages: dict[str, str] = {}
        for check in preflight_checks:
            if not isinstance(check, dict):
                continue
            status = str(check.get("status") or "unknown").strip()
            message = str(check.get("message") or "").strip()
            name = str(check.get("name") or "").strip()
            if name == "kvm_device":
                services["kvm"] = status
                service_messages["kvm"] = message
            elif name == "libvirtd":
                services["libvirt"] = status
                service_messages["libvirt"] = message
            elif name == "virsh_connection":
                services["virsh"] = status
                service_messages["virsh"] = message
            elif name == "control_plane_api":
                services["control_plane"] = status
                service_messages["control_plane"] = message

        warnings: list[str] = []
        if str(node.get("status") or "").lower() != "online":
            warnings.append("Node ist aktuell nicht online oder nicht erreichbar.")
        if member and member.get("enabled") is False:
            warnings.append("Cluster-Member ist deaktiviert.")
        if not bridges:
            warnings.append("Keine Bridges fuer diesen Node erkannt.")
        if not storage:
            warnings.append("Keine Storage-Pools fuer diesen Node erkannt.")
        if is_local and services["kvm"] == "fail":
            warnings.append(service_messages.get("kvm") or "KVM fehlt auf diesem Host.")
        if is_local and services["libvirt"] == "fail":
            warnings.append(service_messages.get("libvirt") or "libvirt ist nicht aktiv.")
        if gpus and not any(bool(item.get("passthrough_ready")) for item in gpus):
            warnings.append("GPU vorhanden, aber keine ist aktuell passthrough-ready.")

        return self._envelope(
            node={
                **node,
                "local": is_local,
                "api_url": str(member.get("api_url") or "") if member else "",
                "rpc_url": str(member.get("rpc_url") or "") if member else "",
                "enabled": bool(member.get("enabled")) if member else True,
                "display_name": str(member.get("display_name") or "") if member else "",
            },
            services=services,
            service_messages=service_messages,
            preflight_checks=preflight_checks,
            storage=storage,
            bridges=bridges,
            gpus=gpus,
            warnings=warnings,
        )

    def _bridge_detail_payload(self, bridge_name: str) -> dict[str, Any] | None:
        target = str(bridge_name or "").strip()
        if not target:
            return None
        bridge = next(
            (item for item in self._bridges_payload() if self._node_matches(target, candidates=[item.get("name"), item.get("id")])),
            None,
        )
        if bridge is None:
            return None
        vm_usage = self._bridge_vm_usage().get(target, [])
        zones = self._bridge_zones_map().get(target, [])
        zones_with_leases = []
        lease_count = 0
        for zone in zones:
            leases = self._zone_leases_payload(str(zone.get("zone_id") or ""))
            lease_count += len(leases)
            zones_with_leases.append({**zone, "leases": leases, "lease_count": len(leases)})
        warnings: list[str] = []
        if not bridge.get("active"):
            warnings.append("Bridge ist aktuell nicht aktiv.")
        if not bridge.get("bridge_ports"):
            warnings.append("Bridge hat aktuell keine hinterlegten Uplink-Ports.")
        if not vm_usage:
            warnings.append("Keine lokalen VMs verwenden diese Bridge.")
        if not zones_with_leases:
            warnings.append("Keine IPAM-Zone ist dieser Bridge zugeordnet.")
        if not bridge.get("cidr") and not any(str(zone.get("subnet") or "").strip() for zone in zones_with_leases):
            warnings.append("Weder Bridge-CIDR noch IPAM-Subnetz sind fuer diese Bridge bekannt.")
        if any(not item.get("firewall_profile_id") for item in vm_usage):
            warnings.append("Mindestens eine VM auf dieser Bridge hat noch kein Firewall-Profil.")
        return self._envelope(
            bridge={
                **bridge,
                "vm_count": len(vm_usage),
                "ipam_zone_count": len(zones_with_leases),
                "lease_count": lease_count,
            },
            vms=vm_usage,
            ipam_zones=zones_with_leases,
            firewall_profiles=self._firewall_profiles_payload(),
            warnings=warnings,
        )

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
            gpus = self._gpus_payload()
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(
                    hosts=hosts,
                    nodes=nodes,
                    storage=storage,
                    bridges=bridges,
                    gpus=gpus,
                    host_count=len(hosts),
                    node_count=len(nodes),
                    storage_count=len(storage),
                    bridge_count=len(bridges),
                    gpu_count=len(gpus),
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

        match = re.match(r"^/api/v1/virtualization/bridges/(?P<bridge>[^/]+)/detail$", path)
        if match:
            payload = self._bridge_detail_payload(match.group("bridge"))
            if payload is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "bridge not found"})
            return self._json_response(HTTPStatus.OK, payload)

        if path == "/api/v1/virtualization/gpus":
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(gpus=self._gpus_payload()),
            )

        match = re.match(r"^/api/v1/virtualization/nodes/(?P<node>[^/]+)/detail$", path)
        if match:
            payload = self._node_detail_payload(match.group("node"))
            if payload is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "node not found"})
            return self._json_response(HTTPStatus.OK, payload)

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
