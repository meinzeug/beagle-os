#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import secrets
import shlex
import tempfile
import time
import uuid
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
from download_metadata import DownloadMetadataService
from endpoint_enrollment import EndpointEnrollmentService
from endpoint_profile_contract import installer_profile_surface, normalize_endpoint_profile_contract
from endpoint_report import EndpointReportService
from endpoint_token_store import EndpointTokenStoreService
from enrollment_token_store import EnrollmentTokenStoreService
from fleet_inventory import FleetInventoryService
from health_payload import HealthPayloadService
from host_provider_contract import HostProvider
from installer_prep import InstallerPrepService
from installer_script import InstallerScriptService
from installer_template_patch import InstallerTemplatePatchService
from policy_normalization import PolicyNormalizationService
from policy_store import PolicyStoreService
from public_streams import PublicStreamService
from registry import create_provider, list_providers, normalize_provider_kind
from runtime_environment import RuntimeEnvironmentService
from runtime_support import RuntimeSupportService
from sunshine_access_token_store import SunshineAccessTokenStoreService
from sunshine_integration import SunshineIntegrationService
from support_bundle_store import SupportBundleStoreService
from ubuntu_beagle_inputs import UbuntuBeagleInputsService
from ubuntu_beagle_restart import UbuntuBeagleRestartService
from ubuntu_beagle_state import UbuntuBeagleStateService
from ubuntu_beagle_provisioning import UbuntuBeagleProvisioningService
from update_feed import UpdateFeedService
from virtualization_inventory import VirtualizationInventoryService
from vm_profile import VmProfileService
from vm_secret_bootstrap import VmSecretBootstrapService
from vm_secret_store import VmSecretStoreService
from vm_state import VmStateService
from vm_usb import VmUsbService

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

RUNTIME_SUPPORT_SERVICE = RuntimeSupportService(monotonic=time.monotonic)


def resolve_public_stream_host(host: str) -> str:
    return runtime_environment_service().resolve_public_stream_host(host)


def current_public_stream_host() -> str:
    return runtime_environment_service().current_public_stream_host()


def public_installer_iso_url() -> str:
    return download_metadata_service().public_installer_iso_url()


def public_windows_installer_url() -> str:
    return download_metadata_service().public_windows_installer_url()


def public_update_sha256sums_url() -> str:
    return download_metadata_service().public_update_sha256sums_url()


def public_versioned_payload_url(version: str) -> str:
    return download_metadata_service().public_versioned_payload_url(version)


def public_versioned_bootstrap_url(version: str) -> str:
    return download_metadata_service().public_versioned_bootstrap_url(version)


def public_payload_latest_download_url() -> str:
    return download_metadata_service().public_payload_latest_download_url()


def public_bootstrap_latest_download_url() -> str:
    return download_metadata_service().public_bootstrap_latest_download_url()


def public_latest_payload_url() -> str:
    return download_metadata_service().public_latest_payload_url()


def public_latest_bootstrap_url() -> str:
    return download_metadata_service().public_latest_bootstrap_url()


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


def runtime_support_service() -> RuntimeSupportService:
    return RUNTIME_SUPPORT_SERVICE


def cache_get(key: str, ttl_seconds: float) -> Any:
    return runtime_support_service().cache_get(key, ttl_seconds)


def cache_put(key: str, value: Any) -> Any:
    return runtime_support_service().cache_put(key, value)


def cache_invalidate(*keys: str) -> None:
    runtime_support_service().cache_invalidate(*keys)


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
    return download_metadata_service().checksum_for_dist_filename(filename)


def update_payload_metadata(version: str) -> dict[str, str]:
    return download_metadata_service().update_payload_metadata(version)


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
DOWNLOAD_METADATA_SERVICE: DownloadMetadataService | None = None
RUNTIME_ENVIRONMENT_SERVICE: RuntimeEnvironmentService | None = None
UPDATE_FEED_SERVICE: UpdateFeedService | None = None
FLEET_INVENTORY_SERVICE: FleetInventoryService | None = None
HEALTH_PAYLOAD_SERVICE: HealthPayloadService | None = None
INSTALLER_PREP_SERVICE: InstallerPrepService | None = None
INSTALLER_SCRIPT_SERVICE: InstallerScriptService | None = None
INSTALLER_TEMPLATE_PATCH_SERVICE: InstallerTemplatePatchService | None = None
ENDPOINT_REPORT_SERVICE: EndpointReportService | None = None
ACTION_QUEUE_SERVICE: ActionQueueService | None = None
POLICY_NORMALIZATION_SERVICE: PolicyNormalizationService | None = None
POLICY_STORE_SERVICE: PolicyStoreService | None = None
PUBLIC_STREAM_SERVICE: PublicStreamService | None = None
SUPPORT_BUNDLE_STORE_SERVICE: SupportBundleStoreService | None = None
ENDPOINT_ENROLLMENT_SERVICE: EndpointEnrollmentService | None = None
UBUNTU_BEAGLE_INPUTS_SERVICE: UbuntuBeagleInputsService | None = None
UBUNTU_BEAGLE_RESTART_SERVICE: UbuntuBeagleRestartService | None = None
UBUNTU_BEAGLE_STATE_SERVICE: UbuntuBeagleStateService | None = None
UBUNTU_BEAGLE_PROVISIONING_SERVICE: UbuntuBeagleProvisioningService | None = None
VM_SECRET_STORE_SERVICE: VmSecretStoreService | None = None
VM_SECRET_BOOTSTRAP_SERVICE: VmSecretBootstrapService | None = None
VM_USB_SERVICE: VmUsbService | None = None
ENROLLMENT_TOKEN_STORE_SERVICE: EnrollmentTokenStoreService | None = None
SUNSHINE_ACCESS_TOKEN_STORE_SERVICE: SunshineAccessTokenStoreService | None = None
SUNSHINE_INTEGRATION_SERVICE: SunshineIntegrationService | None = None
ENDPOINT_TOKEN_STORE_SERVICE: EndpointTokenStoreService | None = None


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


