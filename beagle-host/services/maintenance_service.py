from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from core.persistence.json_state_store import JsonStateStore


class MaintenanceService:
    def __init__(
        self,
        *,
        state_file: Path,
        list_nodes: Callable[[], list[dict[str, Any]]],
        list_vms: Callable[[], list[Any]],
        get_vm_config: Callable[[str, int], dict[str, Any]],
        migrate_vm: Callable[[int, str, bool, bool, str], dict[str, Any]],
        cold_restart_vm: Callable[[int, str, str], dict[str, Any]],
        service_name: str,
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._state_file = Path(state_file)
        self._store = JsonStateStore(self._state_file, default_factory=lambda: {"maintenance_nodes": []})
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
    def _normalize_ha_policy(value: Any) -> str:
        policy = str(value or "").strip().lower().replace("-", "_")
        if policy in {"restart", "fail_over", "disabled"}:
            return policy
        return "disabled"

    def _read_state(self) -> dict[str, Any]:
        payload = self._store.load()
        if isinstance(payload, dict):
            return payload
        return {"maintenance_nodes": []}

    def _write_state(self, payload: dict[str, Any]) -> None:
        self._store.save(payload)

    def maintenance_nodes(self) -> list[str]:
        state = self._read_state()
        nodes = state.get("maintenance_nodes") if isinstance(state.get("maintenance_nodes"), list) else []
        normalized: list[str] = []
        for item in nodes:
            node = str(item or "").strip()
            if node and node not in normalized:
                normalized.append(node)
        return sorted(normalized)

    def is_node_in_maintenance(self, node_name: str) -> bool:
        node = str(node_name or "").strip()
        return bool(node) and node in self.maintenance_nodes()

    def _set_node_maintenance(self, node_name: str, enabled: bool) -> None:
        node = str(node_name or "").strip()
        if not node:
            return
        nodes = self.maintenance_nodes()
        if enabled and node not in nodes:
            nodes.append(node)
        if not enabled:
            nodes = [item for item in nodes if item != node]
        self._write_state({"maintenance_nodes": sorted(nodes)})

    def _pick_target_node(self, source_node: str) -> str:
        source = str(source_node or "").strip()
        candidates: list[str] = []
        for item in self._list_nodes():
            if not isinstance(item, dict):
                continue
            node = str(item.get("name") or item.get("node") or "").strip()
            status = str(item.get("status") or "unknown").strip().lower()
            if not node or node == source:
                continue
            if self.is_node_in_maintenance(node):
                continue
            if status != "online":
                continue
            candidates.append(node)
        if not candidates:
            raise RuntimeError(f"no online non-maintenance target node available for {source}")
        return sorted(candidates)[0]

    def _plan_drain_actions(self, *, node_name: str) -> tuple[str, list[dict[str, Any]]]:
        source_node = str(node_name or "").strip()
        if not source_node:
            raise ValueError("node_name is required")

        known_nodes = {
            str(item.get("name") or item.get("node") or "").strip()
            for item in self._list_nodes()
            if isinstance(item, dict)
        }
        if source_node not in known_nodes:
            raise RuntimeError(f"node {source_node} not found")

        actions: list[dict[str, Any]] = []
        for vm in self._list_vms():
            vm_source = str(getattr(vm, "node", "") or "").strip()
            if vm_source != source_node:
                continue
            vmid = int(getattr(vm, "vmid", 0) or 0)
            vm_status = str(getattr(vm, "status", "unknown") or "unknown").strip().lower()
            vm_name = str(getattr(vm, "name", "") or f"vm-{vmid}")
            config = self._get_vm_config(vm_source, vmid)
            policy = self._normalize_ha_policy(config.get("ha_policy") if isinstance(config, dict) else "")

            action: dict[str, Any] = {
                "vmid": vmid,
                "vm_name": vm_name,
                "source_node": vm_source,
                "ha_policy": policy,
                "vm_status": vm_status,
            }

            if policy == "disabled":
                action.update({"handled": False, "result": "skipped", "reason": "ha_policy=disabled"})
                actions.append(action)
                continue

            target_node = self._pick_target_node(vm_source)
            action["target_node"] = target_node

            if policy == "restart":
                action.update({"handled": True, "result": "cold_restart"})
                actions.append(action)
                continue

            action.update({"handled": True, "result": "live_migration"})
            actions.append(action)

        return source_node, actions

    def preview_drain_node(self, *, node_name: str) -> dict[str, Any]:
        source_node, actions = self._plan_drain_actions(node_name=node_name)
        return self._envelope(
            node_name=source_node,
            maintenance_enabled=self.is_node_in_maintenance(source_node),
            evaluated_vm_count=len(actions),
            handled_vm_count=sum(1 for item in actions if item.get("handled") is True),
            actions=actions,
            maintenance_nodes=self.maintenance_nodes(),
        )

    def drain_node(self, *, node_name: str, requester_identity: str = "") -> dict[str, Any]:
        source_node = str(node_name or "").strip()
        _, planned_actions = self._plan_drain_actions(node_name=node_name)
        self._set_node_maintenance(source_node, True)
        actions: list[dict[str, Any]] = []

        for action in planned_actions:
            current = dict(action)
            if current.get("handled") is not True:
                actions.append(current)
                continue
            vmid = int(current.get("vmid") or 0)
            vm_source = str(current.get("source_node") or source_node).strip()
            target_node = str(current.get("target_node") or "").strip()
            policy = self._normalize_ha_policy(current.get("ha_policy"))
            vm_status = str(current.get("vm_status") or "unknown").strip().lower()

            if policy == "restart":
                details = self._cold_restart_vm(vmid, vm_source, target_node)
                current["details"] = details
                actions.append(current)
                continue

            live = vm_status == "running"
            try:
                details = self._migrate_vm(vmid, target_node, live, False, requester_identity)
                current["details"] = details
            except Exception as exc:
                details = self._cold_restart_vm(vmid, vm_source, target_node)
                current["details"] = details
                current["result"] = "cold_restart_fallback"
                current["fallback_reason"] = str(exc)
            actions.append(current)

        return self._envelope(
            node_name=source_node,
            maintenance_enabled=True,
            evaluated_vm_count=len(actions),
            handled_vm_count=sum(1 for item in actions if item.get("handled") is True),
            actions=actions,
            maintenance_nodes=self.maintenance_nodes(),
        )
