"""MDM Policy Service — per-device and per-group policy engine.

GoEnterprise Plan 02, Schritt 3
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MDMPolicy:
    policy_id: str
    name: str
    # Network
    allowed_networks: list[str] = field(default_factory=list)    # SSID/VLAN whitelist; empty = all
    # Pool access
    allowed_pools: list[str] = field(default_factory=list)       # empty = all pools
    # Stream limits
    max_resolution: str = ""          # e.g. "1920x1080"; empty = unlimited
    allowed_codecs: list[str] = field(default_factory=list)      # empty = all
    # Update behavior
    auto_update: bool = True
    update_window_start_hour: int = 2   # 0-23
    update_window_end_hour: int = 4     # 0-23
    # UX
    screen_lock_timeout_seconds: int = 0   # 0 = disabled


def mdm_policy_from_dict(d: dict[str, Any]) -> MDMPolicy:
    return MDMPolicy(
        policy_id=d["policy_id"],
        name=d.get("name", d["policy_id"]),
        allowed_networks=d.get("allowed_networks", []),
        allowed_pools=d.get("allowed_pools", []),
        max_resolution=d.get("max_resolution", ""),
        allowed_codecs=d.get("allowed_codecs", []),
        auto_update=bool(d.get("auto_update", True)),
        update_window_start_hour=int(d.get("update_window_start_hour", 2)),
        update_window_end_hour=int(d.get("update_window_end_hour", 4)),
        screen_lock_timeout_seconds=int(d.get("screen_lock_timeout_seconds", 0)),
    )


class MDMPolicyService:
    """MDM policy engine: define policies, assign to devices or groups."""

    STATE_FILE = Path("/var/lib/beagle/beagle-manager/mdm-policies.json")

    DEFAULT_POLICY = MDMPolicy(policy_id="__default__", name="Default")

    def __init__(self, state_file: Path | None = None) -> None:
        self._state_file = state_file or self.STATE_FILE
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_policy(self, policy: MDMPolicy) -> MDMPolicy:
        if policy.policy_id in self._state["policies"]:
            raise ValueError(f"Policy {policy.policy_id!r} already exists")
        self._state["policies"][policy.policy_id] = asdict(policy)
        self._save()
        return policy

    def update_policy(self, policy: MDMPolicy) -> MDMPolicy:
        if policy.policy_id not in self._state["policies"]:
            raise KeyError(f"Policy {policy.policy_id!r} not found")
        self._state["policies"][policy.policy_id] = asdict(policy)
        self._save()
        return policy

    def get_policy(self, policy_id: str) -> MDMPolicy | None:
        d = self._state["policies"].get(policy_id)
        return mdm_policy_from_dict(d) if d else None

    def list_policies(self) -> list[MDMPolicy]:
        return [mdm_policy_from_dict(d) for d in self._state["policies"].values()]

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    def assign_to_device(self, device_id: str, policy_id: str) -> None:
        if policy_id not in self._state["policies"]:
            raise KeyError(f"Policy {policy_id!r} not found")
        self._state["device_assignments"][device_id] = policy_id
        self._save()

    def assign_to_group(self, group: str, policy_id: str) -> None:
        if policy_id not in self._state["policies"]:
            raise KeyError(f"Policy {policy_id!r} not found")
        self._state["group_assignments"][group] = policy_id
        self._save()

    def resolve_policy(self, device_id: str, group: str = "") -> MDMPolicy:
        """Effective policy: device-level overrides group-level, group overrides default."""
        # Device-level assignment takes priority
        pid = self._state["device_assignments"].get(device_id)
        if not pid and group:
            pid = self._state["group_assignments"].get(group)
        if pid:
            p = self.get_policy(pid)
            if p:
                return p
        return self.DEFAULT_POLICY

    # ------------------------------------------------------------------
    # Enforcement helpers
    # ------------------------------------------------------------------

    def is_pool_allowed(self, device_id: str, pool_id: str, group: str = "") -> bool:
        policy = self.resolve_policy(device_id, group)
        if not policy.allowed_pools:
            return True
        return pool_id in policy.allowed_pools

    def is_codec_allowed(self, device_id: str, codec: str, group: str = "") -> bool:
        policy = self.resolve_policy(device_id, group)
        if not policy.allowed_codecs:
            return True
        return codec in policy.allowed_codecs

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if self._state_file.exists():
            return json.loads(self._state_file.read_text())
        return {"policies": {}, "device_assignments": {}, "group_assignments": {}}

    def _save(self) -> None:
        self._state_file.write_text(json.dumps(self._state, indent=2))