def public_stream_service() -> PublicStreamService:
    global PUBLIC_STREAM_SERVICE
    if PUBLIC_STREAM_SERVICE is None:
        PUBLIC_STREAM_SERVICE = PublicStreamService(
            current_public_stream_host=runtime_environment_service().current_public_stream_host,
            data_dir=lambda: EFFECTIVE_DATA_DIR,
            get_vm_config=get_vm_config,
            list_vms=lambda: list_vms(),
            load_json_file=load_json_file,
            parse_description_meta=parse_description_meta,
            public_stream_base_port=PUBLIC_STREAM_BASE_PORT,
            public_stream_port_count=PUBLIC_STREAM_PORT_COUNT,
            public_stream_port_step=PUBLIC_STREAM_PORT_STEP,
            safe_slug=safe_slug,
            write_json_file=write_json_file,
        )
    return PUBLIC_STREAM_SERVICE


def runtime_environment_service() -> RuntimeEnvironmentService:
    global RUNTIME_ENVIRONMENT_SERVICE
    if RUNTIME_ENVIRONMENT_SERVICE is None:
        RUNTIME_ENVIRONMENT_SERVICE = RuntimeEnvironmentService(
            manager_cert_file=MANAGER_CERT_FILE,
            public_stream_host_raw=PUBLIC_STREAM_HOST_RAW,
            getaddrinfo=socket.getaddrinfo,
            run_subprocess=subprocess.run,
        )
    return RUNTIME_ENVIRONMENT_SERVICE


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


def vm_secret_bootstrap_service() -> VmSecretBootstrapService:
    global VM_SECRET_BOOTSTRAP_SERVICE
    if VM_SECRET_BOOTSTRAP_SERVICE is None:
        VM_SECRET_BOOTSTRAP_SERVICE = VmSecretBootstrapService(
            data_dir=lambda: EFFECTIVE_DATA_DIR,
            load_vm_secret=load_vm_secret,
            public_server_name=PUBLIC_SERVER_NAME,
            public_stream_host=runtime_environment_service().current_public_stream_host(),
            random_pin=random_pin,
            random_secret=random_secret,
            resolve_sunshine_pinned_pubkey=resolve_vm_sunshine_pinned_pubkey,
            safe_slug=safe_slug,
            save_vm_secret=save_vm_secret,
            session_script_path=Path(__file__).resolve().parent / "beagle-usb-tunnel-session",
            usb_tunnel_attach_host=USB_TUNNEL_ATTACH_HOST,
            usb_tunnel_auth_dir=USB_TUNNEL_AUTH_DIR,
            usb_tunnel_auth_root=USB_TUNNEL_AUTH_ROOT,
            usb_tunnel_base_port=USB_TUNNEL_BASE_PORT,
            usb_tunnel_home=USB_TUNNEL_HOME,
            usb_tunnel_hostkey_file=USB_TUNNEL_HOSTKEY_FILE,
            usb_tunnel_user=USB_TUNNEL_SSH_USER,
        )
    return VM_SECRET_BOOTSTRAP_SERVICE


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


def sunshine_access_token_store_service() -> SunshineAccessTokenStoreService:
    global SUNSHINE_ACCESS_TOKEN_STORE_SERVICE
    if SUNSHINE_ACCESS_TOKEN_STORE_SERVICE is None:
        SUNSHINE_ACCESS_TOKEN_STORE_SERVICE = SunshineAccessTokenStoreService(
            data_dir=lambda: EFFECTIVE_DATA_DIR,
            load_json_file=load_json_file,
            write_json_file=write_json_file,
            parse_utc_timestamp=parse_utc_timestamp,
        )
    return SUNSHINE_ACCESS_TOKEN_STORE_SERVICE


def sunshine_integration_service() -> SunshineIntegrationService:
    global SUNSHINE_INTEGRATION_SERVICE
    if SUNSHINE_INTEGRATION_SERVICE is None:
        SUNSHINE_INTEGRATION_SERVICE = SunshineIntegrationService(
            build_profile=build_profile,
            ensure_vm_secret=ensure_vm_secret,
            find_vm=find_vm,
            get_vm_config=get_vm_config,
            guest_exec_script_text=HOST_PROVIDER.guest_exec_script_text,
            load_sunshine_access_token=load_sunshine_access_token,
            parse_description_meta=parse_description_meta,
            public_manager_url=PUBLIC_MANAGER_URL,
            run_subprocess=subprocess.run,
            safe_slug=safe_slug,
            store_sunshine_access_token=sunshine_access_token_store_service().store,
            sunshine_access_token_is_valid=sunshine_access_token_is_valid,
            sunshine_access_token_ttl_seconds=SUNSHINE_ACCESS_TOKEN_TTL_SECONDS,
            ubuntu_beagle_default_guest_user=UBUNTU_BEAGLE_DEFAULT_GUEST_USER,
            utcnow=utcnow,
        )
    return SUNSHINE_INTEGRATION_SERVICE


