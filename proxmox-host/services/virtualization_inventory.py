from __future__ import annotations

import re
from typing import Any, Callable


class VirtualizationInventoryService:
    def __init__(
        self,
        *,
        provider: Any,
        vm_summary_factory: Callable[[dict[str, Any]], Any],
        list_vms_cache_seconds: float,
        vm_config_cache_seconds: float,
        guest_ipv4_cache_seconds: float,
        enable_guest_ip_lookup: bool,
        guest_agent_timeout_seconds: float,
        default_bridge: str = "",
    ) -> None:
        self._provider = provider
        self._vm_summary_factory = vm_summary_factory
        self._list_vms_cache_seconds = float(list_vms_cache_seconds)
        self._vm_config_cache_seconds = float(vm_config_cache_seconds)
        self._guest_ipv4_cache_seconds = float(guest_ipv4_cache_seconds)
        self._enable_guest_ip_lookup = bool(enable_guest_ip_lookup)
        self._guest_agent_timeout_seconds = float(guest_agent_timeout_seconds)
        self._default_bridge = str(default_bridge or "").strip()

    def first_guest_ipv4(self, vmid: int) -> str:
        return self._provider.get_guest_ipv4(
            vmid,
            cache_key=f"guest-ipv4:{int(vmid)}",
            cache_ttl_seconds=self._guest_ipv4_cache_seconds,
            enable_lookup=self._enable_guest_ip_lookup,
            timeout_seconds=self._guest_agent_timeout_seconds,
        )

    def list_vms(self, *, refresh: bool = False) -> list[Any]:
        return self._provider.list_vms(
            refresh=refresh,
            cache_key="list-vms",
            cache_ttl_seconds=self._list_vms_cache_seconds,
            vm_summary_factory=self._vm_summary_factory,
        )

    def list_nodes_inventory(self) -> list[dict[str, Any]]:
        return self._provider.list_nodes()

    def get_vm_config(self, node: str, vmid: int) -> dict[str, Any]:
        return self._provider.get_vm_config(
            node,
            vmid,
            cache_key=f"vm-config:{node}:{int(vmid)}",
            cache_ttl_seconds=self._vm_config_cache_seconds,
        )

    def find_vm(self, vmid: int, *, refresh: bool = False) -> Any | None:
        return next((candidate for candidate in self.list_vms(refresh=refresh) if candidate.vmid == vmid), None)

    def config_bridge_names(self, config: dict[str, Any]) -> set[str]:
        bridges: set[str] = set()
        if not isinstance(config, dict):
            return bridges
        for key, value in config.items():
            if not str(key).startswith("net"):
                continue
            match = re.search(r"(?:^|,)bridge=([^,]+)", str(value or ""))
            if not match:
                continue
            bridge_name = str(match.group(1) or "").strip()
            if bridge_name:
                bridges.add(bridge_name)
        return bridges

    def list_bridge_inventory(self, node: str = "") -> list[str]:
        bridges: set[str] = set()
        if self._default_bridge:
            bridges.add(self._default_bridge)
        for vm in self.list_vms():
            if node and vm.node != node:
                continue
            bridges.update(self.config_bridge_names(self.get_vm_config(vm.node, vm.vmid)))
        return sorted(bridges)
