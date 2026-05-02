#!/usr/bin/env python3
"""Apply endpoint enrollment config payloads to thin-client runtime files."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def _load_env_file(path: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    if not path.exists():
        return payload
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        payload[key.strip()] = value.strip()
    return payload


def _write_env_file(path: Path, payload: dict[str, str]) -> None:
    path.write_text("".join(f"{key}={value}\n" for key, value in payload.items()), encoding="utf-8")


def _json_env(value: Any) -> str:
    return json.dumps(str(value or ""))


def _write_enrollment_file(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f'{key}="{value}"\n' for key, value in payload.items()), encoding="utf-8")
    path.chmod(0o600)


def _remove_file_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def apply_enrollment_config(
    response_path: Path,
    config_path: Path,
    credentials_path: Path,
    enrollment_conf_path: Path | None = None,
) -> None:
    payload = json.loads(response_path.read_text(encoding="utf-8"))
    config = payload.get("config", {}) if isinstance(payload, dict) else {}
    if not isinstance(config, dict):
        config = {}
    enrollment_conf = enrollment_conf_path or Path(
        os.environ.get("BEAGLE_STREAM_ENROLLMENT_CONF", "/etc/beagle/enrollment.conf")
    )
    stream_mode = str(config.get("beagle_stream_mode", "") or "").strip().lower()
    broker_enabled = stream_mode == "broker"
    stream_allocation_id = str(config.get("beagle_stream_allocation_id", "") or "").strip()

    credentials = _load_env_file(credentials_path)
    for key, value in (
        ("PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN", config.get("beagle_manager_token", "")),
        ("PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_USERNAME", config.get("beagle_stream_server_username", "")),
        ("PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PASSWORD", config.get("beagle_stream_server_password", "")),
        ("PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PIN", config.get("beagle_stream_server_pin", "")),
        ("PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PINNED_PUBKEY", config.get("beagle_stream_server_pinned_pubkey", "")),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PRIVATE_KEY", config.get("egress_wg_private_key", "")),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PRESHARED_KEY", config.get("egress_wg_preshared_key", "")),
    ):
        credentials[key] = _json_env(value)
    credentials["PVE_THIN_CLIENT_BEAGLE_ENROLLMENT_TOKEN"] = _json_env("")
    _write_env_file(credentials_path, credentials)

    config_existing = _load_env_file(config_path)
    for key, value in (
        ("PVE_THIN_CLIENT_BEAGLE_DEVICE_ID", config.get("device_id", "")),
        ("PVE_THIN_CLIENT_CONNECTION_METHOD", "broker" if broker_enabled else "direct"),
        ("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST", "" if broker_enabled else config.get("beagle_stream_client_host", "")),
        ("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LOCAL_HOST", config.get("beagle_stream_client_local_host", "")),
        ("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PORT", config.get("beagle_stream_client_port", "")),
        ("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_APP", config.get("beagle_stream_client_app", "Desktop")),
        ("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BIN", "beagle-stream" if broker_enabled else config_existing.get("PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BIN", '"beagle-stream-client"').strip('"')),
        ("PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_API_URL", "" if broker_enabled else config.get("beagle_stream_server_api_url", "")),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_MODE", config.get("egress_mode", "full")),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_TYPE", config.get("egress_type", "wireguard")),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_INTERFACE", config.get("egress_interface", "wg-beagle")),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_DOMAINS", " ".join(config.get("egress_domains", []) or [])),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_RESOLVERS", " ".join(config.get("egress_resolvers", []) or [])),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_ALLOWED_IPS", " ".join(config.get("egress_allowed_ips", []) or [])),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_ADDRESS", config.get("egress_wg_address", "")),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_DNS", config.get("egress_wg_dns", "")),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PUBLIC_KEY", config.get("egress_wg_public_key", "")),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_ENDPOINT", config.get("egress_wg_endpoint", "")),
        ("PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE", config.get("egress_wg_persistent_keepalive", "25")),
        ("PVE_THIN_CLIENT_BEAGLE_UPDATE_ENABLED", "1" if config.get("update_enabled", True) else "0"),
        ("PVE_THIN_CLIENT_BEAGLE_UPDATE_CHANNEL", config.get("update_channel", "stable")),
        ("PVE_THIN_CLIENT_BEAGLE_UPDATE_BEHAVIOR", config.get("update_behavior", "prompt")),
        ("PVE_THIN_CLIENT_BEAGLE_UPDATE_FEED_URL", config.get("update_feed_url", "")),
        ("PVE_THIN_CLIENT_BEAGLE_UPDATE_VERSION_PIN", config.get("update_version_pin", "")),
        ("PVE_THIN_CLIENT_IDENTITY_HOSTNAME", config.get("identity_hostname", "")),
        ("PVE_THIN_CLIENT_IDENTITY_TIMEZONE", config.get("identity_timezone", "")),
        ("PVE_THIN_CLIENT_IDENTITY_LOCALE", config.get("identity_locale", "")),
        ("PVE_THIN_CLIENT_IDENTITY_KEYMAP", config.get("identity_keymap", "")),
        ("PVE_THIN_CLIENT_IDENTITY_CHROME_PROFILE", config.get("identity_chrome_profile", "default")),
        ("PVE_THIN_CLIENT_BEAGLE_USB_ENABLED", "1" if config.get("usb_enabled", True) else "0"),
        ("PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_HOST", config.get("usb_tunnel_host", "")),
        ("PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_USER", config.get("usb_tunnel_user", "beagle")),
        ("PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PORT", config.get("usb_tunnel_port", "")),
        ("PVE_THIN_CLIENT_BEAGLE_USB_ATTACH_HOST", config.get("usb_tunnel_attach_host", "")),
        ("PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PRIVATE_KEY_FILE", str(config_path.parent / "usb-tunnel.key")),
        ("PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_KNOWN_HOSTS_FILE", str(config_path.parent / "usb-tunnel-known_hosts")),
    ):
        config_existing[key] = _json_env(value)
    _write_env_file(config_path, config_existing)

    usb_key = str(config.get("usb_tunnel_private_key", "") or "")
    if usb_key:
        usb_key_path = config_path.parent / "usb-tunnel.key"
        usb_key_path.write_text(usb_key, encoding="utf-8")
        usb_key_path.chmod(0o600)

    usb_known_host = str(config.get("usb_tunnel_known_host", "") or "")
    if usb_known_host:
        known_hosts_path = config_path.parent / "usb-tunnel-known_hosts"
        known_hosts_path.write_text(usb_known_host.rstrip() + "\n", encoding="utf-8")
        known_hosts_path.chmod(0o644)

    if broker_enabled:
        _write_enrollment_file(
            enrollment_conf,
            {
                "control_plane": str(config.get("beagle_manager_url", "") or "").strip(),
                "enrollment_token": str(config.get("beagle_manager_token", "") or "").strip(),
                "device_id": str(config.get("device_id", "") or "").strip(),
                "pool_id": stream_allocation_id,
            },
        )
    else:
        _remove_file_if_exists(enrollment_conf)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) not in {3, 4}:
        raise SystemExit(
            "usage: apply_enrollment_config.py <response_json> <thinclient_conf> <credentials_env> [enrollment_conf]"
        )
    enrollment_conf = Path(args[3]) if len(args) == 4 else None
    apply_enrollment_config(Path(args[0]), Path(args[1]), Path(args[2]), enrollment_conf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
