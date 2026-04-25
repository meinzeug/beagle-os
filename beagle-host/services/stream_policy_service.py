"""Stream Policy Service — BeagleStream per-pool/per-user policy engine.

Manages stream parameters and network-mode enforcement:
  - max_fps, max_bitrate_mbps, resolution, codec
  - clipboard/audio/gamepad/usb redirect flags
  - network_mode: vpn_required | vpn_preferred | direct_allowed

GoEnterprise Plan 01, Schritt 4
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


NetworkMode = Literal["vpn_required", "vpn_preferred", "direct_allowed"]
Codec = Literal["h264", "h265", "av1"]


@dataclass
class StreamPolicy:
    policy_id: str
    name: str
    # Stream parameters
    max_fps: int = 60                       # 30 | 60 | 120 | 144
    max_bitrate_mbps: int = 20
    resolution: str = "1920x1080"           # e.g. "1920x1080", "2560x1440"
    codec: Codec = "h264"
    # Device redirects
    clipboard_redirect: bool = True
    audio_redirect: bool = True
    gamepad_redirect: bool = True
    usb_redirect: bool = False
    # Network / Zero-Trust mode
    network_mode: NetworkMode = "vpn_preferred"


def stream_policy_from_dict(d: dict[str, Any]) -> StreamPolicy:
    return StreamPolicy(
        policy_id=d["policy_id"],
        name=d.get("name", d["policy_id"]),
        max_fps=int(d.get("max_fps", 60)),
        max_bitrate_mbps=int(d.get("max_bitrate_mbps", 20)),
        resolution=d.get("resolution", "1920x1080"),
        codec=d.get("codec", "h264"),
        clipboard_redirect=bool(d.get("clipboard_redirect", True)),
        audio_redirect=bool(d.get("audio_redirect", True)),
        gamepad_redirect=bool(d.get("gamepad_redirect", True)),
        usb_redirect=bool(d.get("usb_redirect", False)),
        network_mode=d.get("network_mode", "vpn_preferred"),
    )


class StreamPolicyService:
    """CRUD + enforcement logic for BeagleStream policies."""

    STATE_FILE = Path("/var/lib/beagle/beagle-manager/stream-policies.json")

    # Default fallback policy when none assigned
    DEFAULT_POLICY = StreamPolicy(
        policy_id="__default__",
        name="Default",
        network_mode="vpn_preferred",
    )

    def __init__(self, state_file: Path | None = None) -> None:
        self._state_file = state_file or self.STATE_FILE
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_policy(self, policy: StreamPolicy) -> StreamPolicy:
        if policy.policy_id in self._state["policies"]:
            raise ValueError(f"Policy {policy.policy_id!r} already exists")
        self._validate(policy)
        self._state["policies"][policy.policy_id] = asdict(policy)
        self._save()
        return policy

    def update_policy(self, policy: StreamPolicy) -> StreamPolicy:
        if policy.policy_id not in self._state["policies"]:
            raise KeyError(f"Policy {policy.policy_id!r} not found")
        self._validate(policy)
        self._state["policies"][policy.policy_id] = asdict(policy)
        self._save()
        return policy

    def delete_policy(self, policy_id: str) -> bool:
        if policy_id not in self._state["policies"]:
            return False
        del self._state["policies"][policy_id]
        # Remove all assignments pointing to this policy
        self._state["assignments"] = {
            k: v for k, v in self._state["assignments"].items() if v != policy_id
        }
        self._save()
        return True

    def get_policy(self, policy_id: str) -> StreamPolicy | None:
        d = self._state["policies"].get(policy_id)
        return stream_policy_from_dict(d) if d else None

    def list_policies(self) -> list[StreamPolicy]:
        return [stream_policy_from_dict(d) for d in self._state["policies"].values()]

    # ------------------------------------------------------------------
    # Assignment (pool_id or user_id → policy_id)
    # ------------------------------------------------------------------

    def assign_policy(self, target_id: str, policy_id: str) -> None:
        """Assign a policy to a pool or user ID."""
        if policy_id not in self._state["policies"]:
            raise KeyError(f"Policy {policy_id!r} not found")
        self._state["assignments"][target_id] = policy_id
        self._save()

    def resolve_policy(self, target_id: str) -> StreamPolicy:
        """Return the effective policy for a pool/user, falling back to default."""
        pid = self._state["assignments"].get(target_id)
        if pid:
            p = self.get_policy(pid)
            if p:
                return p
        return self.DEFAULT_POLICY

    # ------------------------------------------------------------------
    # Enforcement: called by BeagleStream server stub
    # ------------------------------------------------------------------

    def check_connection_allowed(
        self,
        target_id: str,
        *,
        wireguard_active: bool,
    ) -> tuple[bool, str]:
        """
        Returns (allowed, reason).

        vpn_required  → wireguard_active must be True
        vpn_preferred → allowed regardless, but WG preferred
        direct_allowed → always allowed
        """
        policy = self.resolve_policy(target_id)
        if policy.network_mode == "vpn_required" and not wireguard_active:
            return False, "vpn_required: WireGuard tunnel not active (403)"
        return True, "ok"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _validate(self, policy: StreamPolicy) -> None:
        if policy.max_fps not in (30, 60, 120, 144):
            raise ValueError(f"max_fps must be 30/60/120/144, got {policy.max_fps}")
        if not (1 <= policy.max_bitrate_mbps <= 500):
            raise ValueError("max_bitrate_mbps out of range [1..500]")
        if policy.network_mode not in ("vpn_required", "vpn_preferred", "direct_allowed"):
            raise ValueError(f"Unknown network_mode: {policy.network_mode!r}")

    def _load(self) -> dict[str, Any]:
        if self._state_file.exists():
            return json.loads(self._state_file.read_text())
        return {"policies": {}, "assignments": {}}

    def _save(self) -> None:
        self._state_file.write_text(json.dumps(self._state, indent=2))
