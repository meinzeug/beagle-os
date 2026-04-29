from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from core.persistence.json_state_store import JsonStateStore


class ActionQueueService:
    def __init__(
        self,
        *,
        actions_dir: Callable[[], Path],
        find_vm: Callable[[int], Any | None],
        load_json_file: Callable[[Path, Any], Any],
        monotonic: Callable[[], float] | None = None,
        safe_slug: Callable[[str, str], str],
        sleep: Callable[[float], None] | None = None,
        time_now_epoch: Callable[[], float],
        utcnow: Callable[[], str],
    ) -> None:
        self._actions_dir = actions_dir
        self._find_vm = find_vm
        self._load_json_file = load_json_file
        self._monotonic = monotonic or time.monotonic
        self._safe_slug = safe_slug
        self._sleep = sleep or time.sleep
        self._time_now_epoch = time_now_epoch
        self._utcnow = utcnow

    def queue_path(self, node: str, vmid: int) -> Path:
        safe_node = self._safe_slug(node, "unknown")
        return self._actions_dir() / f"{safe_node}-{int(vmid)}-queue.json"

    def result_path(self, node: str, vmid: int) -> Path:
        safe_node = self._safe_slug(node, "unknown")
        return self._actions_dir() / f"{safe_node}-{int(vmid)}-last-result.json"

    def load_queue(self, node: str, vmid: int) -> list[dict[str, Any]]:
        payload = self._load_json_file(self.queue_path(node, vmid), [])
        return payload if isinstance(payload, list) else []

    def save_queue(self, node: str, vmid: int, queue: list[dict[str, Any]]) -> None:
        JsonStateStore(self.queue_path(node, vmid), default_factory=list).save(queue)

    def queue_action(
        self,
        vm: Any,
        action_name: str,
        requested_by: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        queue = self.load_queue(vm.node, vm.vmid)
        action_id = f"{vm.node}-{vm.vmid}-{int(self._time_now_epoch())}-{len(queue) + 1}"
        payload = {
            "action_id": action_id,
            "action": action_name,
            "vmid": vm.vmid,
            "node": vm.node,
            "requested_at": self._utcnow(),
            "requested_by": requested_by,
        }
        if isinstance(params, dict) and params:
            payload["params"] = params
        queue.append(payload)
        self.save_queue(vm.node, vm.vmid, queue)
        return payload

    def queue_bulk_actions(
        self,
        vmids: list[int],
        action_name: str,
        requested_by: str,
    ) -> list[dict[str, Any]]:
        queued: list[dict[str, Any]] = []
        seen: set[int] = set()
        for vmid in vmids:
            if vmid in seen:
                continue
            seen.add(vmid)
            vm = self._find_vm(vmid)
            if vm is None:
                continue
            queued.append(self.queue_action(vm, action_name, requested_by))
        return queued

    def dequeue_actions(self, node: str, vmid: int) -> list[dict[str, Any]]:
        queue = self.load_queue(node, vmid)
        self.save_queue(node, vmid, [])
        return queue

    def load_result(self, node: str, vmid: int) -> dict[str, Any] | None:
        payload = self._load_json_file(self.result_path(node, vmid), None)
        return payload if isinstance(payload, dict) else None

    def wait_for_result(
        self,
        node: str,
        vmid: int,
        action_id: str,
        *,
        timeout_seconds: float,
    ) -> dict[str, Any] | None:
        deadline = self._monotonic() + max(1.0, timeout_seconds)
        while self._monotonic() < deadline:
            payload = self.load_result(node, vmid)
            if isinstance(payload, dict) and str(payload.get("action_id", "")).strip() == action_id:
                return payload
            self._sleep(1)
        return None

    def store_result(self, node: str, vmid: int, payload: dict[str, Any]) -> None:
        JsonStateStore(self.result_path(node, vmid), default_factory=dict).save(payload)

    def summarize_result(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {
                "action_id": "",
                "action": "",
                "ok": None,
                "message": "",
                "artifact_path": "",
                "stored_artifact_path": "",
                "stored_artifact_bundle_id": "",
                "stored_artifact_download_path": "",
                "stored_artifact_size": 0,
                "requested_at": "",
                "completed_at": "",
            }
        return {
            "action_id": payload.get("action_id", ""),
            "action": payload.get("action", ""),
            "busid": payload.get("busid", ""),
            "ok": payload.get("ok"),
            "message": payload.get("message", ""),
            "artifact_path": payload.get("artifact_path", ""),
            "stored_artifact_path": payload.get("stored_artifact_path", ""),
            "stored_artifact_bundle_id": payload.get("stored_artifact_bundle_id", ""),
            "stored_artifact_download_path": payload.get("stored_artifact_download_path", ""),
            "stored_artifact_size": payload.get("stored_artifact_size", 0),
            "requested_at": payload.get("requested_at", ""),
            "completed_at": payload.get("completed_at", ""),
        }
