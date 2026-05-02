"""Policy payload normalization helpers.

This service owns the canonical normalization of policy selector/profile
payloads before they are persisted or applied. The control plane keeps a thin
wrapper so existing helper signatures stay stable while policy contract logic
leaves the entrypoint.
"""

from __future__ import annotations

from typing import Any, Callable


class PolicyNormalizationService:
    def __init__(
        self,
        *,
        listify: Callable[[Any], list[str]],
        truthy: Callable[..., bool],
        utcnow: Callable[[], str],
    ) -> None:
        self._listify = listify
        self._truthy = truthy
        self._utcnow = utcnow

    def normalize_payload(
        self,
        payload: dict[str, Any],
        *,
        policy_name: str | None = None,
    ) -> dict[str, Any]:
        name = str(policy_name or payload.get("name", "")).strip()
        if not name:
            raise ValueError("missing policy name")
        selector = payload.get("selector", {})
        if selector is None:
            selector = {}
        if not isinstance(selector, dict):
            raise ValueError("selector must be an object")
        profile = payload.get("profile", {})
        if profile is None:
            profile = {}
        if not isinstance(profile, dict):
            raise ValueError("profile must be an object")
        priority = int(payload.get("priority", 100))
        enabled = bool(payload.get("enabled", True))
        return {
            "name": name,
            "enabled": enabled,
            "priority": priority,
            "selector": self._normalize_selector(selector),
            "profile": self._normalize_profile(profile),
            "updated_at": self._utcnow(),
        }

    def _normalize_selector(self, selector: dict[str, Any]) -> dict[str, Any]:
        return {
            "vmid": int(selector["vmid"]) if str(selector.get("vmid", "")).strip() else None,
            "node": str(selector.get("node", "")).strip(),
            "role": str(selector.get("role", "")).strip(),
            "tags_any": [str(item).strip() for item in selector.get("tags_any", []) if str(item).strip()],
            "tags_all": [str(item).strip() for item in selector.get("tags_all", []) if str(item).strip()],
        }

    def _normalize_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "expected_profile_name": str(profile.get("expected_profile_name", "")).strip(),
            "network_mode": str(profile.get("network_mode", "")).strip(),
            "beagle_stream_client_app": str(profile.get("beagle_stream_client_app", "")).strip(),
            "stream_host": str(profile.get("stream_host", "")).strip(),
            "beagle_stream_client_local_host": str(profile.get("beagle_stream_client_local_host", "")).strip(),
            "beagle_stream_client_port": str(profile.get("beagle_stream_client_port", "")).strip(),
            "beagle_stream_server_api_url": str(profile.get("beagle_stream_server_api_url", "")).strip(),
            "update_enabled": self._truthy(profile.get("update_enabled", True), default=True),
            "update_channel": str(profile.get("update_channel", "")).strip(),
            "update_behavior": str(profile.get("update_behavior", "")).strip(),
            "update_feed_url": str(profile.get("update_feed_url", "")).strip(),
            "update_version_pin": str(profile.get("update_version_pin", "")).strip(),
            "beagle_stream_client_resolution": str(profile.get("beagle_stream_client_resolution", "")).strip(),
            "beagle_stream_client_fps": str(profile.get("beagle_stream_client_fps", "")).strip(),
            "beagle_stream_client_bitrate": str(profile.get("beagle_stream_client_bitrate", "")).strip(),
            "beagle_stream_client_video_codec": str(profile.get("beagle_stream_client_video_codec", "")).strip(),
            "beagle_stream_client_video_decoder": str(profile.get("beagle_stream_client_video_decoder", "")).strip(),
            "beagle_stream_client_audio_config": str(profile.get("beagle_stream_client_audio_config", "")).strip(),
            "egress_mode": str(profile.get("egress_mode", "")).strip(),
            "egress_type": str(profile.get("egress_type", "")).strip(),
            "egress_interface": str(profile.get("egress_interface", "")).strip(),
            "egress_domains": self._listify(profile.get("egress_domains", [])),
            "egress_resolvers": self._listify(profile.get("egress_resolvers", [])),
            "egress_allowed_ips": self._listify(profile.get("egress_allowed_ips", [])),
            "egress_wg_address": str(profile.get("egress_wg_address", "")).strip(),
            "egress_wg_dns": str(profile.get("egress_wg_dns", "")).strip(),
            "egress_wg_public_key": str(profile.get("egress_wg_public_key", "")).strip(),
            "egress_wg_endpoint": str(profile.get("egress_wg_endpoint", "")).strip(),
            "egress_wg_private_key": str(profile.get("egress_wg_private_key", "")).strip(),
            "egress_wg_preshared_key": str(profile.get("egress_wg_preshared_key", "")).strip(),
            "egress_wg_persistent_keepalive": str(profile.get("egress_wg_persistent_keepalive", "")).strip(),
            "identity_hostname": str(profile.get("identity_hostname", "")).strip(),
            "identity_timezone": str(profile.get("identity_timezone", "")).strip(),
            "identity_locale": str(profile.get("identity_locale", "")).strip(),
            "identity_keymap": str(profile.get("identity_keymap", "")).strip(),
            "identity_chrome_profile": str(profile.get("identity_chrome_profile", "")).strip(),
            "beagle_role": str(profile.get("beagle_role", "")).strip(),
            "assigned_target": self._normalize_assigned_target(profile.get("assigned_target")),
        }

    @staticmethod
    def _normalize_assigned_target(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        return {
            "vmid": int(value.get("vmid")) if str(value.get("vmid", "")).strip() else None,
            "node": str(value.get("node", "")).strip(),
        }
