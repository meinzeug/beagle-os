from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class EntitlementService:
    """Stores pool entitlements (user/group) in a small JSON state file."""

    def __init__(self, *, state_file: Path) -> None:
        self._state_file = Path(state_file)

    def _load_state(self) -> dict[str, Any]:
        path = self._state_file
        if not path.exists():
            return {"pools": {}}
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except (json.JSONDecodeError, OSError):
            return {"pools": {}}
        pools = data.get("pools")
        if not isinstance(pools, dict):
            return {"pools": {}}
        return {"pools": pools}

    def _save_state(self, state: dict[str, Any]) -> dict[str, Any]:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        return state

    @staticmethod
    def _normalize_pool_id(pool_id: str) -> str:
        value = str(pool_id or "").strip()
        if not value:
            raise ValueError("pool_id is required")
        return value

    @staticmethod
    def _normalize_entries(entries: list[str] | None) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for entry in entries or []:
            value = str(entry or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized

    def get_entitlements(self, pool_id: str) -> dict[str, Any]:
        pool = self._normalize_pool_id(pool_id)
        state = self._load_state()
        pool_entry = state["pools"].get(pool, {})
        users = self._normalize_entries(pool_entry.get("users", []))
        groups = self._normalize_entries(pool_entry.get("groups", []))
        return {
            "pool_id": pool,
            "users": users,
            "groups": groups,
        }

    def set_entitlements(self, pool_id: str, *, users: list[str] | None, groups: list[str] | None) -> dict[str, Any]:
        pool = self._normalize_pool_id(pool_id)
        state = self._load_state()
        users_normalized = self._normalize_entries(users)
        groups_normalized = self._normalize_entries(groups)
        state["pools"][pool] = {
            "users": users_normalized,
            "groups": groups_normalized,
        }
        self._save_state(state)
        return {
            "pool_id": pool,
            "users": users_normalized,
            "groups": groups_normalized,
        }

    def add_entitlement(self, pool_id: str, *, user_id: str = "", group_id: str = "") -> dict[str, Any]:
        if not str(user_id or "").strip() and not str(group_id or "").strip():
            raise ValueError("either user_id or group_id is required")
        current = self.get_entitlements(pool_id)
        users = list(current["users"])
        groups = list(current["groups"])
        if str(user_id or "").strip():
            users.append(str(user_id).strip())
        if str(group_id or "").strip():
            groups.append(str(group_id).strip())
        return self.set_entitlements(pool_id, users=users, groups=groups)

    def remove_entitlement(self, pool_id: str, *, user_id: str = "", group_id: str = "") -> dict[str, Any]:
        current = self.get_entitlements(pool_id)
        users = [item for item in current["users"] if item != str(user_id or "").strip()]
        groups = [item for item in current["groups"] if item != str(group_id or "").strip()]
        return self.set_entitlements(pool_id, users=users, groups=groups)

    def has_explicit_entitlements(self, pool_id: str) -> bool:
        current = self.get_entitlements(pool_id)
        return bool(current["users"] or current["groups"])

    def can_view_pool(
        self,
        pool_id: str,
        *,
        user_id: str = "",
        groups: list[str] | None = None,
        allow_unrestricted: bool = True,
    ) -> bool:
        if not self.has_explicit_entitlements(pool_id):
            return bool(allow_unrestricted)
        return self.is_entitled(pool_id, user_id=user_id, groups=groups)

    def is_entitled(self, pool_id: str, *, user_id: str = "", groups: list[str] | None = None) -> bool:
        current = self.get_entitlements(pool_id)
        user = str(user_id or "").strip()
        if user and user in current["users"]:
            return True
        group_set = {str(item or "").strip() for item in groups or [] if str(item or "").strip()}
        for group in current["groups"]:
            if group in group_set:
                return True
        return False
