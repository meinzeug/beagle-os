#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOSTED_DOWNLOAD_LAYOUT_HELPER="$ROOT_DIR/scripts/lib/hosted_download_layout.sh"
INSTALL_DIR="${INSTALL_DIR:-/opt/beagle}"
CONFIG_DIR="${PVE_DCV_CONFIG_DIR:-/etc/beagle}"
HOST_ENV_FILE="${PVE_DCV_HOST_ENV_FILE:-$CONFIG_DIR/host.env}"
SERVER_NAME="${PVE_DCV_PROXY_SERVER_NAME:-$(hostname -f 2>/dev/null || hostname)}"
LISTEN_PORT="${PVE_DCV_PROXY_LISTEN_PORT:-8443}"
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
BEAGLE_HOST_PROVIDER="${BEAGLE_HOST_PROVIDER:-proxmox}"
USB_TUNNEL_USER="${BEAGLE_USB_TUNNEL_SSH_USER:-beagle}"
USB_TUNNEL_HOME="${BEAGLE_USB_TUNNEL_HOME:-}"
USB_TUNNEL_AUTH_ROOT="${BEAGLE_USB_TUNNEL_AUTH_ROOT:-/var/lib/beagle/usb-tunnel/$USB_TUNNEL_USER}"

load_host_env() {
  if [[ -f "$HOST_ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$HOST_ENV_FILE"
  fi

  SERVER_NAME="${PVE_DCV_PROXY_SERVER_NAME:-$SERVER_NAME}"
  LISTEN_PORT="${PVE_DCV_PROXY_LISTEN_PORT:-$LISTEN_PORT}"
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
  local tls_cert_file="${BEAGLE_HOST_TLS_CERT_FILE:-/etc/pve/local/pve-ssl.pem}"
  local -a curl_args=(curl -fsS --output /dev/null)
  [[ -n "$auth_header" ]] && curl_args+=(-H "$auth_header")
  if [[ "$method" == "HEAD" ]]; then
    curl_args+=(-I)
  fi
  if [[ "$url" == "${HOST_ORIGIN_URL}"* && -f "$tls_cert_file" ]]; then
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

check_status_json() {
  local expected_installer_url=""
  local expected_bootstrap_url=""
  local expected_payload_url=""
  local expected_endpoint_iso_url=""
  local expected_server_installer_iso_url=""

  expected_installer_url="$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-installer-host-latest.sh")"
  expected_bootstrap_url="$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-bootstrap-latest.tar.gz")"
  expected_payload_url="$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-payload-latest.tar.gz")"
  expected_endpoint_iso_url="$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "beagle-os-installer-amd64.iso")"
  expected_server_installer_iso_url="$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "beagle-os-server-installer-amd64.iso")"

  python3 - "$STATUS_JSON_FILE" "$INSTALL_DIR/VERSION" "$expected_installer_url" "$expected_bootstrap_url" "$expected_payload_url" "$expected_endpoint_iso_url" "$expected_server_installer_iso_url" "$SERVER_NAME" "$LISTEN_PORT" "$DOWNLOADS_PATH" "$INSTALL_DIR/dist/pve-thin-client-usb-installer-host-latest.sh" "$INSTALL_DIR/dist/pve-thin-client-usb-bootstrap-latest.tar.gz" "$INSTALL_DIR/dist/pve-thin-client-usb-payload-latest.tar.gz" "$INSTALL_DIR/dist/beagle-os-installer-amd64.iso" "$INSTALL_DIR/dist/beagle-os-server-installer-amd64.iso" <<'PY'
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
expected_server_installer_iso_url = sys.argv[7]
expected_server = sys.argv[8]
expected_port = int(sys.argv[9])
expected_downloads_path = sys.argv[10]
installer_file = Path(sys.argv[11])
bootstrap_file = Path(sys.argv[12])
payload_file = Path(sys.argv[13])
endpoint_iso_file = Path(sys.argv[14])
server_installer_iso_file = Path(sys.argv[15])

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
if status.get("server_installer_iso_url") != expected_server_installer_iso_url:
    errors.append("server_installer_iso_url mismatch")
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
if status.get("server_installer_iso_size") != server_installer_iso_file.stat().st_size:
    errors.append("server_installer_iso_size mismatch")
if status.get("installer_sha256") != sha256(installer_file):
    errors.append("installer_sha256 mismatch")
if status.get("bootstrap_sha256") != sha256(bootstrap_file):
    errors.append("bootstrap_sha256 mismatch")
if status.get("payload_sha256") != sha256(payload_file):
    errors.append("payload_sha256 mismatch")
if status.get("installer_iso_sha256") != sha256(endpoint_iso_file):
    errors.append("installer_iso_sha256 mismatch")
if status.get("server_installer_iso_sha256") != sha256(server_installer_iso_file):
    errors.append("server_installer_iso_sha256 mismatch")

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
check_file "$INSTALL_DIR/dist/beagle-os-server-installer-amd64.iso"
check_file "$REFRESH_STATUS_FILE"
check_file "/usr/share/pve-manager/js/beagle-ui.js"
check_file "/usr/share/pve-manager/js/beagle-ui-config.js"
check_file "/etc/nginx/sites-available/beagle-proxy.conf"
check_file "/etc/systemd/system/beagle-ui-reapply.service"
check_file "/etc/systemd/system/beagle-ui-reapply.path"
check_file "/etc/systemd/system/beagle-control-plane.service"
check_file "$INSTALL_DIR/beagle-host/providers/registry.py"
check_file "$INSTALL_DIR/beagle-host/providers/host_provider_contract.py"
check_file "$INSTALL_DIR/beagle-host/providers/${BEAGLE_HOST_PROVIDER}_host_provider.py"
check_file "$INSTALL_DIR/beagle-host/bin/beagle-usb-tunnel-session"
check_file "$USB_TUNNEL_AUTH_ROOT/authorized_keys"
check_file "/etc/ssh/sshd_config.d/90-beagle-usb-tunnel.conf"

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

check_service_active "pveproxy"
check_service_active "nginx"
check_service_active "beagle-artifacts-refresh.timer"
check_service_active "beagle-ui-reapply.path"
check_service_active "beagle-control-plane"

check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-installer-host-latest.sh")"
check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-bootstrap-latest.tar.gz")"
check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-payload-latest.tar.gz")"
check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "beagle-downloads-status.json")"
check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "SHA256SUMS")"
check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "beagle-os-installer-amd64.iso")"
check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "beagle-os-server-installer-amd64.iso")"
check_http "$(beagle_public_release_artifact_url "$PUBLIC_ARTIFACT_BASE_URL" "pve-thin-client-usb-payload-latest.tar.gz")"
check_http "$(beagle_public_release_artifact_url "$PUBLIC_ARTIFACT_BASE_URL" "pve-thin-client-usb-bootstrap-latest.tar.gz")"
check_http "$(beagle_public_release_artifact_url "$PUBLIC_ARTIFACT_BASE_URL" "beagle-os-installer-amd64.iso")"
check_http "$(beagle_public_release_artifact_url "$PUBLIC_ARTIFACT_BASE_URL" "beagle-os-server-installer-amd64.iso")"
check_http "${HOST_ORIGIN_URL}/beagle-api/healthz" "Authorization: Bearer $BEAGLE_API_TOKEN" "GET"

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