def endpoint_token_store_service() -> EndpointTokenStoreService:
    global ENDPOINT_TOKEN_STORE_SERVICE
    if ENDPOINT_TOKEN_STORE_SERVICE is None:
        ENDPOINT_TOKEN_STORE_SERVICE = EndpointTokenStoreService(
            data_dir=lambda: EFFECTIVE_DATA_DIR,
            load_json_file=load_json_file,
            write_json_file=write_json_file,
            utcnow=utcnow,
        )
    return ENDPOINT_TOKEN_STORE_SERVICE


def endpoint_enrollment_service() -> EndpointEnrollmentService:
    global ENDPOINT_ENROLLMENT_SERVICE
    if ENDPOINT_ENROLLMENT_SERVICE is None:
        ENDPOINT_ENROLLMENT_SERVICE = EndpointEnrollmentService(
            build_profile=build_profile,
            ensure_vm_secret=ensure_vm_secret,
            enrollment_token_ttl_seconds=ENROLLMENT_TOKEN_TTL_SECONDS,
            find_vm=find_vm,
            load_enrollment_token=enrollment_token_store_service().load,
            manager_pinned_pubkey=manager_pinned_pubkey(),
            mark_enrollment_token_used=lambda token, payload, endpoint_id: enrollment_token_store_service().mark_used(
                token,
                payload,
                endpoint_id=endpoint_id,
            ),
            public_manager_url=PUBLIC_MANAGER_URL,
            public_server_name=PUBLIC_SERVER_NAME,
            resolve_vm_sunshine_pinned_pubkey=resolve_vm_sunshine_pinned_pubkey,
            save_vm_secret=save_vm_secret,
            service_name="beagle-control-plane",
            store_endpoint_token=endpoint_token_store_service().store,
            store_enrollment_token=enrollment_token_store_service().store,
            token_is_valid=lambda payload, endpoint_id: enrollment_token_store_service().is_valid(
                payload,
                endpoint_id=endpoint_id,
            ),
            token_urlsafe=secrets.token_urlsafe,
            usb_tunnel_attach_host=USB_TUNNEL_ATTACH_HOST,
            usb_tunnel_known_host_line=usb_tunnel_known_host_line,
            usb_tunnel_user=USB_TUNNEL_SSH_USER,
            utcnow=utcnow,
            version=VERSION,
        )
    return ENDPOINT_ENROLLMENT_SERVICE


def download_metadata_service() -> DownloadMetadataService:
    global DOWNLOAD_METADATA_SERVICE
    if DOWNLOAD_METADATA_SERVICE is None:
        DOWNLOAD_METADATA_SERVICE = DownloadMetadataService(
            cache_get=cache_get,
            cache_put=cache_put,
            dist_sha256sums_file=DIST_SHA256SUMS_FILE,
            downloads_status_file=DOWNLOADS_STATUS_FILE,
            load_json_file=load_json_file,
            manager_pinned_pubkey=manager_pinned_pubkey(),
            public_downloads_path=PUBLIC_DOWNLOADS_PATH,
            public_downloads_port=PUBLIC_DOWNLOADS_PORT,
            public_manager_url=PUBLIC_MANAGER_URL,
            public_server_name=PUBLIC_SERVER_NAME,
            public_update_base_url=PUBLIC_UPDATE_BASE_URL,
            version=VERSION,
        )
    return DOWNLOAD_METADATA_SERVICE


def installer_prep_service() -> InstallerPrepService:
    global INSTALLER_PREP_SERVICE
    if INSTALLER_PREP_SERVICE is None:
        INSTALLER_PREP_SERVICE = InstallerPrepService(
            build_profile=build_profile,
            data_dir=lambda: EFFECTIVE_DATA_DIR,
            ensure_vm_secret=ensure_vm_secret,
            guest_exec_out_data=guest_exec_out_data,
            installer_prep_script_file=INSTALLER_PREP_SCRIPT_FILE,
            installer_profile_surface=installer_profile_surface,
            load_json_file=load_json_file,
            public_installer_iso_url=download_metadata_service().public_installer_iso_url,
            root_dir=ROOT_DIR,
            safe_slug=safe_slug,
            timestamp_age_seconds=timestamp_age_seconds,
            utcnow=utcnow,
            write_json_file=write_json_file,
        )
    return INSTALLER_PREP_SERVICE


def vm_usb_service() -> VmUsbService:
    global VM_USB_SERVICE
    if VM_USB_SERVICE is None:
        VM_USB_SERVICE = VmUsbService(
            ensure_vm_secret=ensure_vm_secret,
            guest_exec_out_data=guest_exec_out_data,
            guest_exec_payload=guest_exec_payload,
            load_endpoint_report=load_endpoint_report,
            monotonic=time.monotonic,
            public_server_name=PUBLIC_SERVER_NAME,
            shlex_quote=shlex.quote,
            sleep=time.sleep,
            summarize_endpoint_report=summarize_endpoint_report,
            usb_tunnel_attach_host=USB_TUNNEL_ATTACH_HOST,
            usb_tunnel_user=USB_TUNNEL_SSH_USER,
        )
    return VM_USB_SERVICE


