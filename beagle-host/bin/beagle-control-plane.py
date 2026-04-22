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

ROOT_DIR = Path(__file__).resolve().parents[2]
PROVIDERS_DIR = Path(__file__).resolve().parents[1] / "providers"
SERVICES_DIR = Path(__file__).resolve().parents[1] / "services"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(PROVIDERS_DIR) not in sys.path:
    sys.path.insert(0, str(PROVIDERS_DIR))
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from action_queue import ActionQueueService
from admin_http_surface import AdminHttpSurfaceService
from auth_http_surface import AuthHttpSurfaceService
from audit_helpers import build_vm_power_audit_event
from audit_export import AuditExportConfig, AuditExportService
from audit_log import AuditLogService
from audit_report import AuditReportService
from auth_session import AuthSessionService, default_now
from authz_policy import AuthzPolicyService, PERMISSION_CATALOG
from cluster_inventory import ClusterInventoryService
from control_plane_read_surface import ControlPlaneReadSurfaceService
from download_metadata import DownloadMetadataService
from endpoint_lifecycle_surface import EndpointLifecycleSurfaceService
from endpoint_http_surface import EndpointHttpSurfaceService
from endpoint_enrollment import EndpointEnrollmentService
from endpoint_profile_contract import installer_profile_surface, normalize_endpoint_profile_contract
from endpoint_report import EndpointReportService
from endpoint_token_store import EndpointTokenStoreService
from enrollment_token_store import EnrollmentTokenStoreService
from fleet_inventory import FleetInventoryService
from health_payload import HealthPayloadService
from host_provider_contract import HostProvider
from identity_provider_registry import IdentityProviderRegistryService
from installer_prep import InstallerPrepService
from installer_script import InstallerScriptService
from installer_template_patch import InstallerTemplatePatchService
from metadata_support import MetadataSupportService
from oidc_service import OidcService
from persistence_support import PersistenceSupportService
from policy_normalization import PolicyNormalizationService
from policy_store import PolicyStoreService
from pairing_service import PairingService
from public_http_surface import PublicHttpSurfaceService
from public_sunshine_surface import PublicSunshineSurfaceService
from public_ubuntu_install_surface import PublicUbuntuInstallSurfaceService
from public_streams import PublicStreamService
from recording_service import RecordingService
from request_support import RequestSupportService
from registry import create_provider, list_providers, normalize_provider_kind
from runtime_environment import RuntimeEnvironmentService
from runtime_exec import RuntimeExecService
from runtime_paths import RuntimePathsService
from runtime_support import RuntimeSupportService
from scim_service import ScimService
from saml_service import SamlService
from sunshine_access_token_store import SunshineAccessTokenStoreService
from sunshine_integration import SunshineIntegrationService
from support_bundle_store import SupportBundleStoreService
from time_support import TimeSupportService
from ubuntu_beagle_inputs import UbuntuBeagleInputsService
from ubuntu_beagle_restart import UbuntuBeagleRestartService
from ubuntu_beagle_state import UbuntuBeagleStateService
from ubuntu_beagle_provisioning import UbuntuBeagleProvisioningService
from update_feed import UpdateFeedService
from utility_support import UtilitySupportService
from virtualization_inventory import VirtualizationInventoryService
from virtualization_read_surface import VirtualizationReadSurfaceService
from webhook_service import WebhookService
from vm_mutation_surface import VmMutationSurfaceService
from vm_profile import VmProfileService
from vm_console_access import VmConsoleAccessService
from vm_http_surface import VmHttpSurfaceService
from server_settings import ServerSettingsService
from storage_quota import StorageQuotaService
from entitlement_service import EntitlementService
from pool_manager import PoolManagerService
from desktop_template_builder import DesktopTemplateBuilderService
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
VERSION_FILE = ROOT_DIR / "VERSION"
if VERSION_FILE.exists():
    VERSION = VERSION_FILE.read_text(encoding="utf-8").strip() or VERSION

LISTEN_HOST = os.environ.get("BEAGLE_MANAGER_LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("BEAGLE_MANAGER_LISTEN_PORT", "9088"))
DATA_DIR = Path(os.environ.get("BEAGLE_MANAGER_DATA_DIR", "/var/lib/beagle/beagle-manager"))
API_TOKEN = os.environ.get("BEAGLE_MANAGER_API_TOKEN", "").strip()
AUTH_BOOTSTRAP_USERNAME = os.environ.get("BEAGLE_AUTH_BOOTSTRAP_USERNAME", "admin").strip() or "admin"
AUTH_BOOTSTRAP_PASSWORD = os.environ.get("BEAGLE_AUTH_BOOTSTRAP_PASSWORD", "").strip()
AUTH_BOOTSTRAP_PASSWORD_FROM_API_TOKEN = os.environ.get("BEAGLE_AUTH_BOOTSTRAP_PASSWORD_FROM_API_TOKEN", "0").strip().lower() in {"1", "true", "yes", "on"}
if not AUTH_BOOTSTRAP_PASSWORD and AUTH_BOOTSTRAP_PASSWORD_FROM_API_TOKEN and API_TOKEN:
    AUTH_BOOTSTRAP_PASSWORD = API_TOKEN
AUTH_BOOTSTRAP_DISABLE = os.environ.get("BEAGLE_AUTH_BOOTSTRAP_DISABLE", "0").strip().lower() in {"1", "true", "yes", "on"}
AUTH_ACCESS_TTL_SECONDS = int(os.environ.get("BEAGLE_AUTH_ACCESS_TTL_SECONDS", "900"))
AUTH_REFRESH_TTL_SECONDS = int(os.environ.get("BEAGLE_AUTH_REFRESH_TTL_SECONDS", str(7 * 24 * 3600)))
AUTH_IDLE_TIMEOUT_SECONDS = int(os.environ.get("BEAGLE_AUTH_IDLE_TIMEOUT_SECONDS", "1800"))
AUTH_ABSOLUTE_TIMEOUT_SECONDS = int(os.environ.get("BEAGLE_AUTH_ABSOLUTE_TIMEOUT_SECONDS", str(7 * 24 * 3600)))
AUTH_MAX_SESSIONS_PER_USER = int(os.environ.get("BEAGLE_AUTH_MAX_SESSIONS_PER_USER", "5"))
API_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("BEAGLE_API_RATE_LIMIT_WINDOW_SECONDS", "60"))
API_RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("BEAGLE_API_RATE_LIMIT_MAX_REQUESTS", "240"))
AUDIT_EXPORT_S3_BUCKET = os.environ.get("BEAGLE_AUDIT_EXPORT_S3_BUCKET", "").strip()
AUDIT_EXPORT_S3_PREFIX = os.environ.get("BEAGLE_AUDIT_EXPORT_S3_PREFIX", "audit").strip() or "audit"
AUDIT_EXPORT_S3_REGION = os.environ.get("BEAGLE_AUDIT_EXPORT_S3_REGION", "us-east-1").strip() or "us-east-1"
AUDIT_EXPORT_S3_ENDPOINT = os.environ.get("BEAGLE_AUDIT_EXPORT_S3_ENDPOINT", "").strip()
AUDIT_EXPORT_S3_ACCESS_KEY = os.environ.get("BEAGLE_AUDIT_EXPORT_S3_ACCESS_KEY", "").strip()
AUDIT_EXPORT_S3_SECRET_KEY = os.environ.get("BEAGLE_AUDIT_EXPORT_S3_SECRET_KEY", "").strip()
AUDIT_EXPORT_SYSLOG_ADDRESS = os.environ.get("BEAGLE_AUDIT_EXPORT_SYSLOG_ADDRESS", "").strip()
AUDIT_EXPORT_SYSLOG_TRANSPORT = os.environ.get("BEAGLE_AUDIT_EXPORT_SYSLOG_TRANSPORT", "udp").strip() or "udp"
AUDIT_EXPORT_WEBHOOK_URL = os.environ.get("BEAGLE_AUDIT_EXPORT_WEBHOOK_URL", "").strip()
AUDIT_EXPORT_WEBHOOK_SECRET = os.environ.get("BEAGLE_AUDIT_EXPORT_WEBHOOK_SECRET", "").strip()
AUDIT_EXPORT_WEBHOOK_TIMEOUT_SECONDS = float(os.environ.get("BEAGLE_AUDIT_EXPORT_WEBHOOK_TIMEOUT_SECONDS", "5"))
AUTH_LOGIN_LOCKOUT_THRESHOLD = int(os.environ.get("BEAGLE_AUTH_LOGIN_LOCKOUT_THRESHOLD", "5"))
AUTH_LOGIN_LOCKOUT_SECONDS = int(os.environ.get("BEAGLE_AUTH_LOGIN_LOCKOUT_SECONDS", "300"))
AUTH_LOGIN_BACKOFF_MAX_SECONDS = int(os.environ.get("BEAGLE_AUTH_LOGIN_BACKOFF_MAX_SECONDS", "30"))
ALLOW_LOCALHOST_NOAUTH = os.environ.get("BEAGLE_MANAGER_ALLOW_LOCALHOST_NOAUTH", "0").strip().lower() in {"1", "true", "yes", "on"}
STALE_ENDPOINT_SECONDS = int(os.environ.get("BEAGLE_MANAGER_STALE_ENDPOINT_SECONDS", "600"))
DOWNLOADS_STATUS_FILE = ROOT_DIR / "dist" / "beagle-downloads-status.json"
DIST_SHA256SUMS_FILE = ROOT_DIR / "dist" / "SHA256SUMS"
VM_INSTALLERS_FILE = ROOT_DIR / "dist" / "beagle-vm-installers.json"
HOSTED_INSTALLER_TEMPLATE_FILE = ROOT_DIR / "dist" / "pve-thin-client-usb-installer-host-latest.sh"
HOSTED_LIVE_USB_TEMPLATE_FILE = ROOT_DIR / "dist" / "pve-thin-client-live-usb-host-latest.sh"
HOSTED_WINDOWS_INSTALLER_TEMPLATE_FILE = ROOT_DIR / "dist" / "pve-thin-client-usb-installer-host-latest.ps1"
RAW_SHELL_INSTALLER_TEMPLATE_FILE = ROOT_DIR / "thin-client-assistant" / "usb" / "pve-thin-client-usb-installer.sh"
RAW_WINDOWS_INSTALLER_TEMPLATE_FILE = ROOT_DIR / "thin-client-assistant" / "usb" / "pve-thin-client-usb-installer.ps1"
HOSTED_INSTALLER_ISO_FILE = ROOT_DIR / "dist" / "beagle-os-installer-amd64.iso"
INSTALLER_PREP_SCRIPT_FILE = ROOT_DIR / "scripts" / "ensure-vm-stream-ready.sh"
CREDENTIALS_ENV_FILE = Path(os.environ.get("PVE_DCV_CREDENTIALS_ENV_FILE", "/etc/beagle/credentials.env"))
MANAGER_CERT_FILE = Path(os.environ.get("BEAGLE_MANAGER_CERT_FILE", "/etc/pve/local/pveproxy-ssl.pem"))
UBUNTU_BEAGLE_TEMPLATE_DIR = ROOT_DIR / "beagle-host" / "templates" / "ubuntu-beagle"
def _resolve_public_hostname(name: str) -> str:
    """Normalise a configured public hostname for use in outward-facing URLs.

    Rules (same as vm_console_access and runtime_environment):
    - IP literal      → return as-is
    - FQDN (has dot)  → return as-is so Let's Encrypt / public TLS stays valid
    - Bare hostname   → resolve to a non-loopback IPv4 so thin clients without
                        local DNS can reach the server; fall back to the primary
                        outbound IPv4 if the name resolves to loopback.
    """
    import ipaddress as _ipaddress

    candidate = str(name or "").strip()
    if not candidate:
        return candidate
    try:
        _ipaddress.ip_address(candidate)
        return candidate
    except ValueError:
        pass
    if "." in candidate:
        return candidate
    try:
        resolved = socket.gethostbyname(candidate)
        if not _ipaddress.ip_address(resolved).is_loopback:
            return resolved
    except OSError:
        pass
    try:
        _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _s.connect(("1.1.1.1", 80))
        _ip = _s.getsockname()[0]
        _s.close()
        if _ip and not _ip.startswith("127."):
            return _ip
    except OSError:
        pass
    return candidate


