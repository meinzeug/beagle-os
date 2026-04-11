#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import hashlib
import ipaddress
import base64
import secrets
import shlex
import signal
import socket
import tempfile
import time
import uuid
import pwd
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse

PROVIDERS_DIR = Path(__file__).resolve().parents[1] / "providers"
SERVICES_DIR = Path(__file__).resolve().parents[1] / "services"
if str(PROVIDERS_DIR) not in sys.path:
    sys.path.insert(0, str(PROVIDERS_DIR))
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from action_queue import ActionQueueService
from endpoint_profile_contract import installer_profile_surface, normalize_endpoint_profile_contract
from endpoint_report import EndpointReportService
from enrollment_token_store import EnrollmentTokenStoreService
from fleet_inventory import FleetInventoryService
from health_payload import HealthPayloadService
from host_provider_contract import HostProvider
from installer_script import InstallerScriptService
from policy_store import PolicyStoreService
from registry import create_provider, list_providers, normalize_provider_kind
from support_bundle_store import SupportBundleStoreService
from ubuntu_beagle_state import UbuntuBeagleStateService
from update_feed import UpdateFeedService
from virtualization_inventory import VirtualizationInventoryService
from vm_profile import VmProfileService
from vm_secret_store import VmSecretStoreService
from vm_state import VmStateService

def load_env_defaults(path: str) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value

load_env_defaults("/etc/beagle/host.env")
load_env_defaults("/etc/beagle/beagle-proxy.env")

VERSION = "dev"
ROOT_DIR = Path(__file__).resolve().parents[2]
VERSION_FILE = ROOT_DIR / "VERSION"
if VERSION_FILE.exists():
    VERSION = VERSION_FILE.read_text(encoding="utf-8").strip() or VERSION

LISTEN_HOST = os.environ.get("BEAGLE_MANAGER_LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("BEAGLE_MANAGER_LISTEN_PORT", "9088"))
DATA_DIR = Path(os.environ.get("BEAGLE_MANAGER_DATA_DIR", "/var/lib/beagle/beagle-manager"))
EFFECTIVE_DATA_DIR = DATA_DIR
API_TOKEN = os.environ.get("BEAGLE_MANAGER_API_TOKEN", "").strip()
ALLOW_LOCALHOST_NOAUTH = os.environ.get("BEAGLE_MANAGER_ALLOW_LOCALHOST_NOAUTH", "0").strip().lower() in {"1", "true", "yes", "on"}
STALE_ENDPOINT_SECONDS = int(os.environ.get("BEAGLE_MANAGER_STALE_ENDPOINT_SECONDS", "600"))
DOWNLOADS_STATUS_FILE = ROOT_DIR / "dist" / "beagle-downloads-status.json"
DIST_SHA256SUMS_FILE = ROOT_DIR / "dist" / "SHA256SUMS"
VM_INSTALLERS_FILE = ROOT_DIR / "dist" / "beagle-vm-installers.json"
HOSTED_INSTALLER_TEMPLATE_FILE = ROOT_DIR / "dist" / "pve-thin-client-usb-installer-host-latest.sh"
HOSTED_LIVE_USB_TEMPLATE_FILE = ROOT_DIR / "dist" / "pve-thin-client-live-usb-host-latest.sh"
HOSTED_WINDOWS_INSTALLER_TEMPLATE_FILE = ROOT_DIR / "dist" / "pve-thin-client-usb-installer-host-latest.ps1"
RAW_WINDOWS_INSTALLER_TEMPLATE_FILE = ROOT_DIR / "thin-client-assistant" / "usb" / "pve-thin-client-usb-installer.ps1"
HOSTED_INSTALLER_ISO_FILE = ROOT_DIR / "dist" / "beagle-os-installer-amd64.iso"
INSTALLER_PREP_SCRIPT_FILE = ROOT_DIR / "scripts" / "ensure-vm-stream-ready.sh"
CREDENTIALS_ENV_FILE = Path(os.environ.get("PVE_DCV_CREDENTIALS_ENV_FILE", "/etc/beagle/credentials.env"))
MANAGER_CERT_FILE = Path(os.environ.get("BEAGLE_MANAGER_CERT_FILE", "/etc/pve/local/pveproxy-ssl.pem"))
UBUNTU_BEAGLE_TEMPLATE_DIR = ROOT_DIR / "beagle-host" / "templates" / "ubuntu-beagle"
PUBLIC_SERVER_NAME = os.environ.get("PVE_DCV_PROXY_SERVER_NAME", "").strip() or os.uname().nodename
PUBLIC_DOWNLOADS_PORT = int(os.environ.get("PVE_DCV_PROXY_LISTEN_PORT", "8443"))
PUBLIC_DOWNLOADS_PATH = os.environ.get("PVE_DCV_DOWNLOADS_PATH", "/beagle-downloads").strip() or "/beagle-downloads"
PUBLIC_UPDATE_BASE_URL = os.environ.get("BEAGLE_PUBLIC_UPDATE_BASE_URL", "").strip() or f"https://{PUBLIC_SERVER_NAME}:{PUBLIC_DOWNLOADS_PORT}{PUBLIC_DOWNLOADS_PATH}"
PUBLIC_STREAM_HOST_RAW = os.environ.get("BEAGLE_PUBLIC_STREAM_HOST", "").strip() or PUBLIC_SERVER_NAME
PUBLIC_STREAM_BASE_PORT = int(os.environ.get("BEAGLE_PUBLIC_STREAM_BASE_PORT", "50000"))
PUBLIC_STREAM_PORT_STEP = int(os.environ.get("BEAGLE_PUBLIC_STREAM_PORT_STEP", "32"))
PUBLIC_STREAM_PORT_COUNT = int(os.environ.get("BEAGLE_PUBLIC_STREAM_PORT_COUNT", "256"))
PUBLIC_MANAGER_URL = os.environ.get("PVE_DCV_BEAGLE_MANAGER_URL", "").strip() or f"https://{PUBLIC_SERVER_NAME}:{PUBLIC_DOWNLOADS_PORT}/beagle-api"
WEB_UI_URL = os.environ.get("BEAGLE_WEB_UI_URL", "").strip()
CORS_ALLOWED_ORIGINS_RAW = os.environ.get("BEAGLE_CORS_ALLOWED_ORIGINS", "").strip()
PROXMOX_UI_PORTS_RAW = os.environ.get("BEAGLE_PROXMOX_UI_PORTS", "8006").strip()
BEAGLE_HOST_PROVIDER_KIND = normalize_provider_kind(os.environ.get("BEAGLE_HOST_PROVIDER", "proxmox"))
ENROLLMENT_TOKEN_TTL_SECONDS = int(os.environ.get("BEAGLE_ENROLLMENT_TOKEN_TTL_SECONDS", "86400"))
SUNSHINE_ACCESS_TOKEN_TTL_SECONDS = int(os.environ.get("BEAGLE_SUNSHINE_ACCESS_TOKEN_TTL_SECONDS", "600"))
USB_TUNNEL_SSH_USER = os.environ.get("BEAGLE_USB_TUNNEL_SSH_USER", "beagle").strip() or "beagle"
USB_TUNNEL_HOME_RAW = os.environ.get("BEAGLE_USB_TUNNEL_HOME", "").strip()
USB_TUNNEL_HOME = Path(USB_TUNNEL_HOME_RAW) if USB_TUNNEL_HOME_RAW else None
USB_TUNNEL_AUTH_ROOT_RAW = os.environ.get("BEAGLE_USB_TUNNEL_AUTH_ROOT", "").strip()
USB_TUNNEL_AUTH_ROOT = Path(USB_TUNNEL_AUTH_ROOT_RAW) if USB_TUNNEL_AUTH_ROOT_RAW else None
USB_TUNNEL_AUTH_DIR_RAW = os.environ.get("BEAGLE_USB_TUNNEL_AUTH_DIR", "").strip()
USB_TUNNEL_AUTH_DIR = Path(USB_TUNNEL_AUTH_DIR_RAW) if USB_TUNNEL_AUTH_DIR_RAW else None
USB_TUNNEL_HOSTKEY_FILE = Path(os.environ.get("BEAGLE_USB_TUNNEL_HOSTKEY_FILE", "/etc/ssh/ssh_host_ed25519_key.pub"))
USB_TUNNEL_ATTACH_HOST = os.environ.get("BEAGLE_USB_TUNNEL_ATTACH_HOST", "10.10.10.1").strip() or "10.10.10.1"
USB_TUNNEL_BASE_PORT = int(os.environ.get("BEAGLE_USB_TUNNEL_BASE_PORT", "43000"))
USB_ACTION_WAIT_SECONDS = float(os.environ.get("BEAGLE_USB_ACTION_WAIT_SECONDS", "25"))
COMMAND_TIMEOUT_SECONDS = float(os.environ.get("BEAGLE_MANAGER_COMMAND_TIMEOUT_SECONDS", "8"))
DEFAULT_COMMAND_TIMEOUT = object()
GUEST_AGENT_TIMEOUT_SECONDS = float(os.environ.get("BEAGLE_MANAGER_GUEST_AGENT_TIMEOUT_SECONDS", "2.5"))
LIST_VMS_CACHE_SECONDS = float(os.environ.get("BEAGLE_MANAGER_LIST_VMS_CACHE_SECONDS", "3"))
VM_CONFIG_CACHE_SECONDS = float(os.environ.get("BEAGLE_MANAGER_VM_CONFIG_CACHE_SECONDS", "5"))
GUEST_IPV4_CACHE_SECONDS = float(os.environ.get("BEAGLE_MANAGER_GUEST_IPV4_CACHE_SECONDS", "10"))
ENABLE_GUEST_IP_LOOKUP = os.environ.get("BEAGLE_MANAGER_ENABLE_GUEST_IP_LOOKUP", "1").strip().lower() in {"1", "true", "yes", "on"}
UBUNTU_BEAGLE_ISO_URL = os.environ.get(
    "BEAGLE_UBUNTU_ISO_URL",
    "https://releases.ubuntu.com/24.04/ubuntu-24.04.4-live-server-amd64.iso",
).strip()
UBUNTU_BEAGLE_ISO_STORAGE = os.environ.get("BEAGLE_UBUNTU_ISO_STORAGE", "local").strip() or "local"
UBUNTU_BEAGLE_DISK_STORAGE = os.environ.get("BEAGLE_UBUNTU_DISK_STORAGE", "local-lvm").strip() or "local-lvm"
UBUNTU_BEAGLE_DEFAULT_BRIDGE = os.environ.get("BEAGLE_UBUNTU_DEFAULT_BRIDGE", "vmbr1").strip() or "vmbr1"
UBUNTU_BEAGLE_DEFAULT_MEMORY_MIB = int(os.environ.get("BEAGLE_UBUNTU_DEFAULT_MEMORY_MIB", "8192"))
UBUNTU_BEAGLE_DEFAULT_CORES = int(os.environ.get("BEAGLE_UBUNTU_DEFAULT_CORES", "4"))
UBUNTU_BEAGLE_DEFAULT_DISK_GB = int(os.environ.get("BEAGLE_UBUNTU_DEFAULT_DISK_GB", "64"))
UBUNTU_BEAGLE_DEFAULT_GUEST_USER = os.environ.get("BEAGLE_UBUNTU_DEFAULT_GUEST_USER", "beagle").strip() or "beagle"
UBUNTU_BEAGLE_DEFAULT_LOCALE = os.environ.get("BEAGLE_UBUNTU_DEFAULT_LOCALE", "de_DE.UTF-8").strip() or "de_DE.UTF-8"
UBUNTU_BEAGLE_DEFAULT_KEYMAP = os.environ.get("BEAGLE_UBUNTU_DEFAULT_KEYMAP", "de").strip() or "de"
UBUNTU_BEAGLE_DEFAULT_DESKTOP = os.environ.get("BEAGLE_UBUNTU_DEFAULT_DESKTOP", "xfce").strip().lower() or "xfce"
UBUNTU_BEAGLE_PROFILE_ID = "ubuntu-24.04-desktop-sunshine"
UBUNTU_BEAGLE_PROFILE_LEGACY_IDS = {
    "ubuntu-24.04-xfce-sunshine": "xfce",
}
UBUNTU_BEAGLE_PROFILE_LABEL = "Ubuntu 24.04 LTS Desktop mit Sunshine"
UBUNTU_BEAGLE_PROFILE_RELEASE = "24.04 LTS"
UBUNTU_BEAGLE_PROFILE_STREAMING = "Sunshine"
UBUNTU_BEAGLE_MIN_PASSWORD_LENGTH = int(os.environ.get("BEAGLE_UBUNTU_MIN_PASSWORD_LENGTH", "8"))
UBUNTU_BEAGLE_SUNSHINE_URL = os.environ.get(
    "BEAGLE_UBUNTU_SUNSHINE_URL",
    "https://github.com/LizardByte/Sunshine/releases/download/v2025.924.154138/sunshine-ubuntu-24.04-amd64.deb",
).strip()
UBUNTU_BEAGLE_AUTOINSTALL_URL_TTL_SECONDS = int(os.environ.get("BEAGLE_UBUNTU_AUTOINSTALL_URL_TTL_SECONDS", "21600"))
UBUNTU_BEAGLE_FIRSTBOOT_POWERDOWN_WAIT_SECONDS = int(os.environ.get("BEAGLE_UBUNTU_FIRSTBOOT_POWERDOWN_WAIT_SECONDS", "600"))
UBUNTU_BEAGLE_DESKTOPS: dict[str, dict[str, Any]] = {
    "xfce": {
        "id": "xfce",
        "label": "XFCE",
        "session": "xfce",
        "packages": ["xfce4", "xfce4-goodies"],
        "features": ["Lightweight desktop", "Thunar", "XFCE panel"],
        "aliases": ["xfce", "xubuntu"],
    },
    "gnome": {
        "id": "gnome",
        "label": "GNOME",
        "session": "ubuntu-xorg",
        "packages": ["ubuntu-desktop-minimal"],
        "features": ["Ubuntu GNOME shell", "Activities overview", "Files app"],
        "aliases": ["gnome", "ubuntu", "ubuntu-desktop"],
    },
    "plasma": {
        "id": "plasma",
        "label": "KDE Plasma",
        "session": "plasma",
        "packages": ["plasma-desktop", "konsole", "dolphin"],
        "features": ["KDE Plasma shell", "Dolphin", "Konsole"],
        "aliases": ["kde", "plasma", "kde-plasma"],
    },
    "mate": {
        "id": "mate",
        "label": "MATE",
        "session": "mate",
        "packages": ["mate-desktop-environment-core", "mate-terminal", "caja"],
        "features": ["Traditional desktop", "Caja", "MATE terminal"],
        "aliases": ["mate", "ubuntu-mate"],
    },
    "lxqt": {
        "id": "lxqt",
        "label": "LXQt",
        "session": "lxqt",
        "packages": ["lxqt", "qterminal", "pcmanfm-qt"],
        "features": ["Very lightweight", "PCManFM-Qt", "Qt desktop"],
        "aliases": ["lxqt", "lubuntu"],
    },
}
UBUNTU_BEAGLE_SOFTWARE_PRESETS: dict[str, dict[str, Any]] = {
    "firefox": {
        "id": "firefox",
        "label": "Firefox",
        "packages": ["firefox"],
        "description": "Additional browser next to Chrome.",
    },
    "thunderbird": {
        "id": "thunderbird",
        "label": "Thunderbird",
        "packages": ["thunderbird"],
        "description": "Mail and calendar client.",
    },
    "libreoffice": {
        "id": "libreoffice",
        "label": "LibreOffice",
        "packages": ["libreoffice"],
        "description": "Office suite for documents and spreadsheets.",
    },
    "vlc": {
        "id": "vlc",
        "label": "VLC",
        "packages": ["vlc"],
        "description": "Media player.",
    },
    "remmina": {
        "id": "remmina",
        "label": "Remmina",
        "packages": ["remmina"],
        "description": "Remote desktop client toolkit.",
    },
    "filezilla": {
        "id": "filezilla",
        "label": "FileZilla",
        "packages": ["filezilla"],
        "description": "FTP and SFTP client.",
    },
    "gimp": {
        "id": "gimp",
        "label": "GIMP",
        "packages": ["gimp"],
        "description": "Image editing.",
    },
}

_CACHE: dict[str, tuple[float, Any]] = {}


def resolve_public_stream_host(host: str) -> str:
    candidate = str(host or "").strip()
    if not candidate:
        return ""
    try:
        ipaddress.ip_address(candidate)
        return candidate
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(candidate, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return candidate
    for item in infos:
        ip = str(item[4][0]).strip()
        if ip:
            return ip
    return candidate


PUBLIC_STREAM_HOST = resolve_public_stream_host(PUBLIC_STREAM_HOST_RAW)


def current_public_stream_host() -> str:
    return resolve_public_stream_host(PUBLIC_STREAM_HOST_RAW)


def public_installer_iso_url() -> str:
    return f"{PUBLIC_UPDATE_BASE_URL.rstrip('/')}/beagle-os-installer-amd64.iso"


def public_windows_installer_url() -> str:
    return f"https://{PUBLIC_SERVER_NAME}:{PUBLIC_DOWNLOADS_PORT}{PUBLIC_DOWNLOADS_PATH}/pve-thin-client-usb-installer-host-latest.ps1"


def public_update_sha256sums_url() -> str:
    return f"{PUBLIC_UPDATE_BASE_URL.rstrip('/')}/SHA256SUMS"


def public_versioned_payload_url(version: str) -> str:
    return f"{PUBLIC_UPDATE_BASE_URL.rstrip('/')}/pve-thin-client-usb-payload-v{version}.tar.gz"


def public_versioned_bootstrap_url(version: str) -> str:
    return f"{PUBLIC_UPDATE_BASE_URL.rstrip('/')}/pve-thin-client-usb-bootstrap-v{version}.tar.gz"


def public_payload_latest_download_url() -> str:
    return f"{PUBLIC_UPDATE_BASE_URL.rstrip('/')}/pve-thin-client-usb-payload-latest.tar.gz"


def public_bootstrap_latest_download_url() -> str:
    return f"{PUBLIC_UPDATE_BASE_URL.rstrip('/')}/pve-thin-client-usb-bootstrap-latest.tar.gz"


def public_latest_payload_url() -> str:
    downloads_status = load_json_file(DOWNLOADS_STATUS_FILE, {})
    published_version = str(downloads_status.get("version", "")).strip() or VERSION
    payload = update_payload_metadata(published_version)
    payload_url = str(payload.get("payload_url", "") or "").strip()
    if payload_url:
        return payload_url
    return public_versioned_payload_url(published_version)


def public_latest_bootstrap_url() -> str:
    downloads_status = load_json_file(DOWNLOADS_STATUS_FILE, {})
    published_version = str(downloads_status.get("version", "")).strip() or VERSION
    bootstrap_url = str(downloads_status.get("bootstrap_url", "") or "").strip()
    if bootstrap_url:
        return bootstrap_url
    return public_versioned_bootstrap_url(published_version)


def url_host_matches(left: str, right: str) -> bool:
    left_host = str(urlparse(str(left or "")).hostname or "").strip().lower()
    right_host = str(urlparse(str(right or "")).hostname or "").strip().lower()
    return bool(left_host and right_host and left_host == right_host)


@dataclass
class VmSummary:
    vmid: int
    node: str
    name: str
    status: str
    tags: str


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_utc_timestamp(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def timestamp_age_seconds(value: str) -> int | None:
    parsed = parse_utc_timestamp(value)
    if parsed is None:
        return None
    return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds()))


def load_json_file(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback
    except json.JSONDecodeError:
        return fallback


def cache_get(key: str, ttl_seconds: float) -> Any:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    created_at, value = entry
    if time.monotonic() - created_at > ttl_seconds:
        _CACHE.pop(key, None)
        return None
    return value


def cache_put(key: str, value: Any) -> Any:
    _CACHE[key] = (time.monotonic(), value)
    return value


def cache_invalidate(*keys: str) -> None:
    for key in keys:
        if key:
            _CACHE.pop(key, None)


def invalidate_vm_cache(vmid: int | None = None, node: str = "") -> None:
    cache_invalidate("list-vms")
    if vmid is None:
        return
    numeric_vmid = int(vmid)
    cache_invalidate(f"guest-ipv4:{numeric_vmid}")
    if node:
        cache_invalidate(f"vm-config:{node}:{numeric_vmid}")


def listify(value: Any) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value is None:
        items = []
    else:
        items = re.split(r"[\s,]+", str(value))
    return [str(item).strip() for item in items if str(item).strip()]


def truthy(value: Any, *, default: bool = False) -> bool:
    text = str(value if value is not None else "").strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on"}


def normalized_origin(value: str) -> str:
    parsed = urlparse(str(value or "").strip())
    if not parsed.scheme or not parsed.hostname:
        return ""
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        return ""
    host = str(parsed.hostname or "").strip().lower()
    if not host:
        return ""
    default_port = 443 if scheme == "https" else 80
    port = parsed.port
    origin = f"{scheme}://{host}"
    if port and port != default_port:
        origin += f":{port}"
    return origin


def cors_allowed_origins() -> set[str]:
    cache_key = "cors-allowed-origins"
    cached = cache_get(cache_key, 60)
    if cached is not None:
        return set(cached)

    candidates: set[str] = {
        WEB_UI_URL,
        PUBLIC_MANAGER_URL,
        f"https://{PUBLIC_SERVER_NAME}",
        f"https://{PUBLIC_SERVER_NAME}:{PUBLIC_DOWNLOADS_PORT}",
    }
    hostnames = {
        str(PUBLIC_SERVER_NAME or "").strip(),
        str(PUBLIC_STREAM_HOST_RAW or "").strip(),
        str(current_public_stream_host() or "").strip(),
        str(urlparse(WEB_UI_URL).hostname or "").strip(),
        str(urlparse(PUBLIC_MANAGER_URL).hostname or "").strip(),
    }
    for port in listify(PROXMOX_UI_PORTS_RAW):
        if not str(port).isdigit():
            continue
        for hostname in hostnames:
            if hostname:
                candidates.add(f"https://{hostname}:{int(port)}")
    for origin in listify(CORS_ALLOWED_ORIGINS_RAW):
        candidates.add(origin)

    normalized = tuple(sorted(origin for origin in (normalized_origin(item) for item in candidates) if origin))
    cache_put(cache_key, normalized)
    return set(normalized)


def checksum_for_dist_filename(filename: str) -> str:
    cache_key = f"dist-checksum::{filename}"
    cached = cache_get(cache_key, 30)
    if cached is not None:
        return str(cached)
    checksum = ""
    try:
        for raw_line in DIST_SHA256SUMS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or "  " not in line:
                continue
            digest, name = line.split("  ", 1)
            if name.strip() == filename:
                checksum = digest.strip()
                break
    except FileNotFoundError:
        checksum = ""
    return str(cache_put(cache_key, checksum))


def update_payload_metadata(version: str) -> dict[str, str]:
    downloads_status = load_json_file(DOWNLOADS_STATUS_FILE, {})
    latest_version = str(downloads_status.get("version", "")).strip()
    filename = f"pve-thin-client-usb-payload-v{version}.tar.gz"
    payload_url = public_versioned_payload_url(version)
    payload_sha256 = checksum_for_dist_filename(filename)
    if not payload_sha256 and version == latest_version:
        payload_sha256 = str(downloads_status.get("payload_sha256", "")).strip()
    payload_pin = MANAGER_PINNED_PUBKEY if url_host_matches(payload_url, PUBLIC_MANAGER_URL) else ""
    return {
        "version": version,
        "filename": filename,
        "payload_url": payload_url,
        "payload_sha256": payload_sha256,
        "sha256sums_url": public_update_sha256sums_url(),
        "payload_pinned_pubkey": payload_pin,
    }


def ensure_data_dir() -> Path:
    def ensure_directory(path: Path, *, mode: int = 0o700) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path, mode)
        except OSError:
            pass
        return path

    try:
        return ensure_directory(DATA_DIR)
    except PermissionError:
        return ensure_directory(Path("/run/beagle-control-plane"))


def run_json(command: list[str], *, timeout: float | None | object = DEFAULT_COMMAND_TIMEOUT) -> Any:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS if timeout is DEFAULT_COMMAND_TIMEOUT else timeout,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError:
        return None


def run_text(command: list[str], *, timeout: float | None | object = DEFAULT_COMMAND_TIMEOUT) -> str:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS if timeout is DEFAULT_COMMAND_TIMEOUT else timeout,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""
    return result.stdout


def run_checked(command: list[str], *, timeout: float | None | object = DEFAULT_COMMAND_TIMEOUT) -> str:
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS if timeout is DEFAULT_COMMAND_TIMEOUT else timeout,
    )
    return result.stdout


