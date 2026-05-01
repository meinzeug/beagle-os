#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOSTED_DOWNLOAD_LAYOUT_HELPER="$ROOT_DIR/scripts/lib/hosted_download_layout.sh"
INSTALL_DIR="${INSTALL_DIR:-/opt/beagle}"
CONFIG_DIR="${PVE_DCV_CONFIG_DIR:-/etc/beagle}"
HOST_ENV_FILE="${PVE_DCV_HOST_ENV_FILE:-$CONFIG_DIR/host.env}"
PROXY_ENV_FILE="${PVE_DCV_PROXY_ENV_FILE:-$CONFIG_DIR/beagle-proxy.env}"
SERVER_NAME="${PVE_DCV_PROXY_SERVER_NAME:-$(hostname -f 2>/dev/null || hostname)}"
LISTEN_PORT="${PVE_DCV_PROXY_LISTEN_PORT:-443}"
SITE_PORT="${BEAGLE_SITE_PORT:-443}"
DOWNLOADS_PATH="${PVE_DCV_DOWNLOADS_PATH:-/beagle-downloads}"
# shellcheck disable=SC1090
source "$HOSTED_DOWNLOAD_LAYOUT_HELPER"
HOST_ORIGIN_URL="$(beagle_host_origin_url "$SERVER_NAME" "$LISTEN_PORT")"
DOWNLOADS_BASE_URL="$(beagle_host_downloads_base_url "$SERVER_NAME" "$LISTEN_PORT" "$DOWNLOADS_PATH")"
PUBLIC_ARTIFACT_BASE_URL=""
FAILURES=0
STATUS_JSON_FILE="$INSTALL_DIR/dist/beagle-downloads-status.json"
REFRESH_STATUS_FILE="${PVE_DCV_STATUS_DIR:-/var/lib/beagle}/refresh.status.json"
BEAGLE_MANAGER_ENV_FILE="${PVE_DCV_BEAGLE_MANAGER_ENV_FILE:-$CONFIG_DIR/beagle-manager.env}"
BEAGLE_API_TOKEN=""
BEAGLE_HOST_PROVIDER="${BEAGLE_HOST_PROVIDER:-beagle}"
USB_TUNNEL_USER="${BEAGLE_USB_TUNNEL_SSH_USER:-beagle-tunnel}"
USB_TUNNEL_HOME="${BEAGLE_USB_TUNNEL_HOME:-}"
USB_TUNNEL_AUTH_ROOT="${BEAGLE_USB_TUNNEL_AUTH_ROOT:-/var/lib/beagle/usb-tunnel/$USB_TUNNEL_USER}"
WEB_UI_INDEX_FILE="${BEAGLE_WEB_UI_INDEX_FILE:-$INSTALL_DIR/website/index.html}"
WEB_UI_CONFIG_FILE="${BEAGLE_WEB_UI_CONFIG_FILE:-$INSTALL_DIR/website/beagle-web-ui-config.js}"
BEAGLE_PROXY_SITE_FILE="${BEAGLE_PROXY_SITE_FILE:-/etc/nginx/sites-available/beagle-proxy.conf}"
BEAGLE_PROXY_TLS_DIR="${BEAGLE_PROXY_TLS_DIR:-$CONFIG_DIR/tls}"
BEAGLE_CONTROL_SERVICE_FILE="${BEAGLE_CONTROL_SERVICE_FILE:-/etc/systemd/system/beagle-control-plane.service}"
BEAGLE_USB_TUNNEL_SSHD_DROPIN="${BEAGLE_USB_TUNNEL_SSHD_DROPIN:-/etc/ssh/sshd_config.d/90-beagle-usb-tunnel.conf}"

host_provider_kind() {
  local kind
  kind="$(printf '%s' "${BEAGLE_HOST_PROVIDER:-beagle}" | tr '[:upper:]' '[:lower:]')"
  case "$kind" in
    ""|pve)
      printf 'beagle\n'
      ;;
    *)
      printf '%s\n' "$kind"
      ;;
  esac
}

