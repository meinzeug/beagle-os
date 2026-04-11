#!/usr/bin/env python3
"""Proxmox-specific preset helpers for thin-client USB flows."""

from __future__ import annotations

import os
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from preset_summary import available_modes

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_SERVICES_DIR = REPO_ROOT / "beagle-host" / "services"
if str(HOST_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_SERVICES_DIR))

from thin_client_preset import build_common_preset, build_runtime_extension_fields, build_streaming_mode_input

DEFAULT_BEAGLE_MANAGER_URL = os.environ.get("PVE_DCV_BEAGLE_MANAGER_URL", "")


@dataclass
class Endpoint:
    scheme: str
    host: str
    port: int


def normalize_endpoint(raw_host: str, raw_scheme: str, raw_port: int) -> Endpoint:
    text = (raw_host or "").strip()
    if not text:
        raise SystemExit("missing Proxmox API host")

    scheme = raw_scheme
    host = text
    port = raw_port

    if "://" in text:
        parsed = urlparse(text)
        if parsed.scheme:
            scheme = parsed.scheme
        if parsed.hostname:
            host = parsed.hostname
        if parsed.port:
            port = parsed.port
    elif text.count(":") == 1 and not text.startswith("["):
        host_part, port_part = text.rsplit(":", 1)
        if port_part.isdigit():
            host = host_part
            port = int(port_part)

    host = host.strip()
    if not host:
        raise SystemExit("invalid Proxmox API host")

    return Endpoint(scheme=scheme, host=host, port=port)


def split_login(login: str) -> tuple[str, str]:
    raw = (login or "").strip()
    if not raw:
        raise SystemExit("missing Proxmox username")
    if "@" in raw:
        username, realm = raw.rsplit("@", 1)
    else:
        username, realm = raw, "pve"
    if not username or not realm:
        raise SystemExit("invalid Proxmox username, expected user@realm")
    return username, realm


