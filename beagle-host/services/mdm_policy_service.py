"""MDM Policy Service — per-device and per-group policy engine.

GoEnterprise Plan 02, Schritt 3
"""
from __future__ import annotations

import json
import re
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
    _VALID_CODECS = {"h264", "h265", "av1", "vp9"}
    _RESOLUTION_RE = re.compile(r"^(?P<width>\d{3,5})x(?P<height>\d{3,5})$")
    _POLICY_FIELDS = (
        "allowed_networks",
        "allowed_pools",
        "max_resolution",
        "allowed_codecs",
        "auto_update",
        "update_window_start_hour",
        "update_window_end_hour",
        "screen_lock_timeout_seconds",
    )

    def __init__(self, state_file: Path | None = None) -> None:
        self._state_file = state_file or self.STATE_FILE
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def validate_policy(self, policy: MDMPolicy) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []

        if not str(policy.policy_id or "").strip():
            errors.append("policy_id required")
        if not str(policy.name or "").strip():
            errors.append("name required")

        codecs = [str(item or "").strip().lower() for item in policy.allowed_codecs if str(item or "").strip()]
        invalid_codecs = sorted({codec for codec in codecs if codec not in self._VALID_CODECS})
        if invalid_codecs:
            errors.append("invalid codecs: " + ", ".join(invalid_codecs))

        for hour_name, value in {
            "update_window_start_hour": policy.update_window_start_hour,
            "update_window_end_hour": policy.update_window_end_hour,
        }.items():
            if int(value) < 0 or int(value) > 23:
                errors.append(f"{hour_name} must be between 0 and 23")

        if int(policy.update_window_start_hour) == int(policy.update_window_end_hour):
            errors.append("update window must not be zero-length")

        if int(policy.screen_lock_timeout_seconds) < 0:
            errors.append("screen_lock_timeout_seconds must be >= 0")
        elif int(policy.screen_lock_timeout_seconds) == 0:
            warnings.append("screen lock timeout disabled")

        max_resolution = str(policy.max_resolution or "").strip()
        if max_resolution:
            match = self._RESOLUTION_RE.match(max_resolution)
            if match is None:
                errors.append("max_resolution must match WIDTHxHEIGHT")
            else:
                width = int(match.group("width"))
                height = int(match.group("height"))
                if width < 640 or height < 480:
                    errors.append("max_resolution must be at least 640x480")
                if width > 7680 or height > 4320:
                    warnings.append("max_resolution exceeds typical 8K boundary")

        if not policy.allowed_pools:
            warnings.append("policy allows all pools")
        if not policy.allowed_networks:
            warnings.append("policy allows all networks")
        if not codecs:
            warnings.append("policy allows all codecs")
        if policy.auto_update and int(policy.update_window_start_hour) > int(policy.update_window_end_hour):
            warnings.append("update window crosses midnight")

        return {"ok": not errors, "errors": errors, "warnings": warnings}

    def create_policy(self, policy: MDMPolicy) -> MDMPolicy:
        validation = self.validate_policy(policy)
        if not validation["ok"]:
            raise ValueError("; ".join(validation["errors"]))
        if policy.policy_id in self._state["policies"]:
            raise ValueError(f"Policy {policy.policy_id!r} already exists")
        self._state["policies"][policy.policy_id] = asdict(policy)
        self._save()
        return policy

    def update_policy(self, policy: MDMPolicy) -> MDMPolicy:
        validation = self.validate_policy(policy)
        if not validation["ok"]:
            raise ValueError("; ".join(validation["errors"]))
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

    def delete_policy(self, policy_id: str) -> bool:
        if policy_id not in self._state["policies"]:
            return False
        del self._state["policies"][policy_id]
        self._state["device_assignments"] = {
            key: value
            for key, value in self._state["device_assignments"].items()
            if value != policy_id
        }
        self._state["group_assignments"] = {
            key: value
            for key, value in self._state["group_assignments"].items()
            if value != policy_id
        }
        self._save()
        return True

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

    def assign_to_devices(self, device_ids: list[str], policy_id: str) -> list[str]:
        if policy_id not in self._state["policies"]:
            raise KeyError(f"Policy {policy_id!r} not found")
        updated: list[str] = []
        for device_id in device_ids:
            normalized = str(device_id or "").strip()
            if not normalized:
                continue
            self._state["device_assignments"][normalized] = policy_id
            updated.append(normalized)
        self._save()
        return updated

    def clear_device_assignment(self, device_id: str) -> bool:
        removed = self._state["device_assignments"].pop(device_id, None)
        if removed is None:
            return False
        self._save()
        return True

    def clear_device_assignments(self, device_ids: list[str]) -> list[str]:
        cleared: list[str] = []
        for device_id in device_ids:
            normalized = str(device_id or "").strip()
            if not normalized:
                continue
            if self._state["device_assignments"].pop(normalized, None) is not None:
                cleared.append(normalized)
        self._save()
        return cleared

    def clear_group_assignment(self, group: str) -> bool:
        removed = self._state["group_assignments"].pop(group, None)
        if removed is None:
            return False
        self._save()
        return True

    def list_assignments(self) -> dict[str, dict[str, str]]:
        return {
            "device_assignments": dict(self._state["device_assignments"]),
            "group_assignments": dict(self._state["group_assignments"]),
        }

    def resolve_policy(self, device_id: str, group: str = "") -> MDMPolicy:
        """Effective policy: device-level overrides group-level, group overrides default."""
        return self.resolve_policy_with_source(device_id, group)[0]

    def resolve_policy_with_source(self, device_id: str, group: str = "") -> tuple[MDMPolicy, str, str]:
        """Return effective policy plus its source tuple (device|group|default, source_id)."""
        # Device-level assignment takes priority
        pid = self._state["device_assignments"].get(device_id)
        if pid:
            p = self.get_policy(pid)
            if p:
                return p, "device", str(device_id or "")
        if not pid and group:
            pid = self._state["group_assignments"].get(group)
        if pid:
            p = self.get_policy(pid)
            if p:
                return p, "group", str(group or "")
        return self.DEFAULT_POLICY, "default", "__default__"

    def describe_effective_policy_conflicts(self, device_id: str, group: str = "") -> list[str]:
        conflicts: list[str] = []
        device_policy_id = str(self._state["device_assignments"].get(device_id) or "").strip()
        group_policy_id = str(self._state["group_assignments"].get(group) or "").strip() if group else ""
        if device_policy_id and group_policy_id and device_policy_id != group_policy_id:
            conflicts.append(f"device assignment overrides group policy {group_policy_id}")
        return conflicts

    def build_effective_policy_diagnostics(self, device_id: str, group: str = "") -> dict[str, Any]:
        device_policy_id = str(self._state["device_assignments"].get(device_id) or "").strip()
        group_policy_id = str(self._state["group_assignments"].get(group) or "").strip() if group else ""
        default_policy = self.DEFAULT_POLICY
        group_policy = self.get_policy(group_policy_id) if group_policy_id else None
        device_policy = self.get_policy(device_policy_id) if device_policy_id else None
        effective_policy, effective_source_type, effective_source_id = self.resolve_policy_with_source(device_id, group)
        return {
            "effective_source_type": effective_source_type,
            "effective_source_id": effective_source_id,
            "default_policy": self._policy_snapshot(default_policy),
            "group_policy": self._policy_snapshot(group_policy, policy_id=group_policy_id or "__default__", source_id=group or ""),
            "device_policy": self._policy_snapshot(device_policy, policy_id=device_policy_id or "__default__", source_id=device_id or ""),
            "diffs": {
                "group_vs_default": self._policy_diff(default_policy, group_policy),
                "device_vs_group": self._policy_diff(group_policy or default_policy, device_policy),
                "effective_vs_default": self._policy_diff(default_policy, effective_policy),
            },
        }

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

    def _policy_snapshot(self, policy: MDMPolicy | None, *, policy_id: str = "", source_id: str = "") -> dict[str, Any] | None:
        if policy is None:
            return None
        payload = asdict(policy)
        payload["policy_id"] = str(policy.policy_id or policy_id or "")
        payload["source_id"] = str(source_id or "")
        payload["validation"] = self.validate_policy(policy)
        return payload

    def _policy_diff(self, baseline: MDMPolicy | None, overlay: MDMPolicy | None) -> list[dict[str, Any]]:
        if overlay is None:
            return []
        diffs: list[dict[str, Any]] = []
        baseline_data = asdict(baseline or self.DEFAULT_POLICY)
        overlay_data = asdict(overlay)
        for field_name in self._POLICY_FIELDS:
            baseline_value = baseline_data.get(field_name)
            overlay_value = overlay_data.get(field_name)
            if baseline_value != overlay_value:
                diffs.append(
                    {
                        "field": field_name,
                        "baseline": baseline_value,
                        "effective": overlay_value,
                    }
                )
        return diffs