load_host_env() {
  if [[ -f "$HOST_ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$HOST_ENV_FILE"
  fi
  if [[ -f "$PROXY_ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$PROXY_ENV_FILE"
  fi

  SERVER_NAME="${PVE_DCV_PROXY_SERVER_NAME:-$SERVER_NAME}"
  LISTEN_PORT="${PVE_DCV_PROXY_LISTEN_PORT:-$LISTEN_PORT}"
  SITE_PORT="${BEAGLE_SITE_PORT:-$SITE_PORT}"
  DOWNLOADS_PATH="${PVE_DCV_DOWNLOADS_PATH:-$DOWNLOADS_PATH}"
  HOST_ORIGIN_URL="$(beagle_host_origin_url "$SERVER_NAME" "$LISTEN_PORT")"
  DOWNLOADS_BASE_URL="${PVE_DCV_DOWNLOADS_BASE_URL:-$(beagle_host_downloads_base_url "$SERVER_NAME" "$LISTEN_PORT" "$DOWNLOADS_PATH")}"
  PUBLIC_ARTIFACT_BASE_URL="$(beagle_public_artifact_base_url "$DOWNLOADS_BASE_URL" "${BEAGLE_PUBLIC_UPDATE_BASE_URL:-}")"

  if [[ -f "$BEAGLE_MANAGER_ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$BEAGLE_MANAGER_ENV_FILE"
    BEAGLE_API_TOKEN="${BEAGLE_MANAGER_API_TOKEN:-}"
    BEAGLE_HOST_PROVIDER="${BEAGLE_HOST_PROVIDER:-$BEAGLE_HOST_PROVIDER}"
  fi
  USB_TUNNEL_USER="${BEAGLE_USB_TUNNEL_SSH_USER:-$USB_TUNNEL_USER}"
  USB_TUNNEL_HOME="${BEAGLE_USB_TUNNEL_HOME:-$USB_TUNNEL_HOME}"
  USB_TUNNEL_AUTH_ROOT="${BEAGLE_USB_TUNNEL_AUTH_ROOT:-/var/lib/beagle/usb-tunnel/$USB_TUNNEL_USER}"
}

host_tls_cert_file() {
  if [[ -n "${BEAGLE_HOST_TLS_CERT_FILE:-}" ]]; then
    printf '%s\n' "$BEAGLE_HOST_TLS_CERT_FILE"
    return 0
  fi
  if [[ "$(host_provider_kind)" == "beagle" ]]; then
    printf '/etc/beagle/manager-ssl.pem\n'
    return 0
  fi
  printf '%s/beagle-proxy.crt\n' "$BEAGLE_PROXY_TLS_DIR"
}

site_origin_url() {
  if [[ "$SITE_PORT" == "443" ]]; then
    printf 'https://%s\n' "$SERVER_NAME"
    return 0
  fi
  printf 'https://%s:%s\n' "$SERVER_NAME" "$SITE_PORT"
}

record_failure() {
  FAILURES=$((FAILURES + 1))
}

check_file() {
  local path="$1"
  if [[ -f "$path" ]]; then
    echo "OK  file  $path"
    return 0
  fi
  echo "ERR file  $path"
  record_failure
}

check_http() {
  local url="$1"
  local auth_header="${2:-}"
  local method="${3:-HEAD}"
  local tls_cert_file
  local web_ui_origin
  tls_cert_file="$(host_tls_cert_file)"
  web_ui_origin="$(site_origin_url)"
  local -a curl_args=(curl -fsS --output /dev/null)
  [[ -n "$auth_header" ]] && curl_args+=(-H "$auth_header")
  if [[ "$method" == "HEAD" ]]; then
    curl_args+=(-I)
  fi
  if [[ ( "$url" == "${HOST_ORIGIN_URL}"* || "$url" == "${web_ui_origin}"* ) && -f "$tls_cert_file" ]]; then
    curl_args+=(--cacert "$tls_cert_file")
  fi
  if "${curl_args[@]}" "$url" >/dev/null 2>&1; then
    echo "OK  http  $url"
    return 0
  fi
  echo "ERR http  $url"
  record_failure
}

check_service_active() {
  local service="$1"
  if systemctl is-active --quiet "$service"; then
    echo "OK  svc   $service"
    return 0
  fi
  echo "ERR svc   $service"
  record_failure
}

check_local_control_plane_health() {
  local port
  port="${BEAGLE_MANAGER_LISTEN_PORT:-9088}"
  if curl -fsS --output /dev/null "http://127.0.0.1:${port}/healthz" >/dev/null 2>&1; then
    echo "OK  http  http://127.0.0.1:${port}/healthz"
    return 0
  fi
  echo "ERR http  http://127.0.0.1:${port}/healthz"
  record_failure
}

check_control_plane_novnc_rwpath() {
  if grep -Eq '^[[:space:]]*ReadWritePaths=.*(/etc/beagle/novnc)' "$BEAGLE_CONTROL_SERVICE_FILE"; then
    echo "OK  cfg   beagle-control-plane ReadWritePaths includes /etc/beagle/novnc"
    return 0
  fi
  echo "ERR cfg   beagle-control-plane missing ReadWritePaths=/etc/beagle/novnc"
  record_failure
}

check_control_plane_runtime_imports() {
  local service_dir="$INSTALL_DIR/beagle-host/services"
  local bin_dir="$INSTALL_DIR/beagle-host/bin"
  local required=(
    "service_registry.py"
    "job_queue_service.py"
    "job_worker.py"
    "jobs_http_surface.py"
    "prometheus_metrics.py"
    "health_aggregator.py"
    "structured_logger.py"
  )
  local missing=0
  local module
  for module in "${required[@]}"; do
    if [[ ! -f "$service_dir/$module" ]]; then
      echo "ERR file  $service_dir/$module"
      missing=1
    fi
  done
  if (( missing > 0 )); then
    record_failure
    return 1
  fi

  if python3 - "$bin_dir" "$service_dir" <<'PY' >/dev/null 2>&1
import sys
from pathlib import Path

bin_dir = Path(sys.argv[1])
service_dir = Path(sys.argv[2])
sys.path.insert(0, str(bin_dir))
sys.path.insert(0, str(service_dir))

import service_registry  # noqa: F401

required_attrs = ("job_queue_service", "jobs_http_surface", "structured_logger")
missing = [name for name in required_attrs if not hasattr(service_registry, name)]
if missing:
    raise SystemExit("missing service_registry attrs: " + ",".join(missing))
PY
  then
    echo "OK  py    control-plane service_registry import + job queue exports"
    return 0
  fi
  echo "ERR py    control-plane service_registry import + job queue exports"
  record_failure
  return 1
}

check_internal_callback_host() {
  local current_provider=""
  local callback_host=""

  current_provider="$(host_provider_kind)"
  if [[ "$current_provider" != "beagle" ]]; then
    return 0
  fi

  callback_host="${BEAGLE_INTERNAL_CALLBACK_HOST:-}"
  callback_host="${callback_host//\"/}"
  callback_host="${callback_host//\'/}"

  if [[ -z "$callback_host" ]]; then
    echo "ERR cfg   BEAGLE_INTERNAL_CALLBACK_HOST missing in $BEAGLE_MANAGER_ENV_FILE"
    record_failure
    return 1
  fi

  if [[ "$callback_host" == "localhost" || "$callback_host" == 127.* ]]; then
    echo "ERR cfg   BEAGLE_INTERNAL_CALLBACK_HOST must not be loopback ($callback_host)"
    record_failure
    return 1
  fi

  echo "OK  cfg   BEAGLE_INTERNAL_CALLBACK_HOST=$callback_host"
}

check_status_json() {
  local expected_installer_url=""
  local expected_bootstrap_url=""
  local expected_payload_url=""
  local expected_endpoint_iso_url=""

  expected_installer_url="$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-installer-host-latest.sh")"
  expected_bootstrap_url="$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-bootstrap-latest.tar.gz")"
  expected_payload_url="$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-payload-latest.tar.gz")"
  expected_endpoint_iso_url="$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "beagle-os-installer-amd64.iso")"

  python3 - "$STATUS_JSON_FILE" "$INSTALL_DIR/VERSION" "$expected_installer_url" "$expected_bootstrap_url" "$expected_payload_url" "$expected_endpoint_iso_url" "$SERVER_NAME" "$LISTEN_PORT" "$DOWNLOADS_PATH" "$INSTALL_DIR/dist/pve-thin-client-usb-installer-host-latest.sh" "$INSTALL_DIR/dist/pve-thin-client-usb-bootstrap-latest.tar.gz" "$INSTALL_DIR/dist/pve-thin-client-usb-payload-latest.tar.gz" "$INSTALL_DIR/dist/beagle-os-installer-amd64.iso" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

status_path = Path(sys.argv[1])
version_file = Path(sys.argv[2])
expected_installer_url = sys.argv[3]
expected_bootstrap_url = sys.argv[4]
expected_payload_url = sys.argv[5]
expected_endpoint_iso_url = sys.argv[6]
expected_server = sys.argv[7]
expected_port = int(sys.argv[8])
expected_downloads_path = sys.argv[9]
installer_file = Path(sys.argv[10])
bootstrap_file = Path(sys.argv[11])
payload_file = Path(sys.argv[12])
endpoint_iso_file = Path(sys.argv[13])

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

status = json.loads(status_path.read_text())
errors = []
version = version_file.read_text().strip()

if status.get("version") != version:
    errors.append(f"status version mismatch: {status.get('version')} != {version}")
if status.get("installer_url") != expected_installer_url:
    errors.append("installer_url mismatch")
if status.get("bootstrap_url") != expected_bootstrap_url:
    errors.append("bootstrap_url mismatch")
if status.get("payload_url") != expected_payload_url:
    errors.append("payload_url mismatch")
if status.get("installer_iso_url") != expected_endpoint_iso_url:
    errors.append("installer_iso_url mismatch")
if status.get("server_name") != expected_server:
    errors.append("server_name mismatch")
if int(status.get("listen_port", -1)) != expected_port:
    errors.append("listen_port mismatch")
if status.get("downloads_path") != expected_downloads_path:
    errors.append("downloads_path mismatch")
if status.get("installer_size") != installer_file.stat().st_size:
    errors.append("installer_size mismatch")
if status.get("bootstrap_size") != bootstrap_file.stat().st_size:
    errors.append("bootstrap_size mismatch")
if status.get("payload_size") != payload_file.stat().st_size:
    errors.append("payload_size mismatch")
if status.get("installer_iso_size") != endpoint_iso_file.stat().st_size:
    errors.append("installer_iso_size mismatch")
if status.get("installer_sha256") != sha256(installer_file):
    errors.append("installer_sha256 mismatch")
if status.get("bootstrap_sha256") != sha256(bootstrap_file):
    errors.append("bootstrap_sha256 mismatch")
if status.get("payload_sha256") != sha256(payload_file):
    errors.append("payload_sha256 mismatch")
if status.get("installer_iso_sha256") != sha256(endpoint_iso_file):
    errors.append("installer_iso_sha256 mismatch")

if errors:
    raise SystemExit("; ".join(errors))
PY
}

check_hosted_installer_binding() {
  local expected_bootstrap_url=""
  local expected_payload_url=""

  expected_bootstrap_url="$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-bootstrap-latest.tar.gz")"
  expected_payload_url="$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-payload-latest.tar.gz")"
  if ! grep -Fq "RELEASE_BOOTSTRAP_URL=\"\${RELEASE_BOOTSTRAP_URL:-${expected_bootstrap_url}}\"" "$INSTALL_DIR/dist/pve-thin-client-usb-installer-host-latest.sh"; then
    echo "ERR bind  hosted installer bootstrap URL"
    record_failure
    return 1
  fi
  if ! grep -Fq "INSTALL_PAYLOAD_URL=\"\${INSTALL_PAYLOAD_URL:-${expected_payload_url}}\"" "$INSTALL_DIR/dist/pve-thin-client-usb-installer-host-latest.sh"; then
    echo "ERR bind  hosted installer install payload URL"
    record_failure
    return 1
  fi
  echo "OK  bind  hosted installer bootstrap/payload URLs"
  return 0
}

check_no_legacy_8443() {
  local found=0

  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq '(^|[^0-9])8443$'; then
    echo "ERR port  legacy 8443 listener is active"
    found=1
  fi

  if grep -RIlE --exclude='*.tar.gz' --exclude='*.iso' '(:8443|https?://[^[:space:]"'\''<>]+8443|PVE_DCV_.*8443|BEAGLE_.*8443)' \
    "$INSTALL_DIR/dist/beagle-downloads-status.json" \
    "$INSTALL_DIR/dist/beagle-downloads-index.html" \
    "$INSTALL_DIR/dist"/pve-thin-client-*.sh \
    "$INSTALL_DIR/dist"/pve-thin-client-*.ps1 \
    "$HOST_ENV_FILE" \
    "$PROXY_ENV_FILE" \
    2>/dev/null | grep -q .; then
    echo "ERR cfg   legacy 8443 reference in hosted download artifacts or runtime env"
    found=1
  fi

  if [[ "$found" -eq 0 ]]; then
    echo "OK  cfg   no legacy 8443 listener, hosted download or runtime env reference"
    return 0
  fi

  record_failure
  return 1
}