HOST_PROVIDER: HostProvider = create_provider(
    BEAGLE_HOST_PROVIDER_KIND,
    run_json=run_json,
    run_text=run_text,
    run_checked=run_checked,
    cache_get=cache_get,
    cache_put=cache_put,
)

VIRTUALIZATION_INVENTORY = VirtualizationInventoryService(
    provider=HOST_PROVIDER,
    vm_summary_factory=lambda item: VmSummary(
        vmid=int(item["vmid"]),
        node=str(item["node"]),
        name=str(item.get("name") or f"vm-{item['vmid']}"),
        status=str(item.get("status") or "unknown"),
        tags=str(item.get("tags") or ""),
    ),
    list_vms_cache_seconds=LIST_VMS_CACHE_SECONDS,
    vm_config_cache_seconds=VM_CONFIG_CACHE_SECONDS,
    guest_ipv4_cache_seconds=GUEST_IPV4_CACHE_SECONDS,
    enable_guest_ip_lookup=ENABLE_GUEST_IP_LOOKUP,
    guest_agent_timeout_seconds=GUEST_AGENT_TIMEOUT_SECONDS,
    default_bridge=UBUNTU_BEAGLE_DEFAULT_BRIDGE,
)

VM_PROFILE_SERVICE: VmProfileService | None = None
VM_STATE_SERVICE: VmStateService | None = None
UPDATE_FEED_SERVICE: UpdateFeedService | None = None
FLEET_INVENTORY_SERVICE: FleetInventoryService | None = None
HEALTH_PAYLOAD_SERVICE: HealthPayloadService | None = None
INSTALLER_SCRIPT_SERVICE: InstallerScriptService | None = None
ENDPOINT_REPORT_SERVICE: EndpointReportService | None = None
ACTION_QUEUE_SERVICE: ActionQueueService | None = None
POLICY_STORE_SERVICE: PolicyStoreService | None = None
SUPPORT_BUNDLE_STORE_SERVICE: SupportBundleStoreService | None = None
UBUNTU_BEAGLE_STATE_SERVICE: UbuntuBeagleStateService | None = None
VM_SECRET_STORE_SERVICE: VmSecretStoreService | None = None
ENROLLMENT_TOKEN_STORE_SERVICE: EnrollmentTokenStoreService | None = None


def endpoints_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "endpoints"
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def actions_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "actions"
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def support_bundles_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "support-bundles"
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def policies_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "policies"
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def vm_secret_store_service() -> VmSecretStoreService:
    global VM_SECRET_STORE_SERVICE
    if VM_SECRET_STORE_SERVICE is None:
        VM_SECRET_STORE_SERVICE = VmSecretStoreService(
            data_dir=lambda: EFFECTIVE_DATA_DIR,
            load_json_file=load_json_file,
            write_json_file=write_json_file,
            safe_slug=safe_slug,
            utcnow=utcnow,
        )
    return VM_SECRET_STORE_SERVICE


def enrollment_token_store_service() -> EnrollmentTokenStoreService:
    global ENROLLMENT_TOKEN_STORE_SERVICE
    if ENROLLMENT_TOKEN_STORE_SERVICE is None:
        ENROLLMENT_TOKEN_STORE_SERVICE = EnrollmentTokenStoreService(
            data_dir=lambda: EFFECTIVE_DATA_DIR,
            load_json_file=load_json_file,
            write_json_file=write_json_file,
            parse_utc_timestamp=parse_utc_timestamp,
            utcnow=utcnow,
        )
    return ENROLLMENT_TOKEN_STORE_SERVICE


def vm_secrets_dir() -> Path:
    return vm_secret_store_service().secrets_dir()


def enrollment_tokens_dir() -> Path:
    return enrollment_token_store_service().tokens_dir()


def endpoint_tokens_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "endpoint-tokens"
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def sunshine_access_tokens_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "sunshine-access-tokens"
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def ubuntu_beagle_state_service() -> UbuntuBeagleStateService:
    global UBUNTU_BEAGLE_STATE_SERVICE
    if UBUNTU_BEAGLE_STATE_SERVICE is None:
        UBUNTU_BEAGLE_STATE_SERVICE = UbuntuBeagleStateService(
            data_dir=lambda: EFFECTIVE_DATA_DIR,
            load_json_file=load_json_file,
            write_json_file=write_json_file,
            safe_slug=safe_slug,
            ubuntu_beagle_profile_id=UBUNTU_BEAGLE_PROFILE_ID,
        )
    return UBUNTU_BEAGLE_STATE_SERVICE


def ubuntu_beagle_tokens_dir() -> Path:
    return ubuntu_beagle_state_service().tokens_dir()


def ubuntu_beagle_token_path(token: str) -> Path:
    return ubuntu_beagle_state_service().token_path(token)


def load_ubuntu_beagle_state(token: str) -> dict[str, Any] | None:
    return ubuntu_beagle_state_service().load(token)


