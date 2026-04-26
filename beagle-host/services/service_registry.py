"""Service registry: all imports, constants and lazy-init factory functions."""
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
import threading
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
from backup_service import BackupService
from auth_session import AuthSessionService, default_now
from authz_policy import AuthzPolicyService, PERMISSION_CATALOG
from ca_manager import ClusterCaService
from cluster_inventory import ClusterInventoryService
from cluster_membership import ClusterMembershipService
from cluster_rpc import ClusterRpcError, ClusterRpcService
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
from ha_manager import HaManagerService
from host_provider_contract import HostProvider
from identity_provider_registry import IdentityProviderRegistryService
from installer_prep import InstallerPrepService
from installer_script import InstallerScriptService
from installer_template_patch import InstallerTemplatePatchService
from maintenance_service import MaintenanceService
from metadata_support import MetadataSupportService
from migration_service import MigrationService
from oidc_service import OidcService
from persistence_support import PersistenceSupportService
from policy_normalization import PolicyNormalizationService
from policy_store import PolicyStoreService
from pairing_service import PairingService
from public_http_surface import PublicHttpSurfaceService
from public_sunshine_surface import PublicSunshineSurfaceService
from public_ubuntu_install_surface import PublicUbuntuInstallSurfaceService
from public_streams import PublicStreamService
from job_queue_service import JobQueueService
from job_worker import JobWorker
from jobs_http_surface import JobsHttpSurface
from prometheus_metrics import PrometheusMetricsService
from health_aggregator import HealthAggregatorService
from structured_logger import StructuredLogger
from recording_service import RecordingService
from request_support import RequestSupportService
from registry import create_provider, list_providers, normalize_provider_kind
from runtime_environment import RuntimeEnvironmentService
from runtime_exec import RuntimeExecService
from runtime_paths import RuntimePathsService
from runtime_support import RuntimeSupportService
from scim_service import ScimService
from saml_service import SamlAssertionError, SamlService
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
from gpu_inventory import GpuInventoryService
from gpu_passthrough_service import GpuPassthroughService
from gpu_passthrough_surface import GpuPassthroughSurfaceService
from vgpu_service import VgpuService, SriovService
from vgpu_surface import VgpuSurfaceService
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
from core.virtualization.desktop_pool import SessionRecordingPolicy
from ipam_service import IpamService
from firewall_service import FirewallService
from secret_store_service import SecretStoreService
from backups_http_surface import BackupsHttpSurfaceService
from pools_http_surface import PoolsHttpSurfaceService
from cluster_http_surface import ClusterHttpSurfaceService
from audit_report_http_surface import AuditReportHttpSurfaceService
from auth_session_http_surface import AuthSessionHttpSurfaceService
from recording_http_surface import RecordingHttpSurfaceService
from network_http_surface import NetworkHttpSurfaceService

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
RECORDING_STORAGE_BACKEND = os.environ.get("BEAGLE_RECORDING_STORAGE_BACKEND", "local").strip().lower() or "local"
RECORDING_STORAGE_PATH = os.environ.get("BEAGLE_RECORDING_STORAGE_PATH", "").strip()
RECORDING_S3_BUCKET = os.environ.get("BEAGLE_RECORDING_S3_BUCKET", "").strip()
RECORDING_S3_PREFIX = os.environ.get("BEAGLE_RECORDING_S3_PREFIX", "recordings").strip() or "recordings"
RECORDING_S3_REGION = os.environ.get("BEAGLE_RECORDING_S3_REGION", "us-east-1").strip() or "us-east-1"
RECORDING_S3_ENDPOINT = os.environ.get("BEAGLE_RECORDING_S3_ENDPOINT", "").strip()
RECORDING_S3_ACCESS_KEY = os.environ.get("BEAGLE_RECORDING_S3_ACCESS_KEY", "").strip()
RECORDING_S3_SECRET_KEY = os.environ.get("BEAGLE_RECORDING_S3_SECRET_KEY", "").strip()
RECORDING_RETENTION_DEFAULT_DAYS = int(os.environ.get("BEAGLE_RECORDING_RETENTION_DEFAULT_DAYS", "30"))
RECORDING_RETENTION_CRON_SECONDS = int(os.environ.get("BEAGLE_RECORDING_RETENTION_CRON_SECONDS", "3600"))
BACKUP_SCHEDULER_INTERVAL_SECONDS = int(os.environ.get("BEAGLE_BACKUP_SCHEDULER_INTERVAL_SECONDS", "300"))
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
# Beagle-native default for the management TLS certificate. Operators may still
# override via BEAGLE_MANAGER_CERT_FILE for legacy installations.
MANAGER_CERT_FILE = Path(os.environ.get("BEAGLE_MANAGER_CERT_FILE", "/etc/beagle/manager-ssl.pem"))
CLUSTER_NODE_NAME = os.environ.get("BEAGLE_CLUSTER_NODE_NAME", os.uname().nodename).strip() or os.uname().nodename
CLUSTER_RPC_LISTEN_HOST = os.environ.get("BEAGLE_CLUSTER_RPC_LISTEN_HOST", "0.0.0.0").strip() or "0.0.0.0"
CLUSTER_RPC_PORT = int(os.environ.get("BEAGLE_CLUSTER_RPC_PORT", "9089"))
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
# Optional Bearer-Token for /metrics scraping (Prometheus). When empty,
# /metrics is unauthenticated — appropriate for hosts behind a reverse
# proxy or local-only scrapes. See docs/observability/setup.md.
METRICS_BEARER_TOKEN = os.environ.get("BEAGLE_METRICS_BEARER_TOKEN", "").strip()
# When set to a truthy value, /api/v1/health returns HTTP 503 if the
# aggregated component status is "unhealthy". Default off to preserve
# back-compat with monitoring that expects 200.
HEALTH_503_ON_UNHEALTHY = os.environ.get(
    "BEAGLE_HEALTH_503_ON_UNHEALTHY", ""
).strip().lower() in {"1", "true", "yes", "on"}
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
BACKUP_SERVICE: BackupService | None = None
IPAM_SERVICE: IpamService | None = None
FIREWALL_SERVICE: FirewallService | None = None
SECRET_STORE_SERVICE: SecretStoreService | None = None


