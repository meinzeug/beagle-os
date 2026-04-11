from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


class ActionQueueService:
    def __init__(
        self,
        *,
        actions_dir: Callable[[], Path],
        load_json_file: Callable[[Path, Any], Any],
        safe_slug: Callable[[str, str], str],
    ) -> None:
        self._actions_dir = actions_dir
        self._load_json_file = load_json_file
        self._safe_slug = safe_slug

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
        self.queue_path(node, vmid).write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")

    def load_result(self, node: str, vmid: int) -> dict[str, Any] | None:
        payload = self._load_json_file(self.result_path(node, vmid), None)
        return payload if isinstance(payload, dict) else None

    def store_result(self, node: str, vmid: int, payload: dict[str, Any]) -> None:
        self.result_path(node, vmid).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

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