def endpoint_tokens_dir() -> Path:
    return endpoint_token_store_service().tokens_dir()


def sunshine_access_tokens_dir() -> Path:
    return sunshine_access_token_store_service().tokens_dir()


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


def ubuntu_beagle_restart_service() -> UbuntuBeagleRestartService:
    global UBUNTU_BEAGLE_RESTART_SERVICE
    if UBUNTU_BEAGLE_RESTART_SERVICE is None:
        UBUNTU_BEAGLE_RESTART_SERVICE = UbuntuBeagleRestartService(
            default_wait_timeout_seconds=UBUNTU_BEAGLE_FIRSTBOOT_POWERDOWN_WAIT_SECONDS,
            kill_process=os.kill,
            kill_process_group=os.killpg,
            schedule_vm_restart_after_stop=lambda vmid, wait_timeout_seconds: HOST_PROVIDER.schedule_vm_restart_after_stop(
                int(vmid),
                wait_timeout_seconds=int(wait_timeout_seconds),
            ),
            utcnow=utcnow,
        )
    return UBUNTU_BEAGLE_RESTART_SERVICE


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
    return ubuntu_beagle_restart_service().schedule(vmid, wait_timeout_seconds=wait_timeout_seconds)


def ensure_ubuntu_beagle_vm_restart_state(state: dict[str, Any], vmid: int) -> dict[str, Any]:
    return ubuntu_beagle_restart_service().ensure_restart_state(state, vmid)


def cancel_scheduled_ubuntu_beagle_vm_restart(state: dict[str, Any]) -> dict[str, Any] | None:
    return ubuntu_beagle_restart_service().cancel(state)


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
            find_vm=lambda vmid: VIRTUALIZATION_INVENTORY.find_vm(vmid),
            load_json_file=load_json_file,
            monotonic=time.monotonic,
            safe_slug=safe_slug,
            sleep=time.sleep,
            time_now_epoch=lambda: datetime.now(timezone.utc).timestamp(),
            utcnow=utcnow,
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
            utcnow=utcnow,
            write_json_file=write_json_file,
        )
    return SUPPORT_BUNDLE_STORE_SERVICE


def ubuntu_beagle_inputs_service() -> UbuntuBeagleInputsService:
    global UBUNTU_BEAGLE_INPUTS_SERVICE
    if UBUNTU_BEAGLE_INPUTS_SERVICE is None:
        UBUNTU_BEAGLE_INPUTS_SERVICE = UbuntuBeagleInputsService(
            ubuntu_beagle_default_desktop=UBUNTU_BEAGLE_DEFAULT_DESKTOP,
            ubuntu_beagle_default_keymap=UBUNTU_BEAGLE_DEFAULT_KEYMAP,
            ubuntu_beagle_default_locale=UBUNTU_BEAGLE_DEFAULT_LOCALE,
            ubuntu_beagle_desktops=UBUNTU_BEAGLE_DESKTOPS,
            ubuntu_beagle_min_password_length=UBUNTU_BEAGLE_MIN_PASSWORD_LENGTH,
            ubuntu_beagle_software_presets=UBUNTU_BEAGLE_SOFTWARE_PRESETS,
        )
    return UBUNTU_BEAGLE_INPUTS_SERVICE


def support_bundle_metadata_path(bundle_id: str) -> Path:
    return support_bundle_store_service().metadata_path(bundle_id)


def support_bundle_archive_path(bundle_id: str, filename: str) -> Path:
    return support_bundle_store_service().archive_path(bundle_id, filename)


def load_shell_env_file(path: Path) -> dict[str, str]:
    return runtime_support_service().load_shell_env_file(path)


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
    return vm_secret_bootstrap_service().default_usb_tunnel_port(vmid)


def generate_ssh_keypair(comment: str) -> tuple[str, str]:
    return vm_secret_bootstrap_service().generate_ssh_keypair(comment)


def usb_tunnel_known_host_line() -> str:
    return vm_secret_bootstrap_service().usb_tunnel_known_host_line()


def usb_tunnel_user_info() -> Any:
    return vm_secret_bootstrap_service().usb_tunnel_user_info()


def usb_tunnel_home() -> Path:
    return vm_secret_bootstrap_service().usb_tunnel_home()


def usb_tunnel_auth_root() -> Path:
    return vm_secret_bootstrap_service().usb_tunnel_auth_root()


def usb_tunnel_auth_dir() -> Path:
    return vm_secret_bootstrap_service().usb_tunnel_auth_dir()


def usb_tunnel_authorized_keys_path() -> Path:
    return vm_secret_bootstrap_service().usb_tunnel_authorized_keys_path()


def usb_tunnel_authorized_key_line(vm: VmSummary, secret: dict[str, Any]) -> str:
    return vm_secret_bootstrap_service().usb_tunnel_authorized_key_line(vm, secret)


def sync_usb_tunnel_authorized_key(vm: VmSummary, secret: dict[str, Any]) -> None:
    vm_secret_bootstrap_service().sync_usb_tunnel_authorized_key(vm, secret)


def ensure_vm_secret(vm: VmSummary) -> dict[str, Any]:
    return vm_secret_bootstrap_service().ensure_vm_secret(vm)


