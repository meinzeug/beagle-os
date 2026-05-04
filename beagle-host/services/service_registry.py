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
from datetime import datetime, timedelta, timezone
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
from alert_service import AlertService
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
from cluster_job_handlers import make_cluster_auto_join_handler, make_cluster_maintenance_drain_handler
from control_plane_read_surface import ControlPlaneReadSurfaceService
from download_metadata import DownloadMetadataService
from endpoint_lifecycle_surface import EndpointLifecycleSurfaceService
from endpoint_http_surface import EndpointHttpSurfaceService
from endpoint_enrollment import EndpointEnrollmentService
from endpoint_profile_contract import installer_profile_surface, normalize_endpoint_profile_contract
from endpoint_report import EndpointReportService
from endpoint_token_store import EndpointTokenStoreService
from enrollment_token_store import EnrollmentTokenStoreService
from attestation_service import AttestationService
from device_registry import DeviceRegistryService
from fleet_inventory import FleetInventoryService
from fleet_http_surface import FleetHttpSurfaceService
from fleet_telemetry_service import FleetTelemetryService
from mdm_policy_http_surface import MDMPolicyHttpSurfaceService
from health_payload import HealthPayloadService
from ha_manager import HaManagerService
from host_provider_contract import HostProvider
from identity_provider_registry import IdentityProviderRegistryService
from installer_prep import InstallerPrepService
from installer_log_service import InstallerLogService
from installer_script import InstallerScriptService
from installer_template_patch import InstallerTemplatePatchService
from maintenance_service import MaintenanceService
from mdm_policy_service import MDMPolicyService
from metadata_support import MetadataSupportService
from migration_service import MigrationService
from oidc_service import OidcService
from persistence_support import PersistenceSupportService
from policy_normalization import PolicyNormalizationService
from policy_store import PolicyStoreService
from pairing_service import PairingService
from public_http_surface import PublicHttpSurfaceService
from public_beagle_stream_server_surface import PublicBeagleStreamServerSurfaceService
from public_ubuntu_install_surface import PublicUbuntuInstallSurfaceService
from public_streams import PublicStreamService
from job_queue_service import JobQueueService
from job_worker import JobWorker
from jobs_http_surface import JobsHttpSurface
from ldap_auth import LdapAuthService
from prometheus_metrics import PrometheusMetricsService
from health_aggregator import HealthAggregatorService
from structured_logger import StructuredLogger
from otel_adapter import OTelHttpLogAdapter
from recording_service import RecordingService
from request_support import RequestSupportService
from registry import create_provider, list_providers, normalize_provider_kind
from runtime_environment import RuntimeEnvironmentService
from runtime_cleanup import cleanup_vm_runtime_artifacts
from runtime_exec import RuntimeExecService
from runtime_paths import RuntimePathsService
from runtime_support import RuntimeSupportService
from scim_service import ScimService
from saml_service import SamlAssertionError, SamlService
from beagle_stream_server_access_token_store import BeagleStreamServerAccessTokenStoreService
from beagle_stream_server_integration import BeagleStreamServerIntegrationService
from stream_http_surface import StreamHttpSurfaceService
from stream_policy_service import StreamPolicyService
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
from storage_image_store import StorageImageStoreService
from storage_quota import StorageQuotaService
from entitlement_service import EntitlementService
from pool_manager import PoolManagerService
from desktop_template_builder import DesktopTemplateBuilderService
from vm_secret_bootstrap import VmSecretBootstrapService
from vm_secret_store import VmSecretStoreService
from vm_state import VmStateService
from vm_usb import VmUsbService
from core.virtualization.desktop_pool import SessionRecordingPolicy
from core.persistence.sqlite_db import BeagleDb
from core.repository.pool_repository import PoolRepository
from core.repository.device_repository import DeviceRepository
from core.repository.vm_repository import VmRepository
from ipam_service import IpamService
from firewall_service import FirewallService
from gaming_metrics_service import GamingMetricsService
from secret_store_service import SecretStoreService
from backups_http_surface import BackupsHttpSurfaceService
from pools_http_surface import PoolsHttpSurfaceService
from cluster_http_surface import ClusterHttpSurfaceService
from audit_report_http_surface import AuditReportHttpSurfaceService
from auth_session_http_surface import AuthSessionHttpSurfaceService
from recording_http_surface import RecordingHttpSurfaceService
from network_http_surface import NetworkHttpSurfaceService
from node_install_check_service import NodeInstallCheckService
from session_manager import SessionManagerService
from wireguard_mesh_service import WireguardMeshService
from smart_scheduler import NodeCapacity, SmartSchedulerService
from scheduler_warm_pool_auto_apply import (
    normalize_auto_apply_config,
    select_recommendations_for_auto_apply,
    should_run_auto_apply,
)
from cost_model_service import CostModelService
from usage_tracking_service import UsageTrackingService
from energy_service import EnergyService
from energy_feed_import import collect_import_payload
from metrics_collector import MetricsCollector
from workload_pattern_analyzer import WorkloadPatternAnalyzer

def load_env_defaults(path: str, *, override: bool = False) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or (key in os.environ and not override):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value

load_env_defaults("/etc/beagle/host.env")
load_env_defaults("/etc/beagle/beagle-proxy.env", override=True)

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
AUTH_LDAP_URI = os.environ.get("BEAGLE_AUTH_LDAP_URI", "").strip()
AUTH_LDAP_BIND_DN_TEMPLATE = os.environ.get("BEAGLE_AUTH_LDAP_BIND_DN_TEMPLATE", "").strip()
AUTH_LDAP_DEFAULT_ROLE = os.environ.get("BEAGLE_AUTH_LDAP_DEFAULT_ROLE", "viewer").strip().lower() or "viewer"
AUTH_LDAP_STARTTLS = os.environ.get("BEAGLE_AUTH_LDAP_STARTTLS", "0").strip().lower() in {"1", "true", "yes", "on"}
AUTH_LDAP_CA_CERT_FILE = os.environ.get("BEAGLE_AUTH_LDAP_CA_CERT_FILE", "").strip()
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
FLEET_REMEDIATION_INTERVAL_SECONDS = int(os.environ.get("BEAGLE_FLEET_REMEDIATION_INTERVAL_SECONDS", "300"))
AUTH_LOGIN_LOCKOUT_THRESHOLD = int(os.environ.get("BEAGLE_AUTH_LOGIN_LOCKOUT_THRESHOLD", "5"))
AUTH_LOGIN_LOCKOUT_SECONDS = int(os.environ.get("BEAGLE_AUTH_LOGIN_LOCKOUT_SECONDS", "300"))
AUTH_LOGIN_BACKOFF_MAX_SECONDS = int(os.environ.get("BEAGLE_AUTH_LOGIN_BACKOFF_MAX_SECONDS", "30"))
INSTALL_CHECK_REPORT_TOKEN = os.environ.get("BEAGLE_INSTALL_CHECK_REPORT_TOKEN", "").strip()
ALLOW_LOCALHOST_NOAUTH = os.environ.get("BEAGLE_MANAGER_ALLOW_LOCALHOST_NOAUTH", "0").strip().lower() in {"1", "true", "yes", "on"}
STALE_ENDPOINT_SECONDS = int(os.environ.get("BEAGLE_MANAGER_STALE_ENDPOINT_SECONDS", "600"))
DOWNLOADS_STATUS_FILE = ROOT_DIR / "dist" / "beagle-downloads-status.json"
DIST_SHA256SUMS_FILE = ROOT_DIR / "dist" / "SHA256SUMS"
BEAGLE_STATE_DB_PATH = (
    Path(os.environ["BEAGLE_STATE_DB_PATH"])
    if os.environ.get("BEAGLE_STATE_DB_PATH")
    else DATA_DIR / "state.db"
)
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
PUBLIC_DOWNLOADS_PORT = int(os.environ.get("PVE_DCV_PROXY_LISTEN_PORT", "443"))
PUBLIC_DOWNLOADS_PATH = os.environ.get("PVE_DCV_DOWNLOADS_PATH", "/beagle-downloads").strip() or "/beagle-downloads"
if PUBLIC_DOWNLOADS_PORT == 443:
    _public_origin = f"https://{PUBLIC_SERVER_NAME}"
else:
    _public_origin = f"https://{PUBLIC_SERVER_NAME}:{PUBLIC_DOWNLOADS_PORT}"
