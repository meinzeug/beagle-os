#!/usr/bin/env python3
"""Generate runtime config dirs from thin-client preset env files."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_ENV_DEFAULTS_FILE = REPO_ROOT / "thin-client-assistant" / "installer" / "env-defaults.json"

PRESET_TO_INSTALLER_ENV = {
    "MODE": "PVE_THIN_CLIENT_PRESET_DEFAULT_MODE",
    "AUTOSTART": "PVE_THIN_CLIENT_PRESET_AUTOSTART",
    "PROFILE_NAME": "PVE_THIN_CLIENT_PRESET_PROFILE_NAME",
    "HOSTNAME_VALUE": "PVE_THIN_CLIENT_PRESET_HOSTNAME_VALUE",
    "CONNECTION_METHOD": None,
    "BEAGLE_STREAM_CLIENT_HOST": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_HOST",
    "BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST",
    "BEAGLE_STREAM_CLIENT_LOCAL_HOST": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_LOCAL_HOST",
    "BEAGLE_STREAM_CLIENT_PORT": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_PORT",
    "BEAGLE_STREAM_CLIENT_APP": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_APP",
    "BEAGLE_STREAM_CLIENT_BIN": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_BIN",
    "BEAGLE_STREAM_CLIENT_RESOLUTION": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_RESOLUTION",
    "BEAGLE_STREAM_CLIENT_FPS": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_FPS",
    "BEAGLE_STREAM_CLIENT_BITRATE": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_BITRATE",
    "BEAGLE_STREAM_CLIENT_VIDEO_CODEC": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_VIDEO_CODEC",
    "BEAGLE_STREAM_CLIENT_VIDEO_DECODER": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_VIDEO_DECODER",
    "BEAGLE_STREAM_CLIENT_AUDIO_CONFIG": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_AUDIO_CONFIG",
    "BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE",
    "BEAGLE_STREAM_CLIENT_QUIT_AFTER": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_QUIT_AFTER",
    "BEAGLE_STREAM_SERVER_API_URL": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_API_URL",
    "BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL",
    "BEAGLE_SCHEME": "PVE_THIN_CLIENT_PRESET_BEAGLE_SCHEME",
    "BEAGLE_HOST": "PVE_THIN_CLIENT_PRESET_BEAGLE_HOST",
    "BEAGLE_PORT": "PVE_THIN_CLIENT_PRESET_BEAGLE_PORT",
    "BEAGLE_NODE": "PVE_THIN_CLIENT_PRESET_BEAGLE_NODE",
    "BEAGLE_VMID": "PVE_THIN_CLIENT_PRESET_BEAGLE_VMID",
    "BEAGLE_REALM": "PVE_THIN_CLIENT_PRESET_BEAGLE_REALM",
    "BEAGLE_VERIFY_TLS": "PVE_THIN_CLIENT_PRESET_BEAGLE_VERIFY_TLS",
    "BEAGLE_MANAGER_URL": "PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_URL",
    "BEAGLE_MANAGER_PINNED_PUBKEY": "PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_PINNED_PUBKEY",
    "BEAGLE_ENROLLMENT_URL": "PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_URL",
    "BEAGLE_UPDATE_ENABLED": "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_ENABLED",
    "BEAGLE_UPDATE_CHANNEL": "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_CHANNEL",
    "BEAGLE_UPDATE_BEHAVIOR": "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_BEHAVIOR",
    "BEAGLE_UPDATE_FEED_URL": "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_FEED_URL",
    "BEAGLE_UPDATE_VERSION_PIN": "PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_VERSION_PIN",
    "BEAGLE_EGRESS_MODE": "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_MODE",
    "BEAGLE_EGRESS_TYPE": "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_TYPE",
    "BEAGLE_EGRESS_INTERFACE": "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_INTERFACE",
    "BEAGLE_EGRESS_DOMAINS": "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_DOMAINS",
    "BEAGLE_EGRESS_RESOLVERS": "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_RESOLVERS",
    "BEAGLE_EGRESS_ALLOWED_IPS": "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_ALLOWED_IPS",
    "BEAGLE_EGRESS_WG_ADDRESS": "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ADDRESS",
    "BEAGLE_EGRESS_WG_DNS": "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_DNS",
    "BEAGLE_EGRESS_WG_PUBLIC_KEY": "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PUBLIC_KEY",
    "BEAGLE_EGRESS_WG_ENDPOINT": "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ENDPOINT",
    "BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE": "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE",
    "IDENTITY_HOSTNAME": "PVE_THIN_CLIENT_PRESET_IDENTITY_HOSTNAME",
    "IDENTITY_TIMEZONE": "PVE_THIN_CLIENT_PRESET_IDENTITY_TIMEZONE",
    "IDENTITY_LOCALE": "PVE_THIN_CLIENT_PRESET_IDENTITY_LOCALE",
    "IDENTITY_KEYMAP": "PVE_THIN_CLIENT_PRESET_IDENTITY_KEYMAP",
    "IDENTITY_CHROME_PROFILE": "PVE_THIN_CLIENT_PRESET_IDENTITY_CHROME_PROFILE",
    "BEAGLE_USB_ENABLED": "PVE_THIN_CLIENT_PRESET_BEAGLE_USB_ENABLED",
    "BEAGLE_USB_TUNNEL_HOST": "PVE_THIN_CLIENT_PRESET_BEAGLE_USB_TUNNEL_HOST",
    "BEAGLE_USB_TUNNEL_USER": "PVE_THIN_CLIENT_PRESET_BEAGLE_USB_TUNNEL_USER",
    "BEAGLE_USB_TUNNEL_PORT": "PVE_THIN_CLIENT_PRESET_BEAGLE_USB_TUNNEL_PORT",
    "BEAGLE_USB_ATTACH_HOST": "PVE_THIN_CLIENT_PRESET_BEAGLE_USB_ATTACH_HOST",
    "NETWORK_MODE": "PVE_THIN_CLIENT_PRESET_NETWORK_MODE",
    "NETWORK_INTERFACE": "PVE_THIN_CLIENT_PRESET_NETWORK_INTERFACE",
    "NETWORK_STATIC_ADDRESS": "PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_ADDRESS",
    "NETWORK_STATIC_PREFIX": "PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_PREFIX",
    "NETWORK_GATEWAY": "PVE_THIN_CLIENT_PRESET_NETWORK_GATEWAY",
    "NETWORK_DNS_SERVERS": "PVE_THIN_CLIENT_PRESET_NETWORK_DNS_SERVERS",
    "CONNECTION_USERNAME": "PVE_THIN_CLIENT_PRESET_BEAGLE_USERNAME",
    "CONNECTION_PASSWORD": "PVE_THIN_CLIENT_PRESET_BEAGLE_PASSWORD",
    "CONNECTION_TOKEN": "PVE_THIN_CLIENT_PRESET_BEAGLE_TOKEN",
    "BEAGLE_MANAGER_TOKEN": None,
    "BEAGLE_ENROLLMENT_TOKEN": "PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_TOKEN",
    "BEAGLE_EGRESS_WG_PRIVATE_KEY": "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRIVATE_KEY",
    "BEAGLE_EGRESS_WG_PRESHARED_KEY": "PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRESHARED_KEY",
    "BEAGLE_STREAM_SERVER_USERNAME": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_USERNAME",
    "BEAGLE_STREAM_SERVER_PASSWORD": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_PASSWORD",
    "BEAGLE_STREAM_SERVER_PINNED_PUBKEY": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_PINNED_PUBKEY",
    "BEAGLE_STREAM_SERVER_NAME": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_NAME",
    "BEAGLE_STREAM_SERVER_STREAM_PORT": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_STREAM_PORT",
    "BEAGLE_STREAM_SERVER_UNIQUEID": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_UNIQUEID",
    "BEAGLE_STREAM_SERVER_CERT_B64": "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_CERT_B64",
    "RUNTIME_PASSWORD": "PVE_THIN_CLIENT_PRESET_THINCLIENT_PASSWORD",
}


def load_installer_env_defaults(path: Path = INSTALLER_ENV_DEFAULTS_FILE) -> dict[str, str]:
    return {
        str(key): str(value)
        for key, value in json.loads(path.read_text(encoding="utf-8")).items()
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
    defaults = load_installer_env_defaults()
    env["RUNTIME_USER"] = str(runtime_user or defaults.get("RUNTIME_USER", "thinclient"))
    for output_key, preset_key in PRESET_TO_INSTALLER_ENV.items():
        if output_key == "RUNTIME_USER":
            continue
        default_value = defaults.get(output_key, "")
        if preset_key is None:
            if output_key == "CONNECTION_METHOD":
                explicit_value = str(preset.get("PVE_THIN_CLIENT_PRESET_CONNECTION_METHOD", "") or "").strip()
                if explicit_value:
                    env[output_key] = explicit_value
                    continue
                stream_mode = str(preset.get("PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_MODE", "") or "").strip().lower()
                env[output_key] = "broker" if stream_mode == "broker" else default_value
                continue
            env[output_key] = default_value
            continue
        env[output_key] = str(preset.get(preset_key, default_value) or default_value)
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