def _secret_store() -> SecretStoreService:
    """Return the singleton SecretStoreService (lazy-init, thread-safe enough for startup)."""
    global SECRET_STORE_SERVICE
    if SECRET_STORE_SERVICE is None:
        SECRET_STORE_SERVICE = SecretStoreService(
            secrets_dir=Path("/var/lib/beagle/secrets"),
        )
    return SECRET_STORE_SERVICE


def _bootstrap_secret(name: str, env_value: str, *, generate: bool = True) -> str:
    """Return env_value if set, otherwise load from SecretStore.

    If the secret does not exist in the store yet and generate=True, a new
    random value is generated and stored.  The value is NEVER logged.
    """
    if env_value:
        return env_value
    store = _secret_store()
    try:
        return store.get_secret(name).value
    except Exception:  # noqa: BLE001
        pass
    if not generate:
        return ""
    import logging as _logging
    sv = store.set_secret(name, secrets.token_hex(32))
    _logging.getLogger(__name__).info(
        "[BEAGLE BOOTSTRAP] Generated secret %r (v%d) — retrieve with: beaglectl secret get %s",
        name, sv.version, name,
    )
    return sv.value


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


def backup_service() -> BackupService:
    global BACKUP_SERVICE
    if BACKUP_SERVICE is None:
        BACKUP_SERVICE = BackupService(
            state_file=DATA_DIR / "backup-state.json",
            utcnow=utcnow,
        )
    return BACKUP_SERVICE


def ipam_service() -> IpamService:
    global IPAM_SERVICE
    if IPAM_SERVICE is None:
        IPAM_SERVICE = IpamService()
    return IPAM_SERVICE


def firewall_service() -> FirewallService:
    global FIREWALL_SERVICE
    if FIREWALL_SERVICE is None:
        FIREWALL_SERVICE = FirewallService()
    return FIREWALL_SERVICE


def network_http_surface_service() -> NetworkHttpSurfaceService:
    global NETWORK_HTTP_SURFACE_SERVICE
    if NETWORK_HTTP_SURFACE_SERVICE is None:
        NETWORK_HTTP_SURFACE_SERVICE = NetworkHttpSurfaceService(
            ipam_service=ipam_service(),
            firewall_service=firewall_service(),
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )
    return NETWORK_HTTP_SURFACE_SERVICE


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
            start_vm=lambda vmid: start_vm_checked(int(vmid)),
            stop_vm=lambda vmid: HOST_PROVIDER.stop_vm(int(vmid), skiplock=True, timeout=None),
            reset_vm_to_template=reset_vm_to_template,
            list_nodes=_cluster_nodes_for_migration,
            vm_node_of=lambda vmid: str(getattr(find_vm(int(vmid), refresh=True), "node", "") or ""),
            list_gpu_inventory=lambda: gpu_inventory_service().list_gpus(),
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

GPU_INVENTORY_SERVICE: GpuInventoryService | None = None
GPU_PASSTHROUGH_SERVICE: GpuPassthroughService | None = None
GPU_PASSTHROUGH_SURFACE_SERVICE: GpuPassthroughSurfaceService | None = None
VGPU_SERVICE: VgpuService | None = None
SRIOV_SERVICE: SriovService | None = None
VGPU_SURFACE_SERVICE: VgpuSurfaceService | None = None
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
MIGRATION_SERVICE: MigrationService | None = None
HA_MANAGER_SERVICE: HaManagerService | None = None
MAINTENANCE_SERVICE: MaintenanceService | None = None
CLUSTER_MEMBERSHIP_SERVICE: ClusterMembershipService | None = None
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
JOB_QUEUE_SERVICE: JobQueueService | None = None
JOB_WORKER: JobWorker | None = None
JOBS_HTTP_SURFACE: JobsHttpSurface | None = None
PROMETHEUS_METRICS_SERVICE: PrometheusMetricsService | None = None
HEALTH_AGGREGATOR_SERVICE: HealthAggregatorService | None = None
STRUCTURED_LOGGER: StructuredLogger | None = None
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
NETWORK_HTTP_SURFACE_SERVICE: NetworkHttpSurfaceService | None = None
# no module-level singleton for AuthSessionHttpSurfaceService: it has per-request callables
ENDPOINT_TOKEN_STORE_SERVICE: EndpointTokenStoreService | None = None
PAIRING_SERVICE: PairingService | None = None
CLUSTER_RPC_SERVER: ThreadingHTTPServer | None = None
CLUSTER_RPC_THREAD: threading.Thread | None = None
RECORDING_RETENTION_THREAD: threading.Thread | None = None
RECORDING_RETENTION_STOP_EVENT: threading.Event | None = None
BACKUP_SCHEDULER_THREAD: threading.Thread | None = None
BACKUP_SCHEDULER_STOP_EVENT: threading.Event | None = None