check_beagle_firewall() {
  local rules=""
  local nft_service=""

  if ! command -v nft >/dev/null 2>&1; then
    echo "ERR fw    nft command missing"
    record_failure
    return 1
  fi

  if ! nft list table inet beagle_guard >/dev/null 2>&1; then
    echo "ERR fw    Beagle firewall table inet beagle_guard missing"
    record_failure
    return 1
  fi

  rules="$(nft list table inet beagle_guard 2>/dev/null || true)"
  nft_service="$(systemctl is-active nftables 2>/dev/null || true)"
  if [[ "$nft_service" != "active" ]]; then
    echo "ERR fw    nftables service is not active"
    record_failure
    return 1
  fi

  if ! grep -Eq 'chain input \{' <<<"$rules" || ! grep -Eq 'policy drop;' <<<"$rules"; then
    echo "ERR fw    Beagle firewall input policy is not drop"
    record_failure
    return 1
  fi

  if ! grep -Eq 'tcp dport (22|\{ 22|22,)' <<<"$rules" || ! grep -Eq 'tcp dport \{ 80, 443 \}|tcp dport \{ 443, 80 \}' <<<"$rules"; then
    echo "ERR fw    Beagle firewall does not allow ssh/http/tls baseline"
    record_failure
    return 1
  fi

  if ! grep -Fq 'ct status dnat' <<<"$rules"; then
    echo "ERR fw    Beagle firewall does not allow explicit DNAT stream forwards"
    record_failure
    return 1
  fi

  echo "OK  fw    Beagle nftables guard is active"
  return 0
}