def parse_description_meta(description: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    text = str(description or "").replace("\\r\\n", "\n").replace("\\n", "\n")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key and key not in meta:
            meta[key] = value
    return meta


def safe_hostname(name: str, vmid: int) -> str:
    cleaned = re.sub(r"[^a-z0-9-]+", "-", str(name or "").strip().lower()).strip("-")
    if not cleaned:
        cleaned = f"pve-tc-{vmid}"
    cleaned = cleaned[:63].strip("-")
    return cleaned or f"pve-tc-{vmid}"


def shell_line(key: str, value: str) -> str:
    return f"{key}={shlex.quote(str(value))}\n"


def build_preset(
    vm: dict[str, Any],
    config: dict[str, Any],
    endpoint: Endpoint,
    login: str,
    verify_tls: bool,
    *,
    beagle_manager_url: str = "",
) -> tuple[dict[str, str], list[str]]:
    meta = parse_description_meta(config.get("description", ""))
    vmid = int(vm["vmid"])
    vm_name = config.get("name") or vm.get("name") or f"vm-{vmid}"
    _, proxmox_realm = split_login(login)
    proxmox_scheme = meta.get("proxmox-scheme", endpoint.scheme)
    proxmox_host = meta.get("proxmox-host", endpoint.host)
    proxmox_port = meta.get("proxmox-port", str(endpoint.port))
    proxmox_verify_tls = meta.get("proxmox-verify-tls", "1" if verify_tls else "0")
    manager_url = str(beagle_manager_url or DEFAULT_BEAGLE_MANAGER_URL or "")

    moonlight_host = meta.get("moonlight-host") or meta.get("sunshine-host") or meta.get("sunshine-ip") or ""
    moonlight_local_host = meta.get("moonlight-local-host") or meta.get("sunshine-ip") or ""
    sunshine_api_url = meta.get("sunshine-api-url") or (f"https://{moonlight_host}:47990" if moonlight_host else "")
    default_mode = "MOONLIGHT" if moonlight_host else ""

    preset = build_common_preset(
        profile_name=f"vm-{vmid}",
        vm_name=vm_name,
        hostname_value=safe_hostname(vm_name, vmid),
        autostart=meta.get("thinclient-autostart", "1"),
        default_mode=default_mode,
        network_mode=meta.get("thinclient-network-mode", "dhcp"),
        network_interface=meta.get("thinclient-network-interface", "eth0"),
        proxmox_scheme=proxmox_scheme,
        proxmox_host=proxmox_host,
        proxmox_port=proxmox_port,
        proxmox_node=str(vm.get("node", "")),
        proxmox_vmid=str(vmid),
        proxmox_realm=proxmox_realm,
        proxmox_verify_tls=proxmox_verify_tls,
        beagle_manager_url=manager_url,
        moonlight_host=moonlight_host,
        moonlight_local_host=moonlight_local_host,
        moonlight_app=meta.get("moonlight-app", meta.get("sunshine-app", "Desktop")),
        moonlight_bin=meta.get("moonlight-bin", "moonlight"),
        moonlight_resolution=meta.get("moonlight-resolution", "auto"),
        moonlight_fps=meta.get("moonlight-fps", "60"),
        moonlight_bitrate=meta.get("moonlight-bitrate", "20000"),
        moonlight_video_codec=meta.get("moonlight-video-codec", "H.264"),
        moonlight_video_decoder=meta.get("moonlight-video-decoder", "auto"),
        moonlight_audio_config=meta.get("moonlight-audio-config", "stereo"),
        moonlight_absolute_mouse=meta.get("moonlight-absolute-mouse", "1"),
        moonlight_quit_after=meta.get("moonlight-quit-after", "0"),
        sunshine_api_url=sunshine_api_url,
        sunshine_username="",
        sunshine_password="",
        sunshine_pin="",
        extra_fields=build_runtime_extension_fields(
            network_static_address=meta.get("thinclient-network-static-address", ""),
            network_static_prefix=meta.get("thinclient-network-static-prefix", "24"),
            network_gateway=meta.get("thinclient-network-gateway", ""),
            network_dns_servers=meta.get("thinclient-network-dns-servers", "1.1.1.1 8.8.8.8"),
            beagle_enrollment_url=f"{manager_url}/api/v1/endpoints/enroll" if manager_url else "",
            beagle_manager_token="",
            beagle_update_enabled=meta.get("beagle-update-enabled", "1"),
            beagle_update_channel=meta.get("beagle-update-channel", "stable"),
            beagle_update_behavior=meta.get("beagle-update-behavior", "prompt"),
            beagle_update_feed_url=meta.get(
                "beagle-update-feed-url",
                f"{manager_url}/api/v1/endpoints/update-feed" if manager_url else "",
            ),
            beagle_update_version_pin=meta.get("beagle-update-version-pin", ""),
            beagle_egress_mode=meta.get("beagle-egress-mode", "direct"),
            beagle_egress_type=meta.get("beagle-egress-type", ""),
            beagle_egress_interface=meta.get("beagle-egress-interface", "beagle-egress"),
            beagle_egress_domains=meta.get("beagle-egress-domains", ""),
            beagle_egress_resolvers=meta.get("beagle-egress-resolvers", "1.1.1.1 8.8.8.8"),
            beagle_egress_allowed_ips=meta.get("beagle-egress-allowed-ips", ""),
            beagle_egress_wg_address=meta.get("beagle-egress-wg-address", ""),
            beagle_egress_wg_dns=meta.get("beagle-egress-wg-dns", ""),
            beagle_egress_wg_public_key=meta.get("beagle-egress-wg-public-key", ""),
            beagle_egress_wg_endpoint=meta.get("beagle-egress-wg-endpoint", ""),
            beagle_egress_wg_private_key=meta.get("beagle-egress-wg-private-key", ""),
            beagle_egress_wg_preshared_key=meta.get("beagle-egress-wg-preshared-key", ""),
            beagle_egress_wg_persistent_keepalive=meta.get("beagle-egress-wg-persistent-keepalive", "25"),
            identity_hostname=meta.get("identity-hostname", ""),
            identity_timezone=meta.get("identity-timezone", ""),
            identity_locale=meta.get("identity-locale", ""),
            identity_keymap=meta.get("identity-keymap", ""),
            identity_chrome_profile=meta.get("identity-chrome-profile", "default"),
            moonlight_port=meta.get("moonlight-port", meta.get("sunshine-port", "")),
        ),
    )
    modes = available_modes(build_streaming_mode_input(preset))
    return preset, modes