def endpoints_dir() -> Path:
    return runtime_paths_service().endpoints_dir()


def actions_dir() -> Path:
    return runtime_paths_service().actions_dir()


def support_bundles_dir() -> Path:
    return runtime_paths_service().support_bundles_dir()


def recordings_dir() -> Path:
    return runtime_paths_service().ensure_named_dir("recordings")


def recordings_storage_dir() -> Path:
    if RECORDING_STORAGE_PATH:
        path = Path(RECORDING_STORAGE_PATH)
        path.mkdir(parents=True, exist_ok=True)
        return path
    return recordings_dir()


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


def prometheus_metrics_service() -> PrometheusMetricsService:
    """Singleton Prometheus metrics registry (GoAdvanced Plan 08)."""
    global PROMETHEUS_METRICS_SERVICE
    if PROMETHEUS_METRICS_SERVICE is None:
        PROMETHEUS_METRICS_SERVICE = PrometheusMetricsService()
        PROMETHEUS_METRICS_SERVICE.register_defaults()
    return PROMETHEUS_METRICS_SERVICE


def health_aggregator_service() -> HealthAggregatorService:
    """Singleton component-health aggregator (GoAdvanced Plan 08 Schritt 5)."""
    global HEALTH_AGGREGATOR_SERVICE
    if HEALTH_AGGREGATOR_SERVICE is None:
        agg = HealthAggregatorService(
            check_timeout_seconds=2.0,
            utcnow=utcnow,
        )
        agg.register("control_plane", agg.control_plane_check)
        agg.register(
            "providers",
            HealthAggregatorService.provider_check(list_providers),
        )
        agg.register(
            "data_dir",
            lambda: HealthAggregatorService.writable_path_check(
                runtime_paths_service().data_dir()
            )(),
        )
        HEALTH_AGGREGATOR_SERVICE = agg
    return HEALTH_AGGREGATOR_SERVICE


def structured_logger() -> StructuredLogger:
    """Singleton JSON-line logger (GoAdvanced Plan 08 Schritt 3)."""
    global STRUCTURED_LOGGER
    if STRUCTURED_LOGGER is None:
        STRUCTURED_LOGGER = StructuredLogger(
            service="beagle-control-plane",
            min_level=os.environ.get("BEAGLE_LOG_LEVEL", "info").strip().lower() or "info",
        )
    return STRUCTURED_LOGGER


def job_queue_service() -> JobQueueService:
    """Singleton async-job queue (GoAdvanced Plan 07 Schritt 1)."""
    global JOB_QUEUE_SERVICE
    if JOB_QUEUE_SERVICE is None:
        JOB_QUEUE_SERVICE = JobQueueService()
    return JOB_QUEUE_SERVICE


def job_worker() -> JobWorker:
    """Singleton background job worker (GoAdvanced Plan 07 Schritt 2)."""
    global JOB_WORKER
    if JOB_WORKER is None:
        JOB_WORKER = JobWorker(
            queue=job_queue_service(),
            max_workers=int(os.environ.get("BEAGLE_JOB_WORKER_COUNT", "4")),
        )
    return JOB_WORKER


def jobs_http_surface() -> JobsHttpSurface:
    """Singleton jobs HTTP surface (GoAdvanced Plan 07 Schritt 4)."""
    global JOBS_HTTP_SURFACE
    if JOBS_HTTP_SURFACE is None:
        JOBS_HTTP_SURFACE = JobsHttpSurface(queue=job_queue_service())
    return JOBS_HTTP_SURFACE


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
            storage_backend=RECORDING_STORAGE_BACKEND,
            storage_path=str(recordings_storage_dir()),
            s3_bucket=RECORDING_S3_BUCKET,
            s3_prefix=RECORDING_S3_PREFIX,
            s3_region=RECORDING_S3_REGION,
            s3_endpoint=RECORDING_S3_ENDPOINT,
            s3_access_key=RECORDING_S3_ACCESS_KEY,
            s3_secret_key=RECORDING_S3_SECRET_KEY,
            safe_slug=utility_support_service().safe_slug,
            write_json_file=write_json_file,
            now_epoch=lambda: datetime.now(timezone.utc).timestamp(),
        )
    return RECORDING_SERVICE


