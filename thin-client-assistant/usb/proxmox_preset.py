#!/usr/bin/env python3
"""Proxmox-specific preset helpers for thin-client USB flows."""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from preset_summary import available_modes

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

    preset = {
        "PVE_THIN_CLIENT_PRESET_PROFILE_NAME": f"vm-{vmid}",
        "PVE_THIN_CLIENT_PRESET_VM_NAME": vm_name,
        "PVE_THIN_CLIENT_PRESET_HOSTNAME_VALUE": safe_hostname(vm_name, vmid),
        "PVE_THIN_CLIENT_PRESET_AUTOSTART": meta.get("thinclient-autostart", "1"),
        "PVE_THIN_CLIENT_PRESET_DEFAULT_MODE": default_mode,
        "PVE_THIN_CLIENT_PRESET_NETWORK_MODE": meta.get("thinclient-network-mode", "dhcp"),
        "PVE_THIN_CLIENT_PRESET_NETWORK_INTERFACE": meta.get("thinclient-network-interface", "eth0"),
        "PVE_THIN_CLIENT_PRESET_PROXMOX_SCHEME": proxmox_scheme,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_HOST": proxmox_host,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_PORT": proxmox_port,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_NODE": str(vm.get("node", "")),
        "PVE_THIN_CLIENT_PRESET_PROXMOX_VMID": str(vmid),
        "PVE_THIN_CLIENT_PRESET_PROXMOX_REALM": proxmox_realm,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_VERIFY_TLS": proxmox_verify_tls,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_USERNAME": "",
        "PVE_THIN_CLIENT_PRESET_PROXMOX_PASSWORD": "",
        "PVE_THIN_CLIENT_PRESET_PROXMOX_TOKEN": "",
        "PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_URL": manager_url,
        "PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_TOKEN": "",
        "PVE_THIN_CLIENT_PRESET_SPICE_METHOD": "",
        "PVE_THIN_CLIENT_PRESET_SPICE_URL": "",
        "PVE_THIN_CLIENT_PRESET_SPICE_USERNAME": "",
        "PVE_THIN_CLIENT_PRESET_SPICE_PASSWORD": "",
        "PVE_THIN_CLIENT_PRESET_SPICE_TOKEN": "",
        "PVE_THIN_CLIENT_PRESET_NOVNC_URL": "",
        "PVE_THIN_CLIENT_PRESET_NOVNC_USERNAME": "",
        "PVE_THIN_CLIENT_PRESET_NOVNC_PASSWORD": "",
        "PVE_THIN_CLIENT_PRESET_NOVNC_TOKEN": "",
        "PVE_THIN_CLIENT_PRESET_DCV_URL": "",
        "PVE_THIN_CLIENT_PRESET_DCV_USERNAME": "",
        "PVE_THIN_CLIENT_PRESET_DCV_PASSWORD": "",
        "PVE_THIN_CLIENT_PRESET_DCV_TOKEN": "",
        "PVE_THIN_CLIENT_PRESET_DCV_SESSION": "",
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_HOST": moonlight_host,
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_LOCAL_HOST": moonlight_local_host,
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_APP": meta.get("moonlight-app", meta.get("sunshine-app", "Desktop")),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_BIN": meta.get("moonlight-bin", "moonlight"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_RESOLUTION": meta.get("moonlight-resolution", "auto"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_FPS": meta.get("moonlight-fps", "60"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_BITRATE": meta.get("moonlight-bitrate", "20000"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_VIDEO_CODEC": meta.get("moonlight-video-codec", "H.264"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_VIDEO_DECODER": meta.get("moonlight-video-decoder", "auto"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_AUDIO_CONFIG": meta.get("moonlight-audio-config", "stereo"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_ABSOLUTE_MOUSE": meta.get("moonlight-absolute-mouse", "1"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_QUIT_AFTER": meta.get("moonlight-quit-after", "0"),
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_API_URL": sunshine_api_url,
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_USERNAME": "",
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_PASSWORD": "",
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_PIN": "",
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_NAME": "",
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_STREAM_PORT": "",
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_UNIQUEID": "",
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_CERT_B64": "",
    }
    modes = available_modes(
        {
            "moonlight_host": preset.get("PVE_THIN_CLIENT_PRESET_MOONLIGHT_HOST", ""),
            "spice_url": preset.get("PVE_THIN_CLIENT_PRESET_SPICE_URL", ""),
            "proxmox_host": preset.get("PVE_THIN_CLIENT_PRESET_PROXMOX_HOST", ""),
            "proxmox_node": preset.get("PVE_THIN_CLIENT_PRESET_PROXMOX_NODE", ""),
            "proxmox_vmid": preset.get("PVE_THIN_CLIENT_PRESET_PROXMOX_VMID", ""),
            "spice_username": preset.get("PVE_THIN_CLIENT_PRESET_SPICE_USERNAME", ""),
            "spice_password": preset.get("PVE_THIN_CLIENT_PRESET_SPICE_PASSWORD", ""),
            "proxmox_username": preset.get("PVE_THIN_CLIENT_PRESET_PROXMOX_USERNAME", ""),
            "proxmox_password": preset.get("PVE_THIN_CLIENT_PRESET_PROXMOX_PASSWORD", ""),
            "novnc_url": preset.get("PVE_THIN_CLIENT_PRESET_NOVNC_URL", ""),
            "dcv_url": preset.get("PVE_THIN_CLIENT_PRESET_DCV_URL", ""),
        }
    )
    return preset, modes
