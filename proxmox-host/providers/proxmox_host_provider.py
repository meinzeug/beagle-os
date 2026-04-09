from __future__ import annotations

from typing import Any, Callable


class ProxmoxHostProvider:
    def __init__(
        self,
        *,
        run_json: Callable[..., Any],
        run_text: Callable[..., str],
        cache_get: Callable[[str, float], Any] | None = None,
        cache_put: Callable[[str, Any], Any] | None = None,
    ) -> None:
        self._run_json = run_json
        self._run_text = run_text
        self._cache_get = cache_get
        self._cache_put = cache_put

    def _get_cached(self, key: str, ttl_seconds: float) -> Any:
        if not key or ttl_seconds <= 0 or self._cache_get is None:
            return None
        return self._cache_get(key, ttl_seconds)

    def _put_cached(self, key: str, value: Any) -> Any:
        if not key or self._cache_put is None:
            return value
        return self._cache_put(key, value)

    def next_vmid(self) -> int:
        raw = self._run_text(["pvesh", "get", "/cluster/nextid"])
        values = str(raw).strip().splitlines()
        if not values:
            raise RuntimeError("failed to determine next VMID")
        return int(values[-1])

    def list_storage_inventory(self) -> list[dict[str, Any]]:
        payload = self._run_json(["pvesh", "get", "/storage", "--output-format", "json"])
        return payload if isinstance(payload, list) else []

    def list_nodes(self) -> list[dict[str, Any]]:
        payload = self._run_json(["pvesh", "get", "/nodes", "--output-format", "json"])
        nodes: list[dict[str, Any]] = []
        if not isinstance(payload, list):
            return nodes
        for item in payload:
            node_name = str(item.get("node", "")).strip()
            if not node_name:
                continue
            nodes.append(
                {
                    "name": node_name,
                    "status": str(item.get("status", "unknown")).strip() or "unknown",
                    "cpu": float(item.get("cpu", 0) or 0),
                    "mem": int(item.get("mem", 0) or 0),
                    "maxmem": int(item.get("maxmem", 0) or 0),
                    "maxcpu": int(item.get("maxcpu", 0) or 0),
                }
            )
        return nodes

    def list_vms(
        self,
        *,
        refresh: bool = False,
        cache_key: str = "",
        cache_ttl_seconds: float = 0,
        vm_summary_factory: Callable[[dict[str, Any]], Any] | None = None,
    ) -> list[Any]:
        cached = None if refresh else self._get_cached(cache_key, cache_ttl_seconds)
        if isinstance(cached, list):
            return cached
        resources = self._run_json(["pvesh", "get", "/cluster/resources", "--type", "vm", "--output-format", "json"])
        vms: list[Any] = []
        if not isinstance(resources, list):
            return vms
        for item in resources:
            if item.get("type") != "qemu" or item.get("vmid") is None or not item.get("node"):
                continue
            if vm_summary_factory is not None:
                vms.append(vm_summary_factory(item))
                continue
            vms.append(item)
        vms = sorted(vms, key=self._vm_sort_key)
        return self._put_cached(cache_key, vms)

    @staticmethod
    def _vm_sort_key(vm: Any) -> int:
        if hasattr(vm, "vmid"):
            try:
                return int(getattr(vm, "vmid"))
            except (TypeError, ValueError):
                return 0
        if isinstance(vm, dict):
            try:
                return int(vm.get("vmid", 0))
            except (TypeError, ValueError):
                return 0
        return 0

    def get_vm_config(
        self,
        node: str,
        vmid: int,
        *,
        cache_key: str = "",
        cache_ttl_seconds: float = 0,
    ) -> dict[str, Any]:
        cached = self._get_cached(cache_key, cache_ttl_seconds)
        if isinstance(cached, dict):
            return cached
        payload = self._run_json(["pvesh", "get", f"/nodes/{node}/qemu/{int(vmid)}/config", "--output-format", "json"])
        if isinstance(payload, dict):
            return self._put_cached(cache_key, payload)
        return {}

    def get_guest_ipv4(
        self,
        vmid: int,
        *,
        cache_key: str = "",
        cache_ttl_seconds: float = 0,
        enable_lookup: bool = True,
        timeout_seconds: float | None = None,
    ) -> str:
        if not enable_lookup:
            return ""
        cached = self._get_cached(cache_key, cache_ttl_seconds)
        if isinstance(cached, str):
            return cached
        payload = self._run_json(
            ["qm", "guest", "cmd", str(int(vmid)), "network-get-interfaces"],
            timeout=timeout_seconds,
        )
        if not isinstance(payload, list):
            return ""
        for iface in payload:
            for address in iface.get("ip-addresses", []):
                ip = str(address.get("ip-address", ""))
                if address.get("ip-address-type") != "ipv4":
                    continue
                if not ip or ip.startswith("127.") or ip.startswith("169.254."):
                    continue
                return str(self._put_cached(cache_key, ip))
        return ""