def _start_recording_retention_thread() -> None:
    global RECORDING_RETENTION_THREAD, RECORDING_RETENTION_STOP_EVENT
    if RECORDING_RETENTION_THREAD is not None and RECORDING_RETENTION_THREAD.is_alive():
        return
    stop_event = threading.Event()
    interval_seconds = max(60, int(RECORDING_RETENTION_CRON_SECONDS))
    default_days = max(1, int(RECORDING_RETENTION_DEFAULT_DAYS))

    def _worker() -> None:
        while not stop_event.wait(interval_seconds):
            try:
                result = recording_service().cleanup_expired_recordings(
                    retention_days_for_pool=lambda pool_id: pool_manager_service().get_pool_recording_retention_days(pool_id),
                    default_retention_days=default_days,
                )
                deleted_items = result.get("deleted") if isinstance(result, dict) else []
                if isinstance(deleted_items, list):
                    for item in deleted_items:
                        if not isinstance(item, dict):
                            continue
                        try:
                            audit_log_service().write_event(
                                "session.recording.retention_delete",
                                "success",
                                {
                                    "session_id": str(item.get("session_id") or ""),
                                    "pool_id": str(item.get("pool_id") or ""),
                                    "filename": str(item.get("filename") or ""),
                                    "retention_days": int(item.get("retention_days") or default_days),
                                },
                            )
                        except Exception:
                            pass
            except Exception:
                pass

    thread = threading.Thread(target=_worker, name="recording-retention-cron", daemon=True)
    thread.start()
    RECORDING_RETENTION_STOP_EVENT = stop_event
    RECORDING_RETENTION_THREAD = thread


def _start_backup_scheduler_thread() -> None:
    global BACKUP_SCHEDULER_THREAD, BACKUP_SCHEDULER_STOP_EVENT
    if BACKUP_SCHEDULER_THREAD is not None and BACKUP_SCHEDULER_THREAD.is_alive():
        return
    stop_event = threading.Event()
    interval_seconds = max(60, int(BACKUP_SCHEDULER_INTERVAL_SECONDS))

    def _worker() -> None:
        while not stop_event.is_set():
            try:
                for job in backup_service().run_scheduled_backups():
                    if not isinstance(job, dict):
                        continue
                    outcome = "success" if str(job.get("status") or "") == "success" else "error"
                    audit_log_service().write_event(
                        "backup.scheduled.run",
                        outcome,
                        {
                            "scope_type": str(job.get("scope_type") or ""),
                            "scope_id": str(job.get("scope_id") or ""),
                            "job_id": str(job.get("job_id") or ""),
                            "archive": str(job.get("archive") or ""),
                            "error": str(job.get("error") or ""),
                        },
                    )
            except Exception:
                pass
            stop_event.wait(interval_seconds)

    thread = threading.Thread(target=_worker, name="backup-scheduler", daemon=True)
    thread.start()
    BACKUP_SCHEDULER_STOP_EVENT = stop_event
    BACKUP_SCHEDULER_THREAD = thread


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


def cluster_ca_service() -> ClusterCaService:
    return ClusterCaService(data_dir=DATA_DIR)


def cluster_membership_service() -> ClusterMembershipService:
    global CLUSTER_MEMBERSHIP_SERVICE
    if CLUSTER_MEMBERSHIP_SERVICE is None:
        CLUSTER_MEMBERSHIP_SERVICE = ClusterMembershipService(
            data_dir=DATA_DIR,
            ca_service=cluster_ca_service(),
            public_manager_url=PUBLIC_MANAGER_URL,
            rpc_port=CLUSTER_RPC_PORT,
            utcnow=utcnow,
            rpc_request=ClusterRpcService.request_json,
            rpc_credentials=_cluster_local_rpc_credentials,
        )
    return CLUSTER_MEMBERSHIP_SERVICE


def _cluster_local_rpc_credentials() -> tuple[Path, Path, Path] | None:
    local_member = cluster_membership_service().local_member()
    if not isinstance(local_member, dict):
        return None
    node_name = str(local_member.get("name") or "").strip()
    if not node_name:
        return None
    node_dir = cluster_ca_service().nodes_dir() / node_name
    cert_path = node_dir / "node.crt"
    key_path = node_dir / "node.key"
    ca_cert_path = cluster_ca_service().ca_cert_path()
    if not cert_path.is_file() or not key_path.is_file() or not ca_cert_path.is_file():
        return None
    return cert_path, key_path, ca_cert_path


def build_cluster_inventory_snapshot() -> dict[str, Any]:
    local_member = cluster_membership_service().local_member() or {}
    return {
        "local_member_name": str(local_member.get("name") or "").strip(),
        "local_member_api_url": str(local_member.get("api_url") or "").strip(),
        "nodes": list_nodes_inventory(),
        "vms": [
            {
                "vmid": int(vm.vmid),
                "node": str(vm.node or ""),
                "status": str(vm.status or "unknown"),
                "name": str(vm.name or ""),
                "tags": str(vm.tags or ""),
            }
            for vm in list_vms(refresh=True)
        ],
    }


