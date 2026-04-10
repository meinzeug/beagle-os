from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class UpdateFeedService:
    def __init__(
        self,
        *,
        downloads_status_file: Path,
        load_json_file: Callable[[Path, Any], Any],
        update_payload_metadata: Callable[[str], dict[str, str]],
        public_update_sha256sums_url: Callable[[], str],
    ) -> None:
        self._downloads_status_file = downloads_status_file
        self._load_json_file = load_json_file
        self._update_payload_metadata = update_payload_metadata
        self._public_update_sha256sums_url = public_update_sha256sums_url

    def build_update_feed(
        self,
        profile: dict[str, Any],
        *,
        installed_version: str = "",
        channel: str = "",
        version_pin: str = "",
    ) -> dict[str, Any]:
        downloads_status = self._load_json_file(self._downloads_status_file, {})
        latest_version = str(downloads_status.get("version", "")).strip()
        configured_channel = str(channel or profile.get("update_channel", "stable") or "stable").strip() or "stable"
        configured_behavior = str(profile.get("update_behavior", "prompt") or "prompt").strip() or "prompt"
        configured_version_pin = str(version_pin or profile.get("update_version_pin", "") or "").strip()
        enabled = bool(profile.get("update_enabled", True))
        target_version = configured_version_pin or latest_version
        payload = self._update_payload_metadata(target_version) if target_version else {
            "version": "",
            "filename": "",
            "payload_url": "",
            "payload_sha256": "",
            "sha256sums_url": self._public_update_sha256sums_url(),
            "payload_pinned_pubkey": "",
        }
        payload_ready = bool(payload.get("payload_url")) and bool(payload.get("payload_sha256"))
        return {
            "enabled": enabled,
            "channel": configured_channel,
            "behavior": configured_behavior,
            "version_pin": configured_version_pin,
            "installed_version": str(installed_version or "").strip(),
            "latest_version": target_version,
            "available": bool(
                enabled
                and target_version
                and payload_ready
                and str(installed_version or "").strip() != target_version
            ),
            "payload_filename": payload.get("filename", "") if payload_ready else "",
            "payload_url": payload.get("payload_url", "") if payload_ready else "",
            "payload_sha256": payload.get("payload_sha256", "") if payload_ready else "",
            "payload_pinned_pubkey": payload.get("payload_pinned_pubkey", "") if payload_ready else "",
            "payload_allow_insecure_tls": False,
            "sha256sums_url": payload.get("sha256sums_url", self._public_update_sha256sums_url()) if payload_ready else "",
            "published_latest_version": latest_version,
        }