load_host_env

if [[ -z "$USB_TUNNEL_HOME" ]] && id "$USB_TUNNEL_USER" >/dev/null 2>&1; then
  USB_TUNNEL_HOME="$(getent passwd "$USB_TUNNEL_USER" | cut -d: -f6)"
fi

check_file "$INSTALL_DIR/VERSION"
check_file "$INSTALL_DIR/dist/pve-thin-client-usb-installer-host-latest.sh"
check_file "$INSTALL_DIR/dist/pve-thin-client-usb-bootstrap-latest.tar.gz"
check_file "$INSTALL_DIR/dist/pve-thin-client-usb-payload-latest.tar.gz"
check_file "$INSTALL_DIR/dist/beagle-downloads-status.json"
check_file "$INSTALL_DIR/dist/SHA256SUMS"
check_file "$INSTALL_DIR/dist/beagle-os-installer-amd64.iso"
check_file "$REFRESH_STATUS_FILE"
check_file "$BEAGLE_CONTROL_SERVICE_FILE"
check_file "$INSTALL_DIR/beagle-host/providers/registry.py"
check_file "$INSTALL_DIR/beagle-host/providers/host_provider_contract.py"
check_file "$INSTALL_DIR/beagle-host/providers/${BEAGLE_HOST_PROVIDER}_host_provider.py"
check_file "$INSTALL_DIR/beagle-host/bin/beagle-usb-tunnel-session"
check_file "$USB_TUNNEL_AUTH_ROOT/authorized_keys"
check_file "$BEAGLE_USB_TUNNEL_SSHD_DROPIN"
check_control_plane_novnc_rwpath
check_control_plane_runtime_imports
check_internal_callback_host