def _cluster_remote_snapshots() -> list[dict[str, Any]]:
    credentials = _cluster_local_rpc_credentials()
    if credentials is None:
        return []
    cert_path, key_path, ca_cert_path = credentials
    snapshots: list[dict[str, Any]] = []
    for member in cluster_membership_service().remote_members():
        if not isinstance(member, dict):
            continue
        rpc_url = str(member.get("rpc_url") or "").strip()
        if not rpc_url:
            continue
        try:
            payload = ClusterRpcService.request_json(
                url=rpc_url,
                ca_cert_path=ca_cert_path,
                cert_path=cert_path,
                key_path=key_path,
                method="cluster.inventory.snapshot",
                params={},
                request_id=f"cluster-inventory-{member.get('name', 'peer')}",
                timeout=5,
                check_hostname=False,
            )
            result = payload.get("result") if isinstance(payload, dict) else None
            if isinstance(result, dict):
                snapshots.append(result)
                continue
        except ClusterRpcError:
            pass
        snapshots.append(
            {
                "nodes": [
                    {
                        "name": str(member.get("name") or "").strip(),
                        "status": "unreachable",
                        "cpu": 0.0,
                        "mem": 0,
                        "maxmem": 0,
                        "maxcpu": 0,
                    }
                ],
                "vms": [],
            }
        )
    return snapshots


def ensure_cluster_rpc_listener() -> None:
    global CLUSTER_RPC_SERVER, CLUSTER_RPC_THREAD
    if CLUSTER_RPC_SERVER is not None:
        return
    credentials = _cluster_local_rpc_credentials()
    if credentials is None:
        return
    cert_path, key_path, ca_cert_path = credentials
    rpc = ClusterRpcService(node_name=CLUSTER_NODE_NAME)
    rpc.register_method("cluster.ping", lambda params, peer: {"node": CLUSTER_NODE_NAME, "peer": peer.common_name})
    rpc.register_method("cluster.inventory.snapshot", lambda params, peer: build_cluster_inventory_snapshot())
    rpc.register_method(
        "cluster.member.leave",
        lambda params, peer: cluster_membership_service().remove_member(
            node_name=str((params or {}).get("node_name") or "").strip(),
            requester_node_name=str(peer.common_name or "").strip(),
        ),
    )
    server, thread = rpc.serve_in_thread(
        host=CLUSTER_RPC_LISTEN_HOST,
        port=CLUSTER_RPC_PORT,
        ca_cert_path=ca_cert_path,
        cert_path=cert_path,
        key_path=key_path,
    )
    CLUSTER_RPC_SERVER = server
    CLUSTER_RPC_THREAD = thread


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


def persist_vm_node(vmid: int, source_node: str, target_node: str) -> None:
    vm = find_vm(vmid, refresh=True)
    if vm is None:
        raise RuntimeError(f"VM {int(vmid)} not found")

    source = str(source_node or getattr(vm, "node", "") or "").strip()
    target = str(target_node or "").strip()
    if not source or not target:
        raise RuntimeError("source and target node are required")

    config = HOST_PROVIDER.get_vm_config(source, int(vmid))
    if not isinstance(config, dict):
        config = {}
    config["node"] = target

    write_vm_config = getattr(HOST_PROVIDER, "_write_vm_config", None)
    replace_vm = getattr(HOST_PROVIDER, "_replace_vm", None)
    vm_config_path = getattr(HOST_PROVIDER, "_vm_config_path", None)
    if callable(write_vm_config):
        write_vm_config(target, int(vmid), config)
    if callable(vm_config_path):
        old_path = Path(vm_config_path(source, int(vmid)))
        new_path = Path(vm_config_path(target, int(vmid)))
        if old_path != new_path and old_path.exists():
            try:
                old_path.unlink()
            except OSError:
                pass
    if callable(replace_vm):
        replace_vm(
            {
                "vmid": int(vmid),
                "node": target,
                "name": str(getattr(vm, "name", "") or f"vm-{int(vmid)}"),
                "status": str(getattr(vm, "status", "unknown") or "unknown"),
                "tags": str(getattr(vm, "tags", "") or ""),
            }
        )


def _cluster_nodes_for_migration() -> list[dict[str, Any]]:
    """Return all cluster nodes (local + remote members) for migration/HA targeting.

    Uses the ClusterInventoryService which merges local provider nodes with
    cluster RPC members and remote inventory snapshots.  This ensures that
    remote hypervisor nodes (e.g. beagle-1 on srv2) are visible to the
    MigrationService and HaManagerService even though HOST_PROVIDER only
    knows about the local node.
    """
    inventory = build_cluster_inventory()
    nodes = inventory.get("nodes") if isinstance(inventory, dict) else []
    return nodes if isinstance(nodes, list) else []


def migration_service() -> MigrationService:
    global MIGRATION_SERVICE
    if MIGRATION_SERVICE is None:
        migration_uri_template = os.environ.get(
            "BEAGLE_CLUSTER_MIGRATION_URI_TEMPLATE",
            "qemu+ssh://{target_node}/system",
        ).strip() or "qemu+ssh://{target_node}/system"

        def build_migration_uri(source_node: str, target_node: str, vmid: int) -> str:
            return migration_uri_template.format(
                source_node=str(source_node or "").strip(),
                target_node=str(target_node or "").strip(),
                vmid=int(vmid),
            )

        MIGRATION_SERVICE = MigrationService(
            build_migration_uri=build_migration_uri,
            find_vm=find_vm,
            invalidate_vm_cache=invalidate_vm_cache,
            libvirt_domain_exists=lambda vmid: bool(getattr(HOST_PROVIDER, "_libvirt_domain_exists", lambda _vmid: False)(int(vmid))),
            libvirt_domain_name=lambda vmid: str(getattr(HOST_PROVIDER, "_libvirt_domain_name", lambda _vmid: f"beagle-{int(_vmid)}")(int(vmid))),
            libvirt_enabled=lambda: bool(getattr(HOST_PROVIDER, "_libvirt_enabled", lambda: False)()),
            list_nodes=_cluster_nodes_for_migration,
            persist_vm_node=persist_vm_node,
            run_virsh_command=lambda command: str(getattr(HOST_PROVIDER, "_run_virsh")(*command)),
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )
    return MIGRATION_SERVICE


