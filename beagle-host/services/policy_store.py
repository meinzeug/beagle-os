from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


class PolicyStoreService:
    def __init__(
        self,
        *,
        load_json_file: Callable[[Path, Any], Any],
        normalize_policy_payload: Callable[..., dict[str, Any]],
        policies_dir: Callable[[], Path],
        safe_slug: Callable[[str, str], str],
    ) -> None:
        self._load_json_file = load_json_file
        self._normalize_policy_payload = normalize_policy_payload
        self._policies_dir = policies_dir
        self._safe_slug = safe_slug

    def policy_path(self, name: str) -> Path:
        return self._policies_dir() / f"{self._safe_slug(name, 'policy')}.json"

    def save(self, payload: dict[str, Any], *, policy_name: str | None = None) -> dict[str, Any]:
        normalized = self._normalize_policy_payload(payload, policy_name=policy_name)
        self.policy_path(normalized["name"]).write_text(
            json.dumps(normalized, indent=2) + "\n", encoding="utf-8"
        )
        return normalized

    def load(self, name: str) -> dict[str, Any] | None:
        payload = self._load_json_file(self.policy_path(name), None)
        return payload if isinstance(payload, dict) else None

    def delete(self, name: str) -> bool:
        path = self.policy_path(name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list_all(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self._policies_dir().glob("*.json")):
            payload = self._load_json_file(path, None)
            if not isinstance(payload, dict):
                continue
            items.append(payload)
        items.sort(key=lambda item: (-int(item.get("priority", 0)), str(item.get("name", ""))))
        return items