if [[ "$(host_provider_kind)" == "beagle" ]]; then
  check_file "$BEAGLE_PROXY_SITE_FILE"
  check_file "$WEB_UI_INDEX_FILE"
  check_file "$WEB_UI_CONFIG_FILE"
else
  check_file "$BEAGLE_PROXY_SITE_FILE"
  check_file "$(host_tls_cert_file)"
fi

if id "$USB_TUNNEL_USER" >/dev/null 2>&1; then
  echo "OK  user  $USB_TUNNEL_USER"
else
  echo "ERR user  $USB_TUNNEL_USER"
  record_failure
fi

if [[ -n "$BEAGLE_HOST_PROVIDER" ]]; then
  echo "OK  cfg   BEAGLE_HOST_PROVIDER=$BEAGLE_HOST_PROVIDER"
else
  echo "ERR cfg   BEAGLE_HOST_PROVIDER is empty"
  record_failure
fi

check_service_active "beagle-artifacts-refresh.timer"
check_service_active "beagle-control-plane"

if [[ "$(host_provider_kind)" == "beagle" ]]; then
  check_service_active "nginx"
  check_local_control_plane_health
  check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-installer-host-latest.sh")"
  check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-bootstrap-latest.tar.gz")"
  check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-payload-latest.tar.gz")"
  check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "beagle-downloads-status.json")"
  check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "SHA256SUMS")"
  check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "beagle-os-installer-amd64.iso")"
  check_http "$(beagle_public_release_artifact_url "$PUBLIC_ARTIFACT_BASE_URL" "pve-thin-client-usb-payload-latest.tar.gz")"
  check_http "$(beagle_public_release_artifact_url "$PUBLIC_ARTIFACT_BASE_URL" "pve-thin-client-usb-bootstrap-latest.tar.gz")"
  check_http "$(beagle_public_release_artifact_url "$PUBLIC_ARTIFACT_BASE_URL" "beagle-os-installer-amd64.iso")"
  check_http "${HOST_ORIGIN_URL}/beagle-api/healthz" "" "GET"
else
  check_local_control_plane_health
  check_service_active "nginx"
  check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-installer-host-latest.sh")"
  check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-bootstrap-latest.tar.gz")"
  check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-payload-latest.tar.gz")"
  check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "beagle-downloads-status.json")"
  check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "SHA256SUMS")"
  check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "beagle-os-installer-amd64.iso")"
  check_http "$(site_origin_url)/" "" "GET"
fi

check_no_legacy_8443
check_beagle_firewall

if check_status_json; then
  echo "OK  json  $STATUS_JSON_FILE"
else
  echo "ERR json  $STATUS_JSON_FILE"
  record_failure
fi

check_hosted_installer_binding

if (( FAILURES > 0 )); then
  echo "Host validation failed with $FAILURES problem(s)." >&2
  exit 1
fi

echo "Host validation completed successfully."
