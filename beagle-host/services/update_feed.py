from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in str(value or "").replace("-", ".").split("."):
        if not part.isdigit():
            break
        parts.append(int(part))
    return tuple(parts)


def _version_lt(left: str, right: str) -> bool:
    left_tuple = _version_tuple(left)
    right_tuple = _version_tuple(right)
    if not left_tuple or not right_tuple:
        return False
    width = max(len(left_tuple), len(right_tuple))
    return left_tuple + (0,) * (width - len(left_tuple)) < right_tuple + (0,) * (width - len(right_tuple))


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
        endpoint_compatibility = (
            downloads_status.get("endpoint_compatibility")
            if isinstance(downloads_status.get("endpoint_compatibility"), dict)
            else {}
        )
        configured_channel = str(channel or profile.get("update_channel", "stable") or "stable").strip() or "stable"
        configured_behavior = str(profile.get("update_behavior", "prompt") or "prompt").strip() or "prompt"
        configured_version_pin = str(version_pin or profile.get("update_version_pin", "") or "").strip()
        enabled = bool(profile.get("update_enabled", True))
        installed = str(installed_version or "").strip()
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
        minimum_self_update_version = str(
            endpoint_compatibility.get("minimum_self_update_version")
            or downloads_status.get("minimum_self_update_version")
            or "8.0"
        ).strip()
        forced_reinstall = bool(endpoint_compatibility.get("reinstall_required", False))
        forced_migration = bool(endpoint_compatibility.get("migration_required", False))
        reinstall_reasons = endpoint_compatibility.get("reinstall_reasons", [])
        if not isinstance(reinstall_reasons, list):
            reinstall_reasons = []
        migration_reasons = endpoint_compatibility.get("migration_reasons", [])
        if not isinstance(migration_reasons, list):
            migration_reasons = []
        if installed and minimum_self_update_version and _version_lt(installed, minimum_self_update_version):
            forced_reinstall = True
            reinstall_reasons = [
                *[str(item) for item in reinstall_reasons],
                f"installed version is older than minimum self-update version {minimum_self_update_version}",
            ]
        update_path = "reinstall_required" if forced_reinstall else ("migration_required" if forced_migration else "self_update")
        return {
            "enabled": enabled,
            "channel": configured_channel,
            "behavior": configured_behavior,
            "version_pin": configured_version_pin,
            "installed_version": installed,
            "latest_version": target_version,
            "available": bool(
                enabled
                and target_version
                and payload_ready
                and installed != target_version
                and update_path == "self_update"
            ),
            "update_path": update_path,
            "self_update_supported": update_path == "self_update",
            "migration_required": update_path == "migration_required",
            "reinstall_required": update_path == "reinstall_required",
            "rebuild_recommended": update_path != "self_update",
            "minimum_self_update_version": minimum_self_update_version,
            "reinstall_reasons": [str(item) for item in reinstall_reasons],
            "migration_reasons": [str(item) for item in migration_reasons],
            "foundation_generation": str(endpoint_compatibility.get("foundation_generation") or downloads_status.get("foundation_generation") or "1"),
            "payload_filename": payload.get("filename", "") if payload_ready else "",
            "payload_url": payload.get("payload_url", "") if payload_ready else "",
            "payload_sha256": payload.get("payload_sha256", "") if payload_ready else "",
            "payload_pinned_pubkey": payload.get("payload_pinned_pubkey", "") if payload_ready else "",
            "payload_allow_insecure_tls": False,
            "sha256sums_url": payload.get("sha256sums_url", self._public_update_sha256sums_url()) if payload_ready else "",
            "published_latest_version": latest_version,
        }