def save_ubuntu_beagle_state(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return ubuntu_beagle_state_service().save(token, payload)


def schedule_ubuntu_beagle_vm_restart(
    vmid: int,
    *,
    wait_timeout_seconds: int = UBUNTU_BEAGLE_FIRSTBOOT_POWERDOWN_WAIT_SECONDS,
) -> dict[str, Any]:
    wait_timeout = max(60, int(wait_timeout_seconds or UBUNTU_BEAGLE_FIRSTBOOT_POWERDOWN_WAIT_SECONDS))
    pid = HOST_PROVIDER.schedule_vm_restart_after_stop(int(vmid), wait_timeout_seconds=wait_timeout)
    return {
        "vmid": int(vmid),
        "pid": int(pid),
        "wait_timeout_seconds": wait_timeout,
        "scheduled_at": utcnow(),
    }


def cancel_scheduled_ubuntu_beagle_vm_restart(state: dict[str, Any]) -> dict[str, Any] | None:
    restart_state = state.get("host_restart") if isinstance(state.get("host_restart"), dict) else None
    if not restart_state:
        return None
    pid_raw = restart_state.get("pid")
    try:
        pid = int(pid_raw)
    except (TypeError, ValueError):
        pid = 0
    result = dict(restart_state)
    result["cancelled_at"] = utcnow()
    if pid <= 0:
        state.pop("host_restart", None)
        return result
    try:
        os.killpg(pid, signal.SIGTERM)
        result["cancelled"] = True
    except ProcessLookupError:
        result["cancelled"] = False
        result["reason"] = "not-running"
    except OSError as exc:
        result["cancelled"] = False
        result["reason"] = str(exc)
    state.pop("host_restart", None)
    return result


def public_ubuntu_beagle_complete_url(token: str) -> str:
    return f"{PUBLIC_MANAGER_URL}/api/v1/public/ubuntu-install/{token}/complete"


def summarize_ubuntu_beagle_state(payload: dict[str, Any], *, include_credentials: bool = False) -> dict[str, Any]:
    return ubuntu_beagle_state_service().summarize(payload, include_credentials=include_credentials)


def list_ubuntu_beagle_states(*, include_credentials: bool = False) -> list[dict[str, Any]]:
    return ubuntu_beagle_state_service().list_all(include_credentials=include_credentials)


def latest_ubuntu_beagle_state_for_vmid(vmid: int, *, include_credentials: bool = False) -> dict[str, Any] | None:
    return ubuntu_beagle_state_service().latest_for_vmid(vmid, include_credentials=include_credentials)


def safe_slug(value: str, default: str = "item") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-")
    return cleaned or default


def action_queue_service() -> ActionQueueService:
    global ACTION_QUEUE_SERVICE
    if ACTION_QUEUE_SERVICE is None:
        ACTION_QUEUE_SERVICE = ActionQueueService(
            actions_dir=actions_dir,
            load_json_file=load_json_file,
            safe_slug=safe_slug,
        )
    return ACTION_QUEUE_SERVICE


def action_queue_path(node: str, vmid: int) -> Path:
    return action_queue_service().queue_path(node, vmid)


def action_result_path(node: str, vmid: int) -> Path:
    return action_queue_service().result_path(node, vmid)


def support_bundle_store_service() -> SupportBundleStoreService:
    global SUPPORT_BUNDLE_STORE_SERVICE
    if SUPPORT_BUNDLE_STORE_SERVICE is None:
        SUPPORT_BUNDLE_STORE_SERVICE = SupportBundleStoreService(
            load_json_file=load_json_file,
            safe_slug=safe_slug,
            support_bundles_dir=support_bundles_dir,
        )
    return SUPPORT_BUNDLE_STORE_SERVICE


def support_bundle_metadata_path(bundle_id: str) -> Path:
    return support_bundle_store_service().metadata_path(bundle_id)


def support_bundle_archive_path(bundle_id: str, filename: str) -> Path:
    return support_bundle_store_service().archive_path(bundle_id, filename)


def load_shell_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return data
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            data[key] = value
    return data


def write_json_file(path: Path, payload: Any, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def random_secret(length: int = 24) -> str:
    alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(max(12, length)))


def random_pin() -> str:
    return f"{secrets.randbelow(10000):04d}"


def vm_secret_path(node: str, vmid: int) -> Path:
    return vm_secret_store_service().secret_path(node, vmid)


def load_vm_secret(node: str, vmid: int) -> dict[str, Any] | None:
    return vm_secret_store_service().load(node, vmid)


def save_vm_secret(node: str, vmid: int, payload: dict[str, Any]) -> dict[str, Any]:
    return vm_secret_store_service().save(node, vmid, payload)


def default_usb_tunnel_port(vmid: int) -> int:
    candidate = USB_TUNNEL_BASE_PORT + int(vmid)
    if 1024 <= candidate <= 65535:
        return candidate
    return 43000 + (int(vmid) % 20000)


def generate_ssh_keypair(comment: str) -> tuple[str, str]:
    with tempfile.TemporaryDirectory(prefix="beagle-usb-keygen-") as tmp_dir:
        key_path = Path(tmp_dir) / "id_ed25519"
        subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", comment, "-f", str(key_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        private_key = key_path.read_text(encoding="utf-8")
        public_key = key_path.with_suffix(".pub").read_text(encoding="utf-8").strip()
        return private_key, public_key


def usb_tunnel_known_host_line() -> str:
    try:
        raw = USB_TUNNEL_HOSTKEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    parts = raw.split()
    if len(parts) < 2:
        return ""
    hostnames = [PUBLIC_SERVER_NAME]
    if PUBLIC_STREAM_HOST and PUBLIC_STREAM_HOST not in hostnames:
        hostnames.append(PUBLIC_STREAM_HOST)
    host_field = ",".join(hostnames)
    return f"{host_field} {parts[0]} {parts[1]}"


def usb_tunnel_user_info() -> pwd.struct_passwd:
    return pwd.getpwnam(USB_TUNNEL_SSH_USER)


def usb_tunnel_home() -> Path:
    if USB_TUNNEL_HOME is not None:
        return USB_TUNNEL_HOME
    return Path(usb_tunnel_user_info().pw_dir)


def usb_tunnel_auth_root() -> Path:
    if USB_TUNNEL_AUTH_ROOT is not None:
        return USB_TUNNEL_AUTH_ROOT
    if USB_TUNNEL_AUTH_DIR is not None:
        return USB_TUNNEL_AUTH_DIR.parent
    return DATA_DIR.parent / "usb-tunnel" / USB_TUNNEL_SSH_USER


def usb_tunnel_auth_dir() -> Path:
    if USB_TUNNEL_AUTH_DIR is not None:
        return USB_TUNNEL_AUTH_DIR
    return usb_tunnel_auth_root() / "authorized_keys.d"


def usb_tunnel_authorized_keys_path() -> Path:
    return usb_tunnel_auth_root() / "authorized_keys"


def usb_tunnel_authorized_key_line(vm: VmSummary, secret: dict[str, Any]) -> str:
    public_key = str(secret.get("usb_tunnel_public_key", "")).strip()
    port = int(secret.get("usb_tunnel_port", 0) or 0)
    session_script = (Path(__file__).resolve().parent / "beagle-usb-tunnel-session").as_posix()
    return (
        f'command="{session_script}",no-agent-forwarding,no-pty,no-user-rc,no-X11-forwarding,'
        f'permitlisten="{USB_TUNNEL_ATTACH_HOST}:{port}" '
        f"{public_key}"
    )


def sync_usb_tunnel_authorized_key(vm: VmSummary, secret: dict[str, Any]) -> None:
    public_key = str(secret.get("usb_tunnel_public_key", "")).strip()
    port = int(secret.get("usb_tunnel_port", 0) or 0)
    if not public_key or port <= 0:
        return
    try:
        user_info = usb_tunnel_user_info()
    except KeyError:
        return
    auth_root = usb_tunnel_auth_root()
    auth_root.mkdir(parents=True, exist_ok=True)
    auth_dir = usb_tunnel_auth_dir()
    auth_dir.mkdir(parents=True, exist_ok=True)
    key_line = usb_tunnel_authorized_key_line(vm, secret) + "\n"
    snippet_path = auth_dir / f"{safe_slug(vm.node, 'node')}-{int(vm.vmid)}.pub"
    snippet_path.write_text(key_line, encoding="utf-8")
    authorized_keys = usb_tunnel_authorized_keys_path()
    managed_lines: list[str] = []
    for item in sorted(auth_dir.glob("*.pub")):
        try:
            text = item.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            managed_lines.append(text)
    existing_text = ""
    if authorized_keys.exists():
        try:
            existing_text = authorized_keys.read_text(encoding="utf-8")
        except OSError:
            existing_text = ""
    begin_marker = "# BEGIN BEAGLE USB TUNNELS"
    end_marker = "# END BEAGLE USB TUNNELS"
    if begin_marker in existing_text and end_marker in existing_text:
        prefix, _, remainder = existing_text.partition(begin_marker)
        _, _, suffix = remainder.partition(end_marker)
        existing_text = prefix.rstrip("\n")
        suffix = suffix.lstrip("\n")
        if suffix:
            existing_text = (existing_text + "\n" + suffix).strip("\n")
    else:
        existing_text = existing_text.strip("\n")
    with authorized_keys.open("w", encoding="utf-8") as handle:
        if existing_text:
            handle.write(existing_text.rstrip("\n") + "\n")
        if managed_lines:
            handle.write(begin_marker + "\n")
            for line in managed_lines:
                handle.write(line + "\n")
            handle.write(end_marker + "\n")
    os.chmod(auth_root, 0o700)
    os.chmod(authorized_keys, 0o600)
    os.chmod(snippet_path, 0o600)
    for path in (auth_root, auth_dir, authorized_keys, snippet_path):
        try:
            os.chown(path, user_info.pw_uid, user_info.pw_gid)
        except OSError:
            pass


def ensure_vm_secret(vm: VmSummary) -> dict[str, Any]:
    existing = load_vm_secret(vm.node, vm.vmid)
    if existing:
        changed = False
        if not str(existing.get("sunshine_username", "")).strip():
            existing["sunshine_username"] = f"sunshine-vm{vm.vmid}"
            changed = True
        if not str(existing.get("sunshine_password", "")).strip():
            existing["sunshine_password"] = random_secret(26)
            changed = True
        if not str(existing.get("sunshine_pin", "")).strip():
            existing["sunshine_pin"] = random_pin()
            changed = True
        if not str(existing.get("thinclient_password", "")).strip():
            existing["thinclient_password"] = random_secret(22)
            changed = True
        if not str(existing.get("usb_tunnel_public_key", "")).strip() or not str(existing.get("usb_tunnel_private_key", "")).strip():
            private_key, public_key = generate_ssh_keypair(f"beagle-vm{vm.vmid}-usb")
            existing["usb_tunnel_private_key"] = private_key
            existing["usb_tunnel_public_key"] = public_key
            changed = True
        if int(existing.get("usb_tunnel_port", 0) or 0) <= 0:
            existing["usb_tunnel_port"] = default_usb_tunnel_port(vm.vmid)
            changed = True
        secret = save_vm_secret(vm.node, vm.vmid, existing) if changed else existing
        secret = ensure_vm_sunshine_pinned_pubkey(vm, secret)
        sync_usb_tunnel_authorized_key(vm, secret)
        return secret
    private_key, public_key = generate_ssh_keypair(f"beagle-vm{vm.vmid}-usb")
    secret = save_vm_secret(
        vm.node,
        vm.vmid,
        {
            "sunshine_username": f"sunshine-vm{vm.vmid}",
            "sunshine_password": random_secret(26),
            "sunshine_pin": random_pin(),
            "thinclient_password": random_secret(22),
            "sunshine_pinned_pubkey": "",
            "usb_tunnel_port": default_usb_tunnel_port(vm.vmid),
            "usb_tunnel_private_key": private_key,
            "usb_tunnel_public_key": public_key,
        },
    )
    secret = ensure_vm_sunshine_pinned_pubkey(vm, secret)
    sync_usb_tunnel_authorized_key(vm, secret)
    return secret


def manager_pinned_pubkey() -> str:
    if not MANAGER_CERT_FILE.is_file():
        return ""
    try:
        pubkey = subprocess.run(
            ["openssl", "x509", "-in", str(MANAGER_CERT_FILE), "-pubkey", "-noout"],
            check=True,
            capture_output=True,
            text=False,
        ).stdout
        der = subprocess.run(
            ["openssl", "pkey", "-pubin", "-outform", "der"],
            check=True,
            input=pubkey,
            capture_output=True,
            text=False,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""
    digest = hashlib.sha256(der).digest()
    return "sha256//" + base64.b64encode(digest).decode("ascii")


MANAGER_PINNED_PUBKEY = manager_pinned_pubkey()


def fetch_https_pinned_pubkey(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    host = str(parsed.hostname or "").strip()
    if not host:
        return ""
    port = parsed.port or 443
    try:
        cert_chain = subprocess.run(
            ["openssl", "s_client", "-connect", f"{host}:{int(port)}", "-servername", host],
            input="",
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=15,
        ).stdout
        cert_match = re.search(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", cert_chain, re.S)
        if not cert_match:
            return ""
        pubkey = subprocess.run(
            ["openssl", "x509", "-pubkey", "-noout"],
            input=cert_match.group(0),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=15,
        ).stdout
        der = subprocess.run(
            ["openssl", "pkey", "-pubin", "-outform", "der"],
            input=pubkey.encode("utf-8"),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""
    digest = hashlib.sha256(der).digest()
    return "sha256//" + base64.b64encode(digest).decode("ascii")


def guest_exec_text(vmid: int, script: str) -> tuple[int, str, str]:
    return HOST_PROVIDER.guest_exec_script_text(
        int(vmid),
        script,
        poll_attempts=300,
        poll_interval_seconds=2.0,
    )


def sunshine_guest_user(vm: VmSummary, config: dict[str, Any] | None = None) -> str:
    vm_config = config if isinstance(config, dict) else get_vm_config(vm.node, vm.vmid)
    meta = parse_description_meta(vm_config.get("description", ""))
    return str(meta.get("sunshine-guest-user", "")).strip() or UBUNTU_BEAGLE_DEFAULT_GUEST_USER


def register_moonlight_certificate_on_vm(vm: VmSummary, client_cert_pem: str, *, device_name: str) -> dict[str, Any]:
    config = get_vm_config(vm.node, vm.vmid)
    guest_user = sunshine_guest_user(vm, config)
    cert_b64 = base64.b64encode(client_cert_pem.encode("utf-8")).decode("ascii")
    device_name = safe_slug(device_name or f"beagle-vm{vm.vmid}-client", f"beagle-vm{vm.vmid}-client")
    script = f"""#!/usr/bin/env bash
set -euo pipefail

guest_user={shlex.quote(guest_user)}
device_name={shlex.quote(device_name)}
state_file="/home/$guest_user/.config/sunshine/sunshine_state.json"
cert_file="$(mktemp /tmp/beagle-cert-XXXXXX.pem)"
trap 'rm -f "$cert_file"' EXIT
cat > "$cert_file.b64" <<'__BEAGLE_CERT__'
{cert_b64}
__BEAGLE_CERT__
base64 -d "$cert_file.b64" > "$cert_file"
rm -f "$cert_file.b64"

python3 - "$state_file" "$device_name" "$cert_file" <<'PY'
import json
import sys
import uuid
from pathlib import Path

state_path = Path(sys.argv[1])
device_name = sys.argv[2]
cert_path = Path(sys.argv[3])

if not state_path.exists():
    raise SystemExit(f"sunshine state file missing: {{state_path}}")

cert = cert_path.read_text(encoding="utf-8")
state = json.loads(state_path.read_text(encoding="utf-8"))
root = state.setdefault("root", {{}})
named = root.setdefault("named_devices", [])

for entry in named:
    if entry.get("cert") == cert:
        entry["name"] = device_name
        state_path.write_text(json.dumps(state, indent=4) + "\\n", encoding="utf-8")
        print("updated-existing")
        raise SystemExit(0)

named.append({{
    "name": device_name,
    "cert": cert,
    "uuid": str(uuid.uuid4()).upper(),
}})
state_path.write_text(json.dumps(state, indent=4) + "\\n", encoding="utf-8")
print("registered-new")
PY

systemctl restart beagle-sunshine.service >/dev/null 2>&1 || true
sleep 2
"""
    exitcode, stdout, stderr = guest_exec_text(vm.vmid, script)
    return {
        "ok": exitcode == 0,
        "guest_user": guest_user,
        "exitcode": exitcode,
        "stdout": stdout,
        "stderr": stderr,
    }


def fetch_sunshine_server_identity(vm: VmSummary, guest_user: str) -> dict[str, Any]:
    state_file = f"/home/{guest_user}/.config/sunshine/sunshine_state.json"
    cert_file = f"/home/{guest_user}/.config/sunshine/credentials/cacert.pem"
    conf_file = f"/home/{guest_user}/.config/sunshine/sunshine.conf"
    script = f"""#!/usr/bin/env bash
set -euo pipefail

python3 - {shlex.quote(state_file)} {shlex.quote(cert_file)} {shlex.quote(conf_file)} <<'PY'
import json
import urllib.request
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

state_path = Path(sys.argv[1])
cert_path = Path(sys.argv[2])
conf_path = Path(sys.argv[3])

payload = {{
    "uniqueid": "",
    "server_cert_pem": "",
    "sunshine_name": "",
    "stream_port": "",
}}

if state_path.exists():
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        payload["uniqueid"] = str(((state.get("root") or {{}}).get("uniqueid") or "")).strip()
    except Exception:
        pass

if cert_path.exists():
    try:
        payload["server_cert_pem"] = cert_path.read_text(encoding="utf-8")
    except Exception:
        pass

if conf_path.exists():
    try:
        for raw_line in conf_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key == "sunshine_name":
                payload["sunshine_name"] = value
            elif key == "port":
                payload["stream_port"] = value
    except Exception:
        pass

stream_port = str(payload.get("stream_port", "") or "").strip()
if not payload["uniqueid"] and stream_port:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{{stream_port}}/serverinfo?uniqueid=0123456789ABCDEF",
            timeout=3,
        ) as response:
            xml_payload = response.read()
        root = ET.fromstring(xml_payload.decode("utf-8", errors="replace"))
        payload["uniqueid"] = str(root.findtext(".//uniqueid", default="") or "").strip()
        if not payload["sunshine_name"]:
            payload["sunshine_name"] = str(root.findtext(".//hostname", default="") or "").strip()
    except Exception:
        pass

print(json.dumps(payload))
PY
"""
    exitcode, stdout, stderr = guest_exec_text(vm.vmid, script)
    if exitcode != 0:
        return {
            "ok": False,
            "exitcode": exitcode,
            "stdout": stdout,
            "stderr": stderr,
            "uniqueid": "",
            "server_cert_pem": "",
            "sunshine_name": "",
            "stream_port": "",
        }
    try:
        payload = json.loads((stdout or "{}").strip() or "{}")
    except json.JSONDecodeError:
        payload = {}
    return {
        "ok": True,
        "exitcode": exitcode,
        "stdout": stdout,
        "stderr": stderr,
        "uniqueid": str(payload.get("uniqueid", "") or "").strip(),
        "server_cert_pem": str(payload.get("server_cert_pem", "") or ""),
        "sunshine_name": str(payload.get("sunshine_name", "") or "").strip(),
        "stream_port": str(payload.get("stream_port", "") or "").strip(),
    }


def internal_sunshine_api_url(vm: VmSummary, profile: dict[str, Any]) -> str:
    public_stream = profile.get("public_stream") if isinstance(profile.get("public_stream"), dict) else None
    guest_ip = str(profile.get("guest_ip", "") or "").strip()
    if public_stream:
        guest_ip = str(public_stream.get("guest_ip", "") or guest_ip).strip()
        ports = public_stream.get("ports", {}) if isinstance(public_stream.get("ports"), dict) else {}
        api_port = ports.get("sunshine_api_port")
        if guest_ip and api_port:
            return f"https://{guest_ip}:{int(api_port)}"
    base_url = str(profile.get("sunshine_api_url", "") or "")
    if guest_ip and base_url:
        parsed = urlparse(base_url)
        if parsed.scheme and parsed.port:
            return urlunparse(parsed._replace(netloc=f"{guest_ip}:{parsed.port}"))
    return base_url


def ensure_vm_sunshine_pinned_pubkey(vm: VmSummary, secret: dict[str, Any]) -> dict[str, Any]:
    if str(secret.get("sunshine_pinned_pubkey", "") or "").strip():
        return secret
    profile = build_profile(vm, allow_assignment=False)
    pin = fetch_https_pinned_pubkey(internal_sunshine_api_url(vm, profile))
    if not pin:
        return secret
    updated = dict(secret)
    updated["sunshine_pinned_pubkey"] = pin
    return save_vm_secret(vm.node, vm.vmid, updated)


def enrollment_token_path(token: str) -> Path:
    return enrollment_token_store_service().token_path(token)


def sunshine_access_token_path(token: str) -> Path:
    return sunshine_access_tokens_dir() / f"{hashlib.sha256(token.encode('utf-8')).hexdigest()}.json"


def issue_enrollment_token(vm: VmSummary) -> tuple[str, dict[str, Any]]:
    record = ensure_vm_secret(vm)
    token = secrets.token_urlsafe(32)
    payload = {
        "vmid": vm.vmid,
        "node": vm.node,
        "profile_name": f"vm-{vm.vmid}",
        "expires_at": datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + ENROLLMENT_TOKEN_TTL_SECONDS, tz=timezone.utc).isoformat(),
        "issued_at": utcnow(),
        "used_at": "",
        "thinclient_password": str(record.get("thinclient_password", "")),
    }
    enrollment_token_store_service().store(token, payload)
    return token, payload


def load_enrollment_token(token: str) -> dict[str, Any] | None:
    return enrollment_token_store_service().load(token)


def issue_sunshine_access_token(vm: VmSummary) -> tuple[str, dict[str, Any]]:
    token = secrets.token_urlsafe(32)
    payload = {
        "vmid": vm.vmid,
        "node": vm.node,
        "issued_at": utcnow(),
        "expires_at": datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + SUNSHINE_ACCESS_TOKEN_TTL_SECONDS, tz=timezone.utc).isoformat(),
    }
    write_json_file(sunshine_access_token_path(token), payload)
    return token, payload


def load_sunshine_access_token(token: str) -> dict[str, Any] | None:
    payload = load_json_file(sunshine_access_token_path(token), None)
    return payload if isinstance(payload, dict) else None


def mark_enrollment_token_used(token: str, payload: dict[str, Any], *, endpoint_id: str) -> None:
    enrollment_token_store_service().mark_used(token, payload, endpoint_id=endpoint_id)


def enrollment_token_is_valid(payload: dict[str, Any] | None, *, endpoint_id: str = "") -> bool:
    return enrollment_token_store_service().is_valid(payload, endpoint_id=endpoint_id)


def sunshine_access_token_is_valid(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    expires_at = parse_utc_timestamp(str(payload.get("expires_at", "")))
    if expires_at is None:
        return False
    return expires_at > datetime.now(timezone.utc)


def endpoint_token_path(token: str) -> Path:
    return endpoint_tokens_dir() / f"{hashlib.sha256(token.encode('utf-8')).hexdigest()}.json"


def store_endpoint_token(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    clean = dict(payload)
    clean["token_issued_at"] = utcnow()
    write_json_file(endpoint_token_path(token), clean)
    return clean


def load_endpoint_token(token: str) -> dict[str, Any] | None:
    payload = load_json_file(endpoint_token_path(token), None)
    return payload if isinstance(payload, dict) else None


def sunshine_proxy_ticket_url(token: str) -> str:
    return f"{PUBLIC_MANAGER_URL}/api/v1/public/sunshine/{token}/"


def proxy_sunshine_request(vm: VmSummary, *, request_path: str, query: str, method: str, body: bytes | None, request_headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
    profile = build_profile(vm)
    base_url = internal_sunshine_api_url(vm, profile).rstrip("/")
    if not base_url:
        raise RuntimeError("missing sunshine api url")
    secret = ensure_vm_secret(vm)
    sunshine_user = str(secret.get("sunshine_username", "") or "")
    sunshine_password = str(secret.get("sunshine_password", "") or "")
    pinned_pubkey = str(secret.get("sunshine_pinned_pubkey", "") or "")
    if not sunshine_user or not sunshine_password:
        raise RuntimeError("missing sunshine credentials")

    relative = "/" + str(request_path or "").lstrip("/")
    target_url = f"{base_url}{relative}"
    if query:
        target_url = f"{target_url}?{query}"

    header_file = tempfile.NamedTemporaryFile(prefix="beagle-sunshine-hdr-", delete=False)
    body_file = tempfile.NamedTemporaryFile(prefix="beagle-sunshine-body-", delete=False)
    header_file.close()
    body_file.close()
    input_name = ""
    try:
        command = [
            "curl",
            "-sS",
            "-D",
            header_file.name,
            "-o",
            body_file.name,
            "-X",
            method.upper(),
            "-u",
            f"{sunshine_user}:{sunshine_password}",
            "--connect-timeout",
            "5",
            "--max-time",
            "30",
        ]
        if pinned_pubkey:
            command.extend(["-k", "--pinnedpubkey", pinned_pubkey])
        for key in ("Content-Type", "Accept"):
            value = str(request_headers.get(key, "") or "").strip()
            if value:
                command.extend(["-H", f"{key}: {value}"])
        if body is not None:
            input_file = tempfile.NamedTemporaryFile(prefix="beagle-sunshine-in-", delete=False)
            input_file.write(body)
            input_file.flush()
            input_name = input_file.name
            input_file.close()
            command.extend(["--data-binary", f"@{input_name}"])
        command.append(target_url)
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "curl failed").strip())

        raw_headers = Path(header_file.name).read_text(encoding="utf-8", errors="replace")
        raw_body = Path(body_file.name).read_bytes()
        blocks = [block for block in re.split(r"\r?\n\r?\n", raw_headers.strip()) if block.strip()]
        header_block = blocks[-1] if blocks else ""
        lines = [line for line in re.split(r"\r?\n", header_block) if line.strip()]
        if not lines or not lines[0].startswith("HTTP/"):
            raise RuntimeError("invalid sunshine proxy response")
        status_code = int(lines[0].split()[1])
        response_headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            response_headers[key.strip()] = value.strip()
        return status_code, response_headers, raw_body
    finally:
        for path in (header_file.name, body_file.name, input_name):
            if path:
                try:
                    Path(path).unlink(missing_ok=True)
                except Exception:
                    pass


DEFAULT_CREDENTIALS = load_shell_env_file(CREDENTIALS_ENV_FILE)
DEFAULT_PROXMOX_USERNAME = (
    DEFAULT_CREDENTIALS.get("PVE_THIN_CLIENT_DEFAULT_PROXMOX_USERNAME")
    or DEFAULT_CREDENTIALS.get("PVE_DCV_PROXMOX_USERNAME")
    or ""
).strip()
DEFAULT_PROXMOX_PASSWORD = (
    DEFAULT_CREDENTIALS.get("PVE_THIN_CLIENT_DEFAULT_PROXMOX_PASSWORD")
    or DEFAULT_CREDENTIALS.get("PVE_DCV_PROXMOX_PASSWORD")
    or ""
).strip()
DEFAULT_PROXMOX_TOKEN = (
    DEFAULT_CREDENTIALS.get("PVE_THIN_CLIENT_DEFAULT_PROXMOX_TOKEN")
    or DEFAULT_CREDENTIALS.get("PVE_DCV_PROXMOX_TOKEN")
    or ""
).strip()


def public_streams_file() -> Path:
    return EFFECTIVE_DATA_DIR / "public-streams.json"


def load_public_streams() -> dict[str, int]:
    payload = load_json_file(public_streams_file(), {})
    if not isinstance(payload, dict):
        return {}
    streams: dict[str, int] = {}
    for key, value in payload.items():
        try:
            streams[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return streams


def save_public_streams(payload: dict[str, int]) -> None:
    write_json_file(public_streams_file(), payload, mode=0o600)


def public_stream_key(node: str, vmid: int) -> str:
    return f"{safe_slug(node, 'node')}:{int(vmid)}"


def explicit_public_stream_base_port(config: dict[str, Any] | None) -> int | None:
    vm_config = config if isinstance(config, dict) else {}
    meta = parse_description_meta(vm_config.get("description", ""))
    explicit_port = str(meta.get("beagle-public-moonlight-port", "")).strip()
    if explicit_port.isdigit():
        return int(explicit_port)
    return None


def used_public_stream_base_ports(
    mappings: dict[str, int],
    *,
    exclude_key: str = "",
    sync_mappings: bool = False,
) -> tuple[set[int], bool]:
    used = {int(value) for key, value in mappings.items() if key != exclude_key}
    changed = False
    known_keys: set[str] = set()
    for vm in list_vms():
        key = public_stream_key(vm.node, vm.vmid)
        known_keys.add(key)
        if key == exclude_key:
            continue
        explicit_port = explicit_public_stream_base_port(get_vm_config(vm.node, vm.vmid))
        if explicit_port is not None:
            used.add(explicit_port)
            if sync_mappings and mappings.get(key) != explicit_port:
                mappings[key] = explicit_port
                changed = True
                continue
        if key in mappings:
            used.add(int(mappings[key]))
    if sync_mappings:
        stale_keys = [key for key in mappings if key != exclude_key and key not in known_keys]
        for key in stale_keys:
            mappings.pop(key, None)
            changed = True
    return used, changed


def allocate_public_stream_base_port(node: str, vmid: int) -> int | None:
    if not current_public_stream_host():
        return None
    mappings = load_public_streams()
    key = public_stream_key(node, vmid)
    explicit_port = explicit_public_stream_base_port(get_vm_config(node, vmid))
    changed = False
    if explicit_port is not None and mappings.get(key) != explicit_port:
        mappings[key] = explicit_port
        changed = True
    existing = explicit_port if explicit_port is not None else mappings.get(key)
    if existing is not None:
        _, sync_changed = used_public_stream_base_ports(mappings, exclude_key=key, sync_mappings=True)
        if changed or sync_changed:
            save_public_streams(mappings)
        return int(existing)
    used, sync_changed = used_public_stream_base_ports(mappings, exclude_key=key, sync_mappings=True)
    changed = changed or sync_changed
    upper_bound = PUBLIC_STREAM_BASE_PORT + (PUBLIC_STREAM_PORT_STEP * PUBLIC_STREAM_PORT_COUNT)
    for candidate in range(PUBLIC_STREAM_BASE_PORT, upper_bound, PUBLIC_STREAM_PORT_STEP):
        if candidate in used:
            continue
        mappings[key] = candidate
        save_public_streams(mappings)
        return candidate
    if changed:
        save_public_streams(mappings)
    return None


def stream_ports(base_port: int) -> dict[str, int]:
    base = int(base_port)
    return {
        "moonlight_port": base,
        "sunshine_api_port": base + 1,
        "https_port": base + 1,
        "rtsp_port": base + 21,
    }


def shell_double_quoted(value: str) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("$", "\\$")
        .replace("`", "\\`")
    )


def patch_installer_defaults(
    script_text: str,
    preset_name: str,
    preset_b64: str,
    installer_iso_url: str,
    installer_bootstrap_url: str,
    installer_payload_url: str,
    writer_variant: str,
) -> str:
    replacements = {
        r'^USB_WRITER_VARIANT="\$\{PVE_THIN_CLIENT_USB_WRITER_VARIANT:-[^"]*}"$':
            f'USB_WRITER_VARIANT="${{PVE_THIN_CLIENT_USB_WRITER_VARIANT:-{shell_double_quoted(writer_variant)}}}"',
        r'^PVE_THIN_CLIENT_PRESET_NAME="\$\{PVE_THIN_CLIENT_PRESET_NAME:-[^"]*}"$':
            f'PVE_THIN_CLIENT_PRESET_NAME="${{PVE_THIN_CLIENT_PRESET_NAME:-{shell_double_quoted(preset_name)}}}"',
        r'^PVE_THIN_CLIENT_PRESET_B64="\$\{PVE_THIN_CLIENT_PRESET_B64:-[^"]*}"$':
            f'PVE_THIN_CLIENT_PRESET_B64="${{PVE_THIN_CLIENT_PRESET_B64:-{shell_double_quoted(preset_b64)}}}"',
        r'^RELEASE_ISO_URL="\$\{RELEASE_ISO_URL:-[^"]*}"$':
            f'RELEASE_ISO_URL="${{RELEASE_ISO_URL:-{shell_double_quoted(installer_iso_url)}}}"',
        r'^RELEASE_BOOTSTRAP_URL="\$\{RELEASE_BOOTSTRAP_URL:-[^"]*}"$':
            f'RELEASE_BOOTSTRAP_URL="${{RELEASE_BOOTSTRAP_URL:-{shell_double_quoted(installer_bootstrap_url)}}}"',
        r'^RELEASE_PAYLOAD_URL="\$\{RELEASE_PAYLOAD_URL:-[^"]*}"$':
            f'RELEASE_PAYLOAD_URL="${{RELEASE_PAYLOAD_URL:-{shell_double_quoted(installer_payload_url)}}}"',
        r'^INSTALL_PAYLOAD_URL="\$\{INSTALL_PAYLOAD_URL:-[^"]*}"$':
            f'INSTALL_PAYLOAD_URL="${{INSTALL_PAYLOAD_URL:-{shell_double_quoted(installer_payload_url)}}}"',
        r'^BOOTSTRAP_DISABLE_CACHE="\$\{PVE_DCV_BOOTSTRAP_DISABLE_CACHE:-[^"]*}"$':
            'BOOTSTRAP_DISABLE_CACHE="${PVE_DCV_BOOTSTRAP_DISABLE_CACHE:-1}"',
    }
    updated = script_text
    for pattern, replacement in replacements.items():
        updated, count = re.subn(pattern, replacement, updated, count=1, flags=re.MULTILINE)
        if count != 1:
            raise ValueError(f"failed to patch installer template for pattern: {pattern}")
    return updated


def patch_windows_installer_defaults(script_text: str, preset_name: str, preset_b64: str, installer_iso_url: str) -> str:
    return (
        script_text
        .replace("__BEAGLE_DEFAULT_RELEASE_ISO_URL__", str(installer_iso_url or ""))
        .replace("__BEAGLE_DEFAULT_PRESET_NAME__", str(preset_name or ""))
        .replace("__BEAGLE_DEFAULT_PRESET_B64__", str(preset_b64 or ""))
    )


def encode_installer_preset(preset: dict[str, Any]) -> str:
    lines = ["# Auto-generated Beagle OS VM preset"]
    for key in sorted(preset):
        lines.append(f"{key}={shlex.quote(str(preset.get(key, '')))}")
    payload = "\n".join(lines) + "\n"
    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


def installer_prep_dir() -> Path:
    path = EFFECTIVE_DATA_DIR / "installer-prep"
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def installer_prep_path(node: str, vmid: int) -> Path:
    safe_node = safe_slug(node, "unknown")
    return installer_prep_dir() / f"{safe_node}-{int(vmid)}.json"


def installer_prep_log_path(node: str, vmid: int) -> Path:
    safe_node = safe_slug(node, "unknown")
    return installer_prep_dir() / f"{safe_node}-{int(vmid)}.log"


def load_installer_prep_state(node: str, vmid: int) -> dict[str, Any] | None:
    payload = load_json_file(installer_prep_path(node, vmid), None)
    return payload if isinstance(payload, dict) else None


def guest_exec_out_data(vmid: int, command: str) -> str:
    payload = HOST_PROVIDER.guest_exec_bash(int(vmid), command)
    return str(payload.get("out-data", "") or "")


def guest_exec_payload(vmid: int, command: str, *, timeout_seconds: int = 20) -> dict[str, Any]:
    return HOST_PROVIDER.guest_exec_bash(
        int(vmid),
        command,
        timeout_seconds=int(timeout_seconds),
        request_timeout=timeout_seconds + 5,
    )


def parse_usbip_port_output(output: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in str(output or "").splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        port_match = re.match(r"Port (\d+):", line.strip())
        if port_match:
            if current:
                items.append(current)
            current = {"port": int(port_match.group(1))}
            continue
        if current is None:
            continue
        if "Remote Bus ID" in line:
            current["busid"] = line.split("Remote Bus ID:", 1)[1].strip()
        elif "Remote bus/dev" in line:
            current["remote_device"] = line.split("Remote bus/dev", 1)[1].strip(": ").strip()
        elif "Remote Bus ID" not in line and "-> usbip" in line:
            current["device"] = line.strip()
            match = re.search(r"/([^/\s]+)\s*$", line.strip())
            if match and not current.get("busid"):
                current["busid"] = match.group(1)
        elif "1-" in line and "usbip" not in line and not current.get("busid"):
            current["device"] = line.strip()
    if current:
        items.append(current)
    return items


def parse_vhci_status_output(output: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("hub ") or line.startswith("hs  ") is False and line.startswith("ss  ") is False:
            continue
        parts = line.split()
        if len(parts) < 6:
            continue
        local_busid = parts[-1]
        if local_busid in {"0-0", "000000"}:
            continue
        try:
            port = int(parts[1])
        except ValueError:
            port = 0
        items.append(
            {
                "port": port,
                "local_busid": local_busid,
                "device": line,
            }
        )
    return items


def guest_usb_attachment_state(vmid: int) -> dict[str, Any]:
    output = guest_exec_out_data(vmid, "command -v usbip >/dev/null 2>&1 && usbip port || true")
    attached = parse_usbip_port_output(output)
    vhci_output = guest_exec_out_data(vmid, "cat /sys/devices/platform/vhci_hcd.0/status 2>/dev/null || true")
    vhci_attached = parse_vhci_status_output(vhci_output)
    return {
        "attached": attached if attached else vhci_attached,
        "attached_count": len(attached if attached else vhci_attached),
        "usbip_available": bool(guest_exec_out_data(vmid, "command -v usbip >/dev/null 2>&1 && echo yes || true").strip()),
        "vhci_attached": vhci_attached,
    }


def wait_for_guest_usb_attachment(vmid: int, busid: str, *, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + max(1.0, timeout_seconds)
    last_state: dict[str, Any] = guest_usb_attachment_state(vmid)
    expected = str(busid).strip()
    while time.monotonic() < deadline:
        attached = last_state.get("attached", []) if isinstance(last_state, dict) else []
        if any(str(item.get("busid", "")).strip() == expected for item in attached):
            return last_state
        vhci_attached = last_state.get("vhci_attached", []) if isinstance(last_state, dict) else []
        if vhci_attached:
            return last_state
        time.sleep(1)
        last_state = guest_usb_attachment_state(vmid)
    return last_state


def wait_for_action_result(node: str, vmid: int, action_id: str, *, timeout_seconds: float) -> dict[str, Any] | None:
    deadline = time.monotonic() + max(1.0, timeout_seconds)
    while time.monotonic() < deadline:
        payload = load_action_result(node, vmid)
        if isinstance(payload, dict) and str(payload.get("action_id", "")).strip() == action_id:
            return payload
        time.sleep(1)
    return None


def build_vm_usb_state(vm: VmSummary, report: dict[str, Any] | None = None) -> dict[str, Any]:
    secret = ensure_vm_secret(vm)
    endpoint_payload = report if isinstance(report, dict) else (load_endpoint_report(vm.node, vm.vmid) or {})
    endpoint_summary = summarize_endpoint_report(endpoint_payload)
    guest_state = guest_usb_attachment_state(vm.vmid)
    return {
        "enabled": True,
        "tunnel_host": PUBLIC_SERVER_NAME,
        "attach_host": USB_TUNNEL_ATTACH_HOST,
        "tunnel_user": USB_TUNNEL_SSH_USER,
        "tunnel_port": int(secret.get("usb_tunnel_port", 0) or 0),
        "tunnel_state": endpoint_summary.get("usb_tunnel_state", ""),
        "device_count": endpoint_summary.get("usb_device_count", 0),
        "bound_count": endpoint_summary.get("usb_bound_count", 0),
        "devices": endpoint_summary.get("usb_devices", []),
        "attached": guest_state.get("attached", []),
        "attached_count": guest_state.get("attached_count", 0),
        "guest_usbip_available": guest_state.get("usbip_available", False),
    }


def attach_usb_to_guest(vm: VmSummary, busid: str) -> dict[str, Any]:
    secret = ensure_vm_secret(vm)
    tunnel_port = int(secret.get("usb_tunnel_port", 0) or 0)
    if tunnel_port <= 0:
        raise RuntimeError("missing usb tunnel port")
    escaped_busid = shlex.quote(str(busid))
    command = (
        "set -euo pipefail; "
        "command -v usbip >/dev/null 2>&1 || { echo 'usbip missing in guest' >&2; exit 40; }; "
        "modprobe vhci-hcd >/dev/null 2>&1 || true; "
        f"if usbip port 2>/dev/null | grep -Fq 'Remote Bus ID: {str(busid)}'; then "
        "  usbip port; "
        "  exit 0; "
        "fi; "
        "ready=0; "
        "for _attempt in $(seq 1 12); do "
        f"  if timeout 2 bash -lc 'exec 3<>/dev/tcp/{USB_TUNNEL_ATTACH_HOST}/{tunnel_port}' >/dev/null 2>&1; then "
        "    ready=1; "
        "    break; "
        "  fi; "
        "  sleep 1; "
        "done; "
        "[ \"$ready\" = \"1\" ] || { echo 'usb tunnel not reachable from guest' >&2; exit 41; }; "
        f"usbip --tcp-port {tunnel_port} attach -r {shlex.quote(USB_TUNNEL_ATTACH_HOST)} -b {escaped_busid}; "
        "usbip port"
    )
    payload = guest_exec_payload(vm.vmid, command, timeout_seconds=30)
    output = str(payload.get("out-data", "") or "")
    error_output = str(payload.get("err-data", "") or "").strip()
    exit_code = int(payload.get("exitcode", 1) or 1)
    guest_state = wait_for_guest_usb_attachment(vm.vmid, busid, timeout_seconds=8)
    attached = guest_state.get("attached", []) if isinstance(guest_state, dict) else []
    vhci_attached = guest_state.get("vhci_attached", []) if isinstance(guest_state, dict) else []
    if exit_code != 0 and not attached and not vhci_attached:
        raise RuntimeError(error_output or output or "usb attach failed")
    if not attached and not vhci_attached:
        raise RuntimeError(error_output or "usb attach completed but guest state did not confirm attachment")
    return {
        "busid": busid,
        "tunnel_port": tunnel_port,
        "attach_host": USB_TUNNEL_ATTACH_HOST,
        "attached": attached or vhci_attached or parse_usbip_port_output(output),
        "guest_state": guest_state,
        "raw_output": output,
        "raw_error": error_output,
    }


def detach_usb_from_guest(vm: VmSummary, *, port: int | None = None, busid: str = "") -> dict[str, Any]:
    guest_state = guest_usb_attachment_state(vm.vmid)
    attached = guest_state.get("attached", []) if isinstance(guest_state, dict) else []
    detach_port = int(port) if port is not None else None
    if detach_port is None and busid:
        for item in attached:
            if str(item.get("busid", "")).strip() == str(busid).strip():
                detach_port = int(item.get("port", 0) or 0)
                break
    if detach_port is None or detach_port < 0:
        raise RuntimeError("usb device is not attached in guest")
    command = f"set -euo pipefail; usbip detach -p {int(detach_port)}; usbip port || true"
    payload = guest_exec_payload(vm.vmid, command, timeout_seconds=15)
    output = str(payload.get("out-data", "") or "")
    error_output = str(payload.get("err-data", "") or "").strip()
    exit_code = int(payload.get("exitcode", 1) or 1)
    post_state = guest_usb_attachment_state(vm.vmid)
    remaining = post_state.get("attached", []) if isinstance(post_state, dict) else []
    if busid:
        still_attached = any(str(item.get("busid", "")).strip() == str(busid).strip() for item in remaining)
    else:
        still_attached = any(int(item.get("port", -1) or -1) == int(detach_port) for item in remaining)
    if exit_code != 0 and still_attached:
        raise RuntimeError(error_output or output or "usb detach failed")
    return {
        "detached_port": int(detach_port),
        "busid": busid,
        "attached": remaining or parse_usbip_port_output(output),
        "raw_output": output,
        "raw_error": error_output,
    }


def quick_sunshine_status(vmid: int) -> dict[str, Any]:
    output = guest_exec_out_data(
        vmid,
        "binary=0; service=0; process=0; "
        "command -v sunshine >/dev/null 2>&1 && binary=1; "
        "(systemctl is-active sunshine >/dev/null 2>&1 || systemctl is-active beagle-sunshine.service >/dev/null 2>&1) && service=1; "
        "pgrep -x sunshine >/dev/null 2>&1 && process=1; "
        "printf '{\"binary\":%s,\"service\":%s,\"process\":%s}\\n' \"$binary\" \"$service\" \"$process\"",
    )
    text = output.strip().splitlines()[-1] if output.strip() else ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = {"binary": 0, "service": 0, "process": 0}
    return {
        "binary": bool(payload.get("binary")),
        "service": bool(payload.get("service")),
        "process": bool(payload.get("process")),
    }


def default_installer_prep_state(vm: VmSummary, sunshine_status: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = build_profile(vm)
    profile_surface = installer_profile_surface(profile, vmid=vm.vmid, installer_iso_url=public_installer_iso_url())
    quick = sunshine_status if isinstance(sunshine_status, dict) else quick_sunshine_status(vm.vmid)
    eligible = bool(profile.get("installer_target_eligible"))
    ready = eligible and bool(quick.get("binary")) and bool(quick.get("service")) and bool(profile.get("stream_host")) and bool(profile.get("moonlight_port"))
    if not eligible:
        status = "unsupported"
        phase = "target"
        progress = 100
        message = str(profile.get("installer_target_message") or "Diese VM ist kein geeignetes Sunshine-Streaming-Ziel.")
    elif ready:
        status = "ready"
        phase = "complete"
        progress = 100
        message = "Sunshine ist aktiv. Das VM-spezifische USB-Installer-Skript ist sofort verfuegbar."
    else:
        status = "idle"
        phase = "inspect"
        progress = 0
        message = "Download startet zuerst die Sunshine-Pruefung und die Stream-Vorbereitung fuer diese VM."
    return {
        "vmid": vm.vmid,
        "node": vm.node,
        "status": status,
        "phase": phase,
        "progress": progress,
        "message": message,
        "updated_at": utcnow(),
        **profile_surface,
        "installer_target_status": "ready" if ready else ("preparing" if eligible else "unsupported"),
        "sunshine_status": {
            "binary": bool(quick.get("binary")),
            "service": bool(quick.get("service")),
            "process": bool(quick.get("process")),
        },
        "ready": ready,
    }


def summarize_installer_prep_state(vm: VmSummary, state: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = build_profile(vm)
    profile_surface = installer_profile_surface(profile, vmid=vm.vmid, installer_iso_url=public_installer_iso_url())
    payload = dict(state) if isinstance(state, dict) else default_installer_prep_state(vm)
    quick = quick_sunshine_status(vm.vmid)
    payload["sunshine_status"] = {
        "binary": bool(quick.get("binary")),
        "service": bool(quick.get("service")),
        "process": bool(quick.get("process")),
    }
    payload["ready"] = str(payload.get("status", "")).strip().lower() == "ready"
    payload.setdefault("vmid", vm.vmid)
    payload.setdefault("node", vm.node)
    payload["contract_version"] = str(payload.get("contract_version") or profile_surface["contract_version"])
    payload["installer_url"] = str(payload.get("installer_url") or profile_surface["installer_url"])
    payload["live_usb_url"] = str(payload.get("live_usb_url") or profile_surface["live_usb_url"])
    payload["installer_windows_url"] = str(payload.get("installer_windows_url") or profile_surface["installer_windows_url"])
    payload["installer_iso_url"] = str(payload.get("installer_iso_url") or profile_surface["installer_iso_url"])
    payload["stream_host"] = str(payload.get("stream_host") or profile_surface["stream_host"])
    payload["moonlight_port"] = str(payload.get("moonlight_port") or profile_surface["moonlight_port"])
    payload["sunshine_api_url"] = str(payload.get("sunshine_api_url") or profile_surface["sunshine_api_url"])
    payload["installer_target_eligible"] = bool(payload.get("installer_target_eligible", profile_surface["installer_target_eligible"]))
    payload["installer_target_message"] = str(payload.get("installer_target_message") or profile_surface["installer_target_message"])
    payload["installer_target_status"] = "ready" if payload["ready"] else ("preparing" if payload["installer_target_eligible"] else "unsupported")
    return payload


def installer_prep_running(state: dict[str, Any] | None) -> bool:
    if not isinstance(state, dict):
        return False
    if str(state.get("status", "")).strip().lower() != "running":
        return False
    age = timestamp_age_seconds(str(state.get("updated_at", "")))
    return age is None or age < 900


def start_installer_prep(vm: VmSummary) -> dict[str, Any]:
    state_path = installer_prep_path(vm.node, vm.vmid)
    log_path = installer_prep_log_path(vm.node, vm.vmid)
    state = load_installer_prep_state(vm.node, vm.vmid)
    default_state = default_installer_prep_state(vm)
    vm_secret = ensure_vm_secret(vm)
    if not bool(default_state.get("installer_target_eligible")):
        return summarize_installer_prep_state(vm, default_state)
    if installer_prep_running(state):
        return summarize_installer_prep_state(vm, state)
    if not INSTALLER_PREP_SCRIPT_FILE.is_file():
        raise FileNotFoundError(f"installer prep script missing: {INSTALLER_PREP_SCRIPT_FILE}")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("ab")
    env = os.environ.copy()
    env.update(
        {
            "VMID": str(vm.vmid),
            "NODE": vm.node,
            "BEAGLE_INSTALLER_PREP_STATE_FILE": str(state_path),
            "BEAGLE_SUNSHINE_DEFAULT_USER": str(vm_secret.get("sunshine_username", "")),
            "BEAGLE_SUNSHINE_DEFAULT_PASSWORD": str(vm_secret.get("sunshine_password", "")),
            "BEAGLE_SUNSHINE_DEFAULT_PIN": str(vm_secret.get("sunshine_pin", "")),
        }
    )
    try:
        subprocess.Popen(
            [str(INSTALLER_PREP_SCRIPT_FILE), "--vmid", str(vm.vmid), "--node", vm.node],
            cwd=str(ROOT_DIR),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log_handle.close()
    bootstrap_state = summarize_installer_prep_state(
        vm,
        {
            "vmid": vm.vmid,
            "node": vm.node,
            "status": "running",
            "phase": "queue",
            "progress": 1,
            "message": f"Sunshine-Pruefung fuer VM {vm.vmid} wurde gestartet.",
            "requested_at": utcnow(),
            "started_at": utcnow(),
            "updated_at": utcnow(),
        },
    )
    state_path.write_text(json.dumps(bootstrap_state, indent=2) + "\n", encoding="utf-8")
    return bootstrap_state


def policy_store_service() -> PolicyStoreService:
    global POLICY_STORE_SERVICE
    if POLICY_STORE_SERVICE is None:
        POLICY_STORE_SERVICE = PolicyStoreService(
            load_json_file=load_json_file,
            normalize_policy_payload=normalize_policy_payload,
            policies_dir=policies_dir,
            safe_slug=safe_slug,
        )
    return POLICY_STORE_SERVICE


def policy_path(name: str) -> Path:
    return policy_store_service().policy_path(name)


def load_action_queue(node: str, vmid: int) -> list[dict[str, Any]]:
    return action_queue_service().load_queue(node, vmid)


def save_action_queue(node: str, vmid: int, queue: list[dict[str, Any]]) -> None:
    action_queue_service().save_queue(node, vmid, queue)


def load_action_result(node: str, vmid: int) -> dict[str, Any] | None:
    return action_queue_service().load_result(node, vmid)


def store_action_result(node: str, vmid: int, payload: dict[str, Any]) -> None:
    action_queue_service().store_result(node, vmid, payload)


def queue_vm_action(vm: VmSummary, action_name: str, requested_by: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    queue = load_action_queue(vm.node, vm.vmid)
    action_id = f"{vm.node}-{vm.vmid}-{int(datetime.now(timezone.utc).timestamp())}-{len(queue) + 1}"
    payload = {
        "action_id": action_id,
        "action": action_name,
        "vmid": vm.vmid,
        "node": vm.node,
        "requested_at": utcnow(),
        "requested_by": requested_by,
    }
    if isinstance(params, dict) and params:
        payload["params"] = params
    queue.append(payload)
    save_action_queue(vm.node, vm.vmid, queue)
    return payload


def queue_bulk_actions(vmids: list[int], action_name: str, requested_by: str) -> list[dict[str, Any]]:
    queued: list[dict[str, Any]] = []
    seen: set[int] = set()
    for vmid in vmids:
        if vmid in seen:
            continue
        seen.add(vmid)
        vm = find_vm(vmid)
        if vm is None:
            continue
        queued.append(queue_vm_action(vm, action_name, requested_by))
    return queued


def dequeue_vm_actions(node: str, vmid: int) -> list[dict[str, Any]]:
    queue = load_action_queue(node, vmid)
    save_action_queue(node, vmid, [])
    return queue


def summarize_action_result(payload: dict[str, Any] | None) -> dict[str, Any]:
    return action_queue_service().summarize_result(payload)


def list_support_bundle_metadata(*, node: str | None = None, vmid: int | None = None) -> list[dict[str, Any]]:
    return support_bundle_store_service().list_metadata(node=node, vmid=vmid)


def find_support_bundle_metadata(bundle_id: str) -> dict[str, Any] | None:
    return support_bundle_store_service().find_metadata(bundle_id)


def store_support_bundle(node: str, vmid: int, action_id: str, filename: str, content: bytes) -> dict[str, Any]:
    safe_node = safe_slug(node, "unknown")
    safe_name = safe_slug(filename, "support-bundle.tar.gz")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    bundle_id = f"{safe_node}-{int(vmid)}-{timestamp}-{safe_slug(action_id, 'action')}"
    archive_path = support_bundle_archive_path(bundle_id, safe_name)
    archive_path.write_bytes(content)
    try:
        os.chmod(archive_path, 0o600)
    except OSError:
        pass
    sha256 = hashlib.sha256(content).hexdigest()
    payload = {
        "bundle_id": bundle_id,
        "node": node,
        "vmid": int(vmid),
        "action_id": action_id,
        "filename": filename,
        "stored_filename": archive_path.name,
        "stored_path": str(archive_path),
        "size": len(content),
        "sha256": sha256,
        "uploaded_at": utcnow(),
        "download_path": f"/api/v1/support-bundles/{bundle_id}/download",
    }
    write_json_file(support_bundle_metadata_path(bundle_id), payload, mode=0o600)
    return payload


def normalize_policy_payload(payload: dict[str, Any], *, policy_name: str | None = None) -> dict[str, Any]:
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
    normalized = {
        "name": name,
        "enabled": enabled,
        "priority": priority,
        "selector": {
            "vmid": int(selector["vmid"]) if str(selector.get("vmid", "")).strip() else None,
            "node": str(selector.get("node", "")).strip(),
            "role": str(selector.get("role", "")).strip(),
            "tags_any": [str(item).strip() for item in selector.get("tags_any", []) if str(item).strip()],
            "tags_all": [str(item).strip() for item in selector.get("tags_all", []) if str(item).strip()],
        },
        "profile": {
            "expected_profile_name": str(profile.get("expected_profile_name", "")).strip(),
            "network_mode": str(profile.get("network_mode", "")).strip(),
            "moonlight_app": str(profile.get("moonlight_app", "")).strip(),
            "stream_host": str(profile.get("stream_host", "")).strip(),
            "moonlight_local_host": str(profile.get("moonlight_local_host", "")).strip(),
            "moonlight_port": str(profile.get("moonlight_port", "")).strip(),
            "sunshine_api_url": str(profile.get("sunshine_api_url", "")).strip(),
            "update_enabled": truthy(profile.get("update_enabled", True), default=True),
            "update_channel": str(profile.get("update_channel", "")).strip(),
            "update_behavior": str(profile.get("update_behavior", "")).strip(),
            "update_feed_url": str(profile.get("update_feed_url", "")).strip(),
            "update_version_pin": str(profile.get("update_version_pin", "")).strip(),
            "moonlight_resolution": str(profile.get("moonlight_resolution", "")).strip(),
            "moonlight_fps": str(profile.get("moonlight_fps", "")).strip(),
            "moonlight_bitrate": str(profile.get("moonlight_bitrate", "")).strip(),
            "moonlight_video_codec": str(profile.get("moonlight_video_codec", "")).strip(),
            "moonlight_video_decoder": str(profile.get("moonlight_video_decoder", "")).strip(),
            "moonlight_audio_config": str(profile.get("moonlight_audio_config", "")).strip(),
            "egress_mode": str(profile.get("egress_mode", "")).strip(),
            "egress_type": str(profile.get("egress_type", "")).strip(),
            "egress_interface": str(profile.get("egress_interface", "")).strip(),
            "egress_domains": listify(profile.get("egress_domains", [])),
            "egress_resolvers": listify(profile.get("egress_resolvers", [])),
            "egress_allowed_ips": listify(profile.get("egress_allowed_ips", [])),
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
            "assigned_target": {
                "vmid": int(profile.get("assigned_target", {}).get("vmid")) if str(profile.get("assigned_target", {}).get("vmid", "")).strip() else None,
                "node": str(profile.get("assigned_target", {}).get("node", "")).strip(),
            } if isinstance(profile.get("assigned_target"), dict) else None,
        },
        "updated_at": utcnow(),
    }
    return normalized


def save_policy(payload: dict[str, Any], *, policy_name: str | None = None) -> dict[str, Any]:
    return policy_store_service().save(payload, policy_name=policy_name)


def load_policy(name: str) -> dict[str, Any] | None:
    return policy_store_service().load(name)


def delete_policy(name: str) -> bool:
    return policy_store_service().delete(name)


def list_policies() -> list[dict[str, Any]]:
    return policy_store_service().list_all()


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
        cleaned = f"beagle-{vmid}"
    return cleaned[:63].strip("-") or f"beagle-{vmid}"


def validate_linux_username(value: str, field_name: str) -> str:
    candidate = str(value or "").strip().lower()
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", candidate):
        raise ValueError(f"invalid {field_name}")
    return candidate


def validate_password(value: str, field_name: str, *, allow_empty: bool = False) -> str:
    candidate = str(value or "")
    if not candidate and allow_empty:
        return ""
    if len(candidate) < UBUNTU_BEAGLE_MIN_PASSWORD_LENGTH:
        raise ValueError(f"{field_name} must be at least {UBUNTU_BEAGLE_MIN_PASSWORD_LENGTH} characters")
    return candidate


def normalize_locale(value: str) -> str:
    candidate = str(value or "").strip() or UBUNTU_BEAGLE_DEFAULT_LOCALE
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+", candidate):
        raise ValueError("invalid identity_locale")
    return candidate


def normalize_keymap(value: str) -> str:
    candidate = str(value or "").strip().lower() or UBUNTU_BEAGLE_DEFAULT_KEYMAP
    if not re.fullmatch(r"[A-Za-z0-9_-]+", candidate):
        raise ValueError("invalid identity_keymap")
    return candidate


def normalize_package_names(value: Any, *, field_name: str) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = re.split(r"[\s,]+", str(value or ""))
    names: list[str] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        item = str(raw_item or "").strip().lower()
        if not item:
            continue
        if not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*", item):
            raise ValueError(f"invalid {field_name}: {item}")
        if item in seen:
            continue
        seen.add(item)
        names.append(item)
    return names


def resolve_ubuntu_beagle_desktop(value: str) -> dict[str, Any]:
    candidate = str(value or "").strip().lower()
    if not candidate:
        candidate = UBUNTU_BEAGLE_DEFAULT_DESKTOP
    if candidate in UBUNTU_BEAGLE_DESKTOPS:
        return UBUNTU_BEAGLE_DESKTOPS[candidate]
    for desktop in UBUNTU_BEAGLE_DESKTOPS.values():
        aliases = [str(item).strip().lower() for item in desktop.get("aliases", []) if str(item).strip()]
        if candidate == str(desktop.get("label", "")).strip().lower() or candidate in aliases:
            return desktop
    raise ValueError(f"unsupported desktop: {candidate}")


def normalize_package_presets(value: Any) -> list[str]:
    presets = normalize_package_names(value, field_name="package_presets")
    supported = set(UBUNTU_BEAGLE_SOFTWARE_PRESETS.keys())
    unknown = [item for item in presets if item not in supported]
    if unknown:
        raise ValueError(f"unsupported package presets: {', '.join(unknown)}")
    return presets


def expand_software_packages(package_presets: list[str], extra_packages: list[str]) -> list[str]:
    packages: list[str] = []
    seen: set[str] = set()
    for preset_id in package_presets:
        preset = UBUNTU_BEAGLE_SOFTWARE_PRESETS.get(preset_id, {})
        for package_name in preset.get("packages", []) if isinstance(preset, dict) else []:
            candidate = str(package_name or "").strip().lower()
            if candidate and candidate not in seen:
                seen.add(candidate)
                packages.append(candidate)
    for package_name in extra_packages:
        candidate = str(package_name or "").strip().lower()
        if candidate and candidate not in seen:
            seen.add(candidate)
            packages.append(candidate)
    return packages


def provisioning_desktop_profiles() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for desktop in UBUNTU_BEAGLE_DESKTOPS.values():
        profiles.append(
            {
                "id": str(desktop.get("id", "")).strip(),
                "label": str(desktop.get("label", "")).strip(),
                "session": str(desktop.get("session", "")).strip(),
                "packages": list(desktop.get("packages", []) or []),
                "features": list(desktop.get("features", []) or []),
            }
        )
    return profiles


def provisioning_software_presets() -> list[dict[str, Any]]:
    presets: list[dict[str, Any]] = []
    for preset in UBUNTU_BEAGLE_SOFTWARE_PRESETS.values():
        presets.append(
            {
                "id": str(preset.get("id", "")).strip(),
                "label": str(preset.get("label", "")).strip(),
                "packages": list(preset.get("packages", []) or []),
                "description": str(preset.get("description", "")).strip(),
            }
        )
    return presets


def provisioning_os_profiles() -> list[dict[str, Any]]:
    return [
        {
            "id": UBUNTU_BEAGLE_PROFILE_ID,
            "label": UBUNTU_BEAGLE_PROFILE_LABEL,
            "family": "ubuntu",
            "release": UBUNTU_BEAGLE_PROFILE_RELEASE,
            "desktop": resolve_ubuntu_beagle_desktop(UBUNTU_BEAGLE_DEFAULT_DESKTOP)["label"],
            "streaming": UBUNTU_BEAGLE_PROFILE_STREAMING,
            "template_set": "ubuntu-beagle",
            "iso_url": UBUNTU_BEAGLE_ISO_URL,
            "features": [
                "Ubuntu Autoinstall",
                "Selectable desktop",
                "LightDM Autologin",
                "Sunshine Streaming",
                "QEMU Guest Agent",
                "Chrome preinstalled",
            ],
        }
    ]


def build_provisioning_catalog() -> dict[str, Any]:
    nodes = list_nodes_inventory()
    storages = list_storage_inventory()
    default_node = next((item["name"] for item in nodes if item.get("status") == "online"), "")
    if not default_node and nodes:
        default_node = str(nodes[0].get("name", "")).strip()
    images_storages = [
        {
            "id": str(item.get("storage", "")).strip(),
            "content": [part.strip() for part in str(item.get("content", "")).split(",") if part.strip()],
            "path": str(item.get("path", "")).strip(),
            "type": str(item.get("type", "")).strip(),
        }
        for item in storages
        if storage_supports_content(str(item.get("storage", "")).strip(), "images")
    ]
    iso_storages = [
        {
            "id": str(item.get("storage", "")).strip(),
            "content": [part.strip() for part in str(item.get("content", "")).split(",") if part.strip()],
            "path": str(item.get("path", "")).strip(),
            "type": str(item.get("type", "")).strip(),
        }
        for item in storages
        if storage_supports_content(str(item.get("storage", "")).strip(), "iso")
    ]
    bridges_by_node = {
        item["name"]: list_bridge_inventory(item["name"]) for item in nodes if str(item.get("name", "")).strip()
    }
    bridges = sorted({bridge for values in bridges_by_node.values() for bridge in values if bridge})
    default_bridge = UBUNTU_BEAGLE_DEFAULT_BRIDGE or (bridges[0] if bridges else "")
    next_vmid_value = next_vmid()
    return {
        "defaults": {
            "node": default_node,
            "bridge": default_bridge,
            "memory": UBUNTU_BEAGLE_DEFAULT_MEMORY_MIB,
            "cores": UBUNTU_BEAGLE_DEFAULT_CORES,
            "disk_gb": UBUNTU_BEAGLE_DEFAULT_DISK_GB,
            "guest_user": UBUNTU_BEAGLE_DEFAULT_GUEST_USER,
            "identity_locale": UBUNTU_BEAGLE_DEFAULT_LOCALE,
            "identity_keymap": UBUNTU_BEAGLE_DEFAULT_KEYMAP,
            "desktop": resolve_ubuntu_beagle_desktop(UBUNTU_BEAGLE_DEFAULT_DESKTOP)["id"],
            "package_presets": [],
            "disk_storage": resolve_storage(UBUNTU_BEAGLE_DISK_STORAGE, "images", UBUNTU_BEAGLE_ISO_STORAGE),
            "iso_storage": resolve_storage(UBUNTU_BEAGLE_ISO_STORAGE, "iso", UBUNTU_BEAGLE_DISK_STORAGE),
            "next_vmid": next_vmid_value,
        },
        "nodes": nodes,
        "bridges": bridges,
        "bridges_by_node": bridges_by_node,
        "storages": {
            "images": images_storages,
            "iso": iso_storages,
        },
        "os_profiles": provisioning_os_profiles(),
        "desktop_profiles": provisioning_desktop_profiles(),
        "software_presets": provisioning_software_presets(),
        "recent_requests": list_ubuntu_beagle_states(),
    }


def create_provisioned_vm(payload: dict[str, Any]) -> dict[str, Any]:
    os_profile = str(payload.get("os_profile", "") or payload.get("os", "") or UBUNTU_BEAGLE_PROFILE_ID).strip() or UBUNTU_BEAGLE_PROFILE_ID
    desktop = str(payload.get("desktop", "") or payload.get("desktop_id", "") or "").strip()
    if os_profile in UBUNTU_BEAGLE_PROFILE_LEGACY_IDS and not desktop:
        desktop = UBUNTU_BEAGLE_PROFILE_LEGACY_IDS[os_profile]
    if os_profile not in {UBUNTU_BEAGLE_PROFILE_ID, *UBUNTU_BEAGLE_PROFILE_LEGACY_IDS.keys()}:
        raise ValueError(f"unsupported os_profile: {os_profile}")
    normalized = dict(payload)
    normalized["os_profile"] = UBUNTU_BEAGLE_PROFILE_ID
    normalized["desktop"] = resolve_ubuntu_beagle_desktop(desktop or UBUNTU_BEAGLE_DEFAULT_DESKTOP)["id"]
    normalized["identity_locale"] = normalize_locale(payload.get("identity_locale", ""))
    normalized["identity_keymap"] = normalize_keymap(payload.get("identity_keymap", ""))
    normalized["package_presets"] = normalize_package_presets(payload.get("package_presets", []))
    normalized["extra_packages"] = normalize_package_names(payload.get("extra_packages", []), field_name="extra_packages")
    return create_ubuntu_beagle_vm(normalized)


def next_vmid() -> int:
    return HOST_PROVIDER.next_vmid()


def indent_block(text: str, prefix: str) -> str:
    lines = str(text).splitlines()
    if not lines:
        return prefix.rstrip()
    return "\n".join(f"{prefix}{line}" if line else prefix.rstrip() for line in lines)


def openssl_password_hash(password: str) -> str:
    salt = secrets.token_hex(8)
    return run_checked(["openssl", "passwd", "-6", "-salt", salt, password]).strip()


def local_iso_storage_dir() -> Path:
    path = Path("/var/lib/vz/template/iso")
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_storage_inventory() -> list[dict[str, Any]]:
    return HOST_PROVIDER.list_storage_inventory()


def storage_supports_content(storage_id: str, content_type: str) -> bool:
    target = str(storage_id or "").strip()
    if not target:
        return False
    for entry in list_storage_inventory():
        if str(entry.get("storage", "")).strip() != target:
            continue
        content = str(entry.get("content", "")).strip()
        supported = {item.strip() for item in content.split(",") if item.strip()}
        return content_type in supported
    return False


def resolve_storage(preferred: str, content_type: str, fallback: str) -> str:
    for candidate in (preferred, fallback):
        if storage_supports_content(candidate, content_type):
            return str(candidate).strip()
    for entry in list_storage_inventory():
        content = str(entry.get("content", "")).strip()
        supported = {item.strip() for item in content.split(",") if item.strip()}
        if content_type in supported:
            candidate = str(entry.get("storage", "")).strip()
            if candidate:
                return candidate
    raise RuntimeError(f"no Proxmox storage with content type '{content_type}' is available")


def ubuntu_beagle_iso_filename(iso_url: str) -> str:
    candidate = Path(urlparse(iso_url).path).name or "ubuntu-live-server-amd64.iso"
    return safe_slug(candidate, "ubuntu-live-server-amd64.iso")


def ubuntu_beagle_extract_dir(iso_filename: str) -> Path:
    path = ubuntu_beagle_tokens_dir() / "extracted" / safe_slug(iso_filename, "ubuntu")
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_ubuntu_beagle_iso_cached(iso_url: str) -> dict[str, str]:
    iso_filename = ubuntu_beagle_iso_filename(iso_url)
    iso_path = local_iso_storage_dir() / iso_filename
    partial_path = iso_path.with_suffix(iso_path.suffix + ".part")
    if not iso_path.exists() or iso_path.stat().st_size == 0:
        run_checked(
            [
                "curl",
                "-fL",
                "--retry",
                "5",
                "--continue-at",
                "-",
                "-o",
                str(partial_path),
                iso_url,
            ],
            timeout=None,
        )
        partial_path.replace(iso_path)

    extract_dir = ubuntu_beagle_extract_dir(iso_filename)
    kernel_path = extract_dir / "vmlinuz"
    initrd_path = extract_dir / "initrd"
    if not kernel_path.exists():
        run_checked(
            [
                "xorriso",
                "-osirrox",
                "on",
                "-indev",
                str(iso_path),
                "-extract",
                "/casper/vmlinuz",
                str(kernel_path),
            ],
            timeout=None,
        )
    if not initrd_path.exists():
        source = "/casper/initrd"
        try:
            run_checked(
                [
                    "xorriso",
                    "-osirrox",
                    "on",
                    "-indev",
                    str(iso_path),
                    "-extract",
                    source,
                    str(initrd_path),
                ],
                timeout=None,
            )
        except subprocess.CalledProcessError:
            run_checked(
                [
                    "xorriso",
                    "-osirrox",
                    "on",
                    "-indev",
                    str(iso_path),
                    "-extract",
                    "/casper/initrd.gz",
                    str(initrd_path),
                ],
                timeout=None,
            )

    return {
        "iso_filename": iso_filename,
        "iso_path": str(iso_path),
        "kernel_path": str(kernel_path),
        "initrd_path": str(initrd_path),
    }


def render_template_file(path: Path, values: dict[str, str]) -> str:
    content = path.read_text(encoding="utf-8")
    for key, value in values.items():
        content = content.replace(key, value)
    return content


def locale_language(locale: str) -> str:
    value = str(locale or "").strip() or UBUNTU_BEAGLE_DEFAULT_LOCALE
    base = value.split(".", 1)[0].strip()
    if not base:
        return ""
    if "_" in base:
        return f"{base}:{base.split('_', 1)[0]}"
    return base


def build_ubuntu_beagle_description(
    hostname: str,
    guest_user: str,
    public_stream: dict[str, Any] | None = None,
    *,
    os_profile: str = UBUNTU_BEAGLE_PROFILE_ID,
    identity_locale: str = "",
    identity_keymap: str = "",
    desktop_id: str = "",
    package_presets: list[str] | None = None,
    extra_packages: list[str] | None = None,
) -> str:
    desktop = resolve_ubuntu_beagle_desktop(desktop_id or UBUNTU_BEAGLE_DEFAULT_DESKTOP)
    package_presets = package_presets or []
    extra_packages = extra_packages or []
    lines = [
        "beagle-role: desktop",
        f"beagle-os-profile: {os_profile}",
        "beagle-os-family: ubuntu",
        f"beagle-os-release: {UBUNTU_BEAGLE_PROFILE_RELEASE}",
        f"beagle-desktop: {desktop['label']}",
        f"beagle-desktop-id: {desktop['id']}",
        f"beagle-desktop-session: {desktop['session']}",
        f"beagle-streaming: {UBUNTU_BEAGLE_PROFILE_STREAMING}",
        f"sunshine-guest-user: {guest_user}",
        "sunshine-app: Desktop",
        "moonlight-app: Desktop",
        "moonlight-resolution: auto",
        "moonlight-fps: 60",
        "moonlight-bitrate: 20000",
        "moonlight-video-codec: H.264",
        "moonlight-video-decoder: auto",
        "moonlight-audio-config: stereo",
        "thinclient-default-mode: MOONLIGHT",
        f"beagle-template-set: ubuntu-beagle",
        f"beagle-template-hostname: {hostname}",
        f"beagle-identity-hostname: {hostname}",
        f"beagle-identity-locale: {identity_locale or UBUNTU_BEAGLE_DEFAULT_LOCALE}",
        f"beagle-identity-keymap: {identity_keymap or UBUNTU_BEAGLE_DEFAULT_KEYMAP}",
    ]
    if package_presets:
        lines.append(f"beagle-package-presets: {','.join(package_presets)}")
    if extra_packages:
        lines.append(f"beagle-extra-packages: {','.join(extra_packages)}")
    if public_stream:
        public_host = str(public_stream.get("host", "")).strip()
        moonlight_port = int(public_stream.get("moonlight_port", 0) or 0)
        sunshine_api_url = str(public_stream.get("sunshine_api_url", "")).strip()
        if public_host:
            lines.append(f"beagle-public-stream-host: {public_host}")
        if moonlight_port > 0:
            lines.append(f"beagle-public-moonlight-port: {moonlight_port}")
        if sunshine_api_url:
            lines.append(f"beagle-public-sunshine-api-url: {sunshine_api_url}")
    return "\n".join(lines) + "\n"


def build_ubuntu_beagle_seed_iso(
    *,
    vmid: int,
    hostname: str,
    guest_user: str,
    guest_password_hash: str,
    identity_locale: str,
    identity_keymap: str,
    desktop_id: str,
    desktop_session: str,
    desktop_packages: list[str],
    software_packages: list[str],
    package_presets: list[str],
    sunshine_user: str,
    sunshine_password: str,
    sunshine_port: int | None,
    callback_url: str,
) -> Path:
    template_dir = UBUNTU_BEAGLE_TEMPLATE_DIR
    if not template_dir.exists():
        raise FileNotFoundError(f"missing ubuntu-beagle templates: {template_dir}")

    firstboot_script = render_template_file(
        template_dir / "firstboot-provision.sh.tpl",
        {
            "__GUEST_USER__": guest_user,
            "__SUNSHINE_USER__": sunshine_user,
            "__SUNSHINE_PASSWORD__": sunshine_password,
            "__SUNSHINE_PORT__": str(int(sunshine_port)) if sunshine_port else "",
            "__SUNSHINE_URL__": UBUNTU_BEAGLE_SUNSHINE_URL,
            "__SUNSHINE_ORIGIN_WEB_UI_ALLOWED__": "wan",
            "__IDENTITY_LOCALE__": identity_locale,
            "__IDENTITY_LANGUAGE__": locale_language(identity_locale),
            "__IDENTITY_KEYMAP__": identity_keymap,
            "__DESKTOP_ID__": desktop_id,
            "__DESKTOP_SESSION__": desktop_session,
            "__DESKTOP_PACKAGES__": " ".join(desktop_packages),
            "__SOFTWARE_PACKAGES__": " ".join(software_packages),
            "__PACKAGE_PRESETS__": ",".join(package_presets),
            "__CALLBACK_URL__": callback_url,
            "__CALLBACK_PINNED_PUBKEY__": MANAGER_PINNED_PUBKEY,
        },
    ).rstrip()
    user_data = render_template_file(
        template_dir / "user-data.tpl",
        {
            "__HOSTNAME__": hostname,
            "__GUEST_USER__": guest_user,
            "__GUEST_PASSWORD_HASH__": guest_password_hash,
            "__IDENTITY_LOCALE__": identity_locale,
            "__IDENTITY_KEYMAP__": identity_keymap,
            "__CALLBACK_URL__": callback_url,
            "__PREPARE_FIRSTBOOT_URL__": callback_url.rsplit("/complete", 1)[0] + "/prepare-firstboot",
            "__PREPARE_FIRSTBOOT_CURL_ARGS__": f'-k --pinnedpubkey "{MANAGER_PINNED_PUBKEY}"' if MANAGER_PINNED_PUBKEY else "",
            "__FIRSTBOOT_SCRIPT__": indent_block(firstboot_script, "          "),
        },
    )
    meta_data = render_template_file(
        template_dir / "meta-data.tpl",
        {
            "__INSTANCE_ID__": f"beagle-ubuntu-{vmid}",
            "__HOSTNAME__": hostname,
        },
    )

    work_dir = ubuntu_beagle_tokens_dir() / "seed" / str(vmid)
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "user-data").write_text(user_data, encoding="utf-8")
    (work_dir / "meta-data").write_text(meta_data, encoding="utf-8")
    seed_name = f"beagle-ubuntu-autoinstall-vm{vmid}.iso"
    seed_path = local_iso_storage_dir() / seed_name
    seed_path.unlink(missing_ok=True)
    run_checked(
        [
            "xorriso",
            "-as",
            "mkisofs",
            "-volid",
            "CIDATA",
            "-joliet",
            "-rock",
            "-output",
            str(seed_path),
            str(work_dir / "user-data"),
            str(work_dir / "meta-data"),
        ],
        timeout=None,
    )
    return seed_path


def finalize_ubuntu_beagle_install(state: dict[str, Any], *, restart: bool = True) -> dict[str, Any]:
    vmid = int(state["vmid"])
    vm = find_vm(vmid)
    config = get_vm_config(vm.node, vm.vmid) if vm is not None else {}
    stale_options = [option for option in ("args", "ide2", "ide3") if option in config]
    for option in stale_options:
        try:
            HOST_PROVIDER.delete_vm_options(vmid, [option], timeout=None)
        except subprocess.CalledProcessError:
            pass
    if str(config.get("boot", "") or "").strip() != "order=scsi0":
        HOST_PROVIDER.set_vm_boot_order(vmid, "order=scsi0", timeout=None)
    if restart:
        try:
            HOST_PROVIDER.stop_vm(vmid, skiplock=True, timeout=None)
        except subprocess.CalledProcessError:
            pass
        try:
            HOST_PROVIDER.start_vm(vmid, timeout=None)
        except subprocess.CalledProcessError:
            pass
    reconcile_script = ROOT_DIR / "scripts" / "reconcile-public-streams.sh"
    if reconcile_script.is_file():
        try:
            run_checked([str(reconcile_script)], timeout=None)
        except subprocess.CalledProcessError:
            pass
    return {"vmid": vmid, "cleanup": "ok", "restart": "stop-start" if restart else "guest-reboot"}


def prepare_ubuntu_beagle_firstboot(state: dict[str, Any]) -> dict[str, Any]:
    cleanup = finalize_ubuntu_beagle_install(state, restart=False)
    restart_state = state.get("host_restart") if isinstance(state.get("host_restart"), dict) else None
    restart_pid = 0
    if restart_state is not None:
        try:
            restart_pid = int(restart_state.get("pid", 0) or 0)
        except (TypeError, ValueError):
            restart_pid = 0
    if restart_pid > 0:
        try:
            os.kill(restart_pid, 0)
        except OSError:
            restart_state = None
    if restart_state is None:
        restart_state = schedule_ubuntu_beagle_vm_restart(int(state["vmid"]))
        state["host_restart"] = restart_state
    state["updated_at"] = utcnow()
    state["status"] = "installing"
    state["phase"] = "firstboot"
    state["message"] = "Ubuntu-Basisinstallation ist abgeschlossen. Der Installer faehrt den Gast jetzt herunter; anschliessend startet der Host ihn vom Systemdatentraeger in das First-Boot-Provisioning."
    state["cleanup"] = cleanup
    return {
        **cleanup,
        "host_restart": restart_state,
    }


def create_ubuntu_beagle_vm(payload: dict[str, Any]) -> dict[str, Any]:
    os_profile = str(payload.get("os_profile", "") or UBUNTU_BEAGLE_PROFILE_ID).strip() or UBUNTU_BEAGLE_PROFILE_ID
    if os_profile not in {UBUNTU_BEAGLE_PROFILE_ID, *UBUNTU_BEAGLE_PROFILE_LEGACY_IDS.keys()}:
        raise ValueError(f"unsupported os_profile: {os_profile}")
    desktop = resolve_ubuntu_beagle_desktop(str(payload.get("desktop", "") or payload.get("desktop_id", "") or UBUNTU_BEAGLE_DEFAULT_DESKTOP))
    package_presets = normalize_package_presets(payload.get("package_presets", []))
    extra_packages = normalize_package_names(payload.get("extra_packages", []), field_name="extra_packages")
    software_packages = expand_software_packages(package_presets, extra_packages)
    node = str(payload.get("node", "")).strip()
    if not node:
        raise ValueError("missing node")
    known_nodes = {str(item.get("name", "")).strip() for item in list_nodes_inventory()}
    if node not in known_nodes:
        raise ValueError(f"unknown node: {node}")
    vmid_value = payload.get("vmid")
    vmid = int(vmid_value) if str(vmid_value or "").strip() else next_vmid()
    if find_vm(vmid, refresh=True) is not None:
        raise ValueError(f"vmid already exists: {vmid}")
    name = str(payload.get("name", "")).strip() or f"ubuntu-beagle-{vmid}"
    if not name:
        raise ValueError("missing name")
    memory = int(payload.get("memory", UBUNTU_BEAGLE_DEFAULT_MEMORY_MIB))
    if memory < 2048:
        raise ValueError("memory must be at least 2048 MiB")
    cores = int(payload.get("cores", UBUNTU_BEAGLE_DEFAULT_CORES))
    if cores < 2:
        raise ValueError("cores must be at least 2")
    disk_gb = int(payload.get("disk_gb", UBUNTU_BEAGLE_DEFAULT_DISK_GB))
    if disk_gb < 32:
        raise ValueError("disk_gb must be at least 32")
    bridge = str(payload.get("bridge", UBUNTU_BEAGLE_DEFAULT_BRIDGE)).strip() or UBUNTU_BEAGLE_DEFAULT_BRIDGE
    if not bridge:
        raise ValueError("missing bridge")
    iso_storage = resolve_storage(
        str(payload.get("iso_storage", UBUNTU_BEAGLE_ISO_STORAGE)).strip() or UBUNTU_BEAGLE_ISO_STORAGE,
        "iso",
        UBUNTU_BEAGLE_ISO_STORAGE,
    )
    disk_storage = resolve_storage(
        str(payload.get("disk_storage", UBUNTU_BEAGLE_DISK_STORAGE)).strip() or UBUNTU_BEAGLE_DISK_STORAGE,
        "images",
        UBUNTU_BEAGLE_DISK_STORAGE,
    )
    guest_user = validate_linux_username(
        str(payload.get("guest_user", UBUNTU_BEAGLE_DEFAULT_GUEST_USER)).strip() or UBUNTU_BEAGLE_DEFAULT_GUEST_USER,
        "guest_user",
    )
    start_after_create = str(payload.get("start", "1")).strip().lower() not in {"0", "false", "no", "off"}
    hostname = safe_hostname(str(payload.get("hostname", "")).strip() or name, vmid)
    iso_assets = ensure_ubuntu_beagle_iso_cached(UBUNTU_BEAGLE_ISO_URL)
    sunshine_user_input = str(payload.get("sunshine_user", "")).strip()
    sunshine_user = validate_linux_username(sunshine_user_input, "sunshine_user") if sunshine_user_input else f"sunshine-vm{vmid}"
    sunshine_password_input = str(payload.get("sunshine_password", ""))
    sunshine_password = validate_password(sunshine_password_input, "sunshine_password", allow_empty=True) or random_secret(26)
    guest_password_input = str(payload.get("guest_password", ""))
    guest_password = validate_password(guest_password_input, "guest_password", allow_empty=True) or random_secret(20)
    identity_locale = normalize_locale(payload.get("identity_locale", ""))
    identity_keymap = normalize_keymap(payload.get("identity_keymap", ""))
    guest_password_hash = openssl_password_hash(guest_password)
    completion_token = secrets.token_urlsafe(24)
    callback_url = public_ubuntu_beagle_complete_url(completion_token)
    public_stream: dict[str, Any] | None = None
    public_base_port = allocate_public_stream_base_port(node, vmid)
    sunshine_port: int | None = None
    resolved_public_stream_host = current_public_stream_host()
    if resolved_public_stream_host and public_base_port is not None:
        ports = stream_ports(public_base_port)
        sunshine_port = ports["moonlight_port"]
        public_stream = {
            "host": resolved_public_stream_host,
            "moonlight_port": ports["moonlight_port"],
            "sunshine_api_url": f"https://{resolved_public_stream_host}:{ports['sunshine_api_port']}",
        }
    seed_path = build_ubuntu_beagle_seed_iso(
        vmid=vmid,
        hostname=hostname,
        guest_user=guest_user,
        guest_password_hash=guest_password_hash,
        identity_locale=identity_locale,
        identity_keymap=identity_keymap,
        desktop_id=str(desktop["id"]),
        desktop_session=str(desktop["session"]),
        desktop_packages=list(desktop.get("packages", []) or []),
        software_packages=software_packages,
        package_presets=package_presets,
        sunshine_user=sunshine_user,
        sunshine_password=sunshine_password,
        sunshine_port=sunshine_port,
        callback_url=callback_url,
    )
    description = build_ubuntu_beagle_description(
        hostname,
        guest_user,
        public_stream,
        os_profile=os_profile,
        identity_locale=identity_locale,
        identity_keymap=identity_keymap,
        desktop_id=str(desktop["id"]),
        package_presets=package_presets,
        extra_packages=extra_packages,
    )
    # When the live-server installer boots with an attached CIDATA seed ISO,
    # Ubuntu 24.04 reliably autodetects NoCloud on its own. Forcing
    # ds=nocloud;s=/cidata/ here leaves Subiquity in interactive mode instead
    # of consuming the bundled autoinstall config.
    args = " ".join(
        [
            f"-kernel {shlex.quote(iso_assets['kernel_path'])}",
            f"-initrd {shlex.quote(iso_assets['initrd_path'])}",
            "-append",
            shlex.quote("autoinstall console=tty0 console=ttyS0,115200n8 ---"),
        ]
    )
    tags = "beagle;desktop;ubuntu"
    state = save_ubuntu_beagle_state(
        completion_token,
        {
            "token": completion_token,
            "node": node,
            "vmid": vmid,
            "name": name,
            "hostname": hostname,
            "os_profile": os_profile,
            "guest_user": guest_user,
            "guest_password": guest_password,
            "sunshine_user": sunshine_user,
            "sunshine_password": sunshine_password,
            "desktop": str(desktop["id"]),
            "desktop_label": str(desktop["label"]),
            "package_presets": package_presets,
            "extra_packages": extra_packages,
            "software_packages": software_packages,
            "identity_locale": identity_locale,
            "identity_keymap": identity_keymap,
            "bridge": bridge,
            "disk_storage": disk_storage,
            "iso_storage": iso_storage,
            "seed_iso": str(seed_path),
            "iso_filename": iso_assets["iso_filename"],
            "callback_url": callback_url,
            "public_stream": public_stream,
            "status": "creating",
            "phase": "proxmox-create",
            "message": "Proxmox-VM und Autoinstall-Medien werden vorbereitet.",
            "created_at": utcnow(),
            "updated_at": utcnow(),
            "expires_at": (
                datetime.now(timezone.utc).timestamp() + UBUNTU_BEAGLE_AUTOINSTALL_URL_TTL_SECONDS
            ),
        },
    )

    try:
        HOST_PROVIDER.create_vm(
            vmid,
            [
                ("name", name),
                ("memory", str(memory)),
                ("cores", str(cores)),
                ("cpu", "host"),
                ("machine", "q35"),
                ("bios", "ovmf"),
                ("ostype", "l26"),
                ("agent", "enabled=1"),
                ("net0", f"virtio,bridge={bridge}"),
                ("tags", tags),
            ],
            timeout=None,
        )
        HOST_PROVIDER.set_vm_description(vmid, description, timeout=None)
        HOST_PROVIDER.set_vm_options(
            vmid,
            [
                ("scsihw", "virtio-scsi-single"),
                ("scsi0", f"{disk_storage}:{disk_gb}"),
                ("efidisk0", f"{disk_storage}:0,efitype=4m,pre-enrolled-keys=1"),
                ("serial0", "socket"),
                ("vga", "std"),
                ("ide2", f"{iso_storage}:iso/{iso_assets['iso_filename']},media=cdrom"),
                ("ide3", f"{iso_storage}:iso/{seed_path.name},media=cdrom"),
                ("args", args),
            ],
            timeout=None,
        )
        HOST_PROVIDER.set_vm_boot_order(vmid, "order=scsi0;ide2;ide3", timeout=None)
        if start_after_create:
            HOST_PROVIDER.start_vm(vmid, timeout=None)
        invalidate_vm_cache(vmid, node)
    except Exception as exc:
        invalidate_vm_cache(vmid, node)
        state["status"] = "failed"
        state["phase"] = "proxmox-create"
        state["message"] = "Die VM konnte nicht vollstaendig angelegt werden."
        state["error"] = str(exc)
        state["failed_at"] = utcnow()
        state["updated_at"] = utcnow()
        save_ubuntu_beagle_state(completion_token, state)
        raise

    save_vm_secret(
        node,
        vmid,
        {
            "sunshine_username": sunshine_user,
            "sunshine_password": sunshine_password,
            "sunshine_pin": random_pin(),
            "thinclient_password": random_secret(22),
            "sunshine_pinned_pubkey": "",
            "usb_tunnel_port": default_usb_tunnel_port(vmid),
            "node": node,
            "vmid": vmid,
            "updated_at": utcnow(),
        },
    )
    created_vm = VmSummary(vmid=vmid, node=node, name=name, status="running" if start_after_create else "stopped", tags=tags)
    secret = ensure_vm_secret(created_vm)
    state["status"] = "installing" if start_after_create else "created"
    state["phase"] = "autoinstall" if start_after_create else "awaiting-start"
    state["message"] = (
        f"Ubuntu-Autoinstall laeuft. {desktop['label']}, LightDM und Sunshine werden im Guest eingerichtet."
        if start_after_create
        else f"VM angelegt. Starten Sie die VM, um Ubuntu, {desktop['label']}, LightDM und Sunshine zu provisionieren."
    )
    state["started"] = start_after_create
    state["updated_at"] = utcnow()
    save_ubuntu_beagle_state(completion_token, state)
    return {
        "vmid": vmid,
        "node": node,
        "name": name,
        "hostname": hostname,
        "os_profile": os_profile,
        "desktop": str(desktop["id"]),
        "desktop_label": str(desktop["label"]),
        "package_presets": package_presets,
        "extra_packages": extra_packages,
        "bridge": bridge,
        "disk_storage": disk_storage,
        "iso_storage": iso_storage,
        "iso_filename": iso_assets["iso_filename"],
        "seed_iso": seed_path.name,
        "guest_user": guest_user,
        "guest_password": guest_password,
        "identity_locale": identity_locale,
        "identity_keymap": identity_keymap,
        "sunshine_user": str(secret.get("sunshine_username", "") or sunshine_user),
        "sunshine_password": str(secret.get("sunshine_password", "") or sunshine_password),
        "completion_token": completion_token,
        "completion_url": callback_url,
        "started": start_after_create,
        "state": state,
        "provisioning": summarize_ubuntu_beagle_state(state, include_credentials=True),
        "public_stream": public_stream,
    }


def first_guest_ipv4(vmid: int) -> str:
    return VIRTUALIZATION_INVENTORY.first_guest_ipv4(vmid)


def list_vms(*, refresh: bool = False) -> list[VmSummary]:
    return VIRTUALIZATION_INVENTORY.list_vms(refresh=refresh)


def list_nodes_inventory() -> list[dict[str, Any]]:
    return VIRTUALIZATION_INVENTORY.list_nodes_inventory()


def config_bridge_names(config: dict[str, Any]) -> set[str]:
    return VIRTUALIZATION_INVENTORY.config_bridge_names(config)


def list_bridge_inventory(node: str = "") -> list[str]:
    return VIRTUALIZATION_INVENTORY.list_bridge_inventory(node)


def get_vm_config(node: str, vmid: int) -> dict[str, Any]:
    return VIRTUALIZATION_INVENTORY.get_vm_config(node, vmid)


def find_vm(vmid: int, *, refresh: bool = False) -> VmSummary | None:
    return VIRTUALIZATION_INVENTORY.find_vm(vmid, refresh=refresh)


def should_use_public_stream(meta: dict[str, str], guest_ip: str) -> bool:
    return vm_profile_service().should_use_public_stream(meta, guest_ip)


def build_public_stream_details(vm: VmSummary, meta: dict[str, str], guest_ip: str) -> dict[str, Any] | None:
    return vm_profile_service().build_public_stream_details(vm, meta, guest_ip)


def resolve_assigned_target(target_vmid: int, target_node: str, *, allow_assignment: bool) -> dict[str, Any] | None:
    return vm_profile_service().resolve_assigned_target(target_vmid, target_node, allow_assignment=allow_assignment)


def resolve_policy_for_vm(vm: VmSummary, meta: dict[str, str]) -> dict[str, Any] | None:
    return vm_profile_service().resolve_policy_for_vm(vm, meta)


def assess_vm_fingerprint(config: dict[str, Any], meta: dict[str, str], guest_ip: str) -> dict[str, Any]:
    return vm_profile_service().assess_vm_fingerprint(config, meta, guest_ip)


def build_profile(vm: VmSummary, *, allow_assignment: bool = True) -> dict[str, Any]:
    return vm_profile_service().build_profile(vm, allow_assignment=allow_assignment)


def vm_profile_service() -> VmProfileService:
    global VM_PROFILE_SERVICE
    if VM_PROFILE_SERVICE is None:
        VM_PROFILE_SERVICE = VmProfileService(
            allocate_public_stream_base_port=allocate_public_stream_base_port,
            current_public_stream_host=current_public_stream_host,
            expand_software_packages=expand_software_packages,
            find_vm=lambda vmid: VIRTUALIZATION_INVENTORY.find_vm(vmid),
            first_guest_ipv4=first_guest_ipv4,
            get_vm_config=get_vm_config,
            list_policies=list_policies,
            listify=listify,
            load_vm_secret=load_vm_secret,
            manager_pinned_pubkey=MANAGER_PINNED_PUBKEY,
            normalize_endpoint_profile_contract=normalize_endpoint_profile_contract,
            parse_description_meta=parse_description_meta,
            public_installer_iso_url=public_installer_iso_url,
            public_manager_url=PUBLIC_MANAGER_URL,
            resolve_public_stream_host=resolve_public_stream_host,
            resolve_ubuntu_beagle_desktop=resolve_ubuntu_beagle_desktop,
            safe_hostname=safe_hostname,
            stream_ports=stream_ports,
            truthy=truthy,
            ubuntu_beagle_default_desktop=UBUNTU_BEAGLE_DEFAULT_DESKTOP,
            ubuntu_beagle_default_guest_user=UBUNTU_BEAGLE_DEFAULT_GUEST_USER,
            ubuntu_beagle_default_keymap=UBUNTU_BEAGLE_DEFAULT_KEYMAP,
            ubuntu_beagle_default_locale=UBUNTU_BEAGLE_DEFAULT_LOCALE,
            ubuntu_beagle_software_presets=UBUNTU_BEAGLE_SOFTWARE_PRESETS,
        )
    return VM_PROFILE_SERVICE


def vm_state_service() -> VmStateService:
    global VM_STATE_SERVICE
    if VM_STATE_SERVICE is None:
        VM_STATE_SERVICE = VmStateService(
            build_profile=build_profile,
            latest_ubuntu_beagle_state_for_vmid=latest_ubuntu_beagle_state_for_vmid,
            load_action_queue=load_action_queue,
            load_action_result=load_action_result,
            load_endpoint_report=load_endpoint_report,
            load_installer_prep_state=load_installer_prep_state,
            stale_endpoint_seconds=STALE_ENDPOINT_SECONDS,
            summarize_action_result=summarize_action_result,
            summarize_endpoint_report=summarize_endpoint_report,
            summarize_installer_prep_state=summarize_installer_prep_state,
            timestamp_age_seconds=timestamp_age_seconds,
        )
    return VM_STATE_SERVICE


def evaluate_endpoint_compliance(profile: dict[str, Any], report: dict[str, Any] | None) -> dict[str, Any]:
    return vm_state_service().evaluate_endpoint_compliance(profile, report)


def build_vm_state(vm: VmSummary) -> dict[str, Any]:
    return vm_state_service().build_vm_state(vm)


def update_ubuntu_beagle_vm(vmid: int, payload: dict[str, Any]) -> dict[str, Any]:
    vm = find_vm(vmid, refresh=True)
    if vm is None:
        raise ValueError("vm not found")
    current_profile = build_profile(vm)
    if str(current_profile.get("beagle_role", "")).strip().lower() != "desktop":
        raise ValueError("vm is not a managed Beagle desktop target")

    desktop = resolve_ubuntu_beagle_desktop(
        str(payload.get("desktop", "") or payload.get("desktop_id", "") or current_profile.get("desktop_id", "") or UBUNTU_BEAGLE_DEFAULT_DESKTOP)
    )
    package_presets = normalize_package_presets(payload.get("package_presets", current_profile.get("package_presets", [])))
    extra_packages = normalize_package_names(payload.get("extra_packages", current_profile.get("extra_packages", [])), field_name="extra_packages")
    software_packages = expand_software_packages(package_presets, extra_packages)
    identity_locale = normalize_locale(payload.get("identity_locale", current_profile.get("identity_locale", "")))
    identity_keymap = normalize_keymap(payload.get("identity_keymap", current_profile.get("identity_keymap", "")))
    guest_user = validate_linux_username(str(current_profile.get("guest_user", "") or UBUNTU_BEAGLE_DEFAULT_GUEST_USER), "guest_user")
    hostname = safe_hostname(
        str(current_profile.get("identity_hostname", "") or current_profile.get("name", "") or f"beagle-{vmid}"),
        vmid,
    )
    public_stream = current_profile.get("public_stream") if isinstance(current_profile.get("public_stream"), dict) else None
    description = build_ubuntu_beagle_description(
        hostname,
        guest_user,
        public_stream,
        os_profile=UBUNTU_BEAGLE_PROFILE_ID,
        identity_locale=identity_locale,
        identity_keymap=identity_keymap,
        desktop_id=str(desktop["id"]),
        package_presets=package_presets,
        extra_packages=extra_packages,
    )
    HOST_PROVIDER.set_vm_description(vmid, description, timeout=None)

    applied = False
    if vm.status == "running":
        secret = ensure_vm_secret(vm)
        provisioning_state = latest_ubuntu_beagle_state_for_vmid(vmid, include_credentials=True) or {}
        credentials = provisioning_state.get("credentials") if isinstance(provisioning_state.get("credentials"), dict) else {}
        guest_password = str(credentials.get("guest_password", "") or "").strip()
        sunshine_user = str(secret.get("sunshine_username", "") or "").strip()
        sunshine_password = str(secret.get("sunshine_password", "") or "").strip()
        if not sunshine_user or not sunshine_password:
            raise RuntimeError("sunshine credentials are missing for guest reconfiguration")
        configure_command = [
            str(ROOT_DIR / "scripts" / "configure-sunshine-guest.sh"),
            "--proxmox-host",
            "localhost",
            "--vmid",
            str(vmid),
            "--guest-user",
            guest_user,
            "--guest-password",
            guest_password,
            "--identity-locale",
            identity_locale,
            "--identity-keymap",
            identity_keymap,
            "--desktop-id",
            str(desktop["id"]),
            "--desktop-label",
            str(desktop["label"]),
            "--desktop-session",
            str(desktop["session"]),
            "--sunshine-user",
            sunshine_user,
            "--sunshine-password",
            sunshine_password,
        ]
        sunshine_pin = str(secret.get("sunshine_pin", "") or "").strip()
        if sunshine_pin:
            configure_command.extend(["--sunshine-pin", sunshine_pin])
        moonlight_port = str(current_profile.get("moonlight_port", "") or "").strip()
        if moonlight_port.isdigit():
            configure_command.extend(["--sunshine-port", moonlight_port])
        public_stream_host = str(current_profile.get("stream_host", "") or "").strip()
        if public_stream_host:
            configure_command.extend(["--public-stream-host", public_stream_host])
        for package_name in desktop.get("packages", []) or []:
            configure_command.extend(["--desktop-package", str(package_name)])
        for package_name in software_packages:
            configure_command.extend(["--software-package", package_name])
        for preset_id in package_presets:
            configure_command.extend(["--package-preset", preset_id])
        for package_name in extra_packages:
            configure_command.extend(["--extra-package", package_name])
        run_checked(configure_command, timeout=None)
        applied = True

    invalidate_vm_cache(vmid, vm.node)
    updated_vm = find_vm(vmid, refresh=True) or vm
    updated_profile = build_profile(updated_vm)
    return {
        "vmid": vmid,
        "node": updated_vm.node,
        "name": updated_vm.name,
        "applied": applied,
        "desktop": str(desktop["id"]),
        "desktop_label": str(desktop["label"]),
        "package_presets": package_presets,
        "extra_packages": extra_packages,
        "software_packages": software_packages,
        "identity_locale": identity_locale,
        "identity_keymap": identity_keymap,
        "requires_running_guest": not applied,
        "profile": updated_profile,
        "message": (
            "Desktop profile and packages were applied inside the running guest."
            if applied
            else "VM metadata was updated. Start the guest and re-run the edit action to apply packages inside Ubuntu."
        ),
    }


def health_payload_service() -> HealthPayloadService:
    global HEALTH_PAYLOAD_SERVICE
    if HEALTH_PAYLOAD_SERVICE is None:
        HEALTH_PAYLOAD_SERVICE = HealthPayloadService(
            build_profile=build_profile,
            data_dir=EFFECTIVE_DATA_DIR,
            downloads_status_file=DOWNLOADS_STATUS_FILE,
            host_provider_kind=BEAGLE_HOST_PROVIDER_KIND,
            list_endpoint_reports=list_endpoint_reports,
            list_policies=list_policies,
            list_providers=list_providers,
            list_vms=list_vms,
            load_action_queue=load_action_queue,
            load_endpoint_report=load_endpoint_report,
            load_json_file=load_json_file,
            service_name="beagle-control-plane",
            stale_endpoint_seconds=STALE_ENDPOINT_SECONDS,
            summarize_endpoint_report=summarize_endpoint_report,
            utcnow=utcnow,
            version=VERSION,
            vm_installers_file=VM_INSTALLERS_FILE,
        )
    return HEALTH_PAYLOAD_SERVICE


def build_health_payload() -> dict[str, Any]:
    return health_payload_service().build_payload()


def endpoint_report_service() -> EndpointReportService:
    global ENDPOINT_REPORT_SERVICE
    if ENDPOINT_REPORT_SERVICE is None:
        ENDPOINT_REPORT_SERVICE = EndpointReportService(
            endpoints_dir=endpoints_dir,
            load_json_file=load_json_file,
            timestamp_age_seconds=timestamp_age_seconds,
        )
    return ENDPOINT_REPORT_SERVICE


def summarize_endpoint_report(payload: dict[str, Any]) -> dict[str, Any]:
    return endpoint_report_service().summarize(payload)


def update_feed_service() -> UpdateFeedService:
    global UPDATE_FEED_SERVICE
    if UPDATE_FEED_SERVICE is None:
        UPDATE_FEED_SERVICE = UpdateFeedService(
            downloads_status_file=DOWNLOADS_STATUS_FILE,
            load_json_file=load_json_file,
            update_payload_metadata=update_payload_metadata,
            public_update_sha256sums_url=public_update_sha256sums_url,
        )
    return UPDATE_FEED_SERVICE


def build_update_feed(profile: dict[str, Any], *, installed_version: str = "", channel: str = "", version_pin: str = "") -> dict[str, Any]:
    return update_feed_service().build_update_feed(
        profile,
        installed_version=installed_version,
        channel=channel,
        version_pin=version_pin,
    )


def endpoint_report_path(node: str, vmid: int) -> Path:
    return endpoint_report_service().report_path(node, vmid)


def load_endpoint_report(node: str, vmid: int) -> dict[str, Any] | None:
    return endpoint_report_service().load(node, vmid)


def list_endpoint_reports() -> list[dict[str, Any]]:
    return endpoint_report_service().list_all()


def fleet_inventory_service() -> FleetInventoryService:
    global FLEET_INVENTORY_SERVICE
    if FLEET_INVENTORY_SERVICE is None:
        FLEET_INVENTORY_SERVICE = FleetInventoryService(
            build_profile=build_profile,
            latest_ubuntu_beagle_state_for_vmid=latest_ubuntu_beagle_state_for_vmid,
            list_support_bundle_metadata=list_support_bundle_metadata,
            list_vms=list_vms,
            load_action_queue=load_action_queue,
            load_action_result=load_action_result,
            load_endpoint_report=load_endpoint_report,
            load_json_file=load_json_file,
            public_installer_iso_url=public_installer_iso_url,
            service_name="beagle-control-plane",
            summarize_action_result=summarize_action_result,
            summarize_endpoint_report=summarize_endpoint_report,
            utcnow=utcnow,
            version=VERSION,
            vm_installers_file=VM_INSTALLERS_FILE,
        )
    return FLEET_INVENTORY_SERVICE


def build_vm_inventory() -> dict[str, Any]:
    return fleet_inventory_service().build_inventory()


def installer_script_service() -> InstallerScriptService:
    global INSTALLER_SCRIPT_SERVICE
    if INSTALLER_SCRIPT_SERVICE is None:
        INSTALLER_SCRIPT_SERVICE = InstallerScriptService(
            build_profile=build_profile,
            encode_installer_preset=encode_installer_preset,
            ensure_vm_secret=ensure_vm_secret,
            fetch_sunshine_server_identity=fetch_sunshine_server_identity,
            get_vm_config=get_vm_config,
            hosted_installer_iso_file=HOSTED_INSTALLER_ISO_FILE,
            hosted_installer_template_file=HOSTED_INSTALLER_TEMPLATE_FILE,
            hosted_live_usb_template_file=HOSTED_LIVE_USB_TEMPLATE_FILE,
            issue_enrollment_token=issue_enrollment_token,
            manager_pinned_pubkey=MANAGER_PINNED_PUBKEY,
            parse_description_meta=parse_description_meta,
            patch_installer_defaults=patch_installer_defaults,
            patch_windows_installer_defaults=patch_windows_installer_defaults,
            public_bootstrap_latest_download_url=public_bootstrap_latest_download_url,
            public_installer_iso_url=public_installer_iso_url,
            public_manager_url=PUBLIC_MANAGER_URL,
            public_payload_latest_download_url=public_payload_latest_download_url,
            public_server_name=PUBLIC_SERVER_NAME,
            raw_windows_installer_template_file=RAW_WINDOWS_INSTALLER_TEMPLATE_FILE,
            safe_hostname=safe_hostname,
            sunshine_guest_user=sunshine_guest_user,
        )
    return INSTALLER_SCRIPT_SERVICE


def build_installer_preset(vm: VmSummary, profile: dict[str, Any], config: dict[str, Any], *, enrollment_token: str, thinclient_password: str) -> dict[str, str]:
    return installer_script_service().build_preset(
        vm,
        profile,
        config,
        enrollment_token=enrollment_token,
        thinclient_password=thinclient_password,
    )


def render_vm_installer_script(vm: VmSummary) -> tuple[bytes, str]:
    return installer_script_service().render_installer_script(vm)


def render_vm_live_usb_script(vm: VmSummary) -> tuple[bytes, str]:
    return installer_script_service().render_live_usb_script(vm)


def render_vm_windows_installer_script(vm: VmSummary) -> tuple[bytes, str]:
    return installer_script_service().render_windows_installer_script(vm)


def extract_bearer_token(header_value: str) -> str:
    header = str(header_value or "").strip()
    if header.startswith("Bearer "):
        return header[7:].strip()
    return ""


class Handler(BaseHTTPRequestHandler):
    server_version = f"BeagleControlPlane/{VERSION}"

    def _is_authenticated(self) -> bool:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in {"/healthz", "/api/v1/health"}:
            return True
        if ALLOW_LOCALHOST_NOAUTH and self.client_address[0] in {"127.0.0.1", "::1"}:
            return True
        if not API_TOKEN:
            return False
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer ") and header[7:].strip() == API_TOKEN:
            return True
        if self.headers.get("X-Beagle-Api-Token", "").strip() == API_TOKEN:
            return True
        return False

    def _endpoint_identity(self) -> dict[str, Any] | None:
        token = extract_bearer_token(self.headers.get("Authorization", ""))
        if not token:
            token = self.headers.get("X-Beagle-Endpoint-Token", "").strip()
        if not token:
            return None
        payload = load_endpoint_token(token)
        return payload if isinstance(payload, dict) else None

    def _is_endpoint_authenticated(self) -> bool:
        if ALLOW_LOCALHOST_NOAUTH and self.client_address[0] in {"127.0.0.1", "::1"}:
            return True
        return self._endpoint_identity() is not None

    def _cors_origin(self) -> str:
        origin = normalized_origin(self.headers.get("Origin", ""))
        if origin and origin in cors_allowed_origins():
            return origin
        return ""

    def _write_common_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")

    def _write_json(self, status: HTTPStatus, payload: Any) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8") + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self._write_common_security_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > 256 * 1024:
            raise ValueError("invalid content length")
        body = self.rfile.read(length)
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid payload")
        return payload

    def _read_binary_body(self, *, max_bytes: int) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > max_bytes:
            raise ValueError("invalid content length")
        return self.rfile.read(length)

    def _write_bytes(self, status: HTTPStatus, body: bytes, *, content_type: str, filename: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self._write_common_security_headers()
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _endpoint_summary_for_vmid(self, vmid: int) -> dict[str, Any] | None:
        for vm in list_vms():
            if vm.vmid == vmid:
                report = load_endpoint_report(vm.node, vm.vmid)
                if report is None:
                    return None
                return summarize_endpoint_report(report)
        return None

    def _vm_state_for_vmid(self, vmid: int) -> dict[str, Any] | None:
        vm = find_vm(vmid)
        if vm is None:
            return None
        return build_vm_state(vm)

    def _requester_identity(self) -> str:
        if self.client_address and self.client_address[0]:
            return self.client_address[0]
        return "unknown"

    def _sunshine_ticket_vm(self, path: str) -> tuple[VmSummary | None, str]:
        prefix = "/api/v1/public/sunshine/"
        if not path.startswith(prefix):
            return None, ""
        remainder = path[len(prefix):]
        parts = remainder.split("/", 1)
        token = parts[0].strip()
        if not token:
            return None, ""
        payload = load_sunshine_access_token(token)
        if not sunshine_access_token_is_valid(payload):
            return None, ""
        vm = find_vm(int(payload.get("vmid", -1))) if payload else None
        relative = "/" if len(parts) == 1 or not parts[1] else f"/{parts[1]}"
        return vm, relative

    def _write_proxy_response(self, status_code: int, headers: dict[str, str], body: bytes) -> None:
        self.send_response(status_code)
        for key, value in headers.items():
            lower = key.lower()
            if lower in {"transfer-encoding", "connection", "content-length", "content-encoding"}:
                continue
            self.send_header(key, value)
        self.send_header("Cache-Control", "no-store")
        self._write_common_security_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._write_common_security_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Beagle-Api-Token, X-Beagle-Endpoint-Token")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query_text = parsed.query

        if path.startswith("/api/v1/public/sunshine/"):
            vm, relative = self._sunshine_ticket_vm(parsed.path)
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "sunshine ticket not found"})
                return
            try:
                status_code, headers, body = proxy_sunshine_request(
                    vm,
                    request_path=relative,
                    query=query_text,
                    method="GET",
                    body=None,
                    request_headers={"Accept": self.headers.get("Accept", "")},
                )
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"sunshine proxy failed: {exc}"})
                return
            self._write_proxy_response(status_code, headers, body)
            return

        if path.startswith("/api/v1/public/vms/") and path.endswith("/state"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            state = self._vm_state_for_vmid(int(vmid_text))
            if state is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            self._write_json(
                HTTPStatus.OK,
                {
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    **state,
                },
            )
            return

        if path.startswith("/api/v1/public/vms/") and path.endswith("/endpoint"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            state = self._vm_state_for_vmid(int(vmid_text))
            if state is None or not state["endpoint"].get("reported_at"):
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "endpoint not found"})
                return
            self._write_json(
                HTTPStatus.OK,
                {
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    **state,
                },
            )
            return

        if path.startswith("/api/v1/public/vms/") and path.endswith("/installer.sh"):
            self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "public installer download disabled"})
            return
        if path.startswith("/api/v1/public/vms/") and path.endswith("/live-usb.sh"):
            self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "public live USB download disabled"})
            return
        if path.startswith("/api/v1/public/vms/") and path.endswith("/installer.ps1"):
            self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "public installer download disabled"})
            return

        if path == "/api/v1/endpoints/update-feed":
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            identity = self._endpoint_identity() or {}
            vmid = int(identity.get("vmid", 0) or 0)
            vm = find_vm(vmid)
            if vm is None or str(identity.get("node", "")).strip() != vm.node:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            query = parse_qs(query_text or "")
            profile = build_profile(vm)
            update_feed = build_update_feed(
                profile,
                installed_version=str((query.get("installed_version") or [""])[0]).strip(),
                channel=str((query.get("channel") or [""])[0]).strip(),
                version_pin=str((query.get("version_pin") or [""])[0]).strip(),
            )
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "update": update_feed,
                },
            )
            return

        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return

        if path == "/healthz":
            self._write_json(HTTPStatus.OK, {"ok": True, "service": "beagle-control-plane", "version": VERSION})
            return
        if path == "/api/v1/provisioning/catalog":
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "catalog": build_provisioning_catalog(),
                },
            )
            return
        match = re.match(r"^/api/v1/provisioning/vms/(?P<vmid>\d+)$", path)
        if match:
            state = latest_ubuntu_beagle_state_for_vmid(int(match.group("vmid")), include_credentials=True)
            if state is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "provisioning state not found"})
                return
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "provisioning": state,
                },
            )
            return
        if path == "/api/v1/health":
            self._write_json(HTTPStatus.OK, build_health_payload())
            return
        if path == "/api/v1/vms":
            self._write_json(HTTPStatus.OK, build_vm_inventory())
            return
        if path == "/api/v1/endpoints":
            self._write_json(
                HTTPStatus.OK,
                {
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "endpoints": [summarize_endpoint_report(item) for item in list_endpoint_reports()],
                },
            )
            return
        if path == "/api/v1/policies":
            self._write_json(
                HTTPStatus.OK,
                {
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "policies": list_policies(),
                },
            )
            return
        if path.startswith("/api/v1/policies/"):
            policy_name = path.rsplit("/", 1)[-1]
            policy = load_policy(policy_name)
            if policy is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "policy not found"})
                return
            self._write_json(
                HTTPStatus.OK,
                {
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "policy": policy,
                },
            )
            return
        if path.startswith("/api/v1/support-bundles/") and path.endswith("/download"):
            bundle_id = path.split("/")[-2]
            metadata = find_support_bundle_metadata(bundle_id)
            if metadata is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "support bundle not found"})
                return
            archive_path = Path(str(metadata.get("stored_path", "")))
            if not archive_path.is_file():
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "support bundle payload missing"})
                return
            self._write_bytes(
                HTTPStatus.OK,
                archive_path.read_bytes(),
                content_type="application/gzip",
                filename=str(metadata.get("stored_filename") or archive_path.name),
            )
            return
        if path.startswith("/api/v1/vms/"):
            match = re.match(r"^/api/v1/vms/(?P<vmid>\d+)/installer\.sh$", path)
            if match:
                vm = find_vm(int(match.group("vmid")))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                try:
                    body, filename = render_vm_installer_script(vm)
                except FileNotFoundError as exc:
                    self._write_json(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": str(exc)})
                    return
                except ValueError as exc:
                    self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                    return
                self._write_bytes(
                    HTTPStatus.OK,
                    body,
                    content_type="text/x-shellscript; charset=utf-8",
                    filename=filename,
                )
                return
            if path.endswith("/installer.sh"):
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            match = re.match(r"^/api/v1/vms/(?P<vmid>\d+)/live-usb\.sh$", path)
            if match:
                vm = find_vm(int(match.group("vmid")))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                try:
                    body, filename = render_vm_live_usb_script(vm)
                except FileNotFoundError as exc:
                    self._write_json(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": str(exc)})
                    return
                except ValueError as exc:
                    self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                    return
                self._write_bytes(
                    HTTPStatus.OK,
                    body,
                    content_type="text/x-shellscript; charset=utf-8",
                    filename=filename,
                )
                return
            if path.endswith("/live-usb.sh"):
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            match = re.match(r"^/api/v1/vms/(?P<vmid>\d+)/installer\.ps1$", path)
            if match:
                vm = find_vm(int(match.group("vmid")))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                try:
                    body, filename = render_vm_windows_installer_script(vm)
                except FileNotFoundError as exc:
                    self._write_json(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": str(exc)})
                    return
                except ValueError as exc:
                    self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                    return
                self._write_bytes(
                    HTTPStatus.OK,
                    body,
                    content_type="text/plain; charset=utf-8",
                    filename=filename,
                )
                return
            if path.endswith("/installer.ps1"):
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            if path.endswith("/credentials"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                vm = find_vm(int(vmid_text))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                secret = ensure_vm_secret(vm)
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "credentials": {
                            "vmid": vm.vmid,
                            "node": vm.node,
                            "thinclient_username": "thinclient",
                            "thinclient_password": str(secret.get("thinclient_password", "")),
                            "sunshine_username": str(secret.get("sunshine_username", "")),
                            "sunshine_password": str(secret.get("sunshine_password", "")),
                            "sunshine_pin": str(secret.get("sunshine_pin", "")),
                            "usb_tunnel_host": PUBLIC_SERVER_NAME,
                            "usb_tunnel_user": USB_TUNNEL_SSH_USER,
                            "usb_tunnel_port": int(secret.get("usb_tunnel_port", 0) or 0),
                        },
                    },
                )
                return
            if path.endswith("/installer-prep"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                vm = find_vm(int(vmid_text))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                state = summarize_installer_prep_state(vm, load_installer_prep_state(vm.node, vm.vmid))
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "installer_prep": state,
                    },
                )
                return
            if path.endswith("/policy"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                vm = find_vm(int(vmid_text))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                profile = build_profile(vm)
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "applied_policy": profile.get("applied_policy"),
                        "assignment_source": profile.get("assignment_source", ""),
                    },
                )
                return
            if path.endswith("/support-bundles"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                vm = find_vm(int(vmid_text))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "support_bundles": list_support_bundle_metadata(node=vm.node, vmid=vm.vmid),
                    },
                )
                return
            if path.endswith("/usb"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                vm = find_vm(int(vmid_text))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                report = load_endpoint_report(vm.node, vm.vmid)
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "usb": build_vm_usb_state(vm, report),
                    },
                )
                return
            if path.endswith("/update"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                vm = find_vm(int(vmid_text))
                if vm is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                profile = build_profile(vm)
                endpoint = summarize_endpoint_report(load_endpoint_report(vm.node, vm.vmid) or {})
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "update": {
                            "policy": {
                                "enabled": bool(profile.get("update_enabled", True)),
                                "channel": str(profile.get("update_channel", "stable") or "stable"),
                                "behavior": str(profile.get("update_behavior", "prompt") or "prompt"),
                                "feed_url": str(profile.get("update_feed_url", f"{PUBLIC_MANAGER_URL}/api/v1/endpoints/update-feed") or ""),
                                "version_pin": str(profile.get("update_version_pin", "") or ""),
                            },
                            "endpoint": {
                                "state": endpoint.get("update_state", ""),
                                "current_version": endpoint.get("update_current_version", ""),
                                "latest_version": endpoint.get("update_latest_version", ""),
                                "staged_version": endpoint.get("update_staged_version", ""),
                                "current_slot": endpoint.get("update_current_slot", ""),
                                "next_slot": endpoint.get("update_next_slot", ""),
                                "available": endpoint.get("update_available", False),
                                "pending_reboot": endpoint.get("update_pending_reboot", False),
                                "last_scan_at": endpoint.get("update_last_scan_at", ""),
                                "last_error": endpoint.get("update_last_error", ""),
                            },
                            "published_latest_version": str(load_json_file(DOWNLOADS_STATUS_FILE, {}).get("version", "")).strip(),
                        },
                    },
                )
                return
            if path.endswith("/state"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                state = self._vm_state_for_vmid(int(vmid_text))
                if state is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        **state,
                    },
                )
                return
            if path.endswith("/actions"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                vmid = int(vmid_text)
                state = self._vm_state_for_vmid(vmid)
                if state is None:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                    return
                vm = find_vm(vmid)
                assert vm is not None
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "pending_actions": load_action_queue(vm.node, vm.vmid),
                        "last_action": state["last_action"],
                    },
                )
                return
            if path.endswith("/endpoint"):
                vmid_text = path.split("/")[-2]
                if not vmid_text.isdigit():
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                    return
                state = self._vm_state_for_vmid(int(vmid_text))
                if state is None or not state["endpoint"].get("reported_at"):
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "endpoint not found"})
                    return
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        **state,
                    },
                )
                return
            vmid_text = path.rsplit("/", 1)[-1]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            vmid = int(vmid_text)
            vm = next((candidate for candidate in list_vms() if candidate.vmid == vmid), None)
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            self._write_json(
                HTTPStatus.OK,
                {
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "profile": build_profile(vm),
                },
            )
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query or "")

        if path.startswith("/api/v1/public/sunshine/"):
            vm, relative = self._sunshine_ticket_vm(parsed.path)
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "sunshine ticket not found"})
                return
            try:
                body = self._read_binary_body(max_bytes=16 * 1024 * 1024)
                status_code, headers, response_body = proxy_sunshine_request(
                    vm,
                    request_path=relative,
                    query=parsed.query,
                    method="POST",
                    body=body,
                    request_headers={
                        "Content-Type": self.headers.get("Content-Type", ""),
                        "Accept": self.headers.get("Accept", ""),
                    },
                )
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"sunshine proxy failed: {exc}"})
                return
            self._write_proxy_response(status_code, headers, response_body)
            return

        match = re.match(r"^/api/v1/public/ubuntu-install/(?P<token>[A-Za-z0-9._~-]+)/complete$", path)
        if match:
            token = match.group("token")
            state = load_ubuntu_beagle_state(token)
            if state is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "ubuntu install token not found"})
                return
            restart_requested = str(query.get("restart", ["1"])[0]).strip().lower() not in {"0", "false", "no", "off"}
            try:
                cleanup = finalize_ubuntu_beagle_install(state, restart=restart_requested)
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"failed to finalize install: {exc}"})
                return
            cancelled_restart = cancel_scheduled_ubuntu_beagle_vm_restart(state)
            state["completed_at"] = utcnow()
            state["updated_at"] = utcnow()
            state["status"] = "completed"
            state["phase"] = "complete"
            state["message"] = (
                "Ubuntu ist installiert. Boot-Medien wurden entfernt und die VM wurde neu gestartet."
                if restart_requested
                else "Ubuntu ist installiert. Boot-Medien wurden entfernt; der Gast startet jetzt selbst sauber neu."
            )
            state["cleanup"] = cleanup
            if cancelled_restart:
                state["host_restart_cancelled"] = cancelled_restart
            save_ubuntu_beagle_state(token, state)
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "ubuntu_beagle_install": state,
                },
            )
            return

        match = re.match(r"^/api/v1/public/ubuntu-install/(?P<token>[A-Za-z0-9._~-]+)/prepare-firstboot$", path)
        if match:
            token = match.group("token")
            state = load_ubuntu_beagle_state(token)
            if state is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "ubuntu install token not found"})
                return
            try:
                cleanup = prepare_ubuntu_beagle_firstboot(state)
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"failed to prepare first boot: {exc}"})
                return
            save_ubuntu_beagle_state(token, state)
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "ubuntu_beagle_install": state,
                    "cleanup": cleanup,
                },
            )
            return

        match = re.match(r"^/api/v1/public/ubuntu-install/(?P<token>[A-Za-z0-9._~-]+)/failed$", path)
        if match:
            token = match.group("token")
            state = load_ubuntu_beagle_state(token)
            if state is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "ubuntu install token not found"})
                return
            payload: dict[str, Any] = {}
            if int(self.headers.get("Content-Length", "0") or "0") > 0:
                try:
                    payload = self._read_json_body()
                except Exception:
                    payload = {}
            state["updated_at"] = utcnow()
            state["failed_at"] = utcnow()
            state["status"] = "failed"
            state["phase"] = str(payload.get("phase", "firstboot") or "firstboot")
            state["message"] = str(payload.get("message", "Ubuntu provisioning im Gast ist fehlgeschlagen.") or "Ubuntu provisioning im Gast ist fehlgeschlagen.")
            state["error"] = str(payload.get("error", "") or "")
            cancelled_restart = cancel_scheduled_ubuntu_beagle_vm_restart(state)
            if cancelled_restart:
                state["host_restart_cancelled"] = cancelled_restart
            save_ubuntu_beagle_state(token, state)
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "ubuntu_beagle_install": state,
                },
            )
            return

        if path == "/api/v1/endpoints/enroll":
            try:
                payload = self._read_json_body()
                enrollment_token = str(payload.get("enrollment_token", "")).strip()
                endpoint_id = str(payload.get("endpoint_id", "")).strip() or str(payload.get("hostname", "")).strip()
                if not enrollment_token or not endpoint_id:
                    raise ValueError("missing enrollment_token or endpoint_id")
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            enrollment = load_enrollment_token(enrollment_token)
            if not enrollment_token_is_valid(enrollment, endpoint_id=endpoint_id):
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "invalid or expired enrollment token"})
                return
            vm = find_vm(int(enrollment.get("vmid", 0)))
            if vm is None or vm.node != str(enrollment.get("node", "")).strip():
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            profile = build_profile(vm)
            secret = ensure_vm_secret(vm)
            sunshine_pinned_pubkey = fetch_https_pinned_pubkey(internal_sunshine_api_url(vm, profile))
            if sunshine_pinned_pubkey and sunshine_pinned_pubkey != str(secret.get("sunshine_pinned_pubkey", "")):
                secret["sunshine_pinned_pubkey"] = sunshine_pinned_pubkey
                secret = save_vm_secret(vm.node, vm.vmid, secret)
            endpoint_token = secrets.token_urlsafe(32)
            endpoint_payload = store_endpoint_token(
                endpoint_token,
                {
                    "endpoint_id": endpoint_id,
                    "hostname": str(payload.get("hostname", "")).strip(),
                    "vmid": vm.vmid,
                    "node": vm.node,
                },
            )
            mark_enrollment_token_used(enrollment_token, enrollment, endpoint_id=endpoint_id)
            self._write_json(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "endpoint": endpoint_payload,
                    "config": {
                        "beagle_manager_url": PUBLIC_MANAGER_URL,
                        "beagle_manager_token": endpoint_token,
                        "beagle_manager_pinned_pubkey": MANAGER_PINNED_PUBKEY,
                        "update_enabled": bool(profile.get("update_enabled", True)),
                        "update_channel": str(profile.get("update_channel", "stable") or "stable"),
                        "update_behavior": str(profile.get("update_behavior", "prompt") or "prompt"),
                        "update_feed_url": str(profile.get("update_feed_url", f"{PUBLIC_MANAGER_URL}/api/v1/endpoints/update-feed") or ""),
                        "update_version_pin": str(profile.get("update_version_pin", "") or ""),
                        "sunshine_api_url": str(profile.get("sunshine_api_url", "") or ""),
                        "sunshine_username": str(secret.get("sunshine_username", "")),
                        "sunshine_password": str(secret.get("sunshine_password", "")),
                        "sunshine_pin": str(secret.get("sunshine_pin", "")),
                        "sunshine_pinned_pubkey": str(secret.get("sunshine_pinned_pubkey", "")),
                        "usb_enabled": True,
                        "usb_tunnel_host": PUBLIC_SERVER_NAME,
                        "usb_tunnel_user": USB_TUNNEL_SSH_USER,
                        "usb_tunnel_port": int(secret.get("usb_tunnel_port", 0) or 0),
                        "usb_tunnel_attach_host": USB_TUNNEL_ATTACH_HOST,
                        "usb_tunnel_private_key": str(secret.get("usb_tunnel_private_key", "")),
                        "usb_tunnel_known_host": usb_tunnel_known_host_line(),
                        "moonlight_host": str(profile.get("stream_host", "") or ""),
                        "moonlight_local_host": str(profile.get("moonlight_local_host", "") or ""),
                        "moonlight_port": str(profile.get("moonlight_port", "") or ""),
                        "moonlight_app": str(profile.get("moonlight_app", "Desktop") or "Desktop"),
                        "egress_mode": str(profile.get("egress_mode", "direct") or "direct"),
                        "egress_type": str(profile.get("egress_type", "") or ""),
                        "egress_interface": str(profile.get("egress_interface", "beagle-egress") or "beagle-egress"),
                        "egress_domains": list(profile.get("egress_domains", []) or []),
                        "egress_resolvers": list(profile.get("egress_resolvers", []) or []),
                        "egress_allowed_ips": list(profile.get("egress_allowed_ips", []) or []),
                        "egress_wg_address": str(profile.get("egress_wg_address", "") or ""),
                        "egress_wg_dns": str(profile.get("egress_wg_dns", "") or ""),
                        "egress_wg_public_key": str(profile.get("egress_wg_public_key", "") or ""),
                        "egress_wg_endpoint": str(profile.get("egress_wg_endpoint", "") or ""),
                        "egress_wg_private_key": str(profile.get("egress_wg_private_key", "") or ""),
                        "egress_wg_preshared_key": str(profile.get("egress_wg_preshared_key", "") or ""),
                        "egress_wg_persistent_keepalive": str(profile.get("egress_wg_persistent_keepalive", "25") or "25"),
                        "identity_hostname": str(profile.get("identity_hostname", "") or ""),
                        "identity_timezone": str(profile.get("identity_timezone", "") or ""),
                        "identity_locale": str(profile.get("identity_locale", "") or ""),
                        "identity_keymap": str(profile.get("identity_keymap", "") or ""),
                        "identity_chrome_profile": str(profile.get("identity_chrome_profile", "") or ""),
                    },
                },
            )
            return

        if path == "/api/v1/endpoints/moonlight/register":
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            identity = self._endpoint_identity() or {}
            vmid = int(identity.get("vmid", 0) or 0)
            vm = find_vm(vmid)
            if vm is None or str(identity.get("node", "")).strip() != vm.node:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            try:
                payload = self._read_json_body()
                client_cert_pem = str(payload.get("client_cert_pem", "")).strip()
                device_name = (
                    str(payload.get("device_name", "")).strip()
                    or str(identity.get("hostname", "")).strip()
                    or f"beagle-vm{vmid}-client"
                )
                if not client_cert_pem or "BEGIN CERTIFICATE" not in client_cert_pem:
                    raise ValueError("missing client certificate")
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            result = register_moonlight_certificate_on_vm(vm, client_cert_pem, device_name=device_name)
            guest_user = str(result.get("guest_user", "") or "").strip()
            sunshine_server: dict[str, Any] = {
                "ok": False,
                "uniqueid": "",
                "server_cert_pem": "",
                "sunshine_name": "",
                "stream_port": "",
                "stdout": "",
                "stderr": "",
            }
            if bool(result.get("ok")) and guest_user:
                sunshine_server = fetch_sunshine_server_identity(vm, guest_user)
            overall_ok = bool(result.get("ok")) and bool(sunshine_server.get("ok")) and bool(
                sunshine_server.get("uniqueid")
            ) and bool(sunshine_server.get("server_cert_pem"))
            self._write_json(
                HTTPStatus.CREATED if overall_ok else HTTPStatus.BAD_GATEWAY,
                {
                    "ok": overall_ok,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "vmid": vm.vmid,
                    "node": vm.node,
                    "device_name": device_name,
                    "guest_user": result.get("guest_user", ""),
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "sunshine_server": {
                        "ok": bool(sunshine_server.get("ok")),
                        "uniqueid": sunshine_server.get("uniqueid", ""),
                        "server_cert_pem": sunshine_server.get("server_cert_pem", ""),
                        "sunshine_name": sunshine_server.get("sunshine_name", ""),
                        "stream_port": sunshine_server.get("stream_port", ""),
                        "stdout": sunshine_server.get("stdout", ""),
                        "stderr": sunshine_server.get("stderr", ""),
                    },
                },
            )
            return

        if path == "/api/v1/endpoints/actions/pull":
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            identity = self._endpoint_identity() or {}
            try:
                payload = self._read_json_body()
                vmid = int(payload.get("vmid"))
                node = str(payload.get("node", "")).strip()
                if not node:
                    raise ValueError("missing node")
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            if identity and (int(identity.get("vmid", -1)) != vmid or str(identity.get("node", "")).strip() != node):
                self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})
                return
            actions = dequeue_vm_actions(node, vmid)
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "actions": actions,
                },
            )
            return

        if path == "/api/v1/endpoints/actions/result":
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            identity = self._endpoint_identity() or {}
            try:
                payload = self._read_json_body()
                vmid = int(payload.get("vmid"))
                node = str(payload.get("node", "")).strip()
                action_name = str(payload.get("action", "")).strip()
                action_id = str(payload.get("action_id", "")).strip()
                if not node or not action_name or not action_id:
                    raise ValueError("missing action result fields")
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            if identity and (int(identity.get("vmid", -1)) != vmid or str(identity.get("node", "")).strip() != node):
                self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})
                return

            payload["vmid"] = vmid
            payload["node"] = node
            payload["received_at"] = utcnow()
            store_action_result(node, vmid, payload)
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "last_action": summarize_action_result(payload),
                },
            )
            return

        if path == "/api/v1/policies":
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                payload = self._read_json_body()
                policy = save_policy(payload)
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid policy: {exc}"})
                return
            self._write_json(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "policy": policy,
                },
            )
            return

        if path == "/api/v1/actions/bulk":
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                payload = self._read_json_body()
                action_name = str(payload.get("action", "")).strip().lower()
                vmid_values = payload.get("vmids", [])
                if action_name not in {"healthcheck", "recheckin", "restart-session", "restart-runtime", "support-bundle", "os-update-scan", "os-update-download"}:
                    raise ValueError("unsupported action")
                if not isinstance(vmid_values, list) or not vmid_values:
                    raise ValueError("missing vmids")
                vmids = [int(item) for item in vmid_values]
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid bulk action: {exc}"})
                return
            queued = queue_bulk_actions(vmids, action_name, self._requester_identity())
            self._write_json(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "queued_actions": queued,
                    "queued_count": len(queued),
                },
            )
            return

        if path == "/api/v1/ubuntu-beagle-vms":
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                payload = self._read_json_body()
                result = create_ubuntu_beagle_vm(payload if isinstance(payload, dict) else {})
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"failed to create ubuntu beagle vm: {exc}"})
                return
            self._write_json(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "ubuntu_beagle_vm": result,
                },
            )
            return

        if path == "/api/v1/provisioning/vms":
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                payload = self._read_json_body()
                result = create_provisioned_vm(payload if isinstance(payload, dict) else {})
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"failed to provision vm: {exc}"})
                return
            self._write_json(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "provisioned_vm": result,
                },
            )
            return

        if path.startswith("/api/v1/vms/") and path.endswith("/installer-prep"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            vm = find_vm(int(vmid_text))
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            try:
                state = start_installer_prep(vm)
            except Exception as exc:
                self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": f"failed to start installer prep: {exc}"})
                return
            status = HTTPStatus.ACCEPTED if str(state.get("status", "")).lower() == "running" else HTTPStatus.OK
            self._write_json(
                status,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "installer_prep": state,
                },
            )
            return

        if path == "/api/v1/endpoints/support-bundles/upload":
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            identity = self._endpoint_identity() or {}
            try:
                vmid_values = query.get("vmid", [])
                node_values = query.get("node", [])
                action_values = query.get("action_id", [])
                filename_values = query.get("filename", [])
                vmid = int(vmid_values[0])
                node = str(node_values[0]).strip()
                action_id = str(action_values[0]).strip()
                filename = str(filename_values[0]).strip() or "support-bundle.tar.gz"
                if not node or not action_id:
                    raise ValueError("missing upload fields")
                payload = self._read_binary_body(max_bytes=128 * 1024 * 1024)
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid upload: {exc}"})
                return
            if identity and (int(identity.get("vmid", -1)) != vmid or str(identity.get("node", "")).strip() != node):
                self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})
                return
            bundle = store_support_bundle(node, vmid, action_id, filename, payload)
            self._write_json(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "support_bundle": bundle,
                },
            )
            return

        match = re.match(r"^/api/v1/vms/(?P<vmid>\d+)/update/(?P<operation>scan|download|apply|rollback)$", path)
        if match:
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            vm = find_vm(int(match.group("vmid")))
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            payload: dict[str, Any] = {}
            if int(self.headers.get("Content-Length", "0") or "0") > 0:
                try:
                    payload = self._read_json_body()
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
            params = payload.get("params", {}) if isinstance(payload.get("params"), dict) else {}
            operation = match.group("operation")
            action_name = {
                "scan": "os-update-scan",
                "download": "os-update-download",
                "apply": "os-update-apply",
                "rollback": "os-update-rollback",
            }[operation]
            params = dict(params)
            if operation == "download":
                params["force"] = True
            if operation in {"apply", "rollback"} and "reboot" not in params:
                params["reboot"] = True
            queued = queue_vm_action(vm, action_name, self._requester_identity(), params)
            self._write_json(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "queued_action": queued,
                },
            )
            return

        if path.startswith("/api/v1/vms/") and path.endswith("/actions"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            vm = find_vm(int(vmid_text))
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            try:
                payload = self._read_json_body()
                action_name = str(payload.get("action", "")).strip().lower()
                action_params = payload.get("params", {}) if isinstance(payload.get("params"), dict) else {}
                if action_name not in {"healthcheck", "recheckin", "restart-session", "restart-runtime", "support-bundle", "os-update-scan", "os-update-download", "os-update-apply", "os-update-rollback"}:
                    raise ValueError("unsupported action")
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            queued = queue_vm_action(vm, action_name, self._requester_identity(), action_params)
            self._write_json(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "queued_action": queued,
                },
            )
            return

        if path.startswith("/api/v1/vms/") and path.endswith("/usb/refresh"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            vmid_text = path.split("/")[-3]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            vm = find_vm(int(vmid_text))
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            queued = queue_vm_action(vm, "usb-refresh", self._requester_identity())
            self._write_json(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "queued_action": queued,
                },
            )
            return

        if path.startswith("/api/v1/vms/") and path.endswith("/usb/attach"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            vmid_text = path.split("/")[-3]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            vm = find_vm(int(vmid_text))
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            try:
                payload = self._read_json_body()
                busid = str(payload.get("busid", "")).strip()
                if not busid:
                    raise ValueError("missing busid")
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            queued = queue_vm_action(vm, "usb-bind", self._requester_identity(), {"busid": busid})
            result = wait_for_action_result(vm.node, vm.vmid, queued["action_id"], timeout_seconds=USB_ACTION_WAIT_SECONDS)
            if result is None:
                self._write_json(
                    HTTPStatus.ACCEPTED,
                    {
                        "ok": True,
                        "service": "beagle-control-plane",
                        "version": VERSION,
                        "generated_at": utcnow(),
                        "queued_action": queued,
                        "message": "USB export queued on endpoint; refresh in a few seconds.",
                    },
                )
                return
            if not bool(result.get("ok")):
                self._write_json(
                    HTTPStatus.CONFLICT,
                    {
                        "ok": False,
                        "error": str(result.get("message", "") or "endpoint usb export failed"),
                        "queued_action": queued,
                        "endpoint_result": summarize_action_result(result),
                    },
                )
                return
            try:
                attach_result = attach_usb_to_guest(vm, busid)
            except Exception as exc:
                message = str(exc)
                if "Device busy (exported)" in message:
                    retry = queue_vm_action(vm, "usb-bind", self._requester_identity(), {"busid": busid})
                    retry_result = wait_for_action_result(vm.node, vm.vmid, retry["action_id"], timeout_seconds=USB_ACTION_WAIT_SECONDS)
                    if retry_result is not None and bool(retry_result.get("ok")):
                        try:
                            attach_result = attach_usb_to_guest(vm, busid)
                        except Exception as retry_exc:
                            message = str(retry_exc)
                        else:
                            self._write_json(
                                HTTPStatus.OK,
                                {
                                    "ok": True,
                                    "service": "beagle-control-plane",
                                    "version": VERSION,
                                    "generated_at": utcnow(),
                                    "queued_action": queued,
                                    "endpoint_result": summarize_action_result(result),
                                    "retry_action": retry,
                                    "retry_endpoint_result": summarize_action_result(retry_result),
                                    "attach_result": attach_result,
                                },
                            )
                            return
                self._write_json(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "error": f"guest usb attach failed: {message}",
                        "queued_action": queued,
                        "endpoint_result": summarize_action_result(result),
                    },
                )
                return
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "queued_action": queued,
                    "endpoint_result": summarize_action_result(result),
                    "guest_attach": attach_result,
                    "usb": build_vm_usb_state(vm),
                },
            )
            return

        if path.startswith("/api/v1/vms/") and path.endswith("/usb/detach"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            vmid_text = path.split("/")[-3]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            vm = find_vm(int(vmid_text))
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            try:
                payload = self._read_json_body()
                busid = str(payload.get("busid", "")).strip()
                port_value = payload.get("port")
                port = int(port_value) if port_value is not None and str(port_value).strip() else None
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            try:
                detach_result = detach_usb_from_guest(vm, port=port, busid=busid)
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"guest usb detach failed: {exc}"})
                return
            queued = None
            endpoint_result = None
            if busid:
                queued = queue_vm_action(vm, "usb-unbind", self._requester_identity(), {"busid": busid})
                endpoint_result = wait_for_action_result(vm.node, vm.vmid, queued["action_id"], timeout_seconds=USB_ACTION_WAIT_SECONDS)
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "guest_detach": detach_result,
                    "queued_action": queued,
                    "endpoint_result": summarize_action_result(endpoint_result),
                    "usb": build_vm_usb_state(vm),
                },
            )
            return

        if path.startswith("/api/v1/vms/") and path.endswith("/sunshine-access"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
                return
            vm = find_vm(int(vmid_text))
            if vm is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
                return
            token, payload = issue_sunshine_access_token(vm)
            self._write_json(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "sunshine_access": {
                        **payload,
                        "url": sunshine_proxy_ticket_url(token),
                    },
                },
            )
            return

        if path != "/api/v1/endpoints/check-in":
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        if not self._is_endpoint_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        identity = self._endpoint_identity() or {}

        try:
            payload = self._read_json_body()
            vmid = int(payload.get("vmid"))
            node = str(payload.get("node", "")).strip()
            if not node:
                raise ValueError("missing node")
        except Exception as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
            return
        if identity and (int(identity.get("vmid", -1)) != vmid or str(identity.get("node", "")).strip() != node):
            self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})
            return

        payload["vmid"] = vmid
        payload["node"] = node
        payload["received_at"] = utcnow()
        payload["remote_addr"] = self.client_address[0]

        path_obj = endpoint_report_path(node, vmid)
        path_obj.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        self._write_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "service": "beagle-control-plane",
                "version": VERSION,
                "stored_at": str(path_obj),
                "endpoint": summarize_endpoint_report(payload),
            },
        )

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        match = re.match(r"^/api/v1/provisioning/vms/(?P<vmid>\d+)$", path)
        if match:
            try:
                payload = self._read_json_body()
                result = update_ubuntu_beagle_vm(int(match.group("vmid")), payload if isinstance(payload, dict) else {})
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"failed to update provisioned vm: {exc}"})
                return
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "generated_at": utcnow(),
                    "provisioned_vm": result,
                },
            )
            return
        if not path.startswith("/api/v1/policies/"):
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        policy_name = path.rsplit("/", 1)[-1]
        try:
            payload = self._read_json_body()
            policy = save_policy(payload, policy_name=policy_name)
        except Exception as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid policy: {exc}"})
            return
        self._write_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "service": "beagle-control-plane",
                "version": VERSION,
                "generated_at": utcnow(),
                "policy": policy,
            },
        )

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if not path.startswith("/api/v1/policies/"):
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        policy_name = path.rsplit("/", 1)[-1]
        if not delete_policy(policy_name):
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "policy not found"})
            return
        self._write_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "service": "beagle-control-plane",
                "version": VERSION,
                "generated_at": utcnow(),
                "deleted": policy_name,
            },
        )

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{utcnow()}] {self.address_string()} {fmt % args}", flush=True)


def main() -> int:
    global EFFECTIVE_DATA_DIR
    EFFECTIVE_DATA_DIR = ensure_data_dir()
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(
        json.dumps(
            {
                "service": "beagle-control-plane",
                "version": VERSION,
                "listen_host": LISTEN_HOST,
                "listen_port": LISTEN_PORT,
                "allow_localhost_noauth": ALLOW_LOCALHOST_NOAUTH,
                "data_dir": str(EFFECTIVE_DATA_DIR),
            }
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