def manager_pinned_pubkey() -> str:
    return runtime_environment_service().manager_pinned_pubkey()


def fetch_https_pinned_pubkey(url: str) -> str:
    return sunshine_integration_service().fetch_https_pinned_pubkey(url)


def guest_exec_text(vmid: int, script: str) -> tuple[int, str, str]:
    return sunshine_integration_service().guest_exec_text(vmid, script)


def sunshine_guest_user(vm: VmSummary, config: dict[str, Any] | None = None) -> str:
    return sunshine_integration_service().sunshine_guest_user(vm, config)


def register_moonlight_certificate_on_vm(vm: VmSummary, client_cert_pem: str, *, device_name: str) -> dict[str, Any]:
    return sunshine_integration_service().register_moonlight_certificate_on_vm(
        vm,
        client_cert_pem,
        device_name=device_name,
    )


def fetch_sunshine_server_identity(vm: VmSummary, guest_user: str) -> dict[str, Any]:
    return sunshine_integration_service().fetch_sunshine_server_identity(vm, guest_user)


def internal_sunshine_api_url(vm: VmSummary, profile: dict[str, Any] | None = None) -> str:
    return sunshine_integration_service().internal_sunshine_api_url(vm, profile)


def resolve_vm_sunshine_pinned_pubkey(vm: VmSummary) -> str:
    return sunshine_integration_service().resolve_vm_sunshine_pinned_pubkey(vm)


def ensure_vm_sunshine_pinned_pubkey(vm: VmSummary, secret: dict[str, Any]) -> dict[str, Any]:
    return vm_secret_bootstrap_service().ensure_vm_sunshine_pinned_pubkey(vm, secret)


def enrollment_token_path(token: str) -> Path:
    return enrollment_token_store_service().token_path(token)


def sunshine_access_token_path(token: str) -> Path:
    return sunshine_access_token_store_service().token_path(token)


def issue_enrollment_token(vm: VmSummary) -> tuple[str, dict[str, Any]]:
    return endpoint_enrollment_service().issue_enrollment_token(vm)


def load_enrollment_token(token: str) -> dict[str, Any] | None:
    return enrollment_token_store_service().load(token)


def issue_sunshine_access_token(vm: VmSummary) -> tuple[str, dict[str, Any]]:
    return sunshine_integration_service().issue_sunshine_access_token(vm)


def load_sunshine_access_token(token: str) -> dict[str, Any] | None:
    return sunshine_access_token_store_service().load(token)


def mark_enrollment_token_used(token: str, payload: dict[str, Any], *, endpoint_id: str) -> None:
    enrollment_token_store_service().mark_used(token, payload, endpoint_id=endpoint_id)


def enrollment_token_is_valid(payload: dict[str, Any] | None, *, endpoint_id: str = "") -> bool:
    return enrollment_token_store_service().is_valid(payload, endpoint_id=endpoint_id)


def sunshine_access_token_is_valid(payload: dict[str, Any] | None) -> bool:
    return sunshine_access_token_store_service().is_valid(payload)


def endpoint_token_path(token: str) -> Path:
    return endpoint_token_store_service().token_path(token)