PUBLIC_UPDATE_BASE_URL = os.environ.get("BEAGLE_PUBLIC_UPDATE_BASE_URL", "").strip() or f"{_public_origin}{PUBLIC_DOWNLOADS_PATH}"
PUBLIC_STREAM_HOST_RAW = os.environ.get("BEAGLE_PUBLIC_STREAM_HOST", "").strip() or PUBLIC_SERVER_NAME
INTERNAL_CALLBACK_HOST_RAW = os.environ.get("BEAGLE_INTERNAL_CALLBACK_HOST", "").strip()
PUBLIC_STREAM_BASE_PORT = int(os.environ.get("BEAGLE_PUBLIC_STREAM_BASE_PORT", "50000"))
PUBLIC_STREAM_PORT_STEP = int(os.environ.get("BEAGLE_PUBLIC_STREAM_PORT_STEP", "32"))
PUBLIC_STREAM_PORT_COUNT = int(os.environ.get("BEAGLE_PUBLIC_STREAM_PORT_COUNT", "256"))
PUBLIC_MANAGER_URL = os.environ.get("PVE_DCV_BEAGLE_MANAGER_URL", "").strip() or f"{_public_origin}/beagle-api"
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
OIDC_JWKS_URI = os.environ.get("BEAGLE_OIDC_JWKS_URI", "").strip()
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
BEAGLE_STREAM_SERVER_ACCESS_TOKEN_TTL_SECONDS = int(os.environ.get("BEAGLE_STREAM_SERVER_ACCESS_TOKEN_TTL_SECONDS", "600"))
BEAGLE_STREAM_SERVER_TOKEN_ROTATION_GRACE_SECONDS = int(os.environ.get("BEAGLE_STREAM_SERVER_TOKEN_ROTATION_GRACE_SECONDS", "600"))
PAIRING_TOKEN_TTL_SECONDS = int(os.environ.get("BEAGLE_PAIRING_TOKEN_TTL_SECONDS", "60"))
PAIRING_TOKEN_SECRET = os.environ.get("BEAGLE_PAIRING_TOKEN_SECRET", "").strip()
ENERGY_FEED_IMPORT_TIMEOUT_SECONDS = float(
    os.environ.get("BEAGLE_ENERGY_FEED_IMPORT_TIMEOUT_SECONDS", "5")
)
ENERGY_FEED_IMPORT_RETRIES = int(os.environ.get("BEAGLE_ENERGY_FEED_IMPORT_RETRIES", "3"))
ENERGY_FEED_IMPORT_RETRY_BACKOFF_SECONDS = float(
    os.environ.get("BEAGLE_ENERGY_FEED_IMPORT_RETRY_BACKOFF_SECONDS", "1")
)
INSTALLER_LOG_TOKEN_TTL_SECONDS = int(os.environ.get("BEAGLE_INSTALLER_LOG_TOKEN_TTL_SECONDS", "86400"))
INSTALLER_LOG_TOKEN_SECRET = os.environ.get("BEAGLE_INSTALLER_LOG_TOKEN_SECRET", "").strip()
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
UBUNTU_BEAGLE_DEFAULT_DESKTOP = (
    os.environ.get("BEAGLE_UBUNTU_DEFAULT_DESKTOP", "plasma-cyberpunk").strip().lower() or "plasma-cyberpunk"
)
UBUNTU_BEAGLE_DEFAULT_PACKAGE_PRESETS = [
    item.strip().lower()
    for item in os.environ.get(
        "BEAGLE_UBUNTU_DEFAULT_PACKAGE_PRESETS",
        "libreoffice,thunderbird,gimp,inkscape,vlc,filezilla,remmina,vscode,dev-core,python-dev,nodejs-dev,java-dev",
    ).split(",")
    if item.strip()
]
UBUNTU_BEAGLE_CYBERPUNK_WALLPAPER_SOURCE = Path(
    os.environ.get(
        "BEAGLE_UBUNTU_CYBERPUNK_WALLPAPER_SOURCE",
        str(ROOT_DIR / "assets" / "branding" / "beagle-cyberpunk-wallpaper.png"),
    ).strip()
    or str(ROOT_DIR / "assets" / "branding" / "beagle-cyberpunk-wallpaper.png")
)
UBUNTU_BEAGLE_PROFILE_ID = "ubuntu-24.04-desktop-beagle-stream-server"
UBUNTU_BEAGLE_PROFILE_LEGACY_IDS = {
    "ubuntu-24.04-xfce-beagle-stream-server": "xfce",
}
UBUNTU_BEAGLE_PROFILE_LABEL = "Ubuntu 24.04 LTS Desktop mit BeagleStream"
UBUNTU_BEAGLE_PROFILE_RELEASE = "24.04 LTS"
UBUNTU_BEAGLE_PROFILE_STREAMING = "BeagleStream"
UBUNTU_BEAGLE_MIN_PASSWORD_LENGTH = int(os.environ.get("BEAGLE_UBUNTU_MIN_PASSWORD_LENGTH", "8"))
UBUNTU_BEAGLE_STREAM_SERVER_URL = os.environ.get(
    "BEAGLE_UBUNTU_STREAM_SERVER_URL",
    "https://github.com/meinzeug/beagle-stream-server/releases/download/beagle-phase-a/beagle-stream-server-latest-ubuntu-24.04-amd64.deb",
).strip()
UBUNTU_BEAGLE_STREAM_SERVER_URL = os.environ.get(
    "BEAGLE_UBUNTU_BEAGLE_STREAM_SERVER_URL",
    UBUNTU_BEAGLE_STREAM_SERVER_URL,
).strip()
UBUNTU_BEAGLE_LOCAL_ISO_DIR = Path(
    os.environ.get("BEAGLE_UBUNTU_LOCAL_ISO_DIR", "/var/lib/vz/template/iso").strip() or "/var/lib/vz/template/iso"
)
UBUNTU_BEAGLE_AUTOINSTALL_URL_TTL_SECONDS = int(os.environ.get("BEAGLE_UBUNTU_AUTOINSTALL_URL_TTL_SECONDS", "21600"))
UBUNTU_BEAGLE_AUTOINSTALL_STALE_SECONDS = int(os.environ.get("BEAGLE_UBUNTU_AUTOINSTALL_STALE_SECONDS", "1800"))
UBUNTU_BEAGLE_FIRSTBOOT_POWERDOWN_WAIT_SECONDS = int(os.environ.get("BEAGLE_UBUNTU_FIRSTBOOT_POWERDOWN_WAIT_SECONDS", "600"))
UBUNTU_BEAGLE_FIRSTBOOT_STALE_SECONDS = int(os.environ.get("BEAGLE_UBUNTU_FIRSTBOOT_STALE_SECONDS", "900"))
UBUNTU_BEAGLE_DESKTOPS: dict[str, dict[str, Any]] = {
    "plasma-cyberpunk": {
        "id": "plasma-cyberpunk",
        "label": "Beagle OS Cyberpunk",
        "session": "plasma",
        "packages": ["plasma-desktop", "plasma-nm", "konsole", "dolphin", "kate", "systemsettings"],
        "features": [
            "KDE Plasma shell",
            "Beagle OS cyberpunk branding",
            "Dark neon profile",
            "Beagle wallpaper",
        ],
        "aliases": ["beagle-cyberpunk", "cyberpunk", "beagle-os-cyberpunk"],
        "visible_in_ui": True,
        "theme_variant": "cyberpunk",
        "wallpaper_required": True,
        "wallpaper_source": str(UBUNTU_BEAGLE_CYBERPUNK_WALLPAPER_SOURCE),
    },
    "plasma-classic": {
        "id": "plasma-classic",
        "label": "KDE Plasma Classic",
        "session": "plasma",
        "packages": ["plasma-desktop", "plasma-nm", "konsole", "dolphin", "kate", "systemsettings"],
        "features": [
            "KDE Plasma shell",
            "Classic Breeze defaults",
            "Neutral desktop profile",
        ],
        "aliases": ["plasma", "kde", "kde-plasma", "classic", "plasma-classic"],
        "visible_in_ui": True,
        "theme_variant": "classic",
        "wallpaper_required": False,
    },
    "xfce": {
        "id": "xfce",
        "label": "XFCE",
        "session": "xfce",
        "packages": ["xfce4", "xfce4-goodies"],
        "features": ["Lightweight desktop", "Thunar", "XFCE panel"],
        "aliases": ["xfce", "xubuntu"],
        "visible_in_ui": False,
    },
    "gnome": {
        "id": "gnome",
        "label": "GNOME",
        "session": "ubuntu-xorg",
        "packages": ["ubuntu-desktop-minimal"],
        "features": ["Ubuntu GNOME shell", "Activities overview", "Files app"],
        "aliases": ["gnome", "ubuntu", "ubuntu-desktop"],
        "visible_in_ui": False,
    },
    "mate": {
        "id": "mate",
        "label": "MATE",
        "session": "mate",
        "packages": ["mate-desktop-environment-core", "mate-terminal", "caja"],
        "features": ["Traditional desktop", "Caja", "MATE terminal"],
        "aliases": ["mate", "ubuntu-mate"],
        "visible_in_ui": False,
    },
    "lxqt": {
        "id": "lxqt",
        "label": "LXQt",
        "session": "lxqt",
        "packages": ["lxqt", "qterminal", "pcmanfm-qt"],
        "features": ["Very lightweight", "PCManFM-Qt", "Qt desktop"],
        "aliases": ["lxqt", "lubuntu"],
        "visible_in_ui": False,
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
    "inkscape": {
        "id": "inkscape",
        "label": "Inkscape",
        "packages": ["inkscape"],
        "description": "Vector graphics editor.",
    },
    "vscode": {
        "id": "vscode",
        "label": "Visual Studio Code",
        "packages": ["code"],
        "description": "Code editor and IDE.",
    },
    "dev-core": {
        "id": "dev-core",
        "label": "Developer Core Tools",
        "packages": ["git", "git-lfs", "curl", "wget", "jq", "unzip", "zip", "build-essential", "cmake"],
        "description": "Common CLI and build tooling.",
    },
    "python-dev": {
        "id": "python-dev",
        "label": "Python Toolchain",
        "packages": ["python3-pip", "python3-venv", "pipx"],
        "description": "Python virtualenv and package tooling.",
    },
    "nodejs-dev": {
        "id": "nodejs-dev",
        "label": "Node.js Toolchain",
        "packages": ["nodejs", "npm"],
        "description": "Node.js and npm runtime.",
    },
    "java-dev": {
        "id": "java-dev",
        "label": "OpenJDK",
        "packages": ["openjdk-17-jdk"],
        "description": "Java development kit.",
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
LDAP_AUTH_SERVICE: LdapAuthService | None = None
AUDIT_LOG_SERVICE: AuditLogService | None = None
AUDIT_EXPORT_SERVICE: AuditExportService | None = None
AUDIT_REPORT_SERVICE: AuditReportService | None = None
AUTHZ_POLICY_SERVICE: AuthzPolicyService | None = None
SERVER_SETTINGS_SERVICE: ServerSettingsService | None = None
STORAGE_QUOTA_SERVICE: StorageQuotaService | None = None
STORAGE_IMAGE_STORE_SERVICE: StorageImageStoreService | None = None
ENTITLEMENT_SERVICE: EntitlementService | None = None
_BEAGLE_DB: BeagleDb | None = None
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
GAMING_METRICS_SERVICE: GamingMetricsService | None = None
NODE_INSTALL_CHECK_SERVICE: NodeInstallCheckService | None = None
SESSION_MANAGER_SERVICE: SessionManagerService | None = None


def _secret_store() -> SecretStoreService:
    """Return the singleton SecretStoreService (lazy-init, thread-safe enough for startup)."""
    global SECRET_STORE_SERVICE
    if SECRET_STORE_SERVICE is None:
        SECRET_STORE_SERVICE = SecretStoreService(
            secrets_dir=Path("/var/lib/beagle/secrets"),
        )
    return SECRET_STORE_SERVICE


def node_install_check_service() -> NodeInstallCheckService:
    global NODE_INSTALL_CHECK_SERVICE
    if NODE_INSTALL_CHECK_SERVICE is None:
        NODE_INSTALL_CHECK_SERVICE = NodeInstallCheckService(
            state_file=DATA_DIR / "install-checks.json",
            report_token=INSTALL_CHECK_REPORT_TOKEN,
            now=lambda: datetime.now(timezone.utc),
            persistence_support=PERSISTENCE_SUPPORT_SERVICE,
        )
    return NODE_INSTALL_CHECK_SERVICE


def session_manager_service() -> SessionManagerService:
    global SESSION_MANAGER_SERVICE
    if SESSION_MANAGER_SERVICE is None:
        SESSION_MANAGER_SERVICE = SessionManagerService(
            state_file=DATA_DIR / "session-manager" / "sessions.json",
            checkpoint_dir=DATA_DIR / "session-manager" / "checkpoints",
            user_geo_resolver=auth_session_service().get_user_session_geo_routing,
            audit_event=lambda event_type, outcome: audit_log_service().write_event(event_type, outcome, {}),
        )
    return SESSION_MANAGER_SERVICE


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


def scim_secret_name() -> str:
    return "scim-bearer-token"


def scim_bearer_token_enabled() -> bool:
    if SCIM_BEARER_TOKEN:
        return True
    try:
        return _secret_store().has_secret(scim_secret_name())
    except Exception:  # noqa: BLE001
        return False


def is_scim_bearer_token_valid(token: str) -> bool:
    candidate = str(token or "").strip()
    if not candidate:
        return False
    if SCIM_BEARER_TOKEN and secrets.compare_digest(candidate, SCIM_BEARER_TOKEN):
        return True
    try:
        return _secret_store().is_valid(scim_secret_name(), candidate)
    except Exception:  # noqa: BLE001
        return False


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
            ldap_authenticate=lambda username, password: ldap_auth_service().authenticate(username=username, password=password),
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


def ldap_auth_service() -> LdapAuthService:
    global LDAP_AUTH_SERVICE
    if LDAP_AUTH_SERVICE is None:
        LDAP_AUTH_SERVICE = LdapAuthService(
            server_uri=AUTH_LDAP_URI,
            bind_dn_template=AUTH_LDAP_BIND_DN_TEMPLATE,
            default_role=AUTH_LDAP_DEFAULT_ROLE,
            start_tls=AUTH_LDAP_STARTTLS,
            ca_cert_file=AUTH_LDAP_CA_CERT_FILE,
        )
    return LDAP_AUTH_SERVICE


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


def gaming_metrics_service() -> GamingMetricsService:
    global GAMING_METRICS_SERVICE
    if GAMING_METRICS_SERVICE is None:
        GAMING_METRICS_SERVICE = GamingMetricsService(
            state_dir=DATA_DIR / "gaming-metrics",
            utcnow=utcnow,
        )
    return GAMING_METRICS_SERVICE


def storage_quota_service() -> StorageQuotaService:
    global STORAGE_QUOTA_SERVICE
    if STORAGE_QUOTA_SERVICE is None:
        STORAGE_QUOTA_SERVICE = StorageQuotaService(
            state_file=DATA_DIR / "storage-quotas.json",
        )
    return STORAGE_QUOTA_SERVICE


def storage_image_store_service() -> StorageImageStoreService:
    global STORAGE_IMAGE_STORE_SERVICE
    if STORAGE_IMAGE_STORE_SERVICE is None:
        STORAGE_IMAGE_STORE_SERVICE = StorageImageStoreService(
            list_storage_inventory=lambda: list_storage_inventory(),
            get_pool_quota=lambda pool_name: storage_quota_service().get_pool_quota(pool_name),
        )
    return STORAGE_IMAGE_STORE_SERVICE


def entitlement_service() -> EntitlementService:
    global ENTITLEMENT_SERVICE
    if ENTITLEMENT_SERVICE is None:
        ENTITLEMENT_SERVICE = EntitlementService(
            state_file=DATA_DIR / "pool-entitlements.json",
        )
    return ENTITLEMENT_SERVICE


def _beagle_db() -> BeagleDb:
    """Singleton BeagleDb instance backed by BEAGLE_STATE_DB_PATH.

    Applies SQL migrations on first access so the schema is always current.
    Errors are silently suppressed to preserve startup resilience — the JSON
    backend remains the authoritative store during this transitional phase.
    """
    global _BEAGLE_DB
    if _BEAGLE_DB is None:
        db = BeagleDb(BEAGLE_STATE_DB_PATH)
        try:
            schema_dir = ROOT_DIR / "core" / "persistence" / "migrations"
            db.migrate(schema_dir)
        except Exception:  # pragma: no cover
            pass
        _BEAGLE_DB = db
    return _BEAGLE_DB


def _pool_repository() -> PoolRepository:
    return PoolRepository(_beagle_db())


def _device_repository() -> DeviceRepository:
    return DeviceRepository(_beagle_db())


def _vm_repository() -> VmRepository:
    return VmRepository(_beagle_db())


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
            smart_pick_node=_smart_pick_pool_node,
            pool_repository=_pool_repository(),
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
            jwks_uri=OIDC_JWKS_URI,
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
STREAM_HTTP_SURFACE_SERVICE: StreamHttpSurfaceService | None = None
ADMIN_HTTP_SURFACE_SERVICE: AdminHttpSurfaceService | None = None
AUTH_HTTP_SURFACE_SERVICE: AuthHttpSurfaceService | None = None
ENDPOINT_LIFECYCLE_SURFACE_SERVICE: EndpointLifecycleSurfaceService | None = None
PUBLIC_BEAGLE_STREAM_SERVER_SURFACE_SERVICE: PublicBeagleStreamServerSurfaceService | None = None
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
DEVICE_REGISTRY_SERVICE: DeviceRegistryService | None = None
MDM_POLICY_SERVICE: MDMPolicyService | None = None
ATTESTATION_SERVICE: AttestationService | None = None
FLEET_HTTP_SURFACE_SERVICE: FleetHttpSurfaceService | None = None
FLEET_TELEMETRY_SERVICE: FleetTelemetryService | None = None
ALERT_SERVICE: AlertService | None = None
MDM_POLICY_HTTP_SURFACE_SERVICE: MDMPolicyHttpSurfaceService | None = None
CLUSTER_INVENTORY_SERVICE: ClusterInventoryService | None = None
HEALTH_PAYLOAD_SERVICE: HealthPayloadService | None = None
SMART_SCHEDULER_SERVICE: SmartSchedulerService | None = None
USAGE_TRACKING_SERVICE: UsageTrackingService | None = None
COST_MODEL_SERVICE: CostModelService | None = None
ENERGY_SERVICE: EnergyService | None = None
METRICS_COLLECTOR_SERVICE: MetricsCollector | None = None
WORKLOAD_PATTERN_ANALYZER_SERVICE: WorkloadPatternAnalyzer | None = None
WIREGUARD_MESH_SERVICE: WireguardMeshService | None = None
INSTALLER_PREP_SERVICE: InstallerPrepService | None = None
INSTALLER_LOG_SERVICE: InstallerLogService | None = None
INSTALLER_SCRIPT_SERVICE: InstallerScriptService | None = None
INSTALLER_TEMPLATE_PATCH_SERVICE: InstallerTemplatePatchService | None = None
ENDPOINT_REPORT_SERVICE: EndpointReportService | None = None
ACTION_QUEUE_SERVICE: ActionQueueService | None = None
POLICY_NORMALIZATION_SERVICE: PolicyNormalizationService | None = None
POLICY_STORE_SERVICE: PolicyStoreService | None = None
PUBLIC_STREAM_SERVICE: PublicStreamService | None = None
JOB_QUEUE_SERVICE: JobQueueService | None = None
STREAM_POLICY_SERVICE: StreamPolicyService | None = None
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
BEAGLE_STREAM_SERVER_ACCESS_TOKEN_STORE_SERVICE: BeagleStreamServerAccessTokenStoreService | None = None
BEAGLE_STREAM_SERVER_INTEGRATION_SERVICE: BeagleStreamServerIntegrationService | None = None
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
FLEET_REMEDIATION_THREAD: threading.Thread | None = None
FLEET_REMEDIATION_STOP_EVENT: threading.Event | None = None


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
        otel_endpoint = os.environ.get("BEAGLE_OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "").strip()
        sinks = []
        if otel_endpoint:
            try:
                otel_timeout_seconds = float(os.environ.get("BEAGLE_OTEL_EXPORT_TIMEOUT_SECONDS", "1.0") or "1.0")
            except ValueError:
                otel_timeout_seconds = 1.0
            sinks.append(OTelHttpLogAdapter(
                endpoint=otel_endpoint,
                service_name=os.environ.get("BEAGLE_OTEL_SERVICE_NAME", "beagle-control-plane").strip() or "beagle-control-plane",
                timeout_seconds=otel_timeout_seconds,
            ))
        STRUCTURED_LOGGER = StructuredLogger(
            service="beagle-control-plane",
            min_level=os.environ.get("BEAGLE_LOG_LEVEL", "info").strip().lower() or "info",
            sinks=sinks,
        )
    return STRUCTURED_LOGGER


def job_queue_service() -> JobQueueService:
    """Singleton async-job queue (GoAdvanced Plan 07 Schritt 1)."""
    global JOB_QUEUE_SERVICE
    if JOB_QUEUE_SERVICE is None:
        JOB_QUEUE_SERVICE = JobQueueService(state_file=DATA_DIR / "jobs-state.json")
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


def initialize_job_worker_handlers() -> None:
    """Register all job handlers and start the worker if not already running.
    
    Must be called once at startup. Safe to call multiple times.
    """
    worker = job_worker()
    
    # Register cluster handlers
    if "cluster.auto_join" not in worker.registered_names():
        handler = make_cluster_auto_join_handler(
            cluster_membership_service=cluster_membership_service(),
            audit_event=audit_log_service().write_event,
        )
        worker.register("cluster.auto_join", handler)
    
    if "cluster.maintenance_drain" not in worker.registered_names():
        handler = make_cluster_maintenance_drain_handler(
            maintenance_service=maintenance_service(),
            audit_event=audit_log_service().write_event,
        )
        worker.register("cluster.maintenance_drain", handler)

    if "vm.snapshot" not in worker.registered_names():
        def _snapshot_handler(job, current_worker):
            payload = job.payload if isinstance(job.payload, dict) else {}
            vmid = int(payload.get("vmid") or 0)
            snap_name = str(payload.get("name") or "").strip()
            if vmid <= 0 or not snap_name:
                raise ValueError("vm.snapshot requires vmid and name")
            current_worker.update_progress(job.job_id, 10, "Snapshot wird vorbereitet")
            result = getattr(HOST_PROVIDER, "_run_virsh")(
                "snapshot-create-as",
                f"beagle-{vmid}",
                snap_name,
                "--atomic",
                "--no-metadata",
            )
            current_worker.update_progress(job.job_id, 95, "Snapshot abgeschlossen")
            return {"ok": True, "vmid": vmid, "snapshot": snap_name, "provider_result": str(result or "").strip()}

        worker.register("vm.snapshot", _snapshot_handler)

    if "vm.migrate" not in worker.registered_names():
        def _migrate_handler(job, current_worker):
            payload = job.payload if isinstance(job.payload, dict) else {}
            vmid = int(payload.get("vmid") or payload.get("vm_id") or 0)
            target_node = str(payload.get("target_node") or "").strip()
            if vmid <= 0 or not target_node:
                raise ValueError("vm.migrate requires vmid and target_node")
            current_worker.update_progress(job.job_id, 10, "Migration wird vorbereitet")
            result = migration_service().migrate_vm(
                vmid,
                target_node=target_node,
                live=payload.get("live", True) is not False,
                copy_storage=payload.get("copy_storage", False) is True,
                requester_identity=str(job.owner or "job-worker"),
            )
            current_worker.update_progress(job.job_id, 95, "Migration abgeschlossen")
            return result

        worker.register("vm.migrate", _migrate_handler)

    if "backup.run" not in worker.registered_names():
        def _backup_run_handler(job, current_worker):
            payload = job.payload if isinstance(job.payload, dict) else {}
            scope_type = str(payload.get("scope_type") or "").strip().lower()
            scope_id = str(payload.get("scope_id") or "").strip()
            current_worker.update_progress(job.job_id, 10, "Backup wird vorbereitet")
            result = backup_service().run_backup_now(scope_type=scope_type, scope_id=scope_id)
            current_worker.update_progress(job.job_id, 95, "Backup abgeschlossen")
            return result

        worker.register("backup.run", _backup_run_handler)
    
    # Start the worker if not already running
    if not worker.is_running:
        worker.start()


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
            resolve_beagle_stream_server_pinned_pubkey=resolve_vm_beagle_stream_server_pinned_pubkey,
            safe_slug=utility_support_service().safe_slug,
            save_vm_secret=save_vm_secret,
            session_script_path=Path(__file__).resolve().parent / "beagle-usb-tunnel-session",
            store_endpoint_token=endpoint_token_store_service().store,
            token_urlsafe=secrets.token_urlsafe,
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


def beagle_stream_server_access_token_store_service() -> BeagleStreamServerAccessTokenStoreService:
    global BEAGLE_STREAM_SERVER_ACCESS_TOKEN_STORE_SERVICE
    if BEAGLE_STREAM_SERVER_ACCESS_TOKEN_STORE_SERVICE is None:
        BEAGLE_STREAM_SERVER_ACCESS_TOKEN_STORE_SERVICE = BeagleStreamServerAccessTokenStoreService(
            data_dir=runtime_paths_service().data_dir,
            load_json_file=load_json_file,
            write_json_file=write_json_file,
            parse_utc_timestamp=parse_utc_timestamp,
        )
    return BEAGLE_STREAM_SERVER_ACCESS_TOKEN_STORE_SERVICE


def beagle_stream_server_integration_service() -> BeagleStreamServerIntegrationService:
    global BEAGLE_STREAM_SERVER_INTEGRATION_SERVICE
    if BEAGLE_STREAM_SERVER_INTEGRATION_SERVICE is None:
        BEAGLE_STREAM_SERVER_INTEGRATION_SERVICE = BeagleStreamServerIntegrationService(
            build_profile=build_profile,
            ensure_vm_secret=ensure_vm_secret,
            find_vm=find_vm,
            get_vm_config=get_vm_config,
            guest_exec_script_text=HOST_PROVIDER.guest_exec_script_text,
            load_beagle_stream_server_access_token=load_beagle_stream_server_access_token,
            parse_description_meta=metadata_support_service().parse_description_meta,
            public_manager_url=PUBLIC_MANAGER_URL,
            run_subprocess=subprocess.run,
            safe_slug=utility_support_service().safe_slug,
            store_beagle_stream_server_access_token=beagle_stream_server_access_token_store_service().store,
            beagle_stream_server_access_token_is_valid=beagle_stream_server_access_token_is_valid,
            beagle_stream_server_access_token_ttl_seconds=BEAGLE_STREAM_SERVER_ACCESS_TOKEN_TTL_SECONDS,
            ubuntu_beagle_default_guest_user=UBUNTU_BEAGLE_DEFAULT_GUEST_USER,
            utcnow=utcnow,
        )
    return BEAGLE_STREAM_SERVER_INTEGRATION_SERVICE


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
            resolve_vm_beagle_stream_server_pinned_pubkey=resolve_vm_beagle_stream_server_pinned_pubkey,
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
            wireguard_bootstrap_defaults=wireguard_bootstrap_defaults,
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


def beagle_stream_server_access_tokens_dir() -> Path:
    return beagle_stream_server_access_token_store_service().tokens_dir()


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


def _ubuntu_beagle_guest_firstboot_runtime(vmid: int) -> str:
    command = (
        "if systemctl is-active --quiet beagle-ubuntu-firstboot.service; then exit 11; fi; "
        "if [ -f /var/lib/beagle/ubuntu-firstboot.done ] || "
        "[ -f /var/lib/beagle/ubuntu-firstboot-callback.done ]; then exit 12; fi; "
        "exit 13"
    )
    try:
        payload = HOST_PROVIDER.guest_exec_bash(int(vmid), command, timeout_seconds=10, request_timeout=15)
    except Exception:
        return "unknown"
    pid = int(payload.get("pid", 0) or 0)
    if pid <= 0:
        return "unknown"
    for _ in range(12):
        try:
            status = HOST_PROVIDER.guest_exec_status(int(vmid), pid, timeout=5)
        except Exception:
            return "unknown"
        if not isinstance(status, dict) or not bool(status.get("exited")):
            time.sleep(0.5)
            continue
        exit_code = int(status.get("exitcode", 255) or 255)
        if exit_code == 11:
            return "active"
        if exit_code == 12:
            return "done"
        if exit_code == 13:
            return "inactive"
        return "unknown"
    return "unknown"


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
                    guest_firstboot_runtime = _ubuntu_beagle_guest_firstboot_runtime(int(vmid))
                    if guest_firstboot_runtime == "active":
                        raw_state["updated_at"] = utcnow()
                        raw_state["message"] = (
                            "Ubuntu firstboot laeuft weiterhin im Gast; der Host wartet auf den "
                            "regulaeren Callback- und Reboot-Abschluss."
                        )
                        save_ubuntu_beagle_state(token, raw_state)
                        return ubuntu_beagle_state_service().latest_for_vmid(vmid, include_credentials=include_credentials)
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


def _start_fleet_remediation_thread() -> None:
    global FLEET_REMEDIATION_THREAD, FLEET_REMEDIATION_STOP_EVENT
    if FLEET_REMEDIATION_THREAD is not None and FLEET_REMEDIATION_THREAD.is_alive():
        return
    stop_event = threading.Event()
    interval_seconds = max(60, int(FLEET_REMEDIATION_INTERVAL_SECONDS))

    def _worker() -> None:
        while not stop_event.is_set():
            try:
                result = fleet_http_surface_service().run_safe_auto_remediation(
                    requester="fleet-auto-remediation",
                    require_enabled=True,
                )
                applied = list(result.get("applied") or []) if isinstance(result, dict) else []
                failed = list(result.get("failed") or []) if isinstance(result, dict) else []
                if applied or failed:
                    structured_logger().info(
                        "fleet.remediation.worker_cycle",
                        applied_count=len(applied),
                        failed_count=len(failed),
                        dry_run=bool(result.get("dry_run", False)) if isinstance(result, dict) else False,
                    )
            except Exception as exc:
                structured_logger().error(
                    "fleet.remediation.worker_failed",
                    error=str(exc),
                )
            stop_event.wait(interval_seconds)

    thread = threading.Thread(target=_worker, name="fleet-remediation-worker", daemon=True)
    thread.start()
    FLEET_REMEDIATION_STOP_EVENT = stop_event
    FLEET_REMEDIATION_THREAD = thread


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
    return beagle_stream_server_integration_service().fetch_https_pinned_pubkey(url)


def guest_exec_text(vmid: int, script: str) -> tuple[int, str, str]:
    return beagle_stream_server_integration_service().guest_exec_text(vmid, script)


def beagle_stream_server_guest_user(vm: VmSummary, config: dict[str, Any] | None = None) -> str:
    return beagle_stream_server_integration_service().beagle_stream_server_guest_user(vm, config)


def register_beagle_stream_client_certificate_on_vm(vm: VmSummary, client_cert_pem: str, *, device_name: str) -> dict[str, Any]:
    return beagle_stream_server_integration_service().register_beagle_stream_client_certificate_on_vm(
        vm,
        client_cert_pem,
        device_name=device_name,
    )


def fetch_beagle_stream_server_identity(vm: VmSummary, guest_user: str) -> dict[str, Any]:
    return beagle_stream_server_integration_service().fetch_beagle_stream_server_identity(vm, guest_user)


def prepare_virtual_display_on_vm(vm: VmSummary, resolution: str) -> dict[str, Any]:
    return beagle_stream_server_integration_service().prepare_virtual_display_on_vm(vm, resolution=resolution)


def internal_beagle_stream_server_api_url(vm: VmSummary, profile: dict[str, Any] | None = None) -> str:
    return beagle_stream_server_integration_service().internal_beagle_stream_server_api_url(vm, profile)


def resolve_vm_beagle_stream_server_pinned_pubkey(vm: VmSummary) -> str:
    return beagle_stream_server_integration_service().resolve_vm_beagle_stream_server_pinned_pubkey(vm)


def ensure_vm_beagle_stream_server_pinned_pubkey(vm: VmSummary, secret: dict[str, Any]) -> dict[str, Any]:
    return vm_secret_bootstrap_service().ensure_vm_beagle_stream_server_pinned_pubkey(vm, secret)


def enrollment_token_path(token: str) -> Path:
    return enrollment_token_store_service().token_path(token)


def beagle_stream_server_access_token_path(token: str) -> Path:
    return beagle_stream_server_access_token_store_service().token_path(token)


def issue_enrollment_token(vm: VmSummary) -> tuple[str, dict[str, Any]]:
    return endpoint_enrollment_service().issue_enrollment_token(vm)


def load_enrollment_token(token: str) -> dict[str, Any] | None:
    return enrollment_token_store_service().load(token)


def issue_beagle_stream_server_access_token(vm: VmSummary) -> tuple[str, dict[str, Any]]:
    return beagle_stream_server_integration_service().issue_beagle_stream_server_access_token(vm)


def load_beagle_stream_server_access_token(token: str) -> dict[str, Any] | None:
    return beagle_stream_server_access_token_store_service().load(token)


def mark_enrollment_token_used(token: str, payload: dict[str, Any], *, endpoint_id: str) -> None:
    enrollment_token_store_service().mark_used(token, payload, endpoint_id=endpoint_id)


def enrollment_token_is_valid(payload: dict[str, Any] | None, *, endpoint_id: str = "") -> bool:
    return enrollment_token_store_service().is_valid(payload, endpoint_id=endpoint_id)


def beagle_stream_server_access_token_is_valid(payload: dict[str, Any] | None) -> bool:
    return beagle_stream_server_access_token_store_service().is_valid(payload)


def endpoint_token_path(token: str) -> Path:
    return endpoint_token_store_service().token_path(token)


def store_endpoint_token(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return endpoint_token_store_service().store(token, payload)


def load_endpoint_token(token: str) -> dict[str, Any] | None:
    payload = endpoint_token_store_service().load(token)
    if not isinstance(payload, dict):
        return None
    if str(payload.get("revoked_at", "") or "").strip():
        return None
    expires_at = str(payload.get("expires_at", "") or "").strip()
    if expires_at:
        try:
            text = expires_at[:-1] + "+00:00" if expires_at.endswith("Z") else expires_at
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if parsed.astimezone(timezone.utc) <= datetime.now(timezone.utc):
                return None
        except Exception:
            return None
    return payload


def rotate_beagle_stream_server_token(vm: VmSummary, *, grace_seconds: int | None = None) -> dict[str, Any]:
    secret = ensure_vm_secret(vm)
    old_token = str(secret.get("beagle_stream_server_token", "") or "").strip()
    new_token = token_urlsafe(32)
    generation = int(secret.get("beagle_stream_server_token_generation", 0) or 0) + 1
    rotated_at = utcnow()
    updated = dict(secret)
    updated["beagle_stream_server_token"] = new_token
    updated["beagle_stream_server_token_generation"] = generation
    updated["beagle_stream_server_token_rotated_at"] = rotated_at
    updated.pop("beagle_stream_server_pin", None)
    save_vm_secret(vm.node, vm.vmid, updated)

    endpoint_payload = {
        "endpoint_id": f"beagle-stream-server-vm{int(vm.vmid)}",
        "hostname": str(getattr(vm, "name", "") or f"vm-{int(vm.vmid)}").strip(),
        "vmid": int(vm.vmid),
        "node": str(vm.node or "").strip(),
        "role": "beagle-stream-server",
        "token_generation": generation,
    }
    endpoint_token_store_service().store(new_token, endpoint_payload)
    if old_token:
        grace = BEAGLE_STREAM_SERVER_TOKEN_ROTATION_GRACE_SECONDS if grace_seconds is None else max(0, int(grace_seconds))
        old_payload = dict(endpoint_payload)
        old_payload["token_generation"] = generation - 1
        old_payload["superseded_at"] = rotated_at
        if grace > 0:
            old_payload["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=grace)).isoformat()
        else:
            old_payload["revoked_at"] = rotated_at
        endpoint_token_store_service().store(old_token, old_payload)
    return {
        "token": new_token,
        "generation": generation,
        "rotated_at": rotated_at,
        "grace_seconds": BEAGLE_STREAM_SERVER_TOKEN_ROTATION_GRACE_SECONDS if grace_seconds is None else max(0, int(grace_seconds)),
    }


def issue_beagle_stream_client_pairing_token(vm: VmSummary, endpoint_identity: dict[str, Any], device_name: str) -> dict[str, Any]:
    endpoint_id = str(endpoint_identity.get("endpoint_id", "") or "").strip()
    hostname = str(endpoint_identity.get("hostname", "") or "").strip()
    token = pairing_service().issue_token(
        {
            "scope": "beagle-stream-client.pair",
            "vmid": int(vm.vmid),
            "node": str(vm.node),
            "endpoint_id": endpoint_id,
            "hostname": hostname,
            "device_name": str(device_name or "").strip(),
            "pairing_secret": "",
        }
    )
    payload = pairing_service().validate_token(token) or {}
    pairing_secret = str(token or "").strip()
    return {
        "ok": True,
        "token": token,
        "expires_at": str(payload.get("expires_at", "") or ""),
    }


def exchange_beagle_stream_client_pairing_token(vm: VmSummary, endpoint_identity: dict[str, Any], pairing_token: str) -> dict[str, Any]:
    payload = pairing_service().consume_token(pairing_token)
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid or expired pairing token"}

    if int(payload.get("vmid", -1)) != int(vm.vmid) or str(payload.get("node", "")).strip() != str(vm.node).strip():
        return {"ok": False, "error": "pairing token scope mismatch"}

    scoped_endpoint_id = str(payload.get("endpoint_id", "") or "").strip()
    identity_endpoint_id = str(endpoint_identity.get("endpoint_id", "") or "").strip()
    if scoped_endpoint_id and identity_endpoint_id and scoped_endpoint_id != identity_endpoint_id:
        return {"ok": False, "error": "pairing token endpoint mismatch"}

    pairing_secret = str(payload.get("pairing_secret", "") or "").strip() or str(pairing_token or "").strip()
    if not pairing_secret:
        return {"ok": False, "error": "pairing token missing secret"}
    device_name = str(payload.get("device_name", "") or "").strip() or f"beagle-vm{vm.vmid}-client"

    status, _, body = proxy_beagle_stream_server_request(
        vm,
        request_path="/api/pair-token",
        query="",
        method="POST",
        body=json.dumps({"token": pairing_secret, "name": device_name}, separators=(",", ":"), ensure_ascii=True).encode("utf-8"),
        request_headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    if int(status) >= 400:
        return {"ok": False, "error": f"beagle-stream-server token exchange failed with HTTP {int(status)}"}

    try:
        response_payload = json.loads((body or b"{}").decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        response_payload = {}
    if not bool((response_payload or {}).get("status")):
        return {"ok": False, "error": "beagle-stream-server token exchange rejected"}
    return {"ok": True}


def beagle_stream_server_proxy_ticket_url(token: str) -> str:
    return beagle_stream_server_integration_service().beagle_stream_server_proxy_ticket_url(token)


def proxy_beagle_stream_server_request(vm: VmSummary, *, request_path: str, query: str, method: str, body: bytes | None, request_headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
    return beagle_stream_server_integration_service().proxy_beagle_stream_server_request(
        vm,
        request_path=request_path,
        query=query,
        method=method,
        body=body,
        request_headers=request_headers,
    )


DEFAULT_CREDENTIALS = load_shell_env_file(CREDENTIALS_ENV_FILE)


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
        "beagle_stream_client_port": base,
        "beagle_stream_server_api_port": base + 1,
        "https_port": base + 1,
        "rtsp_port": base + 21,
    }


def installer_template_patch_service() -> InstallerTemplatePatchService:
    global INSTALLER_TEMPLATE_PATCH_SERVICE
    if INSTALLER_TEMPLATE_PATCH_SERVICE is None:
        INSTALLER_TEMPLATE_PATCH_SERVICE = InstallerTemplatePatchService()
    return INSTALLER_TEMPLATE_PATCH_SERVICE


def installer_log_service() -> InstallerLogService:
    global INSTALLER_LOG_SERVICE
    if INSTALLER_LOG_SERVICE is None:
        INSTALLER_LOG_SERVICE = InstallerLogService(
            log_dir=runtime_paths_service().data_dir() / "installer-logs",
            signing_secret=_bootstrap_secret("installer_log_token_secret", INSTALLER_LOG_TOKEN_SECRET),
            token_ttl_seconds=INSTALLER_LOG_TOKEN_TTL_SECONDS,
            utcnow=utcnow,
        )
    return INSTALLER_LOG_SERVICE


def issue_installer_log_context(*, vmid: int, node: str, script_kind: str, script_name: str) -> dict[str, str]:
    return installer_log_service().issue_log_context(
        vmid=vmid,
        node=node,
        script_kind=script_kind,
        script_name=script_name,
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
    return installer_template_patch_service().patch_installer_defaults(
        script_text,
        preset_name,
        preset_b64,
        installer_iso_url,
        installer_bootstrap_url,
        installer_payload_url,
        writer_variant,
    )


def patch_windows_installer_defaults(
    script_text: str,
    preset_name: str,
    preset_b64: str,
    installer_iso_url: str,
    writer_variant: str,
) -> str:
    return installer_template_patch_service().patch_windows_installer_defaults(
        script_text,
        preset_name,
        preset_b64,
        installer_iso_url,
        writer_variant,
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


def quick_beagle_stream_server_status(vmid: int) -> dict[str, Any]:
    return installer_prep_service().quick_beagle_stream_server_status(vmid)


def default_installer_prep_state(vm: VmSummary, beagle_stream_server_status: dict[str, Any] | None = None) -> dict[str, Any]:
    return installer_prep_service().default_state(vm, beagle_stream_server_status)


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
            configure_beagle_stream_server_guest_script=ROOT_DIR / "scripts" / "configure-beagle-stream-server-guest.sh",
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
            public_manager_url=PUBLIC_MANAGER_URL,
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
            ubuntu_beagle_cyberpunk_wallpaper_source=UBUNTU_BEAGLE_CYBERPUNK_WALLPAPER_SOURCE,
            ubuntu_beagle_default_bridge=UBUNTU_BEAGLE_DEFAULT_BRIDGE,
            ubuntu_beagle_default_cores=UBUNTU_BEAGLE_DEFAULT_CORES,
            ubuntu_beagle_default_desktop=UBUNTU_BEAGLE_DEFAULT_DESKTOP,
            ubuntu_beagle_default_disk_gb=UBUNTU_BEAGLE_DEFAULT_DISK_GB,
            ubuntu_beagle_default_guest_user=UBUNTU_BEAGLE_DEFAULT_GUEST_USER,
            ubuntu_beagle_default_keymap=UBUNTU_BEAGLE_DEFAULT_KEYMAP,
            ubuntu_beagle_default_locale=UBUNTU_BEAGLE_DEFAULT_LOCALE,
            ubuntu_beagle_default_package_presets=UBUNTU_BEAGLE_DEFAULT_PACKAGE_PRESETS,
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
            ubuntu_beagle_stream_server_url=UBUNTU_BEAGLE_STREAM_SERVER_URL,
            ubuntu_beagle_beagle_stream_server_url=UBUNTU_BEAGLE_STREAM_SERVER_URL,
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
    cleanup_vm_runtime_artifacts(
        vmid=int(vmid),
        actions_dir=actions_dir(),
        endpoints_dir=endpoints_dir(),
        installer_prep_dir=installer_prep_dir(),
        load_json_file=load_json_file,
        ubuntu_beagle_tokens_dir=ubuntu_beagle_state_service().tokens_dir(),
        usb_tunnel_auth_dir=vm_secret_bootstrap_service().usb_tunnel_auth_dir(),
        vm_secrets_dir=vm_secrets_dir(),
    )
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
    vmid_value = payload.get("vmid") if isinstance(payload, dict) else None
    if str(vmid_value or "").strip():
        cleanup_vm_runtime_artifacts(
            vmid=int(vmid_value),
            actions_dir=actions_dir(),
            endpoints_dir=endpoints_dir(),
            installer_prep_dir=installer_prep_dir(),
            load_json_file=load_json_file,
            ubuntu_beagle_tokens_dir=ubuntu_beagle_state_service().tokens_dir(),
            usb_tunnel_auth_dir=vm_secret_bootstrap_service().usb_tunnel_auth_dir(),
            vm_secrets_dir=vm_secrets_dir(),
        )
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
            control_env_file=Path("/etc/beagle/beagle-manager.env"),
            install_check_report_token=INSTALL_CHECK_REPORT_TOKEN,
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
            render_vm_windows_live_usb_script=render_vm_windows_live_usb_script,
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
            build_budget_alerts_payload=build_budget_alerts_payload,
            build_chargeback_payload=build_chargeback_payload,
            build_cost_model_payload=build_cost_model_payload,
            build_energy_csrd_payload=build_energy_csrd_payload,
            build_energy_config_payload=build_energy_config_payload,
            build_energy_green_hours_payload=build_energy_green_hours_payload,
            build_energy_nodes_payload=build_energy_nodes_payload,
            build_energy_rankings_payload=build_energy_rankings_payload,
            build_energy_trend_payload=build_energy_trend_payload,
            build_provisioning_catalog=build_provisioning_catalog,
            build_scheduler_config_payload=get_scheduler_config,
            build_scheduler_insights_payload=build_scheduler_insights_payload,
            execute_cost_model_update=update_cost_model_payload,
            execute_energy_hourly_profile_import=import_energy_hourly_profile,
            execute_scheduler_migration=execute_scheduler_migration,
            execute_scheduler_rebalance=execute_scheduler_rebalance,
            execute_scheduler_warm_pool_apply=apply_warm_pool_recommendations,
            execute_energy_config_update=update_energy_config_payload,
            execute_scheduler_config_update=update_scheduler_config,
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
            get_ipam_zone_leases=lambda zone_id: ipam_service().get_zone_leases(zone_id),
            get_ipam_zones=lambda: ipam_service().get_all_zones(),
            get_local_preflight=lambda: cluster_membership_service().local_preflight_kvm_libvirt(),
            get_storage_quota=lambda pool_name: storage_quota_service().get_pool_quota(pool_name),
            get_vm_config=get_vm_config,
            get_vm_firewall_profile=lambda vm_id: firewall_service().get_vm_profile(vm_id),
            host_provider_kind=BEAGLE_HOST_PROVIDER_KIND,
            list_cluster_members=lambda: cluster_membership_service().list_members(),
            list_bridges_inventory=lambda node="": HOST_PROVIDER.list_bridges(node),
            list_firewall_profiles=lambda: firewall_service().list_profiles(),
            list_gpu_inventory=lambda: gpu_inventory_service().list_gpus(),
            list_nodes_inventory=list_nodes_inventory,
            list_storage_inventory=list_storage_inventory,
            list_vms=list_vms,
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
            build_vm_profile=build_profile,
            dequeue_vm_actions=dequeue_vm_actions,
            device_registry_service=device_registry_service(),
            mdm_policy_service=mdm_policy_service(),
            attestation_service=attestation_service(),
            fleet_telemetry_service=fleet_telemetry_service(),
            alert_service=alert_service(),
            exchange_beagle_stream_client_pairing_token=exchange_beagle_stream_client_pairing_token,
            fetch_beagle_stream_server_identity=fetch_beagle_stream_server_identity,
            find_vm=find_vm,
            issue_beagle_stream_client_pairing_token=issue_beagle_stream_client_pairing_token,
            pool_manager_service=pool_manager_service(),
            prepare_virtual_display_on_vm=prepare_virtual_display_on_vm,
            register_beagle_stream_client_certificate_on_vm=register_beagle_stream_client_certificate_on_vm,
            service_name="beagle-control-plane",
            session_manager_service=session_manager_service(),
            store_action_result=store_action_result,
            store_support_bundle=store_support_bundle,
            summarize_action_result=summarize_action_result,
            utcnow=utcnow,
            version=VERSION,
        )
    return ENDPOINT_HTTP_SURFACE_SERVICE


def stream_policy_service() -> StreamPolicyService:
    global STREAM_POLICY_SERVICE
    if STREAM_POLICY_SERVICE is None:
        STREAM_POLICY_SERVICE = StreamPolicyService(
            state_file=runtime_paths_service().data_dir() / "stream-policies.json",
        )
    return STREAM_POLICY_SERVICE


def stream_http_surface_service() -> StreamHttpSurfaceService:
    global STREAM_HTTP_SURFACE_SERVICE
    if STREAM_HTTP_SURFACE_SERVICE is None:
        STREAM_HTTP_SURFACE_SERVICE = StreamHttpSurfaceService(
            state_file=runtime_paths_service().data_dir() / "streams" / "servers.json",
            build_vm_profile=build_profile,
            find_vm=find_vm,
            pool_manager_service=pool_manager_service(),
            stream_policy_service=stream_policy_service(),
            build_wireguard_peer_config=build_stream_allocate_wireguard_profile,
            issue_pairing_token=issue_stream_allocate_pairing_token,
            audit_event=audit_log_service().write_event,
            utcnow=utcnow,
            version=VERSION,
        )
    return STREAM_HTTP_SURFACE_SERVICE


def wireguard_mesh_service() -> WireguardMeshService:
    global WIREGUARD_MESH_SERVICE
    if WIREGUARD_MESH_SERVICE is None:
        WIREGUARD_MESH_SERVICE = WireguardMeshService(
            server_public_key=os.environ.get("BEAGLE_WIREGUARD_SERVER_PUBLIC_KEY", "").strip(),
            server_endpoint=os.environ.get("BEAGLE_WIREGUARD_SERVER_ENDPOINT", "").strip(),
            state_dir=runtime_paths_service().data_dir() / "wireguard-mesh",
        )
    return WIREGUARD_MESH_SERVICE


def wireguard_bootstrap_defaults() -> dict[str, Any]:
    if os.environ.get("BEAGLE_WIREGUARD_ENABLED", "").strip() not in {"1", "true", "yes", "on"}:
        return {}
    if not os.environ.get("BEAGLE_WIREGUARD_SERVER_PUBLIC_KEY", "").strip():
        return {}
    if not os.environ.get("BEAGLE_WIREGUARD_SERVER_ENDPOINT", "").strip():
        return {}
    return {
        "egress_mode": os.environ.get("BEAGLE_WIREGUARD_EGRESS_MODE", "full").strip() or "full",
        "egress_type": "wireguard",
        "egress_interface": os.environ.get("BEAGLE_WIREGUARD_INTERFACE", "wg-beagle").strip() or "wg-beagle",
    }


def register_wireguard_peer(endpoint_identity: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    identity = endpoint_identity if isinstance(endpoint_identity, dict) else {}
    request = payload if isinstance(payload, dict) else {}
    configured_defaults = wireguard_bootstrap_defaults()
    if not configured_defaults:
        raise PermissionError("wireguard mesh is not enabled on this server")

    endpoint_id = str(identity.get("endpoint_id") or identity.get("hostname") or "").strip()
    if not endpoint_id:
        raise PermissionError("missing endpoint identity")
    requested_device_id = str(request.get("device_id", "") or "").strip()
    if requested_device_id and requested_device_id != endpoint_id:
        raise PermissionError("endpoint scope mismatch")
    public_key = str(request.get("public_key", "") or "").strip()
    if not public_key:
        raise ValueError("missing public_key")

    dns_value = os.environ.get("BEAGLE_WIREGUARD_CLIENT_DNS", "").strip() or "1.1.1.1"
    allowed_ips_raw = os.environ.get("BEAGLE_WIREGUARD_ALLOWED_IPS", "").strip() or "10.88.0.0/16,192.168.123.0/24"
    allowed_ips = [item.strip() for item in re.split(r"[\s,]+", allowed_ips_raw) if item.strip()]
    cfg = wireguard_mesh_service().add_peer(
        endpoint_id,
        public_key,
        allowed_ips=allowed_ips,
        dns=dns_value,
    )
    return {
        "ok": True,
        "device_id": endpoint_id,
        "server_public_key": str(cfg.server_public_key or "").strip(),
        "server_endpoint": str(cfg.server_endpoint or "").strip(),
        "allowed_ips": ", ".join(cfg.allowed_ips or []),
        "client_ip": str(cfg.interface_ip or "").strip(),
        "dns": str(cfg.dns or "").strip(),
        "preshared_key": str(cfg.preshared_key or "").strip(),
    }


def build_stream_allocate_wireguard_profile(device_id: str, pool_id: str, user_id: str) -> dict[str, Any]:
    _ = pool_id
    _ = user_id
    config = wireguard_mesh_service().get_peer_config(str(device_id or "").strip())
    if config is None:
        return {}
    return {
        "interface_ip": str(config.interface_ip or "").strip(),
        "server_public_key": str(config.server_public_key or "").strip(),
        "server_endpoint": str(config.server_endpoint or "").strip(),
        "preshared_key": str(config.preshared_key or "").strip(),
        "allowed_ips": list(config.allowed_ips or []),
        "dns": str(config.dns or "").strip(),
    }


def issue_stream_allocate_pairing_token(vm_id: int, user_id: str, device_id: str) -> str:
    vm = find_vm(int(vm_id))
    if vm is None:
        return ""
    result = issue_beagle_stream_client_pairing_token(
        vm,
        {
            "endpoint_id": str(device_id or "").strip(),
            "hostname": str(device_id or "").strip(),
        },
        f"{str(user_id or '').strip()}@{str(device_id or '').strip()}",
    )
    if not isinstance(result, dict):
        return ""
    return str(result.get("token") or "").strip()


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
            register_wireguard_peer=register_wireguard_peer,
            service_name="beagle-control-plane",
            store_endpoint_report=endpoint_report_service().store,
            summarize_endpoint_report=summarize_endpoint_report,
            utcnow=utcnow,
            version=VERSION,
        )
    return ENDPOINT_LIFECYCLE_SURFACE_SERVICE


def public_beagle_stream_server_surface_service() -> PublicBeagleStreamServerSurfaceService:
    global PUBLIC_BEAGLE_STREAM_SERVER_SURFACE_SERVICE
    if PUBLIC_BEAGLE_STREAM_SERVER_SURFACE_SERVICE is None:
        PUBLIC_BEAGLE_STREAM_SERVER_SURFACE_SERVICE = PublicBeagleStreamServerSurfaceService(
            proxy_beagle_stream_server_request=proxy_beagle_stream_server_request,
            resolve_ticket_vm=beagle_stream_server_integration_service().resolve_ticket_vm,
        )
    return PUBLIC_BEAGLE_STREAM_SERVER_SURFACE_SERVICE


def vm_mutation_surface_service() -> VmMutationSurfaceService:
    global VM_MUTATION_SURFACE_SERVICE
    if VM_MUTATION_SURFACE_SERVICE is None:
        VM_MUTATION_SURFACE_SERVICE = VmMutationSurfaceService(
            attach_usb_to_guest=attach_usb_to_guest,
            build_vm_usb_state=build_vm_usb_state,
            find_vm=find_vm,
            invalidate_vm_cache=invalidate_vm_cache,
            issue_beagle_stream_server_access_token=issue_beagle_stream_server_access_token,
            rotate_beagle_stream_server_token=rotate_beagle_stream_server_token,
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
            beagle_stream_server_proxy_ticket_url=beagle_stream_server_proxy_ticket_url,
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
            reset_vm_to_snapshot=lambda vmid, snapshot_name: HOST_PROVIDER.reset_vm_to_snapshot(
                int(vmid),
                str(snapshot_name or "").strip(),
                timeout=None,
            ),
            delete_vm_snapshot=lambda vmid, snapshot_name: HOST_PROVIDER.delete_vm_snapshot(
                int(vmid),
                str(snapshot_name or "").strip(),
                timeout=None,
            ),
            clone_vm=lambda source_vmid, target_vmid, name="": HOST_PROVIDER.clone_vm(
                int(source_vmid),
                int(target_vmid),
                name=str(name or "").strip(),
                timeout=None,
            ),
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


def _cluster_nodes_for_scheduler() -> list[dict[str, Any]]:
    try:
        inventory = build_cluster_inventory()
    except Exception:
        inventory = {}
    nodes = inventory.get("nodes") if isinstance(inventory, dict) else []
    if isinstance(nodes, list) and nodes:
        return [item for item in nodes if isinstance(item, dict)]
    try:
        return [item for item in list_nodes_inventory() if isinstance(item, dict)]
    except Exception:
        return []


def _normalize_node_cpu_pct(raw_value: Any) -> float:
    try:
        value = float(raw_value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if value <= 1.0:
        value *= 100.0
    return max(0.0, min(100.0, value))


def _scheduler_node_capacities() -> list[NodeCapacity]:
    return _scheduler_node_capacities_for_hour(None)


def _default_hourly_profile(config: Any) -> dict[str, list[float]]:
    base_co2 = float(getattr(config, "co2_grams_per_kwh", 400.0) or 400.0)
    base_price = float(getattr(config, "electricity_price_per_kwh", 0.30) or 0.30)
    co2_values: list[float] = []
    price_values: list[float] = []
    for hour in range(24):
        if 10 <= hour <= 15:
            co2_values.append(round(base_co2 * 0.72, 2))
            price_values.append(round(base_price * 0.84, 4))
        elif 18 <= hour <= 21:
            co2_values.append(round(base_co2 * 1.16, 2))
            price_values.append(round(base_price * 1.11, 4))
        else:
            co2_values.append(round(base_co2, 2))
            price_values.append(round(base_price, 4))
    return {
        "co2_grams_per_kwh": co2_values,
        "electricity_price_per_kwh": price_values,
    }


def _energy_hourly_profile_file() -> Path:
    return DATA_DIR / "energy-hourly-profile.json"


def get_energy_hourly_profile() -> dict[str, list[float]]:
    carbon_config = energy_service().get_carbon_config()
    defaults = _default_hourly_profile(carbon_config)
    payload = load_json_file(_energy_hourly_profile_file(), {})
    if not isinstance(payload, dict):
        payload = {}

    def _normalize_series(name: str, fallback: list[float]) -> list[float]:
        raw = payload.get(name, fallback)
        if not isinstance(raw, list):
            raw = fallback
        values: list[float] = []
        for index in range(24):
            try:
                value = float(raw[index])
            except (IndexError, TypeError, ValueError):
                value = float(fallback[index])
            values.append(round(value, 4 if "price" in name else 2))
        return values

    return {
        "co2_grams_per_kwh": _normalize_series("co2_grams_per_kwh", defaults["co2_grams_per_kwh"]),
        "electricity_price_per_kwh": _normalize_series("electricity_price_per_kwh", defaults["electricity_price_per_kwh"]),
    }


def update_energy_hourly_profile(payload: dict[str, Any]) -> dict[str, list[float]]:
    current = get_energy_hourly_profile()
    next_payload = dict(current)
    for key in ("co2_grams_per_kwh", "electricity_price_per_kwh"):
        raw = payload.get(key)
        if isinstance(raw, list) and len(raw) >= 24:
            values: list[float] = []
            for index in range(24):
                try:
                    value = float(raw[index])
                except (TypeError, ValueError):
                    value = current[key][index]
                values.append(round(value, 4 if "price" in key else 2))
            next_payload[key] = values
    write_json_file(_energy_hourly_profile_file(), next_payload)
    return get_energy_hourly_profile()


def import_energy_hourly_profile(payload: dict[str, Any]) -> dict[str, list[float]]:
    imported = collect_import_payload(
        payload,
        retries_default=ENERGY_FEED_IMPORT_RETRIES,
        timeout_default=ENERGY_FEED_IMPORT_TIMEOUT_SECONDS,
        retry_backoff_default=ENERGY_FEED_IMPORT_RETRY_BACKOFF_SECONDS,
        node_id=CLUSTER_NODE_NAME,
        alert_fn=lambda message: alert_service().fire_alert(
            rule_id="energy_feed_import_failed",
            device_id=CLUSTER_NODE_NAME,
            metric="energy_feed_import",
            current_value=float(ENERGY_FEED_IMPORT_RETRIES),
            message=message,
        ),
    )
    return update_energy_hourly_profile(imported)


def _hourly_energy_signal(hour: int | None = None) -> tuple[float, float]:
    profile = get_energy_hourly_profile()
    selected_hour = datetime.now(timezone.utc).hour if hour is None else int(hour) % 24
    return (
        float(profile["electricity_price_per_kwh"][selected_hour]),
        float(profile["co2_grams_per_kwh"][selected_hour]),
    )


def _scheduler_node_capacities_for_hour(hour: int | None) -> list[NodeCapacity]:
    capacities: list[NodeCapacity] = []
    price_per_kwh, co2_per_kwh = _hourly_energy_signal(hour)
    for item in _cluster_nodes_for_scheduler():
        node_id = str(item.get("name") or item.get("node") or "").strip()
        if not node_id:
            continue
        status = str(item.get("status") or "unknown").strip().lower()
        max_cpu = int(item.get("maxcpu", 0) or 0)
        max_mem = int(item.get("maxmem", 0) or 0)
        used_mem = int(item.get("mem", 0) or 0)
        cpu_pct = _normalize_node_cpu_pct(item.get("cpu", 0))
        total_ram_mib = max(0, max_mem // (1024 * 1024))
        free_ram_mib = max(0, (max_mem - used_mem) // (1024 * 1024))
        free_cpu_cores = max(0, int(round(max_cpu * (100.0 - cpu_pct) / 100.0)))
        gpu_slots_free = int(
            item.get("gpu_slots_free")
            or item.get("free_gpu_slots")
            or item.get("gpu_free")
            or item.get("gpu_count")
            or 0
        )
        if status not in {"online", "ready", "ok"}:
            cpu_pct = 100.0
            free_cpu_cores = 0
            free_ram_mib = 0
            gpu_slots_free = 0
        capacities.append(
            NodeCapacity(
                node_id=node_id,
                total_cpu_cores=max_cpu,
                total_ram_mib=total_ram_mib,
                free_cpu_cores=free_cpu_cores,
                free_ram_mib=free_ram_mib,
                gpu_slots_free=max(0, gpu_slots_free),
                predicted_cpu_pct_4h=cpu_pct,
                gpu_utilization_pct=float(item.get("gpu_utilization_pct", 0.0) or 0.0),
                predicted_gpu_utilization_pct_4h=float(item.get("predicted_gpu_utilization_pct_4h", 0.0) or 0.0),
                energy_price_per_kwh=price_per_kwh,
                carbon_intensity_g_per_kwh=co2_per_kwh,
            )
        )
    return capacities


def _scheduler_vm_assignments() -> list[dict[str, Any]]:
    capacities = {node.node_id: node for node in _scheduler_node_capacities()}
    running_by_node: dict[str, list[VmSummary]] = {}
    for vm in list_vms(refresh=True):
        status = str(getattr(vm, "status", "") or "").strip().lower()
        if status not in {"running", "paused"}:
            continue
        node_id = str(getattr(vm, "node", "") or "").strip()
        if not node_id:
            continue
        running_by_node.setdefault(node_id, []).append(vm)

    assignments: list[dict[str, Any]] = []
    for node_id, items in running_by_node.items():
        node_capacity = capacities.get(node_id)
        cpu_pct_per_vm = 0.0
        if node_capacity is not None and items:
            cpu_pct_per_vm = round(node_capacity.predicted_cpu_pct_4h / len(items), 2)
        for vm in items:
            assignments.append(
                {
                    "vmid": int(getattr(vm, "vmid", 0) or 0),
                    "node_id": node_id,
                    "cpu_pct": cpu_pct_per_vm,
                }
            )
    return assignments


def smart_scheduler_service() -> SmartSchedulerService:
    global SMART_SCHEDULER_SERVICE
    if SMART_SCHEDULER_SERVICE is None:
        SMART_SCHEDULER_SERVICE = SmartSchedulerService(
            list_nodes=_scheduler_node_capacities,
        )
    return SMART_SCHEDULER_SERVICE


def _smart_pick_pool_node(
    *,
    required_cpu_cores: int,
    required_ram_mib: int,
    gpu_required: bool,
    preferred_hour: int | None = None,
    green_hours: list[int] | None = None,
    green_scheduling_enabled: bool = True,
    allowed_nodes: list[str] | None = None,
) -> dict[str, Any]:
    scheduler_config = get_scheduler_config()
    selected_hour = preferred_hour if preferred_hour is not None else datetime.now(timezone.utc).hour
    capacities = _scheduler_node_capacities_for_hour(selected_hour)
    allowed = {str(node).strip() for node in (allowed_nodes or []) if str(node).strip()}
    if allowed:
        capacities = [item for item in capacities if item.node_id in allowed]
    scheduler = SmartSchedulerService(list_nodes=lambda: capacities)
    result = scheduler.pick_node(
        required_cpu_cores=int(required_cpu_cores or 1),
        required_ram_mib=int(required_ram_mib or 1024),
        gpu_required=bool(gpu_required),
        preferred_hour=selected_hour,
        green_hours=list(green_hours or scheduler_config.get("green_hours", [])),
        green_scheduling_enabled=bool(scheduler_config.get("green_scheduling_enabled")) and bool(green_scheduling_enabled),
    )
    return {
        "node_id": result.node_id,
        "reason": result.reason,
        "confidence": result.confidence,
        "alternative_nodes": list(result.alternative_nodes or []),
    }


def build_warm_pool_recommendations() -> list[dict[str, Any]]:
    scheduler_config = get_scheduler_config()
    minutes_ahead = int(scheduler_config.get("prewarm_minutes_ahead", 15) or 15)
    recommendations: list[dict[str, Any]] = []
    for pool in pool_manager_service().list_pools():
        pool_id = str(pool.pool_id or "").strip()
        desktops = pool_manager_service().list_pool_desktops(pool_id)
        free_slots = sum(1 for item in desktops if str(item.get("state") or "") == "free")
        active_slots = sum(1 for item in desktops if str(item.get("state") or "") == "in_use")
        prewarm_events = pool_manager_service().list_prewarm_events(pool_id=pool_id)[:50]
        hits = sum(1 for item in prewarm_events if str(item.get("outcome") or "") == "hit")
        misses = sum(1 for item in prewarm_events if str(item.get("outcome") or "") == "miss")
        miss_rate = round(misses / max(1, hits + misses), 4)
        target = max(int(pool.min_pool_size), int(pool.warm_pool_size))
        if misses > hits:
            target = min(int(pool.max_pool_size), max(target, free_slots + misses))
        elif free_slots > max(1, active_slots) and hits == 0:
            target = max(int(pool.min_pool_size), min(target, free_slots - 1))
        if target == int(pool.warm_pool_size):
            continue
        recommendations.append(
            {
                "pool_id": pool_id,
                "current_warm_pool_size": int(pool.warm_pool_size),
                "recommended_warm_pool_size": int(target),
                "free_slots": int(free_slots),
                "active_slots": int(active_slots),
                "prewarm_hits": int(hits),
                "prewarm_misses": int(misses),
                "miss_rate": miss_rate,
                "minutes_ahead": minutes_ahead,
            }
        )
    recommendations.sort(key=lambda item: (item["miss_rate"], item["prewarm_misses"]), reverse=True)
    return recommendations


def apply_warm_pool_recommendations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    requested = payload.get("recommendations")
    items = requested if isinstance(requested, list) else build_warm_pool_recommendations()
    applied: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        pool_id = str(item.get("pool_id") or "").strip()
        if not pool_id:
            continue
        try:
            target_size = int(item.get("recommended_warm_pool_size") or 0)
        except (TypeError, ValueError):
            continue
        pool_info = pool_manager_service().scale_pool(pool_id, target_size)
        applied.append({"pool_id": pool_id, "applied_warm_pool_size": int(pool_info.warm_pool_size)})
    return applied


def usage_tracking_service() -> UsageTrackingService:
    global USAGE_TRACKING_SERVICE
    if USAGE_TRACKING_SERVICE is None:
        USAGE_TRACKING_SERVICE = UsageTrackingService()
    return USAGE_TRACKING_SERVICE


def cost_model_service() -> CostModelService:
    global COST_MODEL_SERVICE
    if COST_MODEL_SERVICE is None:
        COST_MODEL_SERVICE = CostModelService()
    return COST_MODEL_SERVICE


def energy_service() -> EnergyService:
    global ENERGY_SERVICE
    if ENERGY_SERVICE is None:
        ENERGY_SERVICE = EnergyService(utcnow=utcnow)
    return ENERGY_SERVICE


def metrics_collector_service() -> MetricsCollector:
    global METRICS_COLLECTOR_SERVICE
    if METRICS_COLLECTOR_SERVICE is None:
        METRICS_COLLECTOR_SERVICE = MetricsCollector(utcnow=utcnow)
    return METRICS_COLLECTOR_SERVICE


def workload_pattern_analyzer_service() -> WorkloadPatternAnalyzer:
    global WORKLOAD_PATTERN_ANALYZER_SERVICE
    if WORKLOAD_PATTERN_ANALYZER_SERVICE is None:
        WORKLOAD_PATTERN_ANALYZER_SERVICE = WorkloadPatternAnalyzer()
    return WORKLOAD_PATTERN_ANALYZER_SERVICE


def _scheduler_config_file() -> Path:
    return DATA_DIR / "scheduler-config.json"


def get_scheduler_config() -> dict[str, Any]:
    defaults = {
        "green_scheduling_enabled": False,
        "prewarm_minutes_ahead": 15,
        "saved_cpu_hours": 0.0,
        "green_hours": [],
        "warm_pool_auto_apply_enabled": False,
        "warm_pool_auto_apply_max_pools_per_run": 3,
        "warm_pool_auto_apply_max_increase": 2,
        "warm_pool_auto_apply_min_miss_rate": 0.35,
        "warm_pool_auto_apply_cooldown_minutes": 30,
        "warm_pool_auto_apply_last_run_at": "",
    }
    data = load_json_file(_scheduler_config_file(), {})
    if not isinstance(data, dict):
        data = {}
    config = {**defaults, **data}
    config["green_scheduling_enabled"] = bool(config.get("green_scheduling_enabled"))
    try:
        config["prewarm_minutes_ahead"] = max(5, min(180, int(config.get("prewarm_minutes_ahead", 15) or 15)))
    except (TypeError, ValueError):
        config["prewarm_minutes_ahead"] = 15
    try:
        config["saved_cpu_hours"] = round(float(config.get("saved_cpu_hours", 0.0) or 0.0), 4)
    except (TypeError, ValueError):
        config["saved_cpu_hours"] = 0.0
    raw_green_hours = config.get("green_hours", [])
    if not isinstance(raw_green_hours, list):
        raw_green_hours = []
    normalized_hours: list[int] = []
    for value in raw_green_hours:
        try:
            hour = int(value)
        except (TypeError, ValueError):
            continue
        if 0 <= hour <= 23 and hour not in normalized_hours:
            normalized_hours.append(hour)
    config["green_hours"] = sorted(normalized_hours)
    config.update(normalize_auto_apply_config(config))
    return config


def update_scheduler_config(payload: dict[str, Any]) -> dict[str, Any]:
    config = get_scheduler_config()
    if "green_scheduling_enabled" in payload:
        config["green_scheduling_enabled"] = bool(payload.get("green_scheduling_enabled"))
    if "prewarm_minutes_ahead" in payload:
        try:
            config["prewarm_minutes_ahead"] = max(5, min(180, int(payload.get("prewarm_minutes_ahead") or 15)))
        except (TypeError, ValueError):
            pass
    if "green_hours" in payload:
        raw_green_hours = payload.get("green_hours")
        if isinstance(raw_green_hours, list):
            values = []
            for item in raw_green_hours:
                try:
                    hour = int(item)
                except (TypeError, ValueError):
                    continue
                if 0 <= hour <= 23 and hour not in values:
                    values.append(hour)
            config["green_hours"] = sorted(values)
    for key in (
        "warm_pool_auto_apply_enabled",
        "warm_pool_auto_apply_max_pools_per_run",
        "warm_pool_auto_apply_max_increase",
        "warm_pool_auto_apply_min_miss_rate",
        "warm_pool_auto_apply_cooldown_minutes",
    ):
        if key in payload:
            config[key] = payload.get(key)
    config.update(normalize_auto_apply_config(config))
    write_json_file(_scheduler_config_file(), config)
    return get_scheduler_config()


def build_cost_model_payload() -> dict[str, Any]:
    model = cost_model_service().get_cost_model()
    budgets = [
        {
            "department": item.department,
            "monthly_budget": float(item.monthly_budget),
            "alert_at_percent": int(item.alert_at_percent),
            "last_alerted_at": str(item.last_alerted_at or ""),
        }
        for item in cost_model_service().list_budget_alerts()
    ]
    return {
        "model": {
            "cpu_hour_cost": float(model.cpu_hour_cost),
            "ram_gb_hour_cost": float(model.ram_gb_hour_cost),
            "gpu_hour_cost": float(model.gpu_hour_cost),
            "storage_gb_month_cost": float(model.storage_gb_month_cost),
            "electricity_price_per_kwh": float(model.electricity_price_per_kwh),
        },
        "budgets": budgets,
    }


def update_cost_model_payload(payload: dict[str, Any]) -> dict[str, Any]:
    current = cost_model_service().get_cost_model()
    model_payload = payload if isinstance(payload, dict) else {}
    from cost_model_service import CostModel, BudgetAlert
    model = CostModel(
        cpu_hour_cost=float(model_payload.get("cpu_hour_cost", current.cpu_hour_cost) or current.cpu_hour_cost),
        ram_gb_hour_cost=float(model_payload.get("ram_gb_hour_cost", current.ram_gb_hour_cost) or current.ram_gb_hour_cost),
        gpu_hour_cost=float(model_payload.get("gpu_hour_cost", current.gpu_hour_cost) or current.gpu_hour_cost),
        storage_gb_month_cost=float(model_payload.get("storage_gb_month_cost", current.storage_gb_month_cost) or current.storage_gb_month_cost),
        electricity_price_per_kwh=float(model_payload.get("electricity_price_per_kwh", current.electricity_price_per_kwh) or current.electricity_price_per_kwh),
    )
    cost_model_service().set_cost_model(model)
    carbon = energy_service().get_carbon_config()
    carbon.electricity_price_per_kwh = model.electricity_price_per_kwh
    energy_service().set_carbon_config(carbon)
    budget_payload = payload.get("budget_alert") if isinstance(payload.get("budget_alert"), dict) else None
    if budget_payload:
        department = str(budget_payload.get("department") or "").strip()
        if department:
            cost_model_service().set_budget_alert(
                BudgetAlert(
                    department=department,
                    monthly_budget=float(budget_payload.get("monthly_budget", 0.0) or 0.0),
                    alert_at_percent=int(budget_payload.get("alert_at_percent", 80) or 80),
                    last_alerted_at=str(budget_payload.get("last_alerted_at") or ""),
                )
            )
    return build_cost_model_payload()


def build_energy_config_payload() -> dict[str, Any]:
    config = energy_service().get_carbon_config()
    return {
        "carbon_config": {
            "co2_grams_per_kwh": float(config.co2_grams_per_kwh),
            "electricity_price_per_kwh": float(config.electricity_price_per_kwh),
        },
        "scheduler": get_scheduler_config(),
        "hourly_profile": get_energy_hourly_profile(),
    }


def build_energy_green_hours_payload() -> dict[str, Any]:
    config = energy_service().get_carbon_config()
    scheduler = get_scheduler_config()
    hourly_profile = get_energy_hourly_profile()
    green_hours = set(int(value) for value in scheduler.get("green_hours", []))
    current_hour = datetime.now(timezone.utc).hour
    hourly: list[dict[str, Any]] = []
    for hour in range(24):
        active = hour in green_hours
        hourly.append(
            {
                "hour": hour,
                "is_green_hour": active,
                "active_now": hour == current_hour and active,
                "estimated_co2_grams_per_kwh": round(float(hourly_profile["co2_grams_per_kwh"][hour]), 2),
                "estimated_electricity_price_per_kwh": round(float(hourly_profile["electricity_price_per_kwh"][hour]), 4),
            }
        )
    return {
        "co2_grams_per_kwh": round(float(config.co2_grams_per_kwh or 0.0), 2),
        "electricity_price_per_kwh": round(float(config.electricity_price_per_kwh or 0.0), 4),
        "configured_green_hours": sorted(green_hours),
        "current_hour": current_hour,
        "hourly": hourly,
    }


def update_energy_config_payload(payload: dict[str, Any]) -> dict[str, Any]:
    current = energy_service().get_carbon_config()
    from energy_service import CarbonConfig
    config = CarbonConfig(
        co2_grams_per_kwh=float(payload.get("co2_grams_per_kwh", current.co2_grams_per_kwh) or current.co2_grams_per_kwh),
        electricity_price_per_kwh=float(payload.get("electricity_price_per_kwh", current.electricity_price_per_kwh) or current.electricity_price_per_kwh),
    )
    energy_service().set_carbon_config(config)
    hourly_profile_payload = payload.get("hourly_profile")
    if isinstance(hourly_profile_payload, dict):
        update_energy_hourly_profile(hourly_profile_payload)
    model = cost_model_service().get_cost_model()
    model.electricity_price_per_kwh = config.electricity_price_per_kwh
    cost_model_service().set_cost_model(model)
    if isinstance(payload.get("scheduler"), dict):
        update_scheduler_config(payload["scheduler"])
    return build_energy_config_payload()


def build_scheduler_insights_payload() -> dict[str, Any]:
    nodes = _cluster_nodes_for_scheduler()
    capacities = {node.node_id: node for node in _scheduler_node_capacities()}
    assignments = _scheduler_vm_assignments()
    scheduler_config = get_scheduler_config()
    vm_counts: dict[str, int] = {}
    for item in assignments:
        node_id = str(item.get("node_id") or "").strip()
        if node_id:
            vm_counts[node_id] = vm_counts.get(node_id, 0) + 1

    heatmap: list[dict[str, Any]] = []
    for item in nodes:
        node_id = str(item.get("name") or item.get("node") or "").strip()
        if not node_id:
            continue
        cpu_pct = _normalize_node_cpu_pct(item.get("cpu", 0))
        max_mem = int(item.get("maxmem", 0) or 0)
        used_mem = int(item.get("mem", 0) or 0)
        mem_pct = round((used_mem / max_mem) * 100.0, 2) if max_mem > 0 else 0.0
        capacity = capacities.get(node_id)
        heatmap.append(
            {
                "node_id": node_id,
                "status": str(item.get("status") or "unknown").strip() or "unknown",
                "vm_count": vm_counts.get(node_id, 0),
                "cpu_pct": round(cpu_pct, 2),
                "mem_pct": mem_pct,
                "predicted_cpu_pct_4h": round(float(getattr(capacity, "predicted_cpu_pct_4h", cpu_pct) or cpu_pct), 2),
                "green_scheduling_enabled": bool(scheduler_config.get("green_scheduling_enabled")),
            }
        )

    prewarm_candidates: list[dict[str, Any]] = []
    analyzer = workload_pattern_analyzer_service()
    minutes_ahead = int(scheduler_config.get("prewarm_minutes_ahead", 15) or 15)
    historical_trend: list[dict[str, Any]] = []
    historical_heatmap: list[dict[str, Any]] = []
    forecast_24h: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    pool_desktops_by_vmid = {
        int(item.get("vmid") or 0): item
        for item in pool_manager_service().list_pool_desktops()
        if int(item.get("vmid") or 0) > 0
    }
    for item in nodes:
        node_id = str(item.get("name") or item.get("node") or "").strip()
        if not node_id:
            continue
        samples = metrics_collector_service().read_samples(node_id, days=7, vmid=None)
        daily_buckets: dict[str, list[float]] = {}
        hourly_buckets: dict[str, dict[int, list[float]]] = {}
        for sample in samples:
            day = str(getattr(sample, "timestamp", "")[:10] or "")
            if not day:
                continue
            value = float(getattr(sample, "cpu_pct", 0.0) or 0.0)
            daily_buckets.setdefault(day, []).append(value)
            try:
                hour = int(str(getattr(sample, "timestamp", "") or "")[11:13])
            except (TypeError, ValueError):
                continue
            hourly_buckets.setdefault(day, {}).setdefault(hour, []).append(value)
        series = [
            {"day": day, "avg_cpu_pct": round(sum(values) / len(values), 2)}
            for day, values in sorted(daily_buckets.items())[-7:]
            if values
        ]
        historical_trend.append({"node_id": node_id, "series": series})
        heatmap_days = []
        for day in sorted(hourly_buckets.keys())[-7:]:
            hour_values = []
            for hour in range(24):
                samples_for_hour = hourly_buckets.get(day, {}).get(hour, [])
                avg_value = round(sum(samples_for_hour) / len(samples_for_hour), 2) if samples_for_hour else 0.0
                hour_values.append(avg_value)
            heatmap_days.append({"day": day, "hours": hour_values})
        historical_heatmap.append({"node_id": node_id, "days": heatmap_days})
        if samples:
            profile = analyzer.analyze(node_id, samples)
            hourly = []
            for offset in range(24):
                hour = (now.hour + offset) % 24
                hourly.append(
                    {
                        "hour": hour,
                        "cpu_pct": round(float(analyzer.predict_load_at_hour(profile, hour) or 0.0), 2),
                    }
                )
            forecast_24h.append({"node_id": node_id, "hourly": hourly})

    current_hour = now.hour
    green_hours = set(int(value) for value in scheduler_config.get("green_hours", []))
    green_window_active = current_hour in green_hours if green_hours else False
    for vm in list_vms(refresh=True):
        node_id = str(getattr(vm, "node", "") or "").strip()
        if not node_id:
            continue
        samples = metrics_collector_service().read_samples(node_id, days=14, vmid=int(getattr(vm, "vmid", 0) or 0))
        if not samples:
            continue
        profile = analyzer.analyze(f"vm-{int(getattr(vm, 'vmid', 0) or 0)}", samples)
        if not smart_scheduler_service().should_prewarm(
            profile,
            minutes_ahead=minutes_ahead,
            green_scheduling_enabled=bool(scheduler_config.get("green_scheduling_enabled")),
            green_hours=list(green_hours),
            current_hour=current_hour,
        ):
            continue
        prewarm_candidates.append(
            {
                "vm_id": int(getattr(vm, "vmid", 0) or 0),
                "name": str(getattr(vm, "name", "") or f"vm-{int(getattr(vm, 'vmid', 0) or 0)}"),
                "node_id": node_id,
                "pool_id": str(pool_desktops_by_vmid.get(int(getattr(vm, "vmid", 0) or 0), {}).get("pool_id") or ""),
                "user_id": str(pool_desktops_by_vmid.get(int(getattr(vm, "vmid", 0) or 0), {}).get("user_id") or ""),
                "peak_hours": list(profile.peak_hours),
                "avg_cpu_pct": round(float(profile.avg_cpu_pct or 0.0), 2),
                "samples_analyzed": int(profile.samples_analyzed or 0),
                "green_window_active": green_window_active,
            }
        )

    recommendations = [
        {
            "vm_id": int(rec.vm_id),
            "current_node": rec.from_node,
            "recommended_node": rec.to_node,
            "reason": rec.reason,
            "auto_execute": bool(rec.auto_execute),
        }
        for rec in smart_scheduler_service().rebalance_cluster(assignments)[:5]
    ]
    warm_pool_recommendations = build_warm_pool_recommendations()
    auto_apply_cfg = normalize_auto_apply_config(scheduler_config)
    scheduler_config.update(auto_apply_cfg)
    auto_apply_status: dict[str, Any] = {
        "enabled": bool(auto_apply_cfg.get("warm_pool_auto_apply_enabled")),
        "ran": False,
        "reason": "disabled",
        "selected_count": 0,
        "applied": [],
        "last_run_at": str(auto_apply_cfg.get("warm_pool_auto_apply_last_run_at") or ""),
    }
    if auto_apply_status["enabled"]:
        now_utc = datetime.now(timezone.utc)
        can_run = should_run_auto_apply(
            last_run_at=str(auto_apply_cfg.get("warm_pool_auto_apply_last_run_at") or ""),
            cooldown_minutes=int(auto_apply_cfg.get("warm_pool_auto_apply_cooldown_minutes") or 30),
            now=now_utc,
        )
        if can_run:
            selected = select_recommendations_for_auto_apply(
                warm_pool_recommendations,
                max_pools_per_run=int(auto_apply_cfg.get("warm_pool_auto_apply_max_pools_per_run") or 3),
                max_increase=int(auto_apply_cfg.get("warm_pool_auto_apply_max_increase") or 2),
                min_miss_rate=float(auto_apply_cfg.get("warm_pool_auto_apply_min_miss_rate") or 0.35),
            )
            auto_apply_status["selected_count"] = int(len(selected))
            scheduler_config["warm_pool_auto_apply_last_run_at"] = utcnow()
            auto_apply_status["last_run_at"] = str(scheduler_config.get("warm_pool_auto_apply_last_run_at") or "")
            if selected:
                auto_apply_status["applied"] = apply_warm_pool_recommendations({"recommendations": selected})
                auto_apply_status["ran"] = True
                auto_apply_status["reason"] = "applied"
                warm_pool_recommendations = build_warm_pool_recommendations()
            else:
                auto_apply_status["reason"] = "no-eligible-recommendations"
        else:
            auto_apply_status["reason"] = "cooldown-active"
    prewarm_events = pool_manager_service().list_prewarm_events()
    saved_cpu_hours_by_pool: dict[str, dict[str, Any]] = {}
    saved_cpu_hours_by_user: dict[str, dict[str, Any]] = {}
    hit_count = 0
    miss_count = 0
    total_saved_wait_seconds = 0
    for event in prewarm_events:
        outcome = str(event.get("outcome") or "")
        if outcome == "hit":
            hit_count += 1
        elif outcome == "miss":
            miss_count += 1
        saved_wait_seconds = int(event.get("saved_wait_seconds") or 0)
        total_saved_wait_seconds += saved_wait_seconds
        contribution = round(saved_wait_seconds / 3600.0, 4)
        pool_id = str(event.get("pool_id") or "").strip() or "unassigned"
        user_id = str(event.get("user_id") or "").strip() or "ohne user"
        pool_bucket = saved_cpu_hours_by_pool.setdefault(pool_id, {"pool_id": pool_id, "hit_count": 0, "miss_count": 0, "saved_cpu_hours": 0.0})
        user_bucket = saved_cpu_hours_by_user.setdefault(user_id, {"user_id": user_id, "hit_count": 0, "miss_count": 0, "saved_cpu_hours": 0.0})
        if outcome == "hit":
            pool_bucket["hit_count"] += 1
            user_bucket["hit_count"] += 1
        elif outcome == "miss":
            pool_bucket["miss_count"] += 1
            user_bucket["miss_count"] += 1
        pool_bucket["saved_cpu_hours"] = round(float(pool_bucket["saved_cpu_hours"]) + contribution, 4)
        user_bucket["saved_cpu_hours"] = round(float(user_bucket["saved_cpu_hours"]) + contribution, 4)
    estimated_saved_cpu_hours = round(total_saved_wait_seconds / 3600.0, 2)
    scheduler_config["saved_cpu_hours"] = estimated_saved_cpu_hours
    write_json_file(_scheduler_config_file(), scheduler_config)
    return {
        "heatmap": heatmap,
        "recommendations": recommendations,
        "warm_pool_recommendations": warm_pool_recommendations,
        "warm_pool_auto_apply": auto_apply_status,
        "prewarm_candidates": prewarm_candidates[:5],
        "historical_trend": historical_trend,
        "historical_heatmap": historical_heatmap,
        "forecast_24h": forecast_24h,
        "config": scheduler_config,
        "saved_cpu_hours": round(float(scheduler_config.get("saved_cpu_hours", 0.0) or 0.0), 2),
        "saved_cpu_hours_by_pool": sorted(saved_cpu_hours_by_pool.values(), key=lambda item: (-float(item["saved_cpu_hours"]), item["pool_id"])),
        "saved_cpu_hours_by_user": sorted(saved_cpu_hours_by_user.values(), key=lambda item: (-float(item["saved_cpu_hours"]), item["user_id"])),
        "prewarm_hit_count": int(hit_count),
        "prewarm_miss_count": int(miss_count),
        "prewarm_hit_rate": round(hit_count / max(1, hit_count + miss_count), 4),
        "green_window_active": green_window_active,
    }


def execute_scheduler_migration(vmid: int, target_node: str, requester_identity: str = "") -> dict[str, Any]:
    result = migration_service().migrate_vm(
        int(vmid),
        target_node=str(target_node or "").strip(),
        live=True,
        copy_storage=False,
        requester_identity=str(requester_identity or "").strip(),
    )
    return result if isinstance(result, dict) else {"result": result}


def execute_scheduler_rebalance(requester_identity: str = "") -> dict[str, Any]:
    recommendations = smart_scheduler_service().rebalance_cluster(_scheduler_vm_assignments())
    executed: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for rec in recommendations[:5]:
        try:
            executed.append(
                execute_scheduler_migration(
                    int(rec.vm_id),
                    rec.to_node,
                    requester_identity=requester_identity,
                )
            )
        except Exception as exc:
            errors.append(
                {
                    "vm_id": int(rec.vm_id),
                    "from_node": rec.from_node,
                    "to_node": rec.to_node,
                    "error": str(exc),
                }
            )
    return {
        "recommendations": [
            {
                "vm_id": int(rec.vm_id),
                "from_node": rec.from_node,
                "to_node": rec.to_node,
                "reason": rec.reason,
            }
            for rec in recommendations[:5]
        ],
        "executed": executed,
        "errors": errors,
    }


def build_chargeback_payload(month: str, department: str | None = None) -> dict[str, Any]:
    target_month = str(month or "").strip() or datetime.now(timezone.utc).strftime("%Y-%m")
    selected_department = str(department or "").strip() or None
    usage_records = usage_tracking_service().get_usage(month=target_month, department=selected_department)
    report = cost_model_service().generate_chargeback_report(usage_records, target_month, selected_department)
    model = cost_model_service().get_cost_model()
    departments: dict[str, dict[str, Any]] = {}
    top_vms: dict[int, dict[str, Any]] = {}
    for entry in report.get("entries", []):
        if not isinstance(entry, dict):
            continue
        department_name = str(entry.get("department") or "unassigned").strip() or "unassigned"
        item = departments.setdefault(
            department_name,
            {
                "department": department_name,
                "session_count": 0,
                "cpu_hours": 0.0,
                "gpu_hours": 0.0,
                "energy_cost_eur": 0.0,
                "cpu_cost_eur": 0.0,
                "gpu_cost_eur": 0.0,
                "total_cost_eur": 0.0,
            },
        )
        cpu_hours = float(entry.get("cpu_hours", 0.0) or 0.0)
        gpu_hours = float(entry.get("gpu_hours", 0.0) or 0.0)
        energy_cost = float(entry.get("energy_cost", 0.0) or 0.0)
        item["session_count"] += int(entry.get("sessions", 0) or 0)
        item["cpu_hours"] += cpu_hours
        item["gpu_hours"] += gpu_hours
        item["energy_cost_eur"] += energy_cost
        item["cpu_cost_eur"] += cpu_hours * float(model.cpu_hour_cost or 0.0)
        item["gpu_cost_eur"] += gpu_hours * float(model.gpu_hour_cost or 0.0)
        item["total_cost_eur"] += float(entry.get("total_cost", 0.0) or 0.0)

    for record in usage_records:
        if not isinstance(record, dict):
            continue
        vm_id = int(record.get("vm_id", 0) or 0)
        if vm_id <= 0:
            continue
        item = top_vms.setdefault(
            vm_id,
            {
                "vm_id": vm_id,
                "department": str(record.get("department") or "").strip() or "unassigned",
                "user_id": str(record.get("user_id") or "").strip() or "unknown",
                "session_count": 0,
                "cpu_hours": 0.0,
                "gpu_hours": 0.0,
                "energy_cost_eur": 0.0,
                "total_cost_eur": 0.0,
            },
        )
        item["session_count"] += 1
        item["cpu_hours"] += float(record.get("cpu_hours", 0.0) or 0.0)
        item["gpu_hours"] += float(record.get("gpu_hours", 0.0) or 0.0)
        item["energy_cost_eur"] += float(record.get("energy_cost", 0.0) or 0.0)
        storage_gb = float(record.get("storage_gb", 0.0) or 0.0)
        item["total_cost_eur"] += (
            float(record.get("cpu_hours", 0.0) or 0.0) * float(model.cpu_hour_cost or 0.0)
            + float(record.get("gpu_hours", 0.0) or 0.0) * float(model.gpu_hour_cost or 0.0)
            + storage_gb * float(model.storage_gb_month_cost or 0.0) / 720.0
            + float(record.get("energy_cost", 0.0) or 0.0)
        )

    sorted_departments = sorted(departments.values(), key=lambda item: item["total_cost_eur"], reverse=True)
    for item in sorted_departments:
        for key in ("cpu_hours", "gpu_hours", "energy_cost_eur", "cpu_cost_eur", "gpu_cost_eur", "total_cost_eur"):
            item[key] = round(float(item.get(key, 0.0) or 0.0), 4)

    top_vm_rows = sorted(top_vms.values(), key=lambda item: float(item.get("total_cost_eur", 0.0) or 0.0), reverse=True)[:10]
    for item in top_vm_rows:
        for key in ("cpu_hours", "gpu_hours", "energy_cost_eur", "total_cost_eur"):
            item[key] = round(float(item.get(key, 0.0) or 0.0), 4)

    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    month_end = datetime(now.year + (1 if now.month == 12 else 0), 1 if now.month == 12 else now.month + 1, 1, tzinfo=timezone.utc)
    elapsed_days = max(1.0, (now - month_start).total_seconds() / 86400.0)
    total_days = max(1.0, (month_end - month_start).total_seconds() / 86400.0)
    forecast_multiplier = max(1.0, total_days / elapsed_days)
    total_cost_eur = round(float(report.get("total_cost", 0.0) or 0.0), 4)
    total_energy_cost_eur = round(sum(float(item.get("energy_cost_eur", 0.0) or 0.0) for item in sorted_departments), 4)
    by_department_user: dict[str, dict[str, dict[str, Any]]] = {}
    for record in usage_records:
        if not isinstance(record, dict):
            continue
        dept = str(record.get("department") or "unassigned").strip() or "unassigned"
        user_id = str(record.get("user_id") or "unknown").strip() or "unknown"
        dept_bucket = by_department_user.setdefault(dept, {})
        user_bucket = dept_bucket.setdefault(
            user_id,
            {
                "user_id": user_id,
                "session_count": 0,
                "cpu_hours": 0.0,
                "gpu_hours": 0.0,
                "energy_cost_eur": 0.0,
                "total_cost_eur": 0.0,
                "sessions": [],
            },
        )
        user_bucket["session_count"] += 1
        cpu_hours = float(record.get("cpu_hours", 0.0) or 0.0)
        gpu_hours = float(record.get("gpu_hours", 0.0) or 0.0)
        storage_gb = float(record.get("storage_gb", 0.0) or 0.0)
        energy_cost = float(record.get("energy_cost", 0.0) or 0.0)
        total_cost = (
            cpu_hours * float(model.cpu_hour_cost or 0.0)
            + gpu_hours * float(model.gpu_hour_cost or 0.0)
            + storage_gb * float(model.storage_gb_month_cost or 0.0) / 720.0
            + energy_cost
        )
        user_bucket["cpu_hours"] += cpu_hours
        user_bucket["gpu_hours"] += gpu_hours
        user_bucket["energy_cost_eur"] += energy_cost
        user_bucket["total_cost_eur"] += total_cost
        user_bucket["sessions"].append(
            {
                "session_id": str(record.get("session_id") or "").strip(),
                "pool_id": str(record.get("pool_id") or "").strip(),
                "vm_id": int(record.get("vm_id", 0) or 0),
                "start_time": str(record.get("start_time") or "").strip(),
                "end_time": str(record.get("end_time") or "").strip(),
                "cpu_hours": round(cpu_hours, 4),
                "gpu_hours": round(gpu_hours, 4),
                "energy_cost_eur": round(energy_cost, 4),
                "total_cost_eur": round(total_cost, 4),
            }
        )
    drilldown: list[dict[str, Any]] = []
    for department_name, users in sorted(by_department_user.items()):
        drilldown.append(
            {
                "department": department_name,
                "users": [
                    {
                        **{
                            key: round(float(value), 4) if key in {"cpu_hours", "gpu_hours", "energy_cost_eur", "total_cost_eur"} else value
                            for key, value in user_bucket.items()
                            if key != "sessions"
                        },
                        "sessions": sorted(user_bucket["sessions"], key=lambda item: item.get("start_time") or ""),
                    }
                    for _user_id, user_bucket in sorted(users.items())
                ],
            }
        )

    return {
        "month": target_month,
        "department": selected_department,
        "departments": sorted_departments,
        "entries": report.get("entries", []),
        "top_vms": top_vm_rows,
        "csv": str(report.get("csv") or ""),
        "total_cost_eur": total_cost_eur,
        "total_energy_cost_eur": total_energy_cost_eur,
        "forecast_total_cost_eur": round(total_cost_eur * forecast_multiplier, 4),
        "forecast_multiplier": round(forecast_multiplier, 3),
        "drilldown": drilldown,
    }


def build_budget_alerts_payload(month: str) -> list[dict[str, Any]]:
    target_month = str(month or "").strip() or datetime.now(timezone.utc).strftime("%Y-%m")
    chargeback = build_chargeback_payload(target_month)
    totals = {
        str(item.get("department") or "").strip(): float(item.get("total_cost_eur", 0.0) or 0.0)
        for item in chargeback.get("departments", [])
        if str(item.get("department") or "").strip()
    }
    alerts = cost_model_service().check_budget_alerts(totals, utcnow())
    normalized: list[dict[str, Any]] = []
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        current = float(alert.get("spent", 0.0) or 0.0)
        budget = float(alert.get("budget", 0.0) or 0.0)
        normalized.append(
            {
                "department": str(alert.get("department") or "").strip(),
                "current": round(current, 4),
                "budget": round(budget, 4),
                "percent": round(float(alert.get("percent", 0.0) or 0.0), 1),
                "threshold": int(alert.get("threshold", 0) or 0),
                "exceeded": current > budget if budget > 0 else False,
            }
        )
    return normalized


def build_energy_nodes_payload() -> list[dict[str, Any]]:
    target_month = datetime.now(timezone.utc).strftime("%Y-%m")
    payload: list[dict[str, Any]] = []
    for item in _cluster_nodes_for_scheduler():
        node_id = str(item.get("name") or item.get("node") or "").strip()
        if not node_id:
            continue
        samples = energy_service().get_samples(node_id, days=32)
        current_power = float(samples[-1].node_power_w) if samples else 0.0
        observed_max = max((float(sample.node_power_w or 0.0) for sample in samples), default=0.0)
        fallback_max = max(current_power * 1.25, 250.0 if current_power <= 0 else current_power)
        payload.append(
            {
                "node_id": node_id,
                "status": str(item.get("status") or "unknown").strip() or "unknown",
                "current_power_w": round(current_power, 2),
                "max_power_w": round(max(observed_max, fallback_max), 2),
                "month_kwh": round(energy_service().compute_energy_kwh(node_id, month=target_month, days=62), 4),
            }
        )
    return payload


def build_energy_rankings_payload() -> dict[str, list[dict[str, Any]]]:
    target_month = datetime.now(timezone.utc).strftime("%Y-%m")
    nodes = build_energy_nodes_payload()
    highest = sorted(nodes, key=lambda item: float(item.get("month_kwh", 0.0) or 0.0), reverse=True)[:5]
    lowest = sorted(nodes, key=lambda item: float(item.get("month_kwh", 0.0) or 0.0))[:5]
    vm_usage: dict[int, dict[str, Any]] = {}
    for record in usage_tracking_service().get_usage(month=target_month):
        if not isinstance(record, dict):
            continue
        vm_id = int(record.get("vm_id", 0) or 0)
        if vm_id <= 0:
            continue
        bucket = vm_usage.setdefault(
            vm_id,
            {
                "vm_id": vm_id,
                "department": str(record.get("department") or "unassigned").strip() or "unassigned",
                "user_id": str(record.get("user_id") or "unknown").strip() or "unknown",
                "energy_kwh": 0.0,
                "energy_cost_eur": 0.0,
                "session_count": 0,
            },
        )
        bucket["energy_kwh"] += float(record.get("energy_kwh", 0.0) or 0.0)
        bucket["energy_cost_eur"] += float(record.get("energy_cost", 0.0) or 0.0)
        bucket["session_count"] += 1
    vm_rows = list(vm_usage.values())
    for row in vm_rows:
        row["energy_kwh"] = round(float(row.get("energy_kwh", 0.0) or 0.0), 4)
        row["energy_cost_eur"] = round(float(row.get("energy_cost_eur", 0.0) or 0.0), 4)
    most_intensive_vms = sorted(vm_rows, key=lambda item: float(item.get("energy_kwh", 0.0) or 0.0), reverse=True)[:5]
    most_efficient_vms = [item for item in sorted(vm_rows, key=lambda item: float(item.get("energy_kwh", 0.0) or 0.0)) if float(item.get("energy_kwh", 0.0) or 0.0) > 0][:5]
    return {
        "highest_nodes": highest,
        "lowest_nodes": lowest,
        "most_intensive_vms": most_intensive_vms,
        "most_efficient_vms": most_efficient_vms,
    }


def build_energy_trend_payload(months: int = 6) -> list[dict[str, Any]]:
    months_back = max(1, min(24, int(months or 6)))
    now = datetime.now(timezone.utc)
    node_ids = [str(item.get("name") or item.get("node") or "").strip() for item in _cluster_nodes_for_scheduler()]
    node_ids = [node_id for node_id in node_ids if node_id]
    trend: list[dict[str, Any]] = []
    for offset in range(months_back - 1, -1, -1):
        year = now.year
        month_index = now.month - offset
        while month_index <= 0:
            month_index += 12
            year -= 1
        month_label = f"{year}-{month_index:02d}"
        total_kwh = 0.0
        for node_id in node_ids:
            total_kwh += energy_service().compute_energy_kwh(node_id, month=month_label, days=400)
        trend.append(
            {
                "month": month_label,
                "total_kwh": round(total_kwh, 4),
                "total_co2_kg": round(energy_service().compute_co2(total_kwh) / 1000.0, 4),
                "total_cost_eur": round(energy_service().compute_energy_cost(total_kwh), 4),
            }
        )
    return trend


def build_energy_csrd_payload(year: int, quarter: int) -> dict[str, Any]:
    node_ids = [str(item.get("name") or item.get("node") or "").strip() for item in _cluster_nodes_for_scheduler()]
    return energy_service().generate_csrd_report([node_id for node_id in node_ids if node_id], int(year), int(quarter))


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


def device_registry_service() -> DeviceRegistryService:
    global DEVICE_REGISTRY_SERVICE
    if DEVICE_REGISTRY_SERVICE is None:
        DEVICE_REGISTRY_SERVICE = DeviceRegistryService(
            utcnow=utcnow,
            device_repository=_device_repository(),
        )
    return DEVICE_REGISTRY_SERVICE


def mdm_policy_service() -> MDMPolicyService:
    global MDM_POLICY_SERVICE
    if MDM_POLICY_SERVICE is None:
        MDM_POLICY_SERVICE = MDMPolicyService()
    return MDM_POLICY_SERVICE


def attestation_service() -> AttestationService:
    global ATTESTATION_SERVICE
    if ATTESTATION_SERVICE is None:
        ATTESTATION_SERVICE = AttestationService(utcnow=utcnow)
    return ATTESTATION_SERVICE


def fleet_telemetry_service() -> FleetTelemetryService:
    global FLEET_TELEMETRY_SERVICE
    if FLEET_TELEMETRY_SERVICE is None:
        FLEET_TELEMETRY_SERVICE = FleetTelemetryService(utcnow=utcnow)
    return FLEET_TELEMETRY_SERVICE


def alert_service() -> AlertService:
    global ALERT_SERVICE
    if ALERT_SERVICE is None:
        ALERT_SERVICE = AlertService(
            state_file=ensure_data_dir() / "alert-service" / "state.json",
            utcnow=utcnow,
            webhook_fn=lambda payload: webhook_service().dispatch_event(
                event_type="beagle.fleet.alert",
                event_payload=payload,
            ),
        )
        ALERT_SERVICE.ensure_default_rules()
    return ALERT_SERVICE


def fleet_http_surface_service() -> FleetHttpSurfaceService:
    global FLEET_HTTP_SURFACE_SERVICE
    if FLEET_HTTP_SURFACE_SERVICE is None:
        FLEET_HTTP_SURFACE_SERVICE = FleetHttpSurfaceService(
            device_registry_service=device_registry_service(),
            mdm_policy_service=mdm_policy_service(),
            fleet_telemetry_service=fleet_telemetry_service(),
            alert_service=alert_service(),
            audit_event=audit_log_service().write_event,
            requester_identity=lambda: "",
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )
    return FLEET_HTTP_SURFACE_SERVICE


def mdm_policy_http_surface_service() -> MDMPolicyHttpSurfaceService:
    global MDM_POLICY_HTTP_SURFACE_SERVICE
    if MDM_POLICY_HTTP_SURFACE_SERVICE is None:
        MDM_POLICY_HTTP_SURFACE_SERVICE = MDMPolicyHttpSurfaceService(
            mdm_policy_service=mdm_policy_service(),
            requester_identity=lambda: "",
            audit_event=audit_log_service().write_event,
            service_name="beagle-control-plane",
            utcnow=utcnow,
            version=VERSION,
        )
    return MDM_POLICY_HTTP_SURFACE_SERVICE


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
            fetch_beagle_stream_server_identity=fetch_beagle_stream_server_identity,
            get_vm_config=get_vm_config,
            hosted_installer_iso_file=HOSTED_INSTALLER_ISO_FILE,
            hosted_installer_template_file=HOSTED_INSTALLER_TEMPLATE_FILE,
            hosted_live_usb_template_file=HOSTED_LIVE_USB_TEMPLATE_FILE,
            issue_enrollment_token=issue_enrollment_token,
            issue_installer_log_context=issue_installer_log_context,
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
            beagle_stream_server_guest_user=beagle_stream_server_guest_user,
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


def render_vm_windows_live_usb_script(vm: VmSummary) -> tuple[bytes, str]:
    return installer_script_service().render_windows_live_usb_script(vm)


def extract_bearer_token(header_value: str) -> str:
    return request_support_service().extract_bearer_token(header_value)