def ha_manager_service() -> HaManagerService:
    global HA_MANAGER_SERVICE
    if HA_MANAGER_SERVICE is None:
        def cold_restart_vm(vmid: int, source_node: str, target_node: str) -> dict[str, Any]:
            persist_vm_node(vmid, source_node, target_node)
            provider_result = HOST_PROVIDER.start_vm(int(vmid), timeout=None)
            return {
                "vmid": int(vmid),
                "source_node": str(source_node or "").strip(),
                "target_node": str(target_node or "").strip(),
                "provider_result": str(provider_result or ""),
            }

        HA_MANAGER_SERVICE = HaManagerService(
            list_nodes=_cluster_nodes_for_migration,
            list_vms=lambda: list_vms(refresh=True),
            get_vm_config=lambda node, vmid: HOST_PROVIDER.get_vm_config(node, int(vmid)),
            migrate_vm=lambda vmid, target_node, live, copy_storage, requester_identity: migration_service().migrate_vm(
                int(vmid),
                target_node=target_node,
                live=bool(live),
                copy_storage=bool(copy_storage),
                requester_identity=str(requester_identity or ""),
            ),
            cold_restart_vm=cold_restart_vm,
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )
    return HA_MANAGER_SERVICE


def maintenance_service() -> MaintenanceService:
    global MAINTENANCE_SERVICE
    if MAINTENANCE_SERVICE is None:
        maintenance_state_file = DATA_DIR / "ha-maintenance-state.json"

        def cold_restart_vm(vmid: int, source_node: str, target_node: str) -> dict[str, Any]:
            persist_vm_node(vmid, source_node, target_node)
            provider_result = HOST_PROVIDER.start_vm(int(vmid), timeout=None)
            return {
                "vmid": int(vmid),
                "source_node": str(source_node or "").strip(),
                "target_node": str(target_node or "").strip(),
                "provider_result": str(provider_result or ""),
            }

        MAINTENANCE_SERVICE = MaintenanceService(
            state_file=maintenance_state_file,
            list_nodes=_cluster_nodes_for_migration,
            list_vms=lambda: list_vms(refresh=True),
            get_vm_config=lambda node, vmid: HOST_PROVIDER.get_vm_config(node, int(vmid)),
            migrate_vm=lambda vmid, target_node, live, copy_storage, requester_identity: migration_service().migrate_vm(
                int(vmid),
                target_node=target_node,
                live=bool(live),
                copy_storage=bool(copy_storage),
                requester_identity=str(requester_identity or ""),
            ),
            cold_restart_vm=cold_restart_vm,
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )
    return MAINTENANCE_SERVICE


def start_vm_checked(vmid: int) -> str:
    vm = find_vm(int(vmid), refresh=True)
    if vm is None:
        raise RuntimeError(f"VM {int(vmid)} not found")
    watchdog_nodes = _load_watchdog_state_nodes()
    watchdog_item = watchdog_nodes.get(str(vm.node), {})
    if isinstance(watchdog_item, dict):
        watchdog_status = str(watchdog_item.get("status") or "").strip().lower()
        if bool(watchdog_item.get("fencing_active")) or watchdog_status in {"fenced", "fencing"}:
            raise RuntimeError(f"node {vm.node} is fenced; VM start rejected")
    if maintenance_service().is_node_in_maintenance(str(vm.node)):
        raise RuntimeError(f"node {vm.node} is in maintenance mode; VM start rejected")
    return HOST_PROVIDER.start_vm(int(vmid), timeout=None)


def reset_vm_to_template(vmid: int, template_id: str) -> str:
    template_key = str(template_id or "").strip()
    if not template_key:
        raise RuntimeError("template_id is required")
    template = desktop_template_builder_service().get_template(template_key)
    if template is None:
        raise RuntimeError(f"template {template_key!r} not found")
    snapshot_name = str(template.snapshot_name or "").strip() or "sealed"
    return HOST_PROVIDER.reset_vm_to_snapshot(int(vmid), snapshot_name, timeout=None)


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


def gpu_inventory_service() -> GpuInventoryService:
    global GPU_INVENTORY_SERVICE
    if GPU_INVENTORY_SERVICE is None:
        GPU_INVENTORY_SERVICE = GpuInventoryService(
            run_text=lambda command: run_text(command),
        )
    return GPU_INVENTORY_SERVICE


def gpu_passthrough_service() -> GpuPassthroughService:
    global GPU_PASSTHROUGH_SERVICE
    if GPU_PASSTHROUGH_SERVICE is None:
        GPU_PASSTHROUGH_SERVICE = GpuPassthroughService(
            run_virsh=lambda command: str(getattr(HOST_PROVIDER, "_run_virsh")(*command)),
            define_domain_xml=lambda xml_text: getattr(HOST_PROVIDER, "_run_virsh")(
                "define", "/dev/stdin", input_data=xml_text
            ),
            libvirt_domain_name=lambda vmid: str(
                getattr(HOST_PROVIDER, "_libvirt_domain_name", lambda v: f"beagle-{int(v)}")(int(vmid))
            ),
        )
    return GPU_PASSTHROUGH_SERVICE


