from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable


class EndpointReportService:
    def __init__(
        self,
        *,
        endpoints_dir: Callable[[], Path],
        load_json_file: Callable[[Path, Any], Any],
        timestamp_age_seconds: Callable[[str], int | None],
    ) -> None:
        self._endpoints_dir = endpoints_dir
        self._load_json_file = load_json_file
        self._timestamp_age_seconds = timestamp_age_seconds

    def report_path(self, node: str, vmid: int) -> Path:
        safe_node = re.sub(r"[^A-Za-z0-9._-]+", "-", str(node or "unknown")).strip("-") or "unknown"
        return self._endpoints_dir() / f"{safe_node}-{int(vmid)}.json"

    def load(self, node: str, vmid: int) -> dict[str, Any] | None:
        payload = self._load_json_file(self.report_path(node, vmid), None)
        return payload if isinstance(payload, dict) else None

    def list_all(self) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        for path in sorted(self._endpoints_dir().glob("*.json")):
            payload = self._load_json_file(path, None)
            if not isinstance(payload, dict):
                continue
            payload["_path"] = str(path)
            reports.append(payload)
        reports.sort(key=lambda item: (str(item.get("node", "")), int(item.get("vmid", 0))))
        return reports

    def summarize(self, payload: dict[str, Any]) -> dict[str, Any]:
        health = payload.get("health", {}) if isinstance(payload.get("health"), dict) else {}
        session = payload.get("session", {}) if isinstance(payload.get("session"), dict) else {}
        runtime = payload.get("runtime", {}) if isinstance(payload.get("runtime"), dict) else {}
        egress = payload.get("egress", {}) if isinstance(payload.get("egress"), dict) else {}
        identity = payload.get("identity", {}) if isinstance(payload.get("identity"), dict) else {}
        software = payload.get("software", {}) if isinstance(payload.get("software"), dict) else {}
        install = payload.get("install", {}) if isinstance(payload.get("install"), dict) else {}
        update = payload.get("update", {}) if isinstance(payload.get("update"), dict) else {}
        usb = payload.get("usb", {}) if isinstance(payload.get("usb"), dict) else {}
        return {
            "endpoint_id": payload.get("endpoint_id", ""),
            "hostname": payload.get("hostname", ""),
            "profile_name": payload.get("profile_name", ""),
            "vmid": payload.get("vmid"),
            "node": payload.get("node", ""),
            "reported_at": payload.get("reported_at", ""),
            "stream_host": payload.get("stream_host", ""),
            "moonlight_port": payload.get("moonlight_port", ""),
            "moonlight_app": payload.get("moonlight_app", ""),
            "network_mode": payload.get("network_mode", ""),
            "egress_mode": payload.get("egress_mode", "") or egress.get("mode", ""),
            "egress_state": egress.get("state", ""),
            "egress_public_ip": egress.get("public_ip", ""),
            "identity_timezone": identity.get("timezone", ""),
            "identity_locale": identity.get("locale", ""),
            "identity_keymap": identity.get("keymap", ""),
            "identity_chrome_profile": identity.get("chrome_profile", ""),
            "ip_summary": health.get("ip_summary", ""),
            "external_ip": health.get("external_ip", ""),
            "virtualization_type": health.get("virtualization_type", ""),
            "networkmanager_state": health.get("networkmanager_state", ""),
            "autologin_state": health.get("autologin_state", ""),
            "prepare_state": health.get("prepare_state", ""),
            "guest_agent_state": health.get("guest_agent_state", ""),
            "moonlight_target_reachable": health.get("moonlight_target_reachable", ""),
            "sunshine_api_reachable": health.get("sunshine_api_reachable", ""),
            "runtime_binary": runtime.get("required_binary", ""),
            "runtime_binary_available": runtime.get("binary_available", ""),
            "last_launch_mode": session.get("mode", ""),
            "last_launch_target": session.get("target", ""),
            "last_launch_time": session.get("timestamp", ""),
            "software_version": software.get("version", "") or install.get("project_version", ""),
            "software_build_flavor": software.get("build_flavor", ""),
            "software_build_arch": software.get("build_arch", ""),
            "software_build_created_at": software.get("build_created_at", ""),
            "install_project_version": install.get("project_version", "") or software.get("version", ""),
            "install_source_kind": install.get("source_kind", ""),
            "install_payload_source_url": install.get("payload_source_url", ""),
            "install_filesystem_sha256": install.get("filesystem_squashfs_sha256", ""),
            "install_vmlinuz_sha256": install.get("vmlinuz_sha256", ""),
            "install_initrd_sha256": install.get("initrd_sha256", ""),
            "install_bootstrap_manifest_version": install.get("bootstrap_manifest_version", ""),
            "install_installed_at": install.get("installed_at", ""),
            "update_state": update.get("state", ""),
            "update_current_version": update.get("current_version", "")
            or install.get("project_version", "")
            or software.get("version", ""),
            "update_latest_version": update.get("latest_version", ""),
            "update_staged_version": update.get("staged_version", ""),
            "update_current_slot": update.get("current_slot", ""),
            "update_next_slot": update.get("next_slot", ""),
            "update_available": bool(update.get("available", False)),
            "update_pending_reboot": bool(update.get("pending_reboot", False)),
            "update_last_scan_at": update.get("last_scan_at", ""),
            "update_last_error": update.get("last_error", ""),
            "usb_tunnel_state": usb.get("tunnel_state", ""),
            "usb_tunnel_port": usb.get("tunnel_port", ""),
            "usb_device_count": int(usb.get("device_count", 0) or 0),
            "usb_bound_count": int(usb.get("bound_count", 0) or 0),
            "usb_devices": usb.get("devices", []) or [],
            "report_age_seconds": self._timestamp_age_seconds(payload.get("reported_at", "")),
        }