def store_endpoint_token(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return endpoint_token_store_service().store(token, payload)


def load_endpoint_token(token: str) -> dict[str, Any] | None:
    return endpoint_token_store_service().load(token)


def sunshine_proxy_ticket_url(token: str) -> str:
    return sunshine_integration_service().sunshine_proxy_ticket_url(token)


def proxy_sunshine_request(vm: VmSummary, *, request_path: str, query: str, method: str, body: bytes | None, request_headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
    return sunshine_integration_service().proxy_sunshine_request(
        vm,
        request_path=request_path,
        query=query,
        method=method,
        body=body,
        request_headers=request_headers,
    )


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
    return public_stream_service().public_streams_file()


def load_public_streams() -> dict[str, int]:
    return public_stream_service().load_public_streams()


def save_public_streams(payload: dict[str, int]) -> None:
    public_stream_service().save_public_streams(payload)


def public_stream_key(node: str, vmid: int) -> str:
    return public_stream_service().public_stream_key(node, vmid)


def explicit_public_stream_base_port(config: dict[str, Any] | None) -> int | None:
    return public_stream_service().explicit_public_stream_base_port(config)


def used_public_stream_base_ports(
    mappings: dict[str, int],
    *,
    exclude_key: str = "",
    sync_mappings: bool = False,
) -> tuple[set[int], bool]:
    return public_stream_service().used_public_stream_base_ports(
        mappings,
        exclude_key=exclude_key,
        sync_mappings=sync_mappings,
    )


def allocate_public_stream_base_port(node: str, vmid: int) -> int | None:
    return public_stream_service().allocate_public_stream_base_port(node, vmid)


def stream_ports(base_port: int) -> dict[str, int]:
    base = int(base_port)
    return {
        "moonlight_port": base,
        "sunshine_api_port": base + 1,
        "https_port": base + 1,
        "rtsp_port": base + 21,
    }


def installer_template_patch_service() -> InstallerTemplatePatchService:
    global INSTALLER_TEMPLATE_PATCH_SERVICE
    if INSTALLER_TEMPLATE_PATCH_SERVICE is None:
        INSTALLER_TEMPLATE_PATCH_SERVICE = InstallerTemplatePatchService()
    return INSTALLER_TEMPLATE_PATCH_SERVICE


def patch_installer_defaults(
    script_text: str,
    preset_name: str,
    preset_b64: str,
    installer_iso_url: str,
    installer_bootstrap_url: str,
    installer_payload_url: str,
    writer_variant: str,
) -> str:
    return installer_template_patch_service().patch_installer_defaults(
        script_text,
        preset_name,
        preset_b64,
        installer_iso_url,
        installer_bootstrap_url,
        installer_payload_url,
        writer_variant,
    )


def patch_windows_installer_defaults(script_text: str, preset_name: str, preset_b64: str, installer_iso_url: str) -> str:
    return installer_template_patch_service().patch_windows_installer_defaults(
        script_text,
        preset_name,
        preset_b64,
        installer_iso_url,
    )


def installer_prep_dir() -> Path:
    return installer_prep_service().prep_dir()


def installer_prep_path(node: str, vmid: int) -> Path:
    return installer_prep_service().state_path(node, vmid)


def installer_prep_log_path(node: str, vmid: int) -> Path:
    return installer_prep_service().log_path(node, vmid)


def load_installer_prep_state(node: str, vmid: int) -> dict[str, Any] | None:
    return installer_prep_service().load_state(node, vmid)


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
    return vm_usb_service().parse_usbip_port_output(output)


def parse_vhci_status_output(output: str) -> list[dict[str, Any]]:
    return vm_usb_service().parse_vhci_status_output(output)


def guest_usb_attachment_state(vmid: int) -> dict[str, Any]:
    return vm_usb_service().guest_usb_attachment_state(vmid)


def wait_for_guest_usb_attachment(vmid: int, busid: str, *, timeout_seconds: float) -> dict[str, Any]:
    return vm_usb_service().wait_for_guest_usb_attachment(vmid, busid, timeout_seconds=timeout_seconds)


def wait_for_action_result(node: str, vmid: int, action_id: str, *, timeout_seconds: float) -> dict[str, Any] | None:
    return action_queue_service().wait_for_result(
        node,
        vmid,
        action_id,
        timeout_seconds=timeout_seconds,
    )


def build_vm_usb_state(vm: VmSummary, report: dict[str, Any] | None = None) -> dict[str, Any]:
    return vm_usb_service().build_vm_usb_state(vm, report)


def attach_usb_to_guest(vm: VmSummary, busid: str) -> dict[str, Any]:
    return vm_usb_service().attach_usb_to_guest(vm, busid)


def detach_usb_from_guest(vm: VmSummary, *, port: int | None = None, busid: str = "") -> dict[str, Any]:
    return vm_usb_service().detach_usb_from_guest(vm, port=port, busid=busid)


def quick_sunshine_status(vmid: int) -> dict[str, Any]:
    return installer_prep_service().quick_sunshine_status(vmid)


def default_installer_prep_state(vm: VmSummary, sunshine_status: dict[str, Any] | None = None) -> dict[str, Any]:
    return installer_prep_service().default_state(vm, sunshine_status)


def summarize_installer_prep_state(vm: VmSummary, state: dict[str, Any] | None = None) -> dict[str, Any]:
    return installer_prep_service().summarize_state(vm, state)


def installer_prep_running(state: dict[str, Any] | None) -> bool:
    return installer_prep_service().is_running(state)


def start_installer_prep(vm: VmSummary) -> dict[str, Any]:
    return installer_prep_service().start(vm)


def policy_store_service() -> PolicyStoreService:
    global POLICY_STORE_SERVICE
    if POLICY_STORE_SERVICE is None:
        POLICY_STORE_SERVICE = PolicyStoreService(
            load_json_file=load_json_file,
            normalize_policy_payload=policy_normalization_service().normalize_payload,
            policies_dir=policies_dir,
            safe_slug=safe_slug,
        )
    return POLICY_STORE_SERVICE


def policy_normalization_service() -> PolicyNormalizationService:
    global POLICY_NORMALIZATION_SERVICE
    if POLICY_NORMALIZATION_SERVICE is None:
        POLICY_NORMALIZATION_SERVICE = PolicyNormalizationService(
            listify=listify,
            truthy=truthy,
            utcnow=utcnow,
        )
    return POLICY_NORMALIZATION_SERVICE


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
    return action_queue_service().queue_action(vm, action_name, requested_by, params)


def queue_bulk_actions(vmids: list[int], action_name: str, requested_by: str) -> list[dict[str, Any]]:
    return action_queue_service().queue_bulk_actions(vmids, action_name, requested_by)


def dequeue_vm_actions(node: str, vmid: int) -> list[dict[str, Any]]:
    return action_queue_service().dequeue_actions(node, vmid)


def summarize_action_result(payload: dict[str, Any] | None) -> dict[str, Any]:
    return action_queue_service().summarize_result(payload)


def list_support_bundle_metadata(*, node: str | None = None, vmid: int | None = None) -> list[dict[str, Any]]:
    return support_bundle_store_service().list_metadata(node=node, vmid=vmid)


def find_support_bundle_metadata(bundle_id: str) -> dict[str, Any] | None:
    return support_bundle_store_service().find_metadata(bundle_id)


def store_support_bundle(node: str, vmid: int, action_id: str, filename: str, content: bytes) -> dict[str, Any]:
    return support_bundle_store_service().store(node, vmid, action_id, filename, content)


def normalize_policy_payload(payload: dict[str, Any], *, policy_name: str | None = None) -> dict[str, Any]:
    return policy_normalization_service().normalize_payload(payload, policy_name=policy_name)


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
    return ubuntu_beagle_inputs_service().validate_linux_username(value, field_name)


def validate_password(value: str, field_name: str, *, allow_empty: bool = False) -> str:
    return ubuntu_beagle_inputs_service().validate_password(
        value,
        field_name,
        allow_empty=allow_empty,
    )


def normalize_locale(value: str) -> str:
    return ubuntu_beagle_inputs_service().normalize_locale(value)


def normalize_keymap(value: str) -> str:
    return ubuntu_beagle_inputs_service().normalize_keymap(value)


def normalize_package_names(value: Any, *, field_name: str) -> list[str]:
    return ubuntu_beagle_inputs_service().normalize_package_names(value, field_name=field_name)


def resolve_ubuntu_beagle_desktop(value: str) -> dict[str, Any]:
    return ubuntu_beagle_inputs_service().resolve_ubuntu_beagle_desktop(value)


def normalize_package_presets(value: Any) -> list[str]:
    return ubuntu_beagle_inputs_service().normalize_package_presets(value)


def expand_software_packages(package_presets: list[str], extra_packages: list[str]) -> list[str]:
    return ubuntu_beagle_inputs_service().expand_software_packages(package_presets, extra_packages)


def ubuntu_beagle_provisioning_service() -> UbuntuBeagleProvisioningService:
    global UBUNTU_BEAGLE_PROVISIONING_SERVICE
    if UBUNTU_BEAGLE_PROVISIONING_SERVICE is None:
        UBUNTU_BEAGLE_PROVISIONING_SERVICE = UbuntuBeagleProvisioningService(
            allocate_public_stream_base_port=allocate_public_stream_base_port,
            build_profile=build_profile,
            configure_sunshine_guest_script=ROOT_DIR / "scripts" / "configure-sunshine-guest.sh",
            current_public_stream_host=current_public_stream_host,
            default_usb_tunnel_port=default_usb_tunnel_port,
            ensure_vm_secret=ensure_vm_secret,
            expand_software_packages=ubuntu_beagle_inputs_service().expand_software_packages,
            find_vm=find_vm,
            get_vm_config=get_vm_config,
            invalidate_vm_cache=invalidate_vm_cache,
            latest_ubuntu_beagle_state_for_vmid=latest_ubuntu_beagle_state_for_vmid,
            list_bridge_inventory=list_bridge_inventory,
            list_nodes_inventory=list_nodes_inventory,
            list_ubuntu_beagle_states=list_ubuntu_beagle_states,
            local_iso_dir=Path("/var/lib/vz/template/iso"),
            make_vm_summary=lambda **kwargs: VmSummary(**kwargs),
            manager_pinned_pubkey=manager_pinned_pubkey(),
            normalize_keymap=ubuntu_beagle_inputs_service().normalize_keymap,
            normalize_locale=ubuntu_beagle_inputs_service().normalize_locale,
            normalize_package_names=ubuntu_beagle_inputs_service().normalize_package_names,
            normalize_package_presets=ubuntu_beagle_inputs_service().normalize_package_presets,
            provider=HOST_PROVIDER,
            public_ubuntu_beagle_complete_url=public_ubuntu_beagle_complete_url,
            random_pin=random_pin,
            random_secret=random_secret,
            reconcile_public_streams_script=ROOT_DIR / "scripts" / "reconcile-public-streams.sh",
            resolve_ubuntu_beagle_desktop=ubuntu_beagle_inputs_service().resolve_ubuntu_beagle_desktop,
            run_checked=run_checked,
            safe_hostname=safe_hostname,
            safe_slug=safe_slug,
            save_ubuntu_beagle_state=save_ubuntu_beagle_state,
            save_vm_secret=save_vm_secret,
            ensure_ubuntu_beagle_vm_restart_state=ensure_ubuntu_beagle_vm_restart_state,
            stream_ports=stream_ports,
            summarize_ubuntu_beagle_state=summarize_ubuntu_beagle_state,
            template_dir=UBUNTU_BEAGLE_TEMPLATE_DIR,
            time_now_epoch=lambda: datetime.now(timezone.utc).timestamp(),
            ubuntu_beagle_autoinstall_url_ttl_seconds=UBUNTU_BEAGLE_AUTOINSTALL_URL_TTL_SECONDS,
            ubuntu_beagle_default_bridge=UBUNTU_BEAGLE_DEFAULT_BRIDGE,
            ubuntu_beagle_default_cores=UBUNTU_BEAGLE_DEFAULT_CORES,
            ubuntu_beagle_default_desktop=UBUNTU_BEAGLE_DEFAULT_DESKTOP,
            ubuntu_beagle_default_disk_gb=UBUNTU_BEAGLE_DEFAULT_DISK_GB,
            ubuntu_beagle_default_guest_user=UBUNTU_BEAGLE_DEFAULT_GUEST_USER,
            ubuntu_beagle_default_keymap=UBUNTU_BEAGLE_DEFAULT_KEYMAP,
            ubuntu_beagle_default_locale=UBUNTU_BEAGLE_DEFAULT_LOCALE,
            ubuntu_beagle_default_memory_mib=UBUNTU_BEAGLE_DEFAULT_MEMORY_MIB,
            ubuntu_beagle_desktops=UBUNTU_BEAGLE_DESKTOPS,
            ubuntu_beagle_disk_storage=UBUNTU_BEAGLE_DISK_STORAGE,
            ubuntu_beagle_iso_storage=UBUNTU_BEAGLE_ISO_STORAGE,
            ubuntu_beagle_iso_url=UBUNTU_BEAGLE_ISO_URL,
            ubuntu_beagle_profile_id=UBUNTU_BEAGLE_PROFILE_ID,
            ubuntu_beagle_profile_label=UBUNTU_BEAGLE_PROFILE_LABEL,
            ubuntu_beagle_profile_legacy_ids=UBUNTU_BEAGLE_PROFILE_LEGACY_IDS,
            ubuntu_beagle_profile_release=UBUNTU_BEAGLE_PROFILE_RELEASE,
            ubuntu_beagle_profile_streaming=UBUNTU_BEAGLE_PROFILE_STREAMING,
            ubuntu_beagle_software_presets=UBUNTU_BEAGLE_SOFTWARE_PRESETS,
            ubuntu_beagle_sunshine_url=UBUNTU_BEAGLE_SUNSHINE_URL,
            ubuntu_beagle_tokens_dir=ubuntu_beagle_tokens_dir,
            utcnow=utcnow,
            validate_linux_username=ubuntu_beagle_inputs_service().validate_linux_username,
            validate_password=ubuntu_beagle_inputs_service().validate_password,
        )
    return UBUNTU_BEAGLE_PROVISIONING_SERVICE


def build_provisioning_catalog() -> dict[str, Any]:
    return ubuntu_beagle_provisioning_service().build_provisioning_catalog()


def create_provisioned_vm(payload: dict[str, Any]) -> dict[str, Any]:
    return ubuntu_beagle_provisioning_service().create_provisioned_vm(payload)


def finalize_ubuntu_beagle_install(state: dict[str, Any], *, restart: bool = True) -> dict[str, Any]:
    return ubuntu_beagle_provisioning_service().finalize_ubuntu_beagle_install(state, restart=restart)


def prepare_ubuntu_beagle_firstboot(state: dict[str, Any]) -> dict[str, Any]:
    return ubuntu_beagle_provisioning_service().prepare_ubuntu_beagle_firstboot(state)


def create_ubuntu_beagle_vm(payload: dict[str, Any]) -> dict[str, Any]:
    return ubuntu_beagle_provisioning_service().create_ubuntu_beagle_vm(payload)


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
            expand_software_packages=ubuntu_beagle_inputs_service().expand_software_packages,
            find_vm=lambda vmid: VIRTUALIZATION_INVENTORY.find_vm(vmid),
            first_guest_ipv4=first_guest_ipv4,
            get_vm_config=get_vm_config,
            list_policies=list_policies,
            listify=listify,
            load_vm_secret=load_vm_secret,
            manager_pinned_pubkey=manager_pinned_pubkey(),
            normalize_endpoint_profile_contract=normalize_endpoint_profile_contract,
            parse_description_meta=parse_description_meta,
            public_installer_iso_url=download_metadata_service().public_installer_iso_url,
            public_manager_url=PUBLIC_MANAGER_URL,
            resolve_public_stream_host=resolve_public_stream_host,
            resolve_ubuntu_beagle_desktop=ubuntu_beagle_inputs_service().resolve_ubuntu_beagle_desktop,
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
    return ubuntu_beagle_provisioning_service().update_ubuntu_beagle_vm(vmid, payload)


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
            update_payload_metadata=download_metadata_service().update_payload_metadata,
            public_update_sha256sums_url=download_metadata_service().public_update_sha256sums_url,
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
            public_installer_iso_url=download_metadata_service().public_installer_iso_url,
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
            ensure_vm_secret=ensure_vm_secret,
            fetch_sunshine_server_identity=fetch_sunshine_server_identity,
            get_vm_config=get_vm_config,
            hosted_installer_iso_file=HOSTED_INSTALLER_ISO_FILE,
            hosted_installer_template_file=HOSTED_INSTALLER_TEMPLATE_FILE,
            hosted_live_usb_template_file=HOSTED_LIVE_USB_TEMPLATE_FILE,
            issue_enrollment_token=issue_enrollment_token,
            manager_pinned_pubkey=manager_pinned_pubkey(),
            parse_description_meta=parse_description_meta,
            patch_installer_defaults=installer_template_patch_service().patch_installer_defaults,
            patch_windows_installer_defaults=installer_template_patch_service().patch_windows_installer_defaults,
            public_bootstrap_latest_download_url=download_metadata_service().public_bootstrap_latest_download_url,
            public_installer_iso_url=download_metadata_service().public_installer_iso_url,
            public_manager_url=PUBLIC_MANAGER_URL,
            public_payload_latest_download_url=download_metadata_service().public_payload_latest_download_url,
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
        return sunshine_integration_service().resolve_ticket_vm(path)

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
                response_payload = endpoint_enrollment_service().enroll_endpoint(self._read_json_body())
            except Exception as exc:
                if isinstance(exc, ValueError):
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                elif isinstance(exc, PermissionError):
                    self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": str(exc)})
                elif isinstance(exc, LookupError):
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": str(exc)})
                else:
                    raise
                return
            self._write_json(HTTPStatus.CREATED, response_payload)
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