def gpu_passthrough_surface_service() -> GpuPassthroughSurfaceService:
    global GPU_PASSTHROUGH_SURFACE_SERVICE
    if GPU_PASSTHROUGH_SURFACE_SERVICE is None:
        GPU_PASSTHROUGH_SURFACE_SERVICE = GpuPassthroughSurfaceService(
            assign_gpu=lambda pci, vmid: gpu_passthrough_service().assign_gpu(pci, vmid),
            release_gpu=lambda pci, vmid: gpu_passthrough_service().release_gpu(pci, vmid),
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )
    return GPU_PASSTHROUGH_SURFACE_SERVICE


def vgpu_service() -> VgpuService:
    global VGPU_SERVICE
    if VGPU_SERVICE is None:
        VGPU_SERVICE = VgpuService(
            run_virsh=lambda command: str(getattr(HOST_PROVIDER, "_run_virsh")(*command)),
            define_domain_xml=lambda xml_text: getattr(HOST_PROVIDER, "_run_virsh")(
                "define", "/dev/stdin", input_data=xml_text
            ),
            libvirt_domain_name=lambda vmid: str(
                getattr(HOST_PROVIDER, "_libvirt_domain_name", lambda v: f"beagle-{int(v)}")(int(vmid))
            ),
        )
    return VGPU_SERVICE


def sriov_service() -> SriovService:
    global SRIOV_SERVICE
    if SRIOV_SERVICE is None:
        SRIOV_SERVICE = SriovService()
    return SRIOV_SERVICE


def vgpu_surface_service() -> VgpuSurfaceService:
    global VGPU_SURFACE_SERVICE
    if VGPU_SURFACE_SERVICE is None:
        VGPU_SURFACE_SERVICE = VgpuSurfaceService(
            list_mdev_types=lambda gpu_pci: vgpu_service().list_mdev_types(gpu_pci),
            list_mdev_instances=lambda: vgpu_service().list_mdev_instances(),
            create_mdev_instance=lambda pci, tid: vgpu_service().create_mdev_instance(pci, tid),
            delete_mdev_instance=lambda uid: vgpu_service().delete_mdev_instance(uid),
            assign_mdev_to_vm=lambda uid, vmid: vgpu_service().assign_mdev_to_vm(uid, vmid),
            release_mdev_from_vm=lambda uid, vmid: vgpu_service().release_mdev_from_vm(uid, vmid),
            list_sriov_devices=lambda: sriov_service().list_sriov_devices(),
            set_vf_count=lambda pci, count: sriov_service().set_vf_count(pci, count),
            list_vfs=lambda pci: sriov_service().list_vfs(pci),
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )
    return VGPU_SURFACE_SERVICE


def virtualization_read_surface_service() -> VirtualizationReadSurfaceService:
    global VIRTUALIZATION_READ_SURFACE_SERVICE
    if VIRTUALIZATION_READ_SURFACE_SERVICE is None:
        VIRTUALIZATION_READ_SURFACE_SERVICE = VirtualizationReadSurfaceService(
            build_cluster_inventory=build_cluster_inventory,
            find_vm=find_vm,
            get_guest_network_interfaces=lambda vmid: get_guest_network_interfaces(vmid, timeout_seconds=GUEST_AGENT_TIMEOUT_SECONDS),
            get_storage_quota=lambda pool_name: storage_quota_service().get_pool_quota(pool_name),
            get_vm_config=get_vm_config,
            host_provider_kind=BEAGLE_HOST_PROVIDER_KIND,
            list_bridges_inventory=lambda node="": HOST_PROVIDER.list_bridges(node),
            list_gpu_inventory=lambda: gpu_inventory_service().list_gpus(),
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
            migrate_vm=lambda vmid, target_node, live, copy_storage, requester_identity: migration_service().migrate_vm(
                int(vmid),
                target_node=str(target_node or "").strip(),
                live=bool(live),
                copy_storage=bool(copy_storage),
                requester_identity=requester_identity,
            ),
            queue_vm_action=queue_vm_action,
            reboot_vm=lambda vmid: HOST_PROVIDER.reboot_vm(int(vmid), timeout=None),
            service_name="beagle-control-plane",
            start_vm=lambda vmid: start_vm_checked(int(vmid)),
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
            enqueue_job=lambda name, payload, **kw: job_queue_service().enqueue(name, payload, **kw),
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
            list_remote_inventories=_cluster_remote_snapshots,
            list_cluster_members=lambda: cluster_membership_service().list_members() if cluster_membership_service().is_initialized() else [],
            list_nodes_inventory=list_nodes_inventory,
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )
    return CLUSTER_INVENTORY_SERVICE


def build_cluster_inventory() -> dict[str, Any]:
    return cluster_inventory_service().build_inventory()


