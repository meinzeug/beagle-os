from __future__ import annotations

from typing import Any, Callable


class HaManagerService:
    def __init__(
        self,
        *,
        list_nodes: Callable[[], list[dict[str, Any]]],
        list_vms: Callable[[], list[Any]],
        get_vm_config: Callable[[str, int], dict[str, Any]],
        migrate_vm: Callable[[int, str, bool, bool, str], dict[str, Any]],
        cold_restart_vm: Callable[[int, str, str], dict[str, Any]],
        service_name: str,
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._list_nodes = list_nodes
        self._list_vms = list_vms
        self._get_vm_config = get_vm_config
        self._migrate_vm = migrate_vm
        self._cold_restart_vm = cold_restart_vm
        self._service_name = str(service_name or "beagle-control-plane")
        self._utcnow = utcnow
        self._version = str(version or "")

    def _envelope(self, **payload: Any) -> dict[str, Any]:
        return {
            "service": self._service_name,
            "version": self._version,
            "generated_at": self._utcnow(),
            **payload,
        }

    @staticmethod
    def normalize_ha_policy(value: Any) -> str:
        normalized = str(value or "").strip().lower().replace("-", "_")
        if normalized in {"disabled", "restart", "fail_over"}:
            return normalized
        return "disabled"

    def _pick_target_node(self, source_node: str) -> str:
        source = str(source_node or "").strip()
        candidates: list[str] = []
        for item in self._list_nodes():
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("node") or "").strip()
            status = str(item.get("status") or "unknown").strip().lower()
            if not name or name == source:
                continue
            if status != "online":
                continue
            candidates.append(name)
        if not candidates:
            raise RuntimeError(f"no online target node available for source node {source}")
        return sorted(candidates)[0]

    def reconcile_failed_node(self, *, failed_node: str, requester_identity: str = "") -> dict[str, Any]:
        source_node = str(failed_node or "").strip()
        if not source_node:
            raise ValueError("failed_node is required")

        actions: list[dict[str, Any]] = []
        for vm in self._list_vms():
            vm_node = str(getattr(vm, "node", "") or "").strip()
            if vm_node != source_node:
                continue

            vmid = int(getattr(vm, "vmid", 0) or 0)
            vm_status = str(getattr(vm, "status", "unknown") or "unknown").strip().lower()
            config = self._get_vm_config(vm_node, vmid)
            policy = self.normalize_ha_policy(config.get("ha_policy") if isinstance(config, dict) else "")

            action: dict[str, Any] = {
                "vmid": vmid,
                "vm_name": str(getattr(vm, "name", "") or f"vm-{vmid}"),
                "source_node": vm_node,
                "ha_policy": policy,
            }
            if policy == "disabled":
                action.update({"handled": False, "result": "skipped", "reason": "ha_policy=disabled"})
                actions.append(action)
                continue

            target_node = self._pick_target_node(vm_node)
            action["target_node"] = target_node

            if policy == "restart":
                restart_payload = self._cold_restart_vm(vmid, vm_node, target_node)
                action.update({"handled": True, "result": "cold_restart", "details": restart_payload})
                actions.append(action)
                continue

            live = vm_status == "running"
            try:
                migration_payload = self._migrate_vm(vmid, target_node, live, False, requester_identity)
                action.update({"handled": True, "result": "live_migration", "details": migration_payload})
            except Exception as exc:
                restart_payload = self._cold_restart_vm(vmid, vm_node, target_node)
                action.update(
                    {
                        "handled": True,
                        "result": "cold_restart_fallback",
                        "fallback_reason": str(exc),
                        "details": restart_payload,
                    }
                )
            actions.append(action)

        return self._envelope(
            failed_node=source_node,
            evaluated_vm_count=len(actions),
            handled_vm_count=sum(1 for item in actions if item.get("handled") is True),
            actions=actions,
        )
