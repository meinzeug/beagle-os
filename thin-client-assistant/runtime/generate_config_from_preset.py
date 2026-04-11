#!/usr/bin/env python3
"""Generate runtime config dirs from thin-client preset env files."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from pathlib import Path


PRESET_TO_INSTALLER_ENV = {
    "MODE": ("PVE_THIN_CLIENT_PRESET_DEFAULT_MODE", "MOONLIGHT"),
    "AUTOSTART": ("PVE_THIN_CLIENT_PRESET_AUTOSTART", "1"),
    "PROFILE_NAME": ("PVE_THIN_CLIENT_PRESET_PROFILE_NAME", "default"),
    "HOSTNAME_VALUE": ("PVE_THIN_CLIENT_PRESET_HOSTNAME_VALUE", "beagle-os"),
    "CONNECTION_METHOD": (None, "direct"),
    "MOONLIGHT_HOST": ("PVE_THIN_CLIENT_PRESET_MOONLIGHT_HOST", ""),
    "MOONLIGHT_LOCAL_HOST": ("PVE_THIN_CLIENT_PRESET_MOONLIGHT_LOCAL_HOST", ""),
    "MOONLIGHT_PORT": ("PVE_THIN_CLIENT_PRESET_MOONLIGHT_PORT", ""),
    "MOONLIGHT_APP": ("PVE_THIN_CLIENT_PRESET_MOONLIGHT_APP", "Desktop"),
    "MOONLIGHT_BIN": ("PVE_THIN_CLIENT_PRESET_MOONLIGHT_BIN", "moonlight"),
    "MOONLIGHT_RESOLUTION": ("PVE_THIN_CLIENT_PRESET_MOONLIGHT_RESOLUTION", "auto"),
    "MOONLIGHT_FPS": ("PVE_THIN_CLIENT_PRESET_MOONLIGHT_FPS", "60"),
    "MOONLIGHT_BITRATE": ("PVE_THIN_CLIENT_PRESET_MOONLIGHT_BITRATE", "20000"),
    "MOONLIGHT_VIDEO_CODEC": ("PVE_THIN_CLIENT_PRESET_MOONLIGHT_VIDEO_CODEC", "H.264"),
    "MOONLIGHT_VIDEO_DECODER": ("PVE_THIN_CLIENT_PRESET_MOONLIGHT_VIDEO_DECODER", "auto"),
    "MOONLIGHT_AUDIO_CONFIG": ("PVE_THIN_CLIENT_PRESET_MOONLIGHT_AUDIO_CONFIG", "stereo"),
    "MOONLIGHT_ABSOLUTE_MOUSE": ("PVE_THIN_CLIENT_PRESET_MOONLIGHT_ABSOLUTE_MOUSE", "1"),
    "MOONLIGHT_QUIT_AFTER": ("PVE_THIN_CLIENT_PRESET_MOONLIGHT_QUIT_AFTER", "0"),
    "SUNSHINE_API_URL": ("PVE_THIN_CLIENT_PRESET_SUNSHINE_API_URL", ""),
    "PROXMOX_SCHEME": ("PVE_THIN_CLIENT_PRESET_PROXMOX_SCHEME", "https"),
    "PROXMOX_HOST": ("PVE_THIN_CLIENT_PRESET_PROXMOX_HOST", ""),
    "PROXMOX_PORT": ("PVE_THIN_CLIENT_PRESET_PROXMOX_PORT", "8006"),
    "PROXMOX_NODE": ("PVE_THIN_CLIENT_PRESET_PROXMOX_NODE", ""),
    "PROXMOX_VMID": ("PVE_THIN_CLIENT_PRESET_PROXMOX_VMID", ""),
    "PROXMOX_REALM": ("PVE_THIN_CLIENT_PRESET_PROXMOX_REALM", "pam"),
    "PROXMOX_VERIFY_TLS": ("PVE_THIN_CLIENT_PRESET_PROXMOX_VERIFY_TLS", "1"),
    "BEAGLE_MANAGER_URL": ("PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_URL", ""),
    "BEAGLE_MANAGER_PINNED_PUBKEY": ("PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_PINNED_PUBKEY", ""),
    "BEAGLE_ENROLLMENT_URL": ("PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_URL", ""),
    "BEAGLE_UPDATE_ENABLED": ("PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_ENABLED", "1"),
    "BEAGLE_UPDATE_CHANNEL": ("PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_CHANNEL", "stable"),
    "BEAGLE_UPDATE_BEHAVIOR": ("PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_BEHAVIOR", "prompt"),
    "BEAGLE_UPDATE_FEED_URL": ("PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_FEED_URL", ""),
    "BEAGLE_UPDATE_VERSION_PIN": ("PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_VERSION_PIN", ""),
    "BEAGLE_EGRESS_MODE": ("PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_MODE", "direct"),
    "BEAGLE_EGRESS_TYPE": ("PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_TYPE", ""),
    "BEAGLE_EGRESS_INTERFACE": ("PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_INTERFACE", "beagle-egress"),
    "BEAGLE_EGRESS_DOMAINS": ("PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_DOMAINS", ""),
    "BEAGLE_EGRESS_RESOLVERS": ("PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_RESOLVERS", "1.1.1.1 8.8.8.8"),
    "BEAGLE_EGRESS_ALLOWED_IPS": ("PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_ALLOWED_IPS", ""),
    "BEAGLE_EGRESS_WG_ADDRESS": ("PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ADDRESS", ""),
    "BEAGLE_EGRESS_WG_DNS": ("PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_DNS", ""),
    "BEAGLE_EGRESS_WG_PUBLIC_KEY": ("PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PUBLIC_KEY", ""),
    "BEAGLE_EGRESS_WG_ENDPOINT": ("PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ENDPOINT", ""),
    "BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE": ("PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE", "25"),
    "IDENTITY_HOSTNAME": ("PVE_THIN_CLIENT_PRESET_IDENTITY_HOSTNAME", ""),
    "IDENTITY_TIMEZONE": ("PVE_THIN_CLIENT_PRESET_IDENTITY_TIMEZONE", ""),
    "IDENTITY_LOCALE": ("PVE_THIN_CLIENT_PRESET_IDENTITY_LOCALE", ""),
    "IDENTITY_KEYMAP": ("PVE_THIN_CLIENT_PRESET_IDENTITY_KEYMAP", ""),
    "IDENTITY_CHROME_PROFILE": ("PVE_THIN_CLIENT_PRESET_IDENTITY_CHROME_PROFILE", "default"),
    "BEAGLE_USB_ENABLED": ("PVE_THIN_CLIENT_PRESET_BEAGLE_USB_ENABLED", "1"),
    "BEAGLE_USB_TUNNEL_HOST": ("PVE_THIN_CLIENT_PRESET_BEAGLE_USB_TUNNEL_HOST", ""),
    "BEAGLE_USB_TUNNEL_USER": ("PVE_THIN_CLIENT_PRESET_BEAGLE_USB_TUNNEL_USER", "beagle"),
    "BEAGLE_USB_TUNNEL_PORT": ("PVE_THIN_CLIENT_PRESET_BEAGLE_USB_TUNNEL_PORT", ""),
    "BEAGLE_USB_ATTACH_HOST": ("PVE_THIN_CLIENT_PRESET_BEAGLE_USB_ATTACH_HOST", "10.10.10.1"),
    "NETWORK_MODE": ("PVE_THIN_CLIENT_PRESET_NETWORK_MODE", "dhcp"),
    "NETWORK_INTERFACE": ("PVE_THIN_CLIENT_PRESET_NETWORK_INTERFACE", "eth0"),
    "NETWORK_STATIC_ADDRESS": ("PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_ADDRESS", ""),
    "NETWORK_STATIC_PREFIX": ("PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_PREFIX", "24"),
    "NETWORK_GATEWAY": ("PVE_THIN_CLIENT_PRESET_NETWORK_GATEWAY", ""),
    "NETWORK_DNS_SERVERS": ("PVE_THIN_CLIENT_PRESET_NETWORK_DNS_SERVERS", "1.1.1.1 8.8.8.8"),
    "CONNECTION_USERNAME": ("PVE_THIN_CLIENT_PRESET_PROXMOX_USERNAME", ""),
    "CONNECTION_PASSWORD": ("PVE_THIN_CLIENT_PRESET_PROXMOX_PASSWORD", ""),
    "CONNECTION_TOKEN": ("PVE_THIN_CLIENT_PRESET_PROXMOX_TOKEN", ""),
    "BEAGLE_MANAGER_TOKEN": (None, ""),
    "BEAGLE_ENROLLMENT_TOKEN": ("PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_TOKEN", ""),
    "BEAGLE_EGRESS_WG_PRIVATE_KEY": ("PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRIVATE_KEY", ""),
    "BEAGLE_EGRESS_WG_PRESHARED_KEY": ("PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRESHARED_KEY", ""),
    "SUNSHINE_USERNAME": ("PVE_THIN_CLIENT_PRESET_SUNSHINE_USERNAME", ""),
    "SUNSHINE_PASSWORD": ("PVE_THIN_CLIENT_PRESET_SUNSHINE_PASSWORD", ""),
    "SUNSHINE_PIN": ("PVE_THIN_CLIENT_PRESET_SUNSHINE_PIN", ""),
    "SUNSHINE_PINNED_PUBKEY": ("PVE_THIN_CLIENT_PRESET_SUNSHINE_PINNED_PUBKEY", ""),
    "SUNSHINE_SERVER_NAME": ("PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_NAME", ""),
    "SUNSHINE_SERVER_STREAM_PORT": ("PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_STREAM_PORT", ""),
    "SUNSHINE_SERVER_UNIQUEID": ("PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_UNIQUEID", ""),
    "SUNSHINE_SERVER_CERT_B64": ("PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_CERT_B64", ""),
    "RUNTIME_PASSWORD": ("PVE_THIN_CLIENT_PRESET_THINCLIENT_PASSWORD", ""),
}


def parse_preset_env(path: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        parts = shlex.split(line, comments=False, posix=True)
        if len(parts) != 1 or "=" not in parts[0]:
            continue
        key, value = parts[0].split("=", 1)
        payload[key.strip()] = value
    return payload


def build_installer_env(*, preset: dict[str, str], runtime_user: str) -> dict[str, str]:
    env = os.environ.copy()
    env["RUNTIME_USER"] = str(runtime_user or "thinclient")
    for output_key, (preset_key, default_value) in PRESET_TO_INSTALLER_ENV.items():
        if output_key == "RUNTIME_USER":
            continue
        if preset_key is None:
            env[output_key] = str(default_value or "")
            continue
        env[output_key] = str(preset.get(preset_key, default_value) or "")
    return env


def generate_config_dir_from_preset(
    *,
    preset_file: Path,
    state_dir: Path,
    installer_script: Path,
    runtime_user: str,
) -> None:
    preset = parse_preset_env(preset_file)
    state_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
    subprocess.run(
        [str(installer_script), str(state_dir)],
        check=True,
        env=build_installer_env(preset=preset, runtime_user=runtime_user),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate runtime config directory from preset env")
    parser.add_argument("--preset-file", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--installer-script", required=True)
    parser.add_argument("--runtime-user", default="thinclient")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    generate_config_dir_from_preset(
        preset_file=Path(args.preset_file),
        state_dir=Path(args.state_dir),
        installer_script=Path(args.installer_script),
        runtime_user=args.runtime_user,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