def _load_watchdog_state_nodes() -> dict[str, dict[str, Any]]:
    watchdog_state_file = DATA_DIR / "ha-watchdog-state.json"
    try:
        payload = json.loads(watchdog_state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    raw_nodes = payload.get("nodes") if isinstance(payload, dict) else {}
    if not isinstance(raw_nodes, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for raw_name, raw_item in raw_nodes.items():
        name = str(raw_name or "").strip()
        if not name:
            continue
        normalized[name] = raw_item if isinstance(raw_item, dict) else {}
    return normalized


def build_ha_status_payload() -> dict[str, Any]:
    nodes_raw = HOST_PROVIDER.list_nodes()
    vms = list_vms(refresh=True)
    maintenance_nodes = set(maintenance_service().maintenance_nodes())
    watchdog_nodes = _load_watchdog_state_nodes()

    node_status_map: dict[str, str] = {}
    node_names: list[str] = []
    for item in nodes_raw if isinstance(nodes_raw, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("node") or "").strip()
        if not name:
            continue
        if name not in node_names:
            node_names.append(name)
        node_status_map[name] = str(item.get("status") or "unknown").strip().lower() or "unknown"

    for node_name in watchdog_nodes.keys():
        if node_name not in node_names:
            node_names.append(node_name)
        node_status_map.setdefault(node_name, "unknown")

    vm_ha_policy: dict[int, str] = {}
    protected_vms_by_node: dict[str, int] = {}
    for vm in vms:
        vmid = int(getattr(vm, "vmid", 0) or 0)
        node = str(getattr(vm, "node", "") or "").strip()
        if vmid <= 0 or not node:
            continue
        try:
            config = HOST_PROVIDER.get_vm_config(node, vmid)
        except Exception:
            config = {}
        policy = ha_manager_service().normalize_ha_policy(config.get("ha_policy") if isinstance(config, dict) else "")
        vm_ha_policy[vmid] = policy
        if policy in {"restart", "fail_over"}:
            protected_vms_by_node[node] = int(protected_vms_by_node.get(node, 0) or 0) + 1

    total_nodes = len(node_names)
    online_nodes = sum(1 for name in node_names if node_status_map.get(name, "unknown") == "online")
    quorum_min = max(1, (total_nodes // 2) + 1) if total_nodes > 0 else 1
    quorum_ok = online_nodes >= quorum_min

    ha_nodes: list[dict[str, Any]] = []
    fencing_nodes: list[dict[str, Any]] = []
    for name in sorted(node_names):
        provider_status = node_status_map.get(name, "unknown")
        wd_item = watchdog_nodes.get(name) if isinstance(watchdog_nodes.get(name), dict) else {}
        wd_status = str(wd_item.get("status") or "").strip().lower()
        fencing_active = bool(wd_item.get("fencing_active"))
        last_fencing_method = str(wd_item.get("last_fencing_method") or "").strip()
        maintenance = name in maintenance_nodes

        health_status = wd_status or provider_status
        if maintenance and health_status in {"online", "active", "unknown"}:
            health_status = "maintenance"
        if fencing_active:
            health_status = "fencing"

        if fencing_active or health_status == "fenced" or last_fencing_method:
            fencing_nodes.append(
                {
                    "name": name,
                    "status": health_status,
                    "method": last_fencing_method,
                    "active": fencing_active,
                }
            )

        ha_nodes.append(
            {
                "name": name,
                "status": health_status,
                "provider_status": provider_status,
                "maintenance": maintenance,
                "last_heartbeat_utc": str(wd_item.get("last_heartbeat_utc") or ""),
                "fencing_active": fencing_active,
                "last_fencing_method": last_fencing_method,
                "ha_protected_vms": int(protected_vms_by_node.get(name, 0) or 0),
            }
        )

    protected_total = sum(1 for value in vm_ha_policy.values() if value in {"restart", "fail_over"})
    unreachable_nodes = sum(
        1
        for item in ha_nodes
        if str(item.get("status") or "").lower() in {"offline", "unreachable", "fenced"}
    )
    fencing_active_any = any(bool(item.get("active")) for item in fencing_nodes)

    ha_state = "ok"
    if not quorum_ok:
        ha_state = "failed"
    elif fencing_active_any or unreachable_nodes > 0:
        ha_state = "degraded"

    alerts: list[str] = []
    if not quorum_ok:
        alerts.append(
            f"Quorum unterschritten: online={online_nodes}, minimum={quorum_min}."
        )
    for item in fencing_nodes:
        method = str(item.get("method") or "").strip()
        if method:
            alerts.append(f"Fencing aktiv/zuletzt auf {item.get('name')}: {method}.")
        else:
            alerts.append(f"Fencing aktiv auf {item.get('name')}.")

    return {
        "service": "beagle-control-plane",
        "version": VERSION,
        "generated_at": utcnow(),
        "ha_state": ha_state,
        "summary": {
            "total_nodes": total_nodes,
            "online_nodes": online_nodes,
            "unreachable_nodes": unreachable_nodes,
            "ha_protected_vms": protected_total,
            "fencing_active": fencing_active_any,
        },
        "quorum": {
            "minimum_nodes": quorum_min,
            "online_nodes": online_nodes,
            "ok": quorum_ok,
        },
        "fencing": {
            "active": fencing_active_any,
            "nodes": fencing_nodes,
        },
        "nodes": ha_nodes,
        "alerts": alerts,
    }


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