PUBLIC_SERVER_NAME = _resolve_public_hostname(
    os.environ.get("PVE_DCV_PROXY_SERVER_NAME", "").strip() or os.uname().nodename
)
PUBLIC_DOWNLOADS_PORT = int(os.environ.get("PVE_DCV_PROXY_LISTEN_PORT", "8443"))
PUBLIC_DOWNLOADS_PATH = os.environ.get("PVE_DCV_DOWNLOADS_PATH", "/beagle-downloads").strip() or "/beagle-downloads"
PUBLIC_UPDATE_BASE_URL = os.environ.get("BEAGLE_PUBLIC_UPDATE_BASE_URL", "").strip() or f"https://{PUBLIC_SERVER_NAME}:{PUBLIC_DOWNLOADS_PORT}{PUBLIC_DOWNLOADS_PATH}"
PUBLIC_STREAM_HOST_RAW = os.environ.get("BEAGLE_PUBLIC_STREAM_HOST", "").strip() or PUBLIC_SERVER_NAME
INTERNAL_CALLBACK_HOST_RAW = os.environ.get("BEAGLE_INTERNAL_CALLBACK_HOST", "").strip()
PUBLIC_STREAM_BASE_PORT = int(os.environ.get("BEAGLE_PUBLIC_STREAM_BASE_PORT", "50000"))
PUBLIC_STREAM_PORT_STEP = int(os.environ.get("BEAGLE_PUBLIC_STREAM_PORT_STEP", "32"))
PUBLIC_STREAM_PORT_COUNT = int(os.environ.get("BEAGLE_PUBLIC_STREAM_PORT_COUNT", "256"))
PUBLIC_MANAGER_URL = os.environ.get("PVE_DCV_BEAGLE_MANAGER_URL", "").strip() or f"https://{PUBLIC_SERVER_NAME}:{PUBLIC_DOWNLOADS_PORT}/beagle-api"
WEB_UI_URL = os.environ.get("BEAGLE_WEB_UI_URL", "").strip()
IDENTITY_PROVIDER_REGISTRY_FILE = Path(
    os.environ.get("BEAGLE_IDENTITY_PROVIDER_REGISTRY_FILE", "/etc/beagle/identity-providers.json")
)
OIDC_AUTH_URL = os.environ.get("BEAGLE_OIDC_AUTH_URL", "").strip()
SAML_LOGIN_URL = os.environ.get("BEAGLE_SAML_LOGIN_URL", "").strip()
OIDC_ENABLED = os.environ.get("BEAGLE_OIDC_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
OIDC_ISSUER = os.environ.get("BEAGLE_OIDC_ISSUER", "").strip()
OIDC_CLIENT_ID = os.environ.get("BEAGLE_OIDC_CLIENT_ID", "").strip()
OIDC_REDIRECT_URI = os.environ.get("BEAGLE_OIDC_REDIRECT_URI", "").strip() or f"{PUBLIC_MANAGER_URL.rstrip('/')}/api/v1/auth/oidc/callback"
OIDC_AUTHORIZATION_ENDPOINT = os.environ.get("BEAGLE_OIDC_AUTHORIZATION_ENDPOINT", "").strip() or OIDC_AUTH_URL
OIDC_TOKEN_ENDPOINT = os.environ.get("BEAGLE_OIDC_TOKEN_ENDPOINT", "").strip()
OIDC_USERINFO_ENDPOINT = os.environ.get("BEAGLE_OIDC_USERINFO_ENDPOINT", "").strip()
OIDC_SCOPE = os.environ.get("BEAGLE_OIDC_SCOPE", "openid profile email").strip() or "openid profile email"
SAML_ENABLED = os.environ.get("BEAGLE_SAML_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
SAML_ENTITY_ID = os.environ.get("BEAGLE_SAML_ENTITY_ID", "").strip() or f"{PUBLIC_MANAGER_URL.rstrip('/')}/api/v1/auth/saml/metadata"
SAML_ACS_URL = os.environ.get("BEAGLE_SAML_ACS_URL", "").strip() or f"{PUBLIC_MANAGER_URL.rstrip('/')}/api/v1/auth/saml/callback"
SAML_IDP_SSO_URL = os.environ.get("BEAGLE_SAML_IDP_SSO_URL", "").strip() or SAML_LOGIN_URL
SAML_NAMEID_FORMAT = os.environ.get(
    "BEAGLE_SAML_NAMEID_FORMAT",
    "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
).strip() or "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
SAML_SIGNING_CERT_FILE = Path(os.environ.get("BEAGLE_SAML_SIGNING_CERT_FILE", "/etc/beagle/saml/sp-signing.crt"))
SCIM_BEARER_TOKEN = os.environ.get("BEAGLE_SCIM_BEARER_TOKEN", "").strip()
CORS_ALLOWED_ORIGINS_RAW = os.environ.get("BEAGLE_CORS_ALLOWED_ORIGINS", "").strip()
API_V2_PREPARATION_ENABLED = os.environ.get("BEAGLE_API_V2_PREPARATION_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}
API_V1_DEPRECATED_ENDPOINTS_RAW = os.environ.get(
    "BEAGLE_API_V1_DEPRECATED_ENDPOINTS",
    "/api/v1/vms,/api/v1/provisioning/vms",
).strip()
API_V1_DEPRECATED_ENDPOINTS = {
    (item.strip().rstrip("/") or "/")
    for item in API_V1_DEPRECATED_ENDPOINTS_RAW.split(",")
    if item.strip()
}
API_V1_DEPRECATION_SUNSET = os.environ.get(
    "BEAGLE_API_V1_DEPRECATION_SUNSET",
    "Tue, 21 Apr 2027 00:00:00 GMT",
).strip() or "Tue, 21 Apr 2027 00:00:00 GMT"
API_V1_DEPRECATION_DOC_URL = os.environ.get(
    "BEAGLE_API_V1_DEPRECATION_DOC_URL",
    "https://beagle-os.com/api/migrations/v1-to-v2",
).strip() or "https://beagle-os.com/api/migrations/v1-to-v2"
NOVNC_PATH = os.environ.get("BEAGLE_NOVNC_PATH", "/novnc").strip() or "/novnc"
NOVNC_TOKEN_FILE = os.environ.get("BEAGLE_NOVNC_TOKEN_FILE", "/etc/beagle/novnc/tokens").strip() or "/etc/beagle/novnc/tokens"
BEAGLE_HOST_PROVIDER_KIND = normalize_provider_kind(os.environ.get("BEAGLE_HOST_PROVIDER", "beagle"))
ENROLLMENT_TOKEN_TTL_SECONDS = int(os.environ.get("BEAGLE_ENROLLMENT_TOKEN_TTL_SECONDS", "86400"))
SUNSHINE_ACCESS_TOKEN_TTL_SECONDS = int(os.environ.get("BEAGLE_SUNSHINE_ACCESS_TOKEN_TTL_SECONDS", "600"))
PAIRING_TOKEN_TTL_SECONDS = int(os.environ.get("BEAGLE_PAIRING_TOKEN_TTL_SECONDS", "120"))
PAIRING_TOKEN_SECRET = os.environ.get("BEAGLE_PAIRING_TOKEN_SECRET", "").strip()
USB_TUNNEL_SSH_USER = os.environ.get("BEAGLE_USB_TUNNEL_SSH_USER", "beagle-tunnel").strip() or "beagle-tunnel"
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
UBUNTU_BEAGLE_DEFAULT_MEMORY_MIB = int(os.environ.get("BEAGLE_UBUNTU_DEFAULT_MEMORY_MIB", "4096"))
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
UBUNTU_BEAGLE_LOCAL_ISO_DIR = Path(
    os.environ.get("BEAGLE_UBUNTU_LOCAL_ISO_DIR", "/var/lib/vz/template/iso").strip() or "/var/lib/vz/template/iso"
)
UBUNTU_BEAGLE_AUTOINSTALL_URL_TTL_SECONDS = int(os.environ.get("BEAGLE_UBUNTU_AUTOINSTALL_URL_TTL_SECONDS", "21600"))
UBUNTU_BEAGLE_AUTOINSTALL_STALE_SECONDS = int(os.environ.get("BEAGLE_UBUNTU_AUTOINSTALL_STALE_SECONDS", "1800"))
UBUNTU_BEAGLE_FIRSTBOOT_POWERDOWN_WAIT_SECONDS = int(os.environ.get("BEAGLE_UBUNTU_FIRSTBOOT_POWERDOWN_WAIT_SECONDS", "600"))
UBUNTU_BEAGLE_FIRSTBOOT_STALE_SECONDS = int(os.environ.get("BEAGLE_UBUNTU_FIRSTBOOT_STALE_SECONDS", "900"))
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
RUNTIME_EXEC_SERVICE = RuntimeExecService(
    default_timeout_seconds=COMMAND_TIMEOUT_SECONDS,
    default_timeout_sentinel=DEFAULT_COMMAND_TIMEOUT,
    run_subprocess=subprocess.run,
)
PERSISTENCE_SUPPORT_SERVICE = PersistenceSupportService()
TIME_SUPPORT_SERVICE = TimeSupportService(now=lambda: datetime.now(timezone.utc))
RUNTIME_PATHS_SERVICE = RuntimePathsService(
    preferred_data_dir=DATA_DIR,
    fallback_data_dir=Path("/run/beagle-control-plane"),
    chmod_path=os.chmod,
    mkdir_path=lambda path: path.mkdir(parents=True, exist_ok=True),
)
UTILITY_SUPPORT_SERVICE = UtilitySupportService(
    choice=secrets.choice,
    randbelow=secrets.randbelow,
)
METADATA_SUPPORT_SERVICE = MetadataSupportService()
REQUEST_SUPPORT_SERVICE: RequestSupportService | None = None
AUTH_SESSION_SERVICE: AuthSessionService | None = None
AUDIT_LOG_SERVICE: AuditLogService | None = None
AUDIT_EXPORT_SERVICE: AuditExportService | None = None
AUDIT_REPORT_SERVICE: AuditReportService | None = None
AUTHZ_POLICY_SERVICE: AuthzPolicyService | None = None
SERVER_SETTINGS_SERVICE: ServerSettingsService | None = None
STORAGE_QUOTA_SERVICE: StorageQuotaService | None = None
ENTITLEMENT_SERVICE: EntitlementService | None = None
POOL_MANAGER_SERVICE: PoolManagerService | None = None
DESKTOP_TEMPLATE_BUILDER_SERVICE: DesktopTemplateBuilderService | None = None
WEBHOOK_SERVICE: WebhookService | None = None
IDENTITY_PROVIDER_REGISTRY_SERVICE: IdentityProviderRegistryService | None = None
OIDC_SERVICE: OidcService | None = None
SAML_SERVICE: SamlService | None = None
SCIM_SERVICE: ScimService | None = None


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
    return time_support_service().utcnow()


def parse_utc_timestamp(value: str) -> datetime | None:
    return time_support_service().parse_utc_timestamp(value)


def timestamp_age_seconds(value: str) -> int | None:
    return time_support_service().timestamp_age_seconds(value)


def utility_support_service() -> UtilitySupportService:
    return UTILITY_SUPPORT_SERVICE


def metadata_support_service() -> MetadataSupportService:
    return METADATA_SUPPORT_SERVICE


def load_json_file(path: Path, fallback: Any) -> Any:
    return persistence_support_service().load_json_file(path, fallback)


def runtime_support_service() -> RuntimeSupportService:
    return RUNTIME_SUPPORT_SERVICE


def runtime_exec_service() -> RuntimeExecService:
    return RUNTIME_EXEC_SERVICE


def persistence_support_service() -> PersistenceSupportService:
    return PERSISTENCE_SUPPORT_SERVICE


def time_support_service() -> TimeSupportService:
    return TIME_SUPPORT_SERVICE


def runtime_paths_service() -> RuntimePathsService:
    return RUNTIME_PATHS_SERVICE


def request_support_service() -> RequestSupportService:
    global REQUEST_SUPPORT_SERVICE
    if REQUEST_SUPPORT_SERVICE is None:
        REQUEST_SUPPORT_SERVICE = RequestSupportService(
            cache_get=cache_get,
            cache_put=cache_put,
            cors_allowed_origins_raw=CORS_ALLOWED_ORIGINS_RAW,
            current_public_stream_host=current_public_stream_host,
            listify=listify,
            public_downloads_port=PUBLIC_DOWNLOADS_PORT,
            public_manager_url=PUBLIC_MANAGER_URL,
            public_server_name=PUBLIC_SERVER_NAME,
            public_stream_host_raw=PUBLIC_STREAM_HOST_RAW,
            web_ui_url=WEB_UI_URL,
        )
    return REQUEST_SUPPORT_SERVICE


def auth_session_service() -> AuthSessionService:
    global AUTH_SESSION_SERVICE
    if AUTH_SESSION_SERVICE is None:
        AUTH_SESSION_SERVICE = AuthSessionService(
            data_dir=ensure_data_dir(),
            load_json_file=load_json_file,
            write_json_file=lambda path, payload: persistence_support_service().write_json_file(path, payload),
            now=default_now,
            token_urlsafe=secrets.token_urlsafe,
            access_ttl_seconds=AUTH_ACCESS_TTL_SECONDS,
            refresh_ttl_seconds=AUTH_REFRESH_TTL_SECONDS,
            idle_timeout_seconds=AUTH_IDLE_TIMEOUT_SECONDS,
            absolute_timeout_seconds=AUTH_ABSOLUTE_TIMEOUT_SECONDS,
            max_sessions_per_user=AUTH_MAX_SESSIONS_PER_USER,
        )
        if not AUTH_BOOTSTRAP_DISABLE:
            AUTH_SESSION_SERVICE.ensure_bootstrap_admin(
                username=AUTH_BOOTSTRAP_USERNAME,
                password=AUTH_BOOTSTRAP_PASSWORD,
            )
    return AUTH_SESSION_SERVICE


def audit_export_service() -> AuditExportService:
    global AUDIT_EXPORT_SERVICE
    if AUDIT_EXPORT_SERVICE is None:
        AUDIT_EXPORT_SERVICE = AuditExportService(
            config=AuditExportConfig(
                s3_bucket=AUDIT_EXPORT_S3_BUCKET,
                s3_prefix=AUDIT_EXPORT_S3_PREFIX,
                s3_region=AUDIT_EXPORT_S3_REGION,
                s3_endpoint=AUDIT_EXPORT_S3_ENDPOINT,
                s3_access_key=AUDIT_EXPORT_S3_ACCESS_KEY,
                s3_secret_key=AUDIT_EXPORT_S3_SECRET_KEY,
                syslog_address=AUDIT_EXPORT_SYSLOG_ADDRESS,
                syslog_transport=AUDIT_EXPORT_SYSLOG_TRANSPORT,
                webhook_url=AUDIT_EXPORT_WEBHOOK_URL,
                webhook_secret=AUDIT_EXPORT_WEBHOOK_SECRET,
                webhook_timeout_seconds=AUDIT_EXPORT_WEBHOOK_TIMEOUT_SECONDS,
            ),
            data_dir=ensure_data_dir(),
            now_utc=utcnow,
        )
    return AUDIT_EXPORT_SERVICE


def audit_log_service() -> AuditLogService:
    global AUDIT_LOG_SERVICE
    if AUDIT_LOG_SERVICE is None:
        AUDIT_LOG_SERVICE = AuditLogService(
            log_file=ensure_data_dir() / "audit" / "events.log",
            now_utc=utcnow,
            export_event=audit_export_service().export_event,
        )
    return AUDIT_LOG_SERVICE


def audit_report_service() -> AuditReportService:
    global AUDIT_REPORT_SERVICE
    if AUDIT_REPORT_SERVICE is None:
        AUDIT_REPORT_SERVICE = AuditReportService(
            log_file=ensure_data_dir() / "audit" / "events.log",
        )
    return AUDIT_REPORT_SERVICE


def authz_policy_service() -> AuthzPolicyService:
    global AUTHZ_POLICY_SERVICE
    if AUTHZ_POLICY_SERVICE is None:
        AUTHZ_POLICY_SERVICE = AuthzPolicyService()
    return AUTHZ_POLICY_SERVICE


def server_settings_service() -> ServerSettingsService:
    global SERVER_SETTINGS_SERVICE
    if SERVER_SETTINGS_SERVICE is None:
        SERVER_SETTINGS_SERVICE = ServerSettingsService(
            data_dir=ensure_data_dir(),
            utcnow=utcnow,
            webhook_service=webhook_service(),
        )
    return SERVER_SETTINGS_SERVICE


def storage_quota_service() -> StorageQuotaService:
    global STORAGE_QUOTA_SERVICE
    if STORAGE_QUOTA_SERVICE is None:
        STORAGE_QUOTA_SERVICE = StorageQuotaService(
            state_file=DATA_DIR / "storage-quotas.json",
        )
    return STORAGE_QUOTA_SERVICE


def entitlement_service() -> EntitlementService:
    global ENTITLEMENT_SERVICE
    if ENTITLEMENT_SERVICE is None:
        ENTITLEMENT_SERVICE = EntitlementService(
            state_file=DATA_DIR / "pool-entitlements.json",
        )
    return ENTITLEMENT_SERVICE


def pool_manager_service() -> PoolManagerService:
    global POOL_MANAGER_SERVICE
    if POOL_MANAGER_SERVICE is None:
        POOL_MANAGER_SERVICE = PoolManagerService(
            state_file=DATA_DIR / "desktop-pools.json",
            utcnow=utcnow,
        )
    return POOL_MANAGER_SERVICE


def desktop_template_builder_service() -> DesktopTemplateBuilderService:
    global DESKTOP_TEMPLATE_BUILDER_SERVICE
    if DESKTOP_TEMPLATE_BUILDER_SERVICE is None:
        DESKTOP_TEMPLATE_BUILDER_SERVICE = DesktopTemplateBuilderService(
            state_file=DATA_DIR / "desktop-templates.json",
            template_images_dir=DATA_DIR / "template-images",
            utcnow=utcnow,
        )
    return DESKTOP_TEMPLATE_BUILDER_SERVICE


def webhook_service() -> WebhookService:
    global WEBHOOK_SERVICE
    if WEBHOOK_SERVICE is None:
        WEBHOOK_SERVICE = WebhookService(
            data_dir=ensure_data_dir(),
            utcnow=utcnow,
        )
    return WEBHOOK_SERVICE


def identity_provider_registry_service() -> IdentityProviderRegistryService:
    global IDENTITY_PROVIDER_REGISTRY_SERVICE
    if IDENTITY_PROVIDER_REGISTRY_SERVICE is None:
        try:
            IDENTITY_PROVIDER_REGISTRY_SERVICE = IdentityProviderRegistryService(
                load_json_file=load_json_file,
                registry_file=IDENTITY_PROVIDER_REGISTRY_FILE,
                oidc_auth_url=OIDC_AUTH_URL,
                saml_login_url=SAML_LOGIN_URL,
                public_manager_url=PUBLIC_MANAGER_URL,
                oidc_enabled=OIDC_ENABLED,
                saml_enabled=SAML_ENABLED,
            )
        except TypeError:
            # Backward compatibility for stale runtime module copies that may
            # still expose the pre-oidc/saml constructor signature.
            IDENTITY_PROVIDER_REGISTRY_SERVICE = IdentityProviderRegistryService(
                load_json_file=load_json_file,
                registry_file=IDENTITY_PROVIDER_REGISTRY_FILE,
                oidc_auth_url=OIDC_AUTH_URL,
                saml_login_url=SAML_LOGIN_URL,
                public_manager_url=PUBLIC_MANAGER_URL,
            )
    return IDENTITY_PROVIDER_REGISTRY_SERVICE


def oidc_service() -> OidcService:
    global OIDC_SERVICE
    if OIDC_SERVICE is None:
        OIDC_SERVICE = OidcService(
            data_dir=ensure_data_dir(),
            enabled=OIDC_ENABLED,
            issuer=OIDC_ISSUER,
            client_id=OIDC_CLIENT_ID,
            redirect_uri=OIDC_REDIRECT_URI,
            authorization_endpoint=OIDC_AUTHORIZATION_ENDPOINT,
            token_endpoint=OIDC_TOKEN_ENDPOINT,
            userinfo_endpoint=OIDC_USERINFO_ENDPOINT,
            scope=OIDC_SCOPE,
            utcnow=utcnow,
            load_json_file=load_json_file,
            write_json_file=lambda path, payload: persistence_support_service().write_json_file(path, payload),
        )
    return OIDC_SERVICE


def saml_service() -> SamlService:
    global SAML_SERVICE
    if SAML_SERVICE is None:
        cert_text = ""
        if SAML_SIGNING_CERT_FILE.exists():
            cert_text = SAML_SIGNING_CERT_FILE.read_text(encoding="utf-8", errors="ignore")
        SAML_SERVICE = SamlService(
            enabled=SAML_ENABLED,
            entity_id=SAML_ENTITY_ID,
            acs_url=SAML_ACS_URL,
            idp_sso_url=SAML_IDP_SSO_URL,
            nameid_format=SAML_NAMEID_FORMAT,
            signing_cert_pem=cert_text,
        )
    return SAML_SERVICE


def scim_service() -> ScimService:
    global SCIM_SERVICE
    if SCIM_SERVICE is None:
        SCIM_SERVICE = ScimService(
            create_user=auth_session_service().create_user,
            delete_role=auth_session_service().delete_role,
            delete_user=auth_session_service().delete_user,
            list_roles=auth_session_service().list_roles,
            list_users=auth_session_service().list_users,
            save_role=auth_session_service().save_role,
            service_name="beagle-control-plane",
            token_urlsafe=secrets.token_urlsafe,
            update_user=auth_session_service().update_user,
            utcnow=utcnow,
            version=VERSION,
        )
    return SCIM_SERVICE


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
    return request_support_service().normalized_origin(value)


def cors_allowed_origins() -> set[str]:
    return request_support_service().cors_allowed_origins()


def checksum_for_dist_filename(filename: str) -> str:
    return download_metadata_service().checksum_for_dist_filename(filename)


def update_payload_metadata(version: str) -> dict[str, str]:
    return download_metadata_service().update_payload_metadata(version)


def ensure_data_dir() -> Path:
    return runtime_paths_service().ensure_data_dir()


def run_json(command: list[str], *, timeout: float | None | object = DEFAULT_COMMAND_TIMEOUT) -> Any:
    return runtime_exec_service().run_json(command, timeout=timeout)


def run_text(command: list[str], *, timeout: float | None | object = DEFAULT_COMMAND_TIMEOUT) -> str:
    return runtime_exec_service().run_text(command, timeout=timeout)


def run_checked(command: list[str], *, timeout: float | None | object = DEFAULT_COMMAND_TIMEOUT) -> str:
    return runtime_exec_service().run_checked(command, timeout=timeout)


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
VM_CONSOLE_ACCESS_SERVICE: VmConsoleAccessService | None = None
VM_HTTP_SURFACE_SERVICE: VmHttpSurfaceService | None = None
CONTROL_PLANE_READ_SURFACE_SERVICE: ControlPlaneReadSurfaceService | None = None
VIRTUALIZATION_READ_SURFACE_SERVICE: VirtualizationReadSurfaceService | None = None
PUBLIC_HTTP_SURFACE_SERVICE: PublicHttpSurfaceService | None = None
PUBLIC_UBUNTU_INSTALL_SURFACE_SERVICE: PublicUbuntuInstallSurfaceService | None = None
ENDPOINT_HTTP_SURFACE_SERVICE: EndpointHttpSurfaceService | None = None
ADMIN_HTTP_SURFACE_SERVICE: AdminHttpSurfaceService | None = None
AUTH_HTTP_SURFACE_SERVICE: AuthHttpSurfaceService | None = None
ENDPOINT_LIFECYCLE_SURFACE_SERVICE: EndpointLifecycleSurfaceService | None = None
PUBLIC_SUNSHINE_SURFACE_SERVICE: PublicSunshineSurfaceService | None = None
VM_MUTATION_SURFACE_SERVICE: VmMutationSurfaceService | None = None
VM_STATE_SERVICE: VmStateService | None = None
DOWNLOAD_METADATA_SERVICE: DownloadMetadataService | None = None
RUNTIME_ENVIRONMENT_SERVICE: RuntimeEnvironmentService | None = None
UPDATE_FEED_SERVICE: UpdateFeedService | None = None
FLEET_INVENTORY_SERVICE: FleetInventoryService | None = None
CLUSTER_INVENTORY_SERVICE: ClusterInventoryService | None = None
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
RECORDING_SERVICE: RecordingService | None = None
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
PAIRING_SERVICE: PairingService | None = None


def endpoints_dir() -> Path:
    return runtime_paths_service().endpoints_dir()


def actions_dir() -> Path:
    return runtime_paths_service().actions_dir()


def support_bundles_dir() -> Path:
    return runtime_paths_service().support_bundles_dir()


def recordings_dir() -> Path:
    return runtime_paths_service().ensure_named_dir("recordings")


def policies_dir() -> Path:
    return runtime_paths_service().policies_dir()


def public_stream_service() -> PublicStreamService:
    global PUBLIC_STREAM_SERVICE
    if PUBLIC_STREAM_SERVICE is None:
        PUBLIC_STREAM_SERVICE = PublicStreamService(
            current_public_stream_host=runtime_environment_service().current_public_stream_host,
            data_dir=runtime_paths_service().data_dir,
            get_vm_config=get_vm_config,
            list_vms=lambda: list_vms(),
            load_json_file=load_json_file,
            parse_description_meta=metadata_support_service().parse_description_meta,
            public_stream_base_port=PUBLIC_STREAM_BASE_PORT,
            public_stream_port_count=PUBLIC_STREAM_PORT_COUNT,
            public_stream_port_step=PUBLIC_STREAM_PORT_STEP,
            safe_slug=utility_support_service().safe_slug,
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
            data_dir=runtime_paths_service().data_dir,
            load_json_file=load_json_file,
            write_json_file=write_json_file,
            safe_slug=utility_support_service().safe_slug,
            utcnow=utcnow,
        )
    return VM_SECRET_STORE_SERVICE


def vm_secret_bootstrap_service() -> VmSecretBootstrapService:
    global VM_SECRET_BOOTSTRAP_SERVICE
    if VM_SECRET_BOOTSTRAP_SERVICE is None:
        VM_SECRET_BOOTSTRAP_SERVICE = VmSecretBootstrapService(
            data_dir=runtime_paths_service().data_dir,
            load_vm_secret=load_vm_secret,
            public_server_name=PUBLIC_SERVER_NAME,
            public_stream_host=runtime_environment_service().current_public_stream_host(),
            random_pin=utility_support_service().random_pin,
            random_secret=utility_support_service().random_secret,
            resolve_sunshine_pinned_pubkey=resolve_vm_sunshine_pinned_pubkey,
            safe_slug=utility_support_service().safe_slug,
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
            data_dir=runtime_paths_service().data_dir,
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
            data_dir=runtime_paths_service().data_dir,
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
            parse_description_meta=metadata_support_service().parse_description_meta,
            public_manager_url=PUBLIC_MANAGER_URL,
            run_subprocess=subprocess.run,
            safe_slug=utility_support_service().safe_slug,
            store_sunshine_access_token=sunshine_access_token_store_service().store,
            sunshine_access_token_is_valid=sunshine_access_token_is_valid,
            sunshine_access_token_ttl_seconds=SUNSHINE_ACCESS_TOKEN_TTL_SECONDS,
            ubuntu_beagle_default_guest_user=UBUNTU_BEAGLE_DEFAULT_GUEST_USER,
            utcnow=utcnow,
        )
    return SUNSHINE_INTEGRATION_SERVICE


def pairing_service() -> PairingService:
    global PAIRING_SERVICE
    if PAIRING_SERVICE is None:
        signing_secret = PAIRING_TOKEN_SECRET or API_TOKEN or utility_support_service().random_secret(48)
        PAIRING_SERVICE = PairingService(
            signing_secret=signing_secret,
            token_ttl_seconds=PAIRING_TOKEN_TTL_SECONDS,
            utcnow=utcnow,
        )
    return PAIRING_SERVICE


def endpoint_token_store_service() -> EndpointTokenStoreService:
    global ENDPOINT_TOKEN_STORE_SERVICE
    if ENDPOINT_TOKEN_STORE_SERVICE is None:
        ENDPOINT_TOKEN_STORE_SERVICE = EndpointTokenStoreService(
            data_dir=runtime_paths_service().data_dir,
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
            data_dir=runtime_paths_service().data_dir,
            ensure_vm_secret=ensure_vm_secret,
            guest_exec_out_data=guest_exec_out_data,
            installer_prep_script_file=INSTALLER_PREP_SCRIPT_FILE,
            installer_profile_surface=installer_profile_surface,
            load_json_file=load_json_file,
            public_installer_iso_url=download_metadata_service().public_installer_iso_url,
            root_dir=ROOT_DIR,
            safe_slug=utility_support_service().safe_slug,
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
            data_dir=runtime_paths_service().data_dir,
            load_json_file=load_json_file,
            write_json_file=write_json_file,
            safe_slug=utility_support_service().safe_slug,
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
    configured_manager_url = os.environ.get("PVE_DCV_BEAGLE_MANAGER_URL", "").strip()
    manager_base_url = configured_manager_url
    if not manager_base_url:
        # Use BEAGLE_INTERNAL_CALLBACK_HOST if set — VMs on the internal beagle NAT network
        # need to reach the host via the bridge gateway (e.g. 192.168.123.1), not the
        # external/public host IP used by thin clients.
        callback_host = INTERNAL_CALLBACK_HOST_RAW or current_public_stream_host().strip() or PUBLIC_SERVER_NAME
        manager_base_url = f"https://{callback_host}:{PUBLIC_DOWNLOADS_PORT}/beagle-api"
    return f"{manager_base_url}/api/v1/public/ubuntu-install/{token}/complete"


def summarize_ubuntu_beagle_state(payload: dict[str, Any], *, include_credentials: bool = False) -> dict[str, Any]:
    return ubuntu_beagle_state_service().summarize(payload, include_credentials=include_credentials)


def list_ubuntu_beagle_states(*, include_credentials: bool = False) -> list[dict[str, Any]]:
    return ubuntu_beagle_state_service().list_all(include_credentials=include_credentials)


def latest_ubuntu_beagle_state_for_vmid(vmid: int, *, include_credentials: bool = False) -> dict[str, Any] | None:
    latest = ubuntu_beagle_state_service().latest_for_vmid(vmid, include_credentials=False)
    if not isinstance(latest, dict):
        return None

    status = str(latest.get("status", "")).strip().lower()
    phase = str(latest.get("phase", "")).strip().lower()
    token = str(latest.get("token", "")).strip()

    # Late-command callbacks can occasionally be missed by the installer runtime.
    # If autoinstall has already powered off, or remains stale for too long,
    # move to firstboot server-side so the lifecycle can continue deterministically.
    if status == "installing" and phase == "autoinstall" and token:
        vm = find_vm(int(vmid), refresh=True)
        vm_status = str(getattr(vm, "status", "")).strip().lower() if vm is not None else ""
        updated_at_raw = str(latest.get("updated_at", "")).strip()
        autoinstall_stale = False
        if updated_at_raw:
            try:
                updated_at = datetime.fromisoformat(updated_at_raw.replace("Z", "+00:00"))
                age_seconds = (datetime.now(timezone.utc) - updated_at.astimezone(timezone.utc)).total_seconds()
                autoinstall_stale = age_seconds >= float(max(300, UBUNTU_BEAGLE_AUTOINSTALL_STALE_SECONDS))
            except Exception:
                autoinstall_stale = False
        should_force_firstboot = vm is not None and (
            vm_status not in {"running", "paused", "starting"} or autoinstall_stale
        )
        if should_force_firstboot:
            raw_state = load_ubuntu_beagle_state(token)
            if isinstance(raw_state, dict):
                try:
                    ubuntu_beagle_provisioning_service().prepare_ubuntu_beagle_firstboot(raw_state)
                    if autoinstall_stale:
                        raw_state["message"] = (
                            "Ubuntu-Autoinstall callback blieb aus; der Host hat nach Ablauf des "
                            "Autoinstall-Stale-Timeouts serverseitig in den First-Boot-Modus gewechselt."
                        )
                    save_ubuntu_beagle_state(token, raw_state)
                except Exception:
                    pass

    # If guest callbacks are missing after firstboot has been running for a long
    # time, complete server-side so provisioning does not remain stuck forever.
    if status == "installing" and phase == "firstboot" and token:
        vm = find_vm(int(vmid), refresh=True)
        vm_status = str(getattr(vm, "status", "")).strip().lower() if vm is not None else ""
        updated_at_raw = str(latest.get("updated_at", "")).strip()
        firstboot_stale = False
        if updated_at_raw:
            try:
                updated_at = datetime.fromisoformat(updated_at_raw.replace("Z", "+00:00"))
                age_seconds = (datetime.now(timezone.utc) - updated_at.astimezone(timezone.utc)).total_seconds()
                firstboot_stale = age_seconds >= float(max(60, UBUNTU_BEAGLE_FIRSTBOOT_STALE_SECONDS))
            except Exception:
                firstboot_stale = False
        if vm is not None and vm_status == "running" and firstboot_stale:
            raw_state = load_ubuntu_beagle_state(token)
            raw_status = str((raw_state or {}).get("status", "")).strip().lower()
            raw_phase = str((raw_state or {}).get("phase", "")).strip().lower()
            if isinstance(raw_state, dict) and raw_status == "installing" and raw_phase == "firstboot":
                try:
                    cleanup = ubuntu_beagle_provisioning_service().finalize_ubuntu_beagle_install(raw_state, restart=False)
                    cancelled_restart = cancel_scheduled_ubuntu_beagle_vm_restart(raw_state)
                    raw_state["completed_at"] = utcnow()
                    raw_state["updated_at"] = utcnow()
                    raw_state["status"] = "completed"
                    raw_state["phase"] = "complete"
                    raw_state["message"] = (
                        "Ubuntu firstboot callback blieb aus; Installationsstatus wurde nach Ablauf "
                        "des Stale-Timeouts serverseitig abgeschlossen."
                    )
                    raw_state["cleanup"] = cleanup
                    if cancelled_restart:
                        raw_state["host_restart_cancelled"] = cancelled_restart
                    save_ubuntu_beagle_state(token, raw_state)
                except Exception:
                    pass

    return ubuntu_beagle_state_service().latest_for_vmid(vmid, include_credentials=include_credentials)


def safe_slug(value: str, default: str = "item") -> str:
    return utility_support_service().safe_slug(value, default)


def action_queue_service() -> ActionQueueService:
    global ACTION_QUEUE_SERVICE
    if ACTION_QUEUE_SERVICE is None:
        ACTION_QUEUE_SERVICE = ActionQueueService(
            actions_dir=actions_dir,
            find_vm=lambda vmid: VIRTUALIZATION_INVENTORY.find_vm(vmid),
            load_json_file=load_json_file,
            monotonic=time.monotonic,
            safe_slug=utility_support_service().safe_slug,
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
            safe_slug=utility_support_service().safe_slug,
            support_bundles_dir=support_bundles_dir,
            utcnow=utcnow,
            write_json_file=write_json_file,
        )
    return SUPPORT_BUNDLE_STORE_SERVICE


def recording_service() -> RecordingService:
    global RECORDING_SERVICE
    if RECORDING_SERVICE is None:
        RECORDING_SERVICE = RecordingService(
            load_json_file=load_json_file,
            now_utc=utcnow,
            popen=subprocess.Popen,
            recordings_dir=recordings_dir,
            safe_slug=utility_support_service().safe_slug,
            write_json_file=write_json_file,
        )
    return RECORDING_SERVICE


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
    persistence_support_service().write_json_file(path, payload, mode=mode)


def random_secret(length: int = 24) -> str:
    return utility_support_service().random_secret(length)


def random_pin() -> str:
    return utility_support_service().random_pin()


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


def prepare_virtual_display_on_vm(vm: VmSummary, resolution: str) -> dict[str, Any]:
    return sunshine_integration_service().prepare_virtual_display_on_vm(vm, resolution=resolution)


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


def issue_moonlight_pairing_token(vm: VmSummary, endpoint_identity: dict[str, Any], device_name: str) -> dict[str, Any]:
    pin = random_pin()
    endpoint_id = str(endpoint_identity.get("endpoint_id", "") or "").strip()
    hostname = str(endpoint_identity.get("hostname", "") or "").strip()
    token = pairing_service().issue_token(
        {
            "scope": "moonlight.pair",
            "vmid": int(vm.vmid),
            "node": str(vm.node),
            "endpoint_id": endpoint_id,
            "hostname": hostname,
            "device_name": str(device_name or "").strip(),
            "pairing_pin": pin,
        }
    )
    payload = pairing_service().validate_token(token) or {}
    return {
        "ok": True,
        "token": token,
        "pin": pin,
        "expires_at": str(payload.get("expires_at", "") or ""),
    }


def exchange_moonlight_pairing_token(vm: VmSummary, endpoint_identity: dict[str, Any], pairing_token: str) -> dict[str, Any]:
    payload = pairing_service().validate_token(pairing_token)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid or expired pairing token"}

    if int(payload.get("vmid", -1)) != int(vm.vmid) or str(payload.get("node", "")).strip() != str(vm.node).strip():
        return {"ok": False, "error": "pairing token scope mismatch"}

    scoped_endpoint_id = str(payload.get("endpoint_id", "") or "").strip()
    identity_endpoint_id = str(endpoint_identity.get("endpoint_id", "") or "").strip()
    if scoped_endpoint_id and identity_endpoint_id and scoped_endpoint_id != identity_endpoint_id:
        return {"ok": False, "error": "pairing token endpoint mismatch"}

    pin = str(payload.get("pairing_pin", "") or "").strip()
    if not pin:
        return {"ok": False, "error": "pairing token missing pin"}
    device_name = str(payload.get("device_name", "") or "").strip() or f"beagle-vm{vm.vmid}-client"

    status, _, body = proxy_sunshine_request(
        vm,
        request_path="/api/pin",
        query="",
        method="POST",
        body=json.dumps({"pin": pin, "name": device_name}, separators=(",", ":"), ensure_ascii=True).encode("utf-8"),
        request_headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    if int(status) >= 400:
        return {"ok": False, "error": f"sunshine pin exchange failed with HTTP {int(status)}"}

    try:
        response_payload = json.loads((body or b"{}").decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        response_payload = {}
    if not bool((response_payload or {}).get("status")):
        return {"ok": False, "error": "sunshine pin exchange rejected"}
    return {"ok": True}


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
            safe_slug=utility_support_service().safe_slug,
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
    return metadata_support_service().parse_description_meta(description)


def safe_hostname(name: str, vmid: int) -> str:
    return metadata_support_service().safe_hostname(name, vmid)


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
            get_storage_quota=lambda pool_name: storage_quota_service().get_pool_quota(pool_name),
            get_vm_config=get_vm_config,
            invalidate_vm_cache=invalidate_vm_cache,
            latest_ubuntu_beagle_state_for_vmid=latest_ubuntu_beagle_state_for_vmid,
            list_bridge_inventory=list_bridge_inventory,
            list_nodes_inventory=list_nodes_inventory,
            list_ubuntu_beagle_states=list_ubuntu_beagle_states,
            local_iso_dir=UBUNTU_BEAGLE_LOCAL_ISO_DIR,
            make_vm_summary=lambda **kwargs: VmSummary(**kwargs),
            manager_pinned_pubkey=manager_pinned_pubkey(),
            normalize_keymap=ubuntu_beagle_inputs_service().normalize_keymap,
            normalize_locale=ubuntu_beagle_inputs_service().normalize_locale,
            normalize_package_names=ubuntu_beagle_inputs_service().normalize_package_names,
            normalize_package_presets=ubuntu_beagle_inputs_service().normalize_package_presets,
            provider=HOST_PROVIDER,
            public_ubuntu_beagle_complete_url=public_ubuntu_beagle_complete_url,
            random_pin=utility_support_service().random_pin,
            random_secret=utility_support_service().random_secret,
            reconcile_public_streams_script=ROOT_DIR / "scripts" / "reconcile-public-streams.sh",
            resolve_ubuntu_beagle_desktop=ubuntu_beagle_inputs_service().resolve_ubuntu_beagle_desktop,
            run_checked=run_checked,
            safe_hostname=metadata_support_service().safe_hostname,
            safe_slug=utility_support_service().safe_slug,
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


def delete_provisioned_vm(vmid: int) -> dict[str, Any]:
    vm = find_vm(vmid, refresh=True)
    if vm is None:
        raise ValueError(f"vm not found: {int(vmid)}")
    provider_result = HOST_PROVIDER.delete_vm(int(vmid), timeout=None)
    invalidate_vm_cache(int(vmid), vm.node)
    return {
        "vmid": int(vmid),
        "node": vm.node,
        "name": vm.name,
        "deleted": True,
        "provider_result": str(provider_result or "").strip(),
    }


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


def list_storage_inventory() -> list[dict[str, Any]]:
    return HOST_PROVIDER.list_storage_inventory()


def get_guest_network_interfaces(vmid: int, *, timeout_seconds: float | None = None) -> list[dict[str, Any]]:
    return HOST_PROVIDER.get_guest_network_interfaces(vmid, timeout_seconds=timeout_seconds)


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
            parse_description_meta=metadata_support_service().parse_description_meta,
            public_installer_iso_url=download_metadata_service().public_installer_iso_url,
            public_manager_url=PUBLIC_MANAGER_URL,
            resolve_public_stream_host=resolve_public_stream_host,
            resolve_ubuntu_beagle_desktop=ubuntu_beagle_inputs_service().resolve_ubuntu_beagle_desktop,
            safe_hostname=metadata_support_service().safe_hostname,
            stream_ports=stream_ports,
            truthy=truthy,
            ubuntu_beagle_default_desktop=UBUNTU_BEAGLE_DEFAULT_DESKTOP,
            ubuntu_beagle_default_guest_user=UBUNTU_BEAGLE_DEFAULT_GUEST_USER,
            ubuntu_beagle_default_keymap=UBUNTU_BEAGLE_DEFAULT_KEYMAP,
            ubuntu_beagle_default_locale=UBUNTU_BEAGLE_DEFAULT_LOCALE,
            ubuntu_beagle_software_presets=UBUNTU_BEAGLE_SOFTWARE_PRESETS,
        )
    return VM_PROFILE_SERVICE


def vm_console_access_service() -> VmConsoleAccessService:
    global VM_CONSOLE_ACCESS_SERVICE
    if VM_CONSOLE_ACCESS_SERVICE is None:
        VM_CONSOLE_ACCESS_SERVICE = VmConsoleAccessService(
            host_provider_kind=BEAGLE_HOST_PROVIDER_KIND,
            listify=listify,
            novnc_path=NOVNC_PATH,
            novnc_token_file=NOVNC_TOKEN_FILE,
            public_server_name=PUBLIC_SERVER_NAME,
        )
    return VM_CONSOLE_ACCESS_SERVICE


def vm_http_surface_service() -> VmHttpSurfaceService:
    global VM_HTTP_SURFACE_SERVICE
    if VM_HTTP_SURFACE_SERVICE is None:
        VM_HTTP_SURFACE_SERVICE = VmHttpSurfaceService(
            build_profile=build_profile,
            build_novnc_access=vm_console_access_service().build_novnc_access,
            build_vm_state=build_vm_state,
            build_vm_usb_state=build_vm_usb_state,
            downloads_status_file=DOWNLOADS_STATUS_FILE,
            ensure_vm_secret=ensure_vm_secret,
            find_vm=find_vm,
            list_support_bundle_metadata=list_support_bundle_metadata,
            load_action_queue=load_action_queue,
            load_endpoint_report=load_endpoint_report,
            load_installer_prep_state=load_installer_prep_state,
            load_json_file=load_json_file,
            public_manager_url=PUBLIC_MANAGER_URL,
            public_server_name=PUBLIC_SERVER_NAME,
            render_vm_installer_script=render_vm_installer_script,
            render_vm_live_usb_script=render_vm_live_usb_script,
            render_vm_windows_installer_script=render_vm_windows_installer_script,
            service_name="beagle-control-plane",
            summarize_endpoint_report=summarize_endpoint_report,
            summarize_installer_prep_state=summarize_installer_prep_state,
            usb_tunnel_ssh_user=USB_TUNNEL_SSH_USER,
            utcnow=utcnow,
            version=VERSION,
        )
    return VM_HTTP_SURFACE_SERVICE


def control_plane_read_surface_service() -> ControlPlaneReadSurfaceService:
    global CONTROL_PLANE_READ_SURFACE_SERVICE
    if CONTROL_PLANE_READ_SURFACE_SERVICE is None:
        CONTROL_PLANE_READ_SURFACE_SERVICE = ControlPlaneReadSurfaceService(
            build_provisioning_catalog=build_provisioning_catalog,
            find_support_bundle_metadata=find_support_bundle_metadata,
            latest_ubuntu_beagle_state_for_vmid=latest_ubuntu_beagle_state_for_vmid,
            list_endpoint_reports=list_endpoint_reports,
            list_policies=list_policies,
            load_policy=load_policy,
            service_name="beagle-control-plane",
            summarize_endpoint_report=summarize_endpoint_report,
            utcnow=utcnow,
            version=VERSION,
        )
    return CONTROL_PLANE_READ_SURFACE_SERVICE


def virtualization_read_surface_service() -> VirtualizationReadSurfaceService:
    global VIRTUALIZATION_READ_SURFACE_SERVICE
    if VIRTUALIZATION_READ_SURFACE_SERVICE is None:
        VIRTUALIZATION_READ_SURFACE_SERVICE = VirtualizationReadSurfaceService(
            find_vm=find_vm,
            get_guest_network_interfaces=lambda vmid: get_guest_network_interfaces(vmid, timeout_seconds=GUEST_AGENT_TIMEOUT_SECONDS),
            get_storage_quota=lambda pool_name: storage_quota_service().get_pool_quota(pool_name),
            get_vm_config=get_vm_config,
            host_provider_kind=BEAGLE_HOST_PROVIDER_KIND,
            list_bridges_inventory=lambda node="": HOST_PROVIDER.list_bridges(node),
            list_nodes_inventory=list_nodes_inventory,
            list_storage_inventory=list_storage_inventory,
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )
    return VIRTUALIZATION_READ_SURFACE_SERVICE


def public_http_surface_service() -> PublicHttpSurfaceService:
    global PUBLIC_HTTP_SURFACE_SERVICE
    if PUBLIC_HTTP_SURFACE_SERVICE is None:
        PUBLIC_HTTP_SURFACE_SERVICE = PublicHttpSurfaceService(
            build_profile=build_profile,
            build_update_feed=build_update_feed,
            build_vm_state=build_vm_state,
            find_vm=find_vm,
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )
    return PUBLIC_HTTP_SURFACE_SERVICE


def public_ubuntu_install_surface_service() -> PublicUbuntuInstallSurfaceService:
    global PUBLIC_UBUNTU_INSTALL_SURFACE_SERVICE
    if PUBLIC_UBUNTU_INSTALL_SURFACE_SERVICE is None:
        PUBLIC_UBUNTU_INSTALL_SURFACE_SERVICE = PublicUbuntuInstallSurfaceService(
            cancel_scheduled_ubuntu_beagle_vm_restart=cancel_scheduled_ubuntu_beagle_vm_restart,
            finalize_ubuntu_beagle_install=finalize_ubuntu_beagle_install,
            load_ubuntu_beagle_state=load_ubuntu_beagle_state,
            prepare_ubuntu_beagle_firstboot=prepare_ubuntu_beagle_firstboot,
            save_ubuntu_beagle_state=save_ubuntu_beagle_state,
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )
    return PUBLIC_UBUNTU_INSTALL_SURFACE_SERVICE


def endpoint_http_surface_service() -> EndpointHttpSurfaceService:
    global ENDPOINT_HTTP_SURFACE_SERVICE
    if ENDPOINT_HTTP_SURFACE_SERVICE is None:
        ENDPOINT_HTTP_SURFACE_SERVICE = EndpointHttpSurfaceService(
            dequeue_vm_actions=dequeue_vm_actions,
            exchange_moonlight_pairing_token=exchange_moonlight_pairing_token,
            fetch_sunshine_server_identity=fetch_sunshine_server_identity,
            find_vm=find_vm,
            issue_moonlight_pairing_token=issue_moonlight_pairing_token,
            prepare_virtual_display_on_vm=prepare_virtual_display_on_vm,
            register_moonlight_certificate_on_vm=register_moonlight_certificate_on_vm,
            service_name="beagle-control-plane",
            store_action_result=store_action_result,
            store_support_bundle=store_support_bundle,
            summarize_action_result=summarize_action_result,
            utcnow=utcnow,
            version=VERSION,
        )
    return ENDPOINT_HTTP_SURFACE_SERVICE


def admin_http_surface_service() -> AdminHttpSurfaceService:
    global ADMIN_HTTP_SURFACE_SERVICE
    if ADMIN_HTTP_SURFACE_SERVICE is None:
        ADMIN_HTTP_SURFACE_SERVICE = AdminHttpSurfaceService(
            create_provisioned_vm=create_provisioned_vm,
            create_ubuntu_beagle_vm=create_ubuntu_beagle_vm,
            delete_provisioned_vm=delete_provisioned_vm,
            delete_policy=delete_policy,
            queue_bulk_actions=queue_bulk_actions,
            save_policy=save_policy,
            service_name="beagle-control-plane",
            update_ubuntu_beagle_vm=update_ubuntu_beagle_vm,
            utcnow=utcnow,
            version=VERSION,
        )
    return ADMIN_HTTP_SURFACE_SERVICE


def auth_http_surface_service() -> AuthHttpSurfaceService:
    global AUTH_HTTP_SURFACE_SERVICE
    if AUTH_HTTP_SURFACE_SERVICE is None:
        AUTH_HTTP_SURFACE_SERVICE = AuthHttpSurfaceService(
            auth_session=auth_session_service(),
        )
    return AUTH_HTTP_SURFACE_SERVICE


def endpoint_lifecycle_surface_service() -> EndpointLifecycleSurfaceService:
    global ENDPOINT_LIFECYCLE_SURFACE_SERVICE
    if ENDPOINT_LIFECYCLE_SURFACE_SERVICE is None:
        ENDPOINT_LIFECYCLE_SURFACE_SERVICE = EndpointLifecycleSurfaceService(
            enroll_endpoint=endpoint_enrollment_service().enroll_endpoint,
            service_name="beagle-control-plane",
            store_endpoint_report=endpoint_report_service().store,
            summarize_endpoint_report=summarize_endpoint_report,
            utcnow=utcnow,
            version=VERSION,
        )
    return ENDPOINT_LIFECYCLE_SURFACE_SERVICE


def public_sunshine_surface_service() -> PublicSunshineSurfaceService:
    global PUBLIC_SUNSHINE_SURFACE_SERVICE
    if PUBLIC_SUNSHINE_SURFACE_SERVICE is None:
        PUBLIC_SUNSHINE_SURFACE_SERVICE = PublicSunshineSurfaceService(
            proxy_sunshine_request=proxy_sunshine_request,
            resolve_ticket_vm=sunshine_integration_service().resolve_ticket_vm,
        )
    return PUBLIC_SUNSHINE_SURFACE_SERVICE


def vm_mutation_surface_service() -> VmMutationSurfaceService:
    global VM_MUTATION_SURFACE_SERVICE
    if VM_MUTATION_SURFACE_SERVICE is None:
        VM_MUTATION_SURFACE_SERVICE = VmMutationSurfaceService(
            attach_usb_to_guest=attach_usb_to_guest,
            build_vm_usb_state=build_vm_usb_state,
            find_vm=find_vm,
            invalidate_vm_cache=invalidate_vm_cache,
            issue_sunshine_access_token=issue_sunshine_access_token,
            queue_vm_action=queue_vm_action,
            reboot_vm=lambda vmid: HOST_PROVIDER.reboot_vm(int(vmid), timeout=None),
            service_name="beagle-control-plane",
            start_vm=lambda vmid: HOST_PROVIDER.start_vm(int(vmid), timeout=None),
            start_installer_prep=start_installer_prep,
            stop_vm=lambda vmid: HOST_PROVIDER.stop_vm(int(vmid), skiplock=True, timeout=None),
            summarize_action_result=summarize_action_result,
            sunshine_proxy_ticket_url=sunshine_proxy_ticket_url,
            usb_action_wait_seconds=USB_ACTION_WAIT_SECONDS,
            utcnow=utcnow,
            version=VERSION,
            wait_for_action_result=lambda node, vmid, action_id: wait_for_action_result(
                node,
                vmid,
                action_id,
                timeout_seconds=USB_ACTION_WAIT_SECONDS,
            ),
            detach_usb_from_guest=lambda vm, port, busid: detach_usb_from_guest(vm, port=port, busid=busid),
        )
    return VM_MUTATION_SURFACE_SERVICE


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
            data_dir=runtime_paths_service().data_dir(),
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


def store_endpoint_report(node: str, vmid: int, payload: dict[str, Any]) -> Path:
    return endpoint_report_service().store(node, vmid, payload)


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


def cluster_inventory_service() -> ClusterInventoryService:
    global CLUSTER_INVENTORY_SERVICE
    if CLUSTER_INVENTORY_SERVICE is None:
        CLUSTER_INVENTORY_SERVICE = ClusterInventoryService(
            build_vm_inventory=build_vm_inventory,
            host_provider_kind=BEAGLE_HOST_PROVIDER_KIND,
            list_nodes_inventory=list_nodes_inventory,
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )
    return CLUSTER_INVENTORY_SERVICE


def build_cluster_inventory() -> dict[str, Any]:
    return cluster_inventory_service().build_inventory()


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
            parse_description_meta=metadata_support_service().parse_description_meta,
            patch_installer_defaults=installer_template_patch_service().patch_installer_defaults,
            patch_windows_installer_defaults=installer_template_patch_service().patch_windows_installer_defaults,
            public_bootstrap_latest_download_url=download_metadata_service().public_bootstrap_latest_download_url,
            public_installer_iso_url=download_metadata_service().public_installer_iso_url,
            public_manager_url=PUBLIC_MANAGER_URL,
            public_payload_latest_download_url=download_metadata_service().public_payload_latest_download_url,
            public_server_name=PUBLIC_SERVER_NAME,
            raw_shell_installer_template_file=RAW_SHELL_INSTALLER_TEMPLATE_FILE,
            raw_windows_installer_template_file=RAW_WINDOWS_INSTALLER_TEMPLATE_FILE,
            safe_hostname=metadata_support_service().safe_hostname,
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
    return request_support_service().extract_bearer_token(header_value)


class Handler(BaseHTTPRequestHandler):
    server_version = f"BeagleControlPlane/{VERSION}"
    _rate_limit_state: dict[str, list[float]] = {}
    _login_guard_state: dict[str, dict[str, float]] = {}
    _security_state_lock = None

    @classmethod
    def _state_lock(cls):
        if cls._security_state_lock is None:
            import threading
            cls._security_state_lock = threading.RLock()
        return cls._security_state_lock

    @staticmethod
    def _error_code_for_status(status: int) -> str:
        mapping = {
            int(HTTPStatus.BAD_REQUEST): "bad_request",
            int(HTTPStatus.UNAUTHORIZED): "unauthorized",
            int(HTTPStatus.FORBIDDEN): "forbidden",
            int(HTTPStatus.NOT_FOUND): "not_found",
            int(HTTPStatus.CONFLICT): "conflict",
            int(HTTPStatus.TOO_MANY_REQUESTS): "rate_limited",
            int(HTTPStatus.BAD_GATEWAY): "bad_gateway",
            int(HTTPStatus.INTERNAL_SERVER_ERROR): "internal_error",
        }
        return mapping.get(int(status), "request_error")

    def _client_addr(self) -> str:
        return self.client_address[0] if self.client_address else ""

    def _login_guard_key(self, username: str) -> str:
        return f"{self._client_addr()}::{str(username or '').strip().lower()}"

    def _check_login_guard(self, username: str) -> tuple[bool, int]:
        now_ts = time.time()
        key = self._login_guard_key(username)
        with self._state_lock():
            state = self._login_guard_state.get(key)
            if not isinstance(state, dict):
                return True, 0
            locked_until = float(state.get("locked_until") or 0.0)
            next_allowed = float(state.get("next_allowed") or 0.0)
            if locked_until > now_ts:
                return False, int(max(1, locked_until - now_ts))
            if next_allowed > now_ts:
                return False, int(max(1, next_allowed - now_ts))
        return True, 0

    def _record_login_success(self, username: str) -> None:
        key = self._login_guard_key(username)
        with self._state_lock():
            self._login_guard_state.pop(key, None)

    def _record_login_failure(self, username: str) -> None:
        now_ts = time.time()
        key = self._login_guard_key(username)
        with self._state_lock():
            state = self._login_guard_state.get(key)
            if not isinstance(state, dict):
                state = {"failures": 0.0, "locked_until": 0.0, "next_allowed": 0.0}
            failures = int(float(state.get("failures") or 0.0)) + 1
            backoff_seconds = min(2 ** max(0, failures - 1), AUTH_LOGIN_BACKOFF_MAX_SECONDS)
            state["failures"] = float(failures)
            state["next_allowed"] = now_ts + float(backoff_seconds)
            if failures >= max(1, AUTH_LOGIN_LOCKOUT_THRESHOLD):
                state["locked_until"] = now_ts + float(max(1, AUTH_LOGIN_LOCKOUT_SECONDS))
            self._login_guard_state[key] = state

    def _rate_limit_key(self) -> str:
        return self._client_addr() or "unknown"

    def _enforce_api_rate_limit(self, path: str) -> bool:
        if not str(path or "").startswith("/api/"):
            return True
        now_ts = time.time()
        window = float(max(1, API_RATE_LIMIT_WINDOW_SECONDS))
        max_requests = int(max(1, API_RATE_LIMIT_MAX_REQUESTS))
        key = self._rate_limit_key()
        with self._state_lock():
            entries = self._rate_limit_state.get(key, [])
            entries = [ts for ts in entries if now_ts - ts <= window]
            if len(entries) >= max_requests:
                self._rate_limit_state[key] = entries
                self._write_json(
                    HTTPStatus.TOO_MANY_REQUESTS,
                    {
                        "ok": False,
                        "error": "rate limit exceeded",
                        "code": "rate_limited",
                        "retry_after_seconds": int(window),
                    },
                )
                return False
            entries.append(now_ts)
            self._rate_limit_state[key] = entries
        return True

    def _log_response_event(self, status: int) -> None:
        try:
            path = str(urlparse(getattr(self, "path", "") or "").path)
            action = f"{str(getattr(self, 'command', '')).upper()} {path}"
            resource_type = ""
            resource_id: str | int = ""
            vm_match = re.search(r"/vms/(\d+)", path)
            auth_user_match = re.search(r"/auth/users/([A-Za-z0-9._-]+)", path)
            auth_role_match = re.search(r"/auth/roles/([A-Za-z0-9._:-]+)", path)
            if vm_match is not None:
                resource_type = "vm"
                resource_id = int(vm_match.group(1))
            elif auth_user_match is not None:
                resource_type = "user"
                resource_id = auth_user_match.group(1)
            elif auth_role_match is not None:
                resource_type = "role"
                resource_id = auth_role_match.group(1)
            print(
                json.dumps(
                    {
                        "event": "api.response",
                        "timestamp": utcnow(),
                        "method": str(getattr(self, "command", "")),
                        "path": path,
                        "action": action,
                        "status": int(status),
                        "user": self._requester_identity(),
                        "remote_addr": self._client_addr(),
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                ),
                flush=True,
            )
        except Exception:
            pass

    def _handle_unexpected_error(self, error: Exception) -> None:
        self._audit_event(
            "request.unhandled_exception",
            "error",
            method=str(getattr(self, "command", "")),
            path=str(urlparse(getattr(self, "path", "") or "").path),
            username=self._requester_identity(),
            remote_addr=self._client_addr(),
            error_type=type(error).__name__,
            error_message=str(error),
        )
        try:
            self._write_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "ok": False,
                    "error": "internal server error",
                    "code": "internal_error",
                },
            )
        except Exception:
            pass

    @staticmethod
    def _auth_user_match(path: str) -> re.Match[str] | None:
        return re.match(r"^/api/v1/auth/users/(?P<username>[A-Za-z0-9._-]+)$", path)

    @staticmethod
    def _auth_role_match(path: str) -> re.Match[str] | None:
        return re.match(r"^/api/v1/auth/roles/(?P<name>[A-Za-z0-9._:-]+)$", path)

    @staticmethod
    def _auth_user_revoke_sessions_match(path: str) -> re.Match[str] | None:
        return re.match(r"^/api/v1/auth/users/(?P<username>[A-Za-z0-9._-]+)/revoke-sessions$", path)

    @staticmethod
    def _session_recording_get_match(path: str) -> re.Match[str] | None:
        return re.match(r"^/api/v1/sessions/(?P<session_id>[A-Za-z0-9._:-]+)/recording$", path)

    @staticmethod
    def _session_recording_start_match(path: str) -> re.Match[str] | None:
        return re.match(r"^/api/v1/sessions/(?P<session_id>[A-Za-z0-9._:-]+)/recording/start$", path)

    @staticmethod
    def _session_recording_stop_match(path: str) -> re.Match[str] | None:
        return re.match(r"^/api/v1/sessions/(?P<session_id>[A-Za-z0-9._:-]+)/recording/stop$", path)

    def _audit_auth_surface_response(self, method: str, path: str, response: dict[str, Any]) -> None:
        status = int(response.get("status") or 500)
        outcome = "success" if status < 400 else "error"
        payload = response.get("payload") if isinstance(response.get("payload"), dict) else {}
        if method == "POST" and path == "/api/v1/auth/users":
            created_username = str((payload or {}).get("user", {}).get("username", "")).strip()
            if created_username:
                self._audit_event(
                    "auth.user.create",
                    outcome,
                    username=created_username,
                    requested_by=self._requester_identity(),
                    resource_type="user",
                    resource_id=created_username,
                    remote_addr=self.client_address[0] if self.client_address else "",
                )
            return
        if method == "POST" and path == "/api/v1/auth/roles":
            self._audit_event(
                "auth.role.save",
                outcome,
                role=(payload or {}).get("role", {}).get("name", ""),
                requested_by=self._requester_identity(),
            )
            return
        revoke_match = self._auth_user_revoke_sessions_match(path)
        if method == "POST" and revoke_match is not None:
            self._audit_event(
                "auth.user.revoke_sessions",
                outcome,
                username=str(revoke_match.group("username") or "").strip(),
                revoked_count=(payload or {}).get("revoked_count", 0),
                requested_by=self._requester_identity(),
            )
            return
        user_match = self._auth_user_match(path)
        if method == "PUT" and user_match is not None:
            self._audit_event(
                "auth.user.update",
                outcome,
                username=(payload or {}).get("user", {}).get("username", "") or str(user_match.group("username") or ""),
                requested_by=self._requester_identity(),
            )
            return
        role_match = self._auth_role_match(path)
        if method == "PUT" and role_match is not None:
            self._audit_event(
                "auth.role.update",
                outcome,
                role=(payload or {}).get("role", {}).get("name", "") or str(role_match.group("name") or ""),
                requested_by=self._requester_identity(),
            )
            return
        if method == "DELETE" and user_match is not None:
            self._audit_event(
                "auth.user.delete",
                outcome,
                username=str(user_match.group("username") or ""),
                requested_by=self._requester_identity(),
            )
            return
        if method == "DELETE" and role_match is not None:
            self._audit_event(
                "auth.role.delete",
                outcome,
                role=str(role_match.group("name") or ""),
                requested_by=self._requester_identity(),
            )

    def _audit_event(self, event_type: str, outcome: str, **details: Any) -> None:
        try:
            audit_log_service().write_event(event_type, outcome, details)
        except Exception:
            pass

    def _authorize_or_respond(self, method: str, path: str) -> bool:
        permission = authz_policy_service().required_permission(method, path)
        if permission is None:
            return True
        principal = self._auth_principal()
        if principal is None:
            return False
        role = str(principal.get("role") or "viewer").strip().lower() or "viewer"
        allowed = authz_policy_service().is_allowed(
            role,
            permission,
            auth_session_service().role_permissions(role),
        )
        if allowed:
            return True
        self._audit_event(
            "mutation.authorization",
            "denied",
            method=method,
            path=path,
            permission=permission,
            role=role,
            username=str(principal.get("username") or ""),
            remote_addr=self.client_address[0] if self.client_address else "",
        )
        self._write_json(
            HTTPStatus.FORBIDDEN,
            {
                "ok": False,
                "error": "forbidden",
                "permission": permission,
                "role": role,
            },
        )
        return False

    def _auth_principal(self) -> dict[str, Any] | None:
        cached = getattr(self, "_cached_auth_principal", None)
        if cached is not None:
            return cached
        if ALLOW_LOCALHOST_NOAUTH and self.client_address[0] in {"127.0.0.1", "::1"}:
            principal = {"username": "localhost", "role": "superadmin", "auth_type": "localhost"}
            setattr(self, "_cached_auth_principal", principal)
            return principal
        header = self.headers.get("Authorization", "")
        bearer = header[7:].strip() if header.startswith("Bearer ") else ""
        if bearer:
            session_principal = auth_session_service().resolve_access_token(bearer)
            if session_principal is not None:
                setattr(self, "_cached_auth_principal", session_principal)
                return session_principal
            if API_TOKEN and secrets.compare_digest(bearer, API_TOKEN):
                principal = {"username": "legacy-api-token", "role": "superadmin", "auth_type": "api_token"}
                setattr(self, "_cached_auth_principal", principal)
                return principal
        api_token = self.headers.get("X-Beagle-Api-Token", "").strip()
        if api_token and API_TOKEN and secrets.compare_digest(api_token, API_TOKEN):
            principal = {"username": "legacy-api-token", "role": "superadmin", "auth_type": "api_token"}
            setattr(self, "_cached_auth_principal", principal)
            return principal
        setattr(self, "_cached_auth_principal", None)
        return None

    def _is_authenticated(self) -> bool:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in {"/healthz", "/api/v1/health"}:
            return True
        return self._auth_principal() is not None

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

    def _is_scim_authenticated(self) -> bool:
        if not SCIM_BEARER_TOKEN:
            return False
        token = extract_bearer_token(self.headers.get("Authorization", ""))
        if not token:
            return False
        return secrets.compare_digest(token, SCIM_BEARER_TOKEN)

    def _stream_principal(self, parsed) -> dict[str, Any] | None:
        # EventSource cannot send custom Authorization headers, so accept
        # access_token query parameter for this dedicated stream endpoint.
        query = parse_qs(parsed.query or "")
        candidate = str((query.get("access_token") or query.get("token") or [""])[0] or "").strip()
        if candidate:
            session_principal = auth_session_service().resolve_access_token(candidate)
            if session_principal is not None:
                return session_principal
            if API_TOKEN and secrets.compare_digest(candidate, API_TOKEN):
                return {"username": "legacy-api-token", "role": "superadmin", "auth_type": "api_token"}
        return self._auth_principal()

    def _write_sse_event(self, event_name: str, payload: dict[str, Any]) -> None:
        body = (
            f"event: {str(event_name or 'message')}\n"
            f"data: {json.dumps(payload, ensure_ascii=True, separators=(',', ':'))}\n\n"
        ).encode("utf-8")
        self.wfile.write(body)
        self.wfile.flush()

    def _stream_live_events(self, principal: dict[str, Any]) -> None:
        try:
            self.send_response(HTTPStatus.OK)
            self._write_common_security_headers()
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            self._write_sse_event(
                "hello",
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "user": str((principal or {}).get("username") or ""),
                    "ts": utcnow(),
                },
            )

            # Keep stream bounded so EventSource reconnects and refreshes auth state.
            for _ in range(0, 180):
                time.sleep(5)
                self._write_sse_event(
                    "tick",
                    {
                        "ok": True,
                        "ts": utcnow(),
                        "manager_status": "online",
                    },
                )
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            return

    def _stream_auth_error(self, status: HTTPStatus, code: str = "unauthorized", message: str = "unauthorized") -> None:
        """Return an SSE-framed auth error so EventSource does not fail with MIME mismatch."""
        try:
            self.send_response(status)
            self._write_common_security_headers()
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            self._write_sse_event(
                "error",
                {
                    "ok": False,
                    "error": str(message or "unauthorized"),
                    "code": str(code or "unauthorized"),
                    "ts": utcnow(),
                },
            )
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            return

    def _cors_origin(self) -> str:
        origin = normalized_origin(self.headers.get("Origin", ""))
        if origin and origin in cors_allowed_origins():
            return origin
        return ""

    def _write_common_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; worker-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
        )
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")

    def _deprecation_headers_for_request(self) -> list[tuple[str, str]]:
        path = str(urlparse(getattr(self, "path", "") or "").path or "").rstrip("/") or "/"
        if not path.startswith("/api/v1/"):
            return []
        if path not in API_V1_DEPRECATED_ENDPOINTS:
            return []
        return [
            ("Deprecation", "true"),
            ("Sunset", API_V1_DEPRECATION_SUNSET),
            ("Link", f'<{API_V1_DEPRECATION_DOC_URL}>; rel="deprecation"'),
        ]

    def _write_json(self, status: HTTPStatus, payload: Any, *, extra_headers: list[tuple[str, str]] | None = None) -> None:
        if isinstance(payload, dict) and payload.get("ok") is False and payload.get("error") and not payload.get("code"):
            payload = dict(payload)
            payload["code"] = self._error_code_for_status(int(status))
        body = json.dumps(payload, indent=2).encode("utf-8") + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self._write_common_security_headers()
        merged_headers = list(extra_headers or []) + self._deprecation_headers_for_request()
        for header_name, header_value in merged_headers:
            self.send_header(header_name, header_value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self._log_response_event(int(status))

    def _refresh_cookie_header(self, refresh_token: str) -> tuple[str, str]:
        """Return a Set-Cookie header tuple for the refresh token (HttpOnly, SameSite=Strict)."""
        return (
            "Set-Cookie",
            f"beagle_refresh_token={refresh_token}; HttpOnly; SameSite=Strict; Path=/api/v1/auth; Secure",
        )

    def _clear_refresh_cookie_header(self) -> tuple[str, str]:
        """Return a Set-Cookie header tuple that expires the refresh token cookie."""
        return (
            "Set-Cookie",
            "beagle_refresh_token=; HttpOnly; SameSite=Strict; Path=/api/v1/auth; Secure; Max-Age=0",
        )

    def _read_refresh_cookie(self) -> str:
        """Read the beagle_refresh_token value from the Cookie header, or return empty string."""
        cookie_header = str(self.headers.get("Cookie") or "")
        for part in cookie_header.split(";"):
            name, _, value = part.strip().partition("=")
            if name.strip() == "beagle_refresh_token":
                return value.strip()
        return ""

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > 256 * 1024:
            raise ValueError("invalid content length")
        body = self.rfile.read(length)
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid payload")
        return payload

    @staticmethod
    def _sanitize_identifier(value: Any, *, label: str, pattern: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{label} is required")
        if not re.fullmatch(pattern, text):
            raise ValueError(f"invalid {label}")
        return text

    @staticmethod
    def _validate_payload_whitelist(
        payload: dict[str, Any],
        *,
        required: set[str] | None = None,
        optional: set[str] | None = None,
    ) -> None:
        required_keys = set(required or set())
        optional_keys = set(optional or set())
        allowed = required_keys | optional_keys
        missing = [key for key in sorted(required_keys) if key not in payload]
        if missing:
            raise ValueError(f"missing keys: {', '.join(missing)}")
        extras = [key for key in sorted(payload.keys()) if key not in allowed]
        if extras:
            raise ValueError(f"unexpected keys: {', '.join(extras)}")

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
        for header_name, header_value in self._deprecation_headers_for_request():
            self.send_header(header_name, header_value)
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_redirect(self, location: str, *, status: HTTPStatus = HTTPStatus.FOUND) -> None:
        self.send_response(status)
        self._write_common_security_headers()
        self.send_header("Location", str(location or "/"))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _requester_identity(self) -> str:
        principal = self._auth_principal()
        if principal and principal.get("username"):
            return str(principal.get("username"))
        if self.client_address and self.client_address[0]:
            return self.client_address[0]
        return "unknown"

    def _requester_groups(self) -> list[str]:
        principal = self._auth_principal() or {}
        raw_groups = principal.get("groups", [])
        if isinstance(raw_groups, str):
            raw_groups = [raw_groups]
        groups: list[str] = []
        seen: set[str] = set()
        for item in raw_groups if isinstance(raw_groups, list) else []:
            value = str(item or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            groups.append(value)
        return groups

    def _requester_permissions(self) -> set[str]:
        principal = self._auth_principal()
        if principal is None:
            return set()
        role = str(principal.get("role") or "viewer").strip().lower() or "viewer"
        return auth_session_service().role_permissions(role)

    def _can_bypass_pool_visibility(self) -> bool:
        permissions = self._requester_permissions()
        return "*" in permissions or "pool:write" in permissions

    def _can_view_pool(self, pool_id: str) -> bool:
        if self._can_bypass_pool_visibility():
            return True
        return entitlement_service().can_view_pool(
            pool_id,
            user_id=self._requester_identity(),
            groups=self._requester_groups(),
        )

    def _write_proxy_response(self, status_code: int, headers: dict[str, str], body: bytes) -> None:
        self.send_response(status_code)
        for key, value in headers.items():
            lower = key.lower()
            if lower in {"transfer-encoding", "connection", "content-length", "content-encoding"}:
                continue
            self.send_header(key, value)
        self.send_header("Cache-Control", "no-store")
        self._write_common_security_headers()
        for header_name, header_value in self._deprecation_headers_for_request():
            self.send_header(header_name, header_value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._write_common_security_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Beagle-Api-Token, X-Beagle-Endpoint-Token, X-Beagle-Refresh-Token")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if not self._enforce_api_rate_limit(urlparse(self.path).path.rstrip("/") or "/"):
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query_text = parsed.query

        response = public_sunshine_surface_service().route_request(
            parsed.path,
            query=query_text,
            method="GET",
            body=None,
            request_headers={"Accept": self.headers.get("Accept", "")},
        )
        if response is not None:
            if response["kind"] == "proxy":
                self._write_proxy_response(response["status"], response["headers"], response["body"])
            else:
                self._write_json(response["status"], response["payload"])
            return

        response = public_http_surface_service().route_get(path)
        if response is not None:
            self._write_json(response["status"], response["payload"])
            return

        if path == "/api/v1/endpoints/update-feed":
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            response = public_http_surface_service().endpoint_update_feed(
                query_text=query_text,
                endpoint_identity=self._endpoint_identity(),
            )
            self._write_json(response["status"], response["payload"])
            return

        if path == "/api/v1/auth/me":
            principal = self._auth_principal()
            if principal is None:
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "user": {
                        "username": str(principal.get("username") or ""),
                        "role": str(principal.get("role") or "viewer"),
                        "auth_type": str(principal.get("auth_type") or "session"),
                        "tenant_id": principal.get("tenant_id") or None,
                    },
                },
            )
            return

        if path == "/api/v1/auth/onboarding/status":
            status_payload = auth_session_service().onboarding_status(
                bootstrap_username=AUTH_BOOTSTRAP_USERNAME,
                bootstrap_disabled=AUTH_BOOTSTRAP_DISABLE,
            )
            self._write_json(HTTPStatus.OK, {"ok": True, "onboarding": status_payload})
            return

        if path == "/api/v1/auth/providers":
            try:
                payload = identity_provider_registry_service().payload()
            except Exception:
                payload = {
                    "ok": True,
                    "providers": [
                        {
                            "id": "local",
                            "type": "local",
                            "label": "Lokaler Account",
                            "description": "Benutzername + Passwort (Break-Glass).",
                            "mode": "password",
                            "enabled": True,
                            "login_url": "",
                        }
                    ],
                    "provider_hint": "",
                }
            self._write_json(HTTPStatus.OK, payload)
            return

        if path == "/api/v1/events/stream":
            principal = self._stream_principal(parsed)
            if principal is None:
                self._stream_auth_error(HTTPStatus.UNAUTHORIZED, code="unauthorized", message="unauthorized")
                return
            self._stream_live_events(principal)
            return

        if path == "/api/v1/auth/permission-tags":
            self._write_json(HTTPStatus.OK, {"ok": True, "catalog": PERMISSION_CATALOG})
            return

        if path == "/api/v1/audit/report":
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("GET", path):
                return
            query = parse_qs(parsed.query or "")
            start = str((query.get("start") or [""])[0] or "").strip()
            end = str((query.get("end") or [""])[0] or "").strip()
            tenant_id = str((query.get("tenant") or query.get("tenant_id") or [""])[0] or "").strip()
            action = str((query.get("action") or [""])[0] or "").strip()
            resource_type = str((query.get("resource_type") or [""])[0] or "").strip()
            user_id = str((query.get("user") or query.get("user_id") or [""])[0] or "").strip()
            accept = str(self.headers.get("Accept") or "").lower()
            if "text/csv" in accept:
                body = audit_report_service().build_csv_report(
                    start=start,
                    end=end,
                    tenant_id=tenant_id,
                    action=action,
                    resource_type=resource_type,
                    user_id=user_id,
                )
                self._write_bytes(
                    HTTPStatus.OK,
                    body,
                    content_type="text/csv; charset=utf-8",
                    filename="audit-report.csv",
                )
            else:
                self._write_json(
                    HTTPStatus.OK,
                    audit_report_service().build_json_report(
                        start=start,
                        end=end,
                        tenant_id=tenant_id,
                        action=action,
                        resource_type=resource_type,
                        user_id=user_id,
                    ),
                )
            self._audit_event(
                "audit.report.download",
                "success",
                requested_by=self._requester_identity(),
                resource_type="audit-report",
                resource_id="audit-report",
                start=start,
                end=end,
                tenant_id=tenant_id,
                action_filter=action,
                resource_filter=resource_type,
                user_filter=user_id,
                accept=accept,
            )
            return

        if scim_service().handles_path(path):
            if not SCIM_BEARER_TOKEN:
                self._write_json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": "scim disabled"})
                return
            if not self._is_scim_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            response = scim_service().route_get(path)
            self._write_json(response["status"], response["payload"])
            return

        if path == "/api/v1/auth/oidc/login":
            try:
                login_url = oidc_service().begin_login()
            except RuntimeError as exc:
                self._write_json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": str(exc)})
                return
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"oidc unavailable: {exc}"})
                return
            self._write_redirect(login_url)
            return

        if path == "/api/v1/auth/oidc/callback":
            query = parse_qs(parsed.query or "")
            code = str((query.get("code") or [""])[0] or "").strip()
            state = str((query.get("state") or [""])[0] or "").strip()
            if not code or not state:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "missing code/state"})
                return
            try:
                payload = oidc_service().finish_login(code=code, state=state)
            except PermissionError as exc:
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": str(exc)})
                return
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"oidc callback failed: {exc}"})
                return
            self._write_json(HTTPStatus.OK, payload)
            return

        if path == "/api/v1/auth/saml/login":
            query = parse_qs(parsed.query or "")
            relay_state = str((query.get("relay") or [""])[0] or "").strip()
            try:
                login_url = saml_service().begin_login(relay_state=relay_state)
            except RuntimeError as exc:
                self._write_json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": str(exc)})
                return
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"saml unavailable: {exc}"})
                return
            self._write_redirect(login_url)
            return

        if path == "/api/v1/auth/saml/metadata":
            xml = saml_service().metadata_xml().encode("utf-8")
            self._write_bytes(
                HTTPStatus.OK,
                xml,
                content_type="application/samlmetadata+xml; charset=utf-8",
                filename="beagle-sp-metadata.xml",
            )
            return

        if API_V2_PREPARATION_ENABLED and path in {"/api/v2", "/api/v2/health"}:
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "api": {
                        "current": "v1",
                        "next": "v2",
                        "status": "preparation",
                        "deprecated_v1_endpoints": sorted(API_V1_DEPRECATED_ENDPOINTS),
                        "deprecation_doc": API_V1_DEPRECATION_DOC_URL,
                        "sunset": API_V1_DEPRECATION_SUNSET,
                    },
                },
            )
            return

        if auth_http_surface_service().handles_get(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("GET", path):
                return
            principal = self._auth_principal()
            requester_tenant = (principal or {}).get("tenant_id") or None
            response = auth_http_surface_service().route_get(
                path, requester_tenant_id=requester_tenant
            )
            self._write_json(response["status"], response["payload"])
            return

        recording_get_match = self._session_recording_get_match(path)
        if recording_get_match is not None:
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("GET", path):
                return
            session_id = str(recording_get_match.group("session_id") or "").strip()
            file_payload = recording_service().read_recording_bytes(session_id=session_id)
            if file_payload is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "recording not found"})
                return
            body, filename = file_payload
            self._audit_event(
                "session.recording.download",
                "success",
                session_id=session_id,
                downloader=self._requester_identity(),
                remote_addr=self.client_address[0] if self.client_address else "",
            )
            self._write_bytes(HTTPStatus.OK, body, content_type="video/mp4", filename=filename)
            return

        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return

        storage_quota_match = re.match(r"^/api/v1/storage/pools/(?P<pool>[A-Za-z0-9._-]+)/quota$", path)
        if storage_quota_match is not None:
            if not self._authorize_or_respond("GET", path):
                return
            pool_name = str(storage_quota_match.group("pool") or "").strip()
            try:
                payload = storage_quota_service().get_pool_quota(pool_name)
            except ValueError as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._write_json(HTTPStatus.OK, {"ok": True, **payload})
            return

        # --- VDI Pool & Template GET routes ---
        if path == "/api/v1/pools":
            if not self._authorize_or_respond("GET", path):
                return
            pools = [pool for pool in pool_manager_service().list_pools() if self._can_view_pool(pool.pool_id)]
            self._write_json(HTTPStatus.OK, {
                "ok": True,
                "pools": [pool_manager_service().pool_info_to_dict(p) for p in pools],
            })
            return

        pool_match = re.match(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)$", path)
        if pool_match is not None:
            if not self._authorize_or_respond("GET", path):
                return
            pool_id = pool_match.group("pool_id")
            if not self._can_view_pool(pool_id):
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "pool not found"})
                return
            pool_info = pool_manager_service().get_pool(pool_id)
            if pool_info is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "pool not found"})
                return
            self._write_json(HTTPStatus.OK, {"ok": True, **pool_manager_service().pool_info_to_dict(pool_info)})
            return

        pool_vms_match = re.match(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)/vms$", path)
        if pool_vms_match is not None:
            if not self._authorize_or_respond("GET", path):
                return
            pool_id = pool_vms_match.group("pool_id")
            if not self._can_view_pool(pool_id):
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "pool not found"})
                return
            try:
                desktops = pool_manager_service().list_desktops(pool_id)
            except ValueError as exc:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": str(exc)})
                return
            self._write_json(HTTPStatus.OK, {"ok": True, "vms": desktops})
            return

        pool_entitlements_get_match = re.match(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)/entitlements$", path)
        if pool_entitlements_get_match is not None:
            if not self._authorize_or_respond("GET", path):
                return
            pool_id = pool_entitlements_get_match.group("pool_id")
            if not self._can_view_pool(pool_id):
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "pool not found"})
                return
            try:
                result = entitlement_service().get_entitlements(pool_id)
            except ValueError as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._write_json(HTTPStatus.OK, {"ok": True, **result})
            return

        if path == "/api/v1/pool-templates":
            if not self._authorize_or_respond("GET", path):
                return
            templates = desktop_template_builder_service().list_templates()
            self._write_json(HTTPStatus.OK, {
                "ok": True,
                "templates": [desktop_template_builder_service().template_info_to_dict(t) for t in templates],
            })
            return

        pool_template_match = re.match(r"^/api/v1/pool-templates/(?P<tid>[A-Za-z0-9._-]+)$", path)
        if pool_template_match is not None:
            if not self._authorize_or_respond("GET", path):
                return
            tid = pool_template_match.group("tid")
            tmpl = desktop_template_builder_service().get_template(tid)
            if tmpl is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "template not found"})
                return
            self._write_json(HTTPStatus.OK, {"ok": True, **desktop_template_builder_service().template_info_to_dict(tmpl)})
            return

        if path == "/healthz":
            self._write_json(HTTPStatus.OK, {"ok": True, "service": "beagle-control-plane", "version": VERSION})
            return
        response = control_plane_read_surface_service().route_get(path)
        if response is not None:
            if response["kind"] == "bytes":
                self._write_bytes(
                    response["status"],
                    response["body"],
                    content_type=response["content_type"],
                    filename=response["filename"],
                )
            else:
                self._write_json(response["status"], response["payload"])
            return
        response = virtualization_read_surface_service().route_get(path)
        if response is not None:
            self._write_json(response["status"], response["payload"])
            return
        if path == "/api/v1/health":
            self._write_json(HTTPStatus.OK, build_health_payload())
            return
        if path == "/api/v1/vms":
            self._write_json(HTTPStatus.OK, build_vm_inventory())
            return
        if path == "/api/v1/cluster/inventory" or path == "/api/v1/cluster/nodes":
            self._write_json(HTTPStatus.OK, build_cluster_inventory())
            return
        if path.startswith("/api/v1/vms/"):
            response = vm_http_surface_service().route_get(path)
            if response["kind"] == "bytes":
                self._write_bytes(
                    response["status"],
                    response["body"],
                    content_type=response["content_type"],
                    filename=response["filename"],
                )
            else:
                self._write_json(response["status"], response["payload"])
            return

        if path.startswith("/api/v1/settings/"):
            if not self._authorize_or_respond("GET", path):
                return
            response = server_settings_service().route_get(path)
            if response is not None:
                self._write_json(response["status"], response["payload"])
                return

        self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._enforce_api_rate_limit(urlparse(self.path).path.rstrip("/") or "/"):
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query or "")

        if path == "/api/v1/auth/login":
            try:
                payload = self._read_json_body()
                self._validate_payload_whitelist(payload, required={"username", "password"})
                username = self._sanitize_identifier(payload.get("username"), label="username", pattern=r"^[A-Za-z0-9._-]{1,64}$")
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            password = str(payload.get("password") or "")
            if not password:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "username and password are required"})
                return
            allowed, wait_seconds = self._check_login_guard(username)
            if not allowed:
                self._write_json(
                    HTTPStatus.TOO_MANY_REQUESTS,
                    {
                        "ok": False,
                        "error": "login temporarily blocked",
                        "code": "rate_limited",
                        "retry_after_seconds": int(max(1, wait_seconds)),
                    },
                )
                return
            session_payload = auth_session_service().login(
                username=username,
                password=password,
                remote_addr=self.client_address[0] if self.client_address else "",
                user_agent=str(self.headers.get("User-Agent") or "")[:256],
            )
            if session_payload is None:
                self._record_login_failure(username)
                self._audit_event(
                    "auth.login",
                    "denied",
                    username=username,
                    remote_addr=self.client_address[0] if self.client_address else "",
                )
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "invalid credentials"})
                return
            self._record_login_success(username)
            self._audit_event(
                "auth.login",
                "success",
                username=str(session_payload.get("user", {}).get("username") or username),
                remote_addr=self.client_address[0] if self.client_address else "",
            )
            self._write_json(
                HTTPStatus.OK,
                session_payload,
                extra_headers=[self._refresh_cookie_header(str(session_payload.get("refresh_token") or ""))],
            )
            return

        if path == "/api/v1/auth/refresh":
            try:
                payload = self._read_json_body()
                self._validate_payload_whitelist(payload, optional={"refresh_token"})
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            refresh_token = str(
                payload.get("refresh_token")
                or self._read_refresh_cookie()
                or self.headers.get("X-Beagle-Refresh-Token")
                or ""
            ).strip()
            if not refresh_token:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "refresh token missing"})
                return
            session_payload = auth_session_service().refresh(refresh_token)
            if session_payload is None:
                self._audit_event("auth.refresh", "denied", remote_addr=self.client_address[0] if self.client_address else "")
                self._write_json(
                    HTTPStatus.UNAUTHORIZED,
                    {"ok": False, "error": "invalid refresh token"},
                    extra_headers=[self._clear_refresh_cookie_header()],
                )
                return
            self._audit_event(
                "auth.refresh",
                "success",
                username=str(session_payload.get("user", {}).get("username") or ""),
                remote_addr=self.client_address[0] if self.client_address else "",
            )
            self._write_json(
                HTTPStatus.OK,
                session_payload,
                extra_headers=[self._refresh_cookie_header(str(session_payload.get("refresh_token") or ""))],
            )
            return

        if path == "/api/v1/auth/logout":
            refresh_token = ""
            if int(self.headers.get("Content-Length", "0") or "0") > 0:
                try:
                    payload = self._read_json_body()
                    self._validate_payload_whitelist(payload, optional={"refresh_token"})
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
                refresh_token = str(payload.get("refresh_token") or "").strip()
            # Also accept the refresh token from the HttpOnly cookie
            if not refresh_token:
                refresh_token = self._read_refresh_cookie()
            revoked = auth_session_service().revoke(
                access_token=extract_bearer_token(self.headers.get("Authorization", "")),
                refresh_token=refresh_token,
            )
            self._audit_event(
                "auth.logout",
                "success" if revoked else "noop",
                username=self._requester_identity(),
                remote_addr=self.client_address[0] if self.client_address else "",
            )
            self._write_json(
                HTTPStatus.OK,
                {"ok": True, "revoked": bool(revoked)},
                extra_headers=[self._clear_refresh_cookie_header()],
            )
            return

        if path == "/api/v1/auth/onboarding/complete":
            try:
                payload = self._read_json_body()
                self._validate_payload_whitelist(payload, required={"username", "password", "password_confirm"})
                username = self._sanitize_identifier(payload.get("username"), label="username", pattern=r"^[A-Za-z0-9._-]{1,64}$")
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            password = str(payload.get("password") or "")
            password_confirm = str(payload.get("password_confirm") or "")
            if not password:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "username and password are required"})
                return
            if password != password_confirm:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "password confirmation mismatch"})
                return
            try:
                onboarding_state = auth_session_service().complete_onboarding(
                    username=username,
                    password=password,
                    bootstrap_username=AUTH_BOOTSTRAP_USERNAME,
                    bootstrap_disabled=AUTH_BOOTSTRAP_DISABLE,
                )
            except Exception as exc:
                message = str(exc)
                status_code = HTTPStatus.CONFLICT if message == "onboarding already completed" else HTTPStatus.BAD_REQUEST
                self._write_json(status_code, {"ok": False, "error": message})
                return
            self._audit_event(
                "auth.onboarding.complete",
                "success",
                username=username,
                remote_addr=self.client_address[0] if self.client_address else "",
            )
            self._write_json(HTTPStatus.OK, {"ok": True, "onboarding": onboarding_state})
            return

        if scim_service().handles_path(path):
            if not SCIM_BEARER_TOKEN:
                self._write_json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": "scim disabled"})
                return
            if not self._is_scim_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = scim_service().route_post(path, json_payload)
            self._write_json(response["status"], response["payload"])
            return

        if auth_http_surface_service().handles_post(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            json_payload: dict[str, Any] | None = None
            if auth_http_surface_service().requires_json_body(path):
                try:
                    json_payload = self._read_json_body()
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
            principal = self._auth_principal()
            requester_tenant = (principal or {}).get("tenant_id") or None
            response = auth_http_surface_service().route_post(
                path, json_payload=json_payload, requester_tenant_id=requester_tenant
            )
            self._audit_auth_surface_response("POST", path, response)
            self._write_json(response["status"], response["payload"])
            return

        recording_start_match = self._session_recording_start_match(path)
        if recording_start_match is not None:
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            try:
                payload = self._read_json_body() if int(self.headers.get("Content-Length", "0") or "0") > 0 else {}
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            session_id = str(recording_start_match.group("session_id") or "").strip()
            response = recording_service().start_recording(
                session_id=session_id,
                input_url=str(payload.get("input_url") or "").strip(),
                codec=str(payload.get("codec") or "h264").strip(),
                test_source=bool(payload.get("test_source", False)),
            )
            self._audit_event(
                "session.recording.start",
                "success",
                session_id=session_id,
                requested_by=self._requester_identity(),
                remote_addr=self.client_address[0] if self.client_address else "",
            )
            self._write_json(HTTPStatus.OK, response)
            return

        recording_stop_match = self._session_recording_stop_match(path)
        if recording_stop_match is not None:
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            session_id = str(recording_stop_match.group("session_id") or "").strip()
            response = recording_service().stop_recording(session_id=session_id)
            if not bool(response.get("ok")):
                self._write_json(HTTPStatus.NOT_FOUND, response)
                return
            self._audit_event(
                "session.recording.stop",
                "success",
                session_id=session_id,
                requested_by=self._requester_identity(),
                remote_addr=self.client_address[0] if self.client_address else "",
            )
            self._write_json(HTTPStatus.OK, response)
            return

        sunshine_body: bytes | None = None
        if path.startswith("/api/v1/public/sunshine/"):
            try:
                sunshine_body = self._read_binary_body(max_bytes=16 * 1024 * 1024)
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid content length: {exc}"})
                return
            response = public_sunshine_surface_service().route_request(
                parsed.path,
                query=parsed.query,
                method="POST",
                body=sunshine_body,
                request_headers={
                    "Content-Type": self.headers.get("Content-Type", ""),
                    "Accept": self.headers.get("Accept", ""),
                },
            )
            if response is not None:
                if response["kind"] == "proxy":
                    self._write_proxy_response(response["status"], response["headers"], response["body"])
                else:
                    self._write_json(response["status"], response["payload"])
                return
            return

        public_install_payload: dict[str, Any] | None = None
        if path.endswith("/failed") and int(self.headers.get("Content-Length", "0") or "0") > 0:
            try:
                public_install_payload = self._read_json_body()
            except Exception:
                public_install_payload = {}
        response = public_ubuntu_install_surface_service().route_post(
            path,
            query=query,
            payload=public_install_payload,
        )
        if response is not None:
            self._write_json(response["status"], response["payload"])
            return

        if endpoint_http_surface_service().handles_path(path):
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            json_payload: dict[str, Any] | None = None
            binary_payload: bytes | None = None
            if endpoint_http_surface_service().requires_json_body(path):
                try:
                    json_payload = self._read_json_body()
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
            if endpoint_http_surface_service().requires_binary_body(path):
                try:
                    binary_payload = self._read_binary_body(max_bytes=128 * 1024 * 1024)
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid upload: {exc}"})
                    return
            response = endpoint_http_surface_service().route_post(
                path,
                endpoint_identity=self._endpoint_identity(),
                query=query,
                json_payload=json_payload,
                binary_payload=binary_payload,
            )
            self._write_json(response["status"], response["payload"])
            return

        if endpoint_lifecycle_surface_service().handles_post(path):
            if endpoint_lifecycle_surface_service().requires_endpoint_auth(path) and not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = endpoint_lifecycle_surface_service().route_post(
                path,
                endpoint_identity=self._endpoint_identity(),
                json_payload=json_payload,
                remote_addr=self.client_address[0],
            )
            self._audit_event(
                "endpoint.lifecycle",
                "success" if int(response["status"]) < 400 else "error",
                method="POST",
                path=path,
                status=int(response["status"]),
            )
            self._write_json(response["status"], response["payload"])
            return

        if vm_mutation_surface_service().handles_path(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            json_payload: dict[str, Any] | None = None
            if vm_mutation_surface_service().requires_json_body(path):
                try:
                    json_payload = self._read_json_body()
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
            elif vm_mutation_surface_service().accepts_optional_json_body(path) and int(self.headers.get("Content-Length", "0") or "0") > 0:
                try:
                    json_payload = self._read_json_body()
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
            response = vm_mutation_surface_service().route_post(
                path,
                json_payload=json_payload,
                requester_identity=self._requester_identity(),
            )
            self._audit_event(
                "mutation.request",
                "success" if int(response["status"]) < 400 else "error",
                method="POST",
                path=path,
                permission=authz_policy_service().required_permission("POST", path),
                username=self._requester_identity(),
                status=int(response["status"]),
            )
            vm_power_event = build_vm_power_audit_event(response, requester_identity=self._requester_identity())
            if isinstance(vm_power_event, dict):
                self._audit_event(
                    str(vm_power_event.get("event_type") or "vm.unknown"),
                    str(vm_power_event.get("outcome") or "unknown"),
                    **(vm_power_event.get("details") if isinstance(vm_power_event.get("details"), dict) else {}),
                )
                if str(vm_power_event.get("outcome") or "") == "success":
                    event_type = str(vm_power_event.get("event_type") or "")
                    event_details = vm_power_event.get("details") if isinstance(vm_power_event.get("details"), dict) else {}
                    try:
                        webhook_service().dispatch_event(
                            event_type=event_type,
                            event_payload={
                                "vm": event_details,
                                "requested_by": self._requester_identity(),
                            },
                        )
                    except Exception:
                        pass
            self._write_json(response["status"], response["payload"])
            return

        # --- VDI Pool & Template POST routes ---
        if path == "/api/v1/pools":
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            try:
                body = self._read_json_body() or {}
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            from core.virtualization.desktop_pool import DesktopPoolMode, DesktopPoolSpec
            try:
                mode = DesktopPoolMode(str(body.get("mode", "floating_non_persistent")))
                spec = DesktopPoolSpec(
                    pool_id=str(body.get("pool_id", "") or "").strip(),
                    template_id=str(body.get("template_id", "") or ""),
                    mode=mode,
                    min_pool_size=int(body.get("min_pool_size", 0)),
                    max_pool_size=int(body.get("max_pool_size", 10)),
                    warm_pool_size=int(body.get("warm_pool_size", 2)),
                    cpu_cores=int(body.get("cpu_cores", 2)),
                    memory_mib=int(body.get("memory_mib", 2048)),
                    storage_pool=str(body.get("storage_pool", "local") or "local"),
                    enabled=bool(body.get("enabled", True)),
                    labels=tuple(str(l) for l in body.get("labels", [])),
                )
                pool_info = pool_manager_service().create_pool(spec)
            except (ValueError, TypeError) as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._audit_event("pool.create", "success", pool_id=pool_info.pool_id, username=self._requester_identity())
            self._write_json(HTTPStatus.CREATED, {"ok": True, **pool_manager_service().pool_info_to_dict(pool_info)})
            return

        pool_entitlements_post_match = re.match(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)/entitlements$", path)
        if pool_entitlements_post_match is not None:
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            pool_id = pool_entitlements_post_match.group("pool_id")
            try:
                body = self._read_json_body() or {}
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            action = str(body.get("action", "set")).strip().lower()
            try:
                if action == "add":
                    result = entitlement_service().add_entitlement(
                        pool_id,
                        user_id=str(body.get("user_id", "") or ""),
                        group_id=str(body.get("group_id", "") or ""),
                    )
                elif action == "remove":
                    result = entitlement_service().remove_entitlement(
                        pool_id,
                        user_id=str(body.get("user_id", "") or ""),
                        group_id=str(body.get("group_id", "") or ""),
                    )
                else:
                    result = entitlement_service().set_entitlements(
                        pool_id,
                        users=body.get("users"),
                        groups=body.get("groups"),
                    )
            except ValueError as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._audit_event("pool.entitlement.update", "success", pool_id=pool_id, action=action, username=self._requester_identity())
            self._write_json(HTTPStatus.OK, {"ok": True, **result})
            return

        pool_vm_register_match = re.match(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)/vms$", path)
        if pool_vm_register_match is not None:
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            pool_id = pool_vm_register_match.group("pool_id")
            try:
                body = self._read_json_body() or {}
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            try:
                vmid = int(body.get("vmid") or 0)
                if not vmid:
                    raise ValueError("vmid is required")
                result = pool_manager_service().register_vm(pool_id, vmid)
            except (ValueError, TypeError) as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._audit_event("pool.vm.register", "success", pool_id=pool_id, vmid=vmid, username=self._requester_identity())
            self._write_json(HTTPStatus.CREATED, {"ok": True, **result})
            return

        pool_allocate_match = re.match(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)/allocate$", path)
        if pool_allocate_match is not None:
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            pool_id = pool_allocate_match.group("pool_id")
            try:
                body = self._read_json_body() or {}
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            user_id = str(body.get("user_id", "") or "").strip() or self._requester_identity()
            try:
                # Check entitlement
                if not entitlement_service().is_entitled(pool_id, user_id=user_id):
                    self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "not entitled to this pool"})
                    return
                lease = pool_manager_service().allocate_desktop(pool_id, user_id)
            except (ValueError, RuntimeError) as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._audit_event("pool.desktop.allocate", "success", pool_id=pool_id, user_id=user_id, vmid=lease.vmid, username=self._requester_identity())
            self._write_json(HTTPStatus.OK, {"ok": True, **pool_manager_service().lease_to_dict(lease)})
            return

        pool_release_match = re.match(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)/release$", path)
        if pool_release_match is not None:
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            pool_id = pool_release_match.group("pool_id")
            try:
                body = self._read_json_body() or {}
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            try:
                vmid = int(body.get("vmid") or 0)
                user_id = str(body.get("user_id", "") or "").strip() or self._requester_identity()
                lease = pool_manager_service().release_desktop(pool_id, vmid, user_id)
            except (ValueError, RuntimeError) as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._audit_event("pool.desktop.release", "success", pool_id=pool_id, vmid=vmid, username=self._requester_identity())
            self._write_json(HTTPStatus.OK, {"ok": True, **pool_manager_service().lease_to_dict(lease)})
            return

        pool_recycle_match = re.match(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)/recycle$", path)
        if pool_recycle_match is not None:
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            pool_id = pool_recycle_match.group("pool_id")
            try:
                body = self._read_json_body() or {}
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            try:
                vmid = int(body.get("vmid") or 0)
                lease = pool_manager_service().recycle_desktop(pool_id, vmid)
            except (ValueError, RuntimeError) as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._audit_event("pool.desktop.recycle", "success", pool_id=pool_id, vmid=vmid, username=self._requester_identity())
            self._write_json(HTTPStatus.OK, {"ok": True, **pool_manager_service().lease_to_dict(lease)})
            return

        pool_scale_match = re.match(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)/scale$", path)
        if pool_scale_match is not None:
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            pool_id = pool_scale_match.group("pool_id")
            try:
                body = self._read_json_body() or {}
                target_size = int(body.get("target_size") or 0)
                pool_info = pool_manager_service().scale_pool(pool_id, target_size)
            except (ValueError, TypeError) as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._audit_event("pool.scale", "success", pool_id=pool_id, target_size=target_size, username=self._requester_identity())
            self._write_json(HTTPStatus.OK, {"ok": True, **pool_manager_service().pool_info_to_dict(pool_info)})
            return

        if path == "/api/v1/pool-templates":
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            try:
                body = self._read_json_body() or {}
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            from core.virtualization.desktop_template import DesktopTemplateBuildSpec
            try:
                spec = DesktopTemplateBuildSpec(
                    template_id=str(body.get("template_id", "") or "").strip(),
                    source_vmid=int(body.get("source_vmid") or 0),
                    template_name=str(body.get("template_name", "") or "").strip(),
                    os_family=str(body.get("os_family", "linux") or "linux"),
                    storage_pool=str(body.get("storage_pool", "local") or "local"),
                    snapshot_name=str(body.get("snapshot_name", "sealed") or "sealed"),
                    backing_image=str(body.get("backing_image", "") or ""),
                    cpu_cores=int(body.get("cpu_cores", 2)),
                    memory_mib=int(body.get("memory_mib", 2048)),
                    software_packages=tuple(str(p) for p in body.get("software_packages", [])),
                    notes=str(body.get("notes", "") or ""),
                )
                tmpl_info = desktop_template_builder_service().build_template(spec)
            except (ValueError, RuntimeError, TypeError) as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._audit_event("pool_template.create", "success", template_id=tmpl_info.template_id, username=self._requester_identity())
            self._write_json(HTTPStatus.CREATED, {"ok": True, **desktop_template_builder_service().template_info_to_dict(tmpl_info)})
            return

        admin_post_path = "/api/v1/provisioning/vms" if path == "/api/v1/vms" else path
        if admin_http_surface_service().handles_post(admin_post_path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", admin_post_path):
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                response = admin_http_surface_service().read_error_response("POST", admin_post_path, exc)
                self._write_json(response["status"], response["payload"])
                return
            response = admin_http_surface_service().route_post(
                admin_post_path,
                json_payload=json_payload,
                requester_identity=self._requester_identity(),
            )
            self._audit_event(
                "mutation.request",
                "success" if int(response["status"]) < 400 else "error",
                method="POST",
                path=path,
                effective_path=admin_post_path,
                permission=authz_policy_service().required_permission("POST", admin_post_path),
                username=self._requester_identity(),
                status=int(response["status"]),
            )
            self._write_json(response["status"], response["payload"])
            return

        if path.startswith("/api/v1/settings/"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = server_settings_service().route_post(path, json_payload or {})
            if response is not None:
                self._audit_event(
                    "settings.mutation",
                    "success" if int(response["status"]) < 400 else "error",
                    method="POST",
                    path=path,
                    username=self._requester_identity(),
                )
                self._write_json(response["status"], response["payload"])
                return

        self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_PUT(self) -> None:  # noqa: N802
        if not self._enforce_api_rate_limit(urlparse(self.path).path.rstrip("/") or "/"):
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if scim_service().handles_path(path):
            if not SCIM_BEARER_TOKEN:
                self._write_json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": "scim disabled"})
                return
            if not self._is_scim_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = scim_service().route_put(path, payload)
            self._write_json(response["status"], response["payload"])
            return

        if auth_http_surface_service().handles_put(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("PUT", path):
                return
            try:
                payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            principal = self._auth_principal()
            requester_tenant = (principal or {}).get("tenant_id") or None
            response = auth_http_surface_service().route_put(
                path, json_payload=payload, requester_tenant_id=requester_tenant
            )
            self._audit_auth_surface_response("PUT", path, response)
            self._write_json(response["status"], response["payload"])
            return

        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        if not self._authorize_or_respond("PUT", path):
            return

        storage_quota_match = re.match(r"^/api/v1/storage/pools/(?P<pool>[A-Za-z0-9._-]+)/quota$", path)
        if storage_quota_match is not None:
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            pool_name = str(storage_quota_match.group("pool") or "").strip()
            quota_bytes = int((json_payload or {}).get("quota_bytes", 0) or 0)
            try:
                payload = storage_quota_service().set_pool_quota(pool_name, quota_bytes)
            except ValueError as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._audit_event(
                "storage.quota.update",
                "success",
                pool=pool_name,
                quota_bytes=quota_bytes,
                username=self._requester_identity(),
            )
            self._write_json(HTTPStatus.OK, {"ok": True, **payload})
            return

        pool_match = re.match(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)$", path)
        if pool_match is not None:
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            pool_id = str(pool_match.group("pool_id") or "").strip()
            try:
                payload = pool_manager_service().update_pool(pool_id, json_payload or {})
            except ValueError as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._audit_event(
                "pool.update",
                "success",
                pool_id=pool_id,
                username=self._requester_identity(),
            )
            self._write_json(HTTPStatus.OK, {"ok": True, **pool_manager_service().pool_info_to_dict(payload)})
            return

        if path.startswith("/api/v1/settings/"):
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = server_settings_service().route_put(path, json_payload or {})
            if response is not None:
                self._audit_event(
                    "settings.mutation",
                    "success" if int(response["status"]) < 400 else "error",
                    method="PUT",
                    path=path,
                    username=self._requester_identity(),
                )
                self._write_json(response["status"], response["payload"])
                return

        if not admin_http_surface_service().handles_put(path):
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        try:
            json_payload = self._read_json_body()
        except Exception as exc:
            response = admin_http_surface_service().read_error_response("PUT", path, exc)
            self._write_json(response["status"], response["payload"])
            return
        response = admin_http_surface_service().route_put(path, json_payload=json_payload)
        self._audit_event(
            "mutation.request",
            "success" if int(response["status"]) < 400 else "error",
            method="PUT",
            path=path,
            permission=authz_policy_service().required_permission("PUT", path),
            username=self._requester_identity(),
            status=int(response["status"]),
        )
        self._write_json(response["status"], response["payload"])

    def do_DELETE(self) -> None:  # noqa: N802
        if not self._enforce_api_rate_limit(urlparse(self.path).path.rstrip("/") or "/"):
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if scim_service().handles_path(path):
            if not SCIM_BEARER_TOKEN:
                self._write_json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": "scim disabled"})
                return
            if not self._is_scim_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            response = scim_service().route_delete(path)
            if int(response["status"]) == int(HTTPStatus.NO_CONTENT):
                self.send_response(HTTPStatus.NO_CONTENT)
                self._write_common_security_headers()
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._write_json(response["status"], response["payload"])
            return

        if auth_http_surface_service().handles_delete(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("DELETE", path):
                return
            principal = self._auth_principal()
            requester_tenant = (principal or {}).get("tenant_id") or None
            response = auth_http_surface_service().route_delete(
                path, requester_tenant_id=requester_tenant
            )
            self._audit_auth_surface_response("DELETE", path, response)
            self._write_json(response["status"], response["payload"])
            return

        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        if not self._authorize_or_respond("DELETE", path):
            return
        pool_match = re.match(r"^/api/v1/pools/(?P<pool_id>[A-Za-z0-9._-]+)$", path)
        if pool_match is not None:
            pool_id = pool_match.group("pool_id")
            deleted = pool_manager_service().delete_pool(pool_id)
            if not deleted:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "pool not found"})
                return
            self._audit_event(
                "pool.delete",
                "success",
                pool_id=pool_id,
                username=self._requester_identity(),
            )
            self._write_json(HTTPStatus.OK, {"ok": True, "pool_id": pool_id, "deleted": True})
            return

        template_match = re.match(r"^/api/v1/pool-templates/(?P<template_id>[A-Za-z0-9._-]+)$", path)
        if template_match is not None:
            template_id = template_match.group("template_id")
            deleted = desktop_template_builder_service().delete_template(template_id)
            if not deleted:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "template not found"})
                return
            self._audit_event(
                "pool_template.delete",
                "success",
                template_id=template_id,
                username=self._requester_identity(),
            )
            self._write_json(HTTPStatus.OK, {"ok": True, "template_id": template_id, "deleted": True})
            return

        if not admin_http_surface_service().handles_delete(path):
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        response = admin_http_surface_service().route_delete(path)
        self._audit_event(
            "mutation.request",
            "success" if int(response["status"]) < 400 else "error",
            method="DELETE",
            path=path,
            permission=authz_policy_service().required_permission("DELETE", path),
            username=self._requester_identity(),
            status=int(response["status"]),
        )
        self._write_json(response["status"], response["payload"])

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{utcnow()}] {self.address_string()} {fmt % args}", flush=True)

    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        except Exception as error:
            self._handle_unexpected_error(error)


def main() -> int:
    effective_data_dir = ensure_data_dir()
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(
        json.dumps(
            {
                "service": "beagle-control-plane",
                "version": VERSION,
                "listen_host": LISTEN_HOST,
                "listen_port": LISTEN_PORT,
                "allow_localhost_noauth": ALLOW_LOCALHOST_NOAUTH,
                "data_dir": str(effective_data_dir),
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
