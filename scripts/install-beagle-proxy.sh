#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROVIDER_MODULE_PATH="${BEAGLE_PROVIDER_MODULE_PATH:-$ROOT_DIR/scripts/lib/beagle_provider.py}"
# Legacy variable names from the old host stack; kept for backwards compatibility with existing deployments
ASSET_ROOT="${PVE_DCV_PROXY_ASSET_ROOT:-}"
CONFIG_DIR="${PVE_DCV_PROXY_CONFIG_DIR:-/etc/beagle}"
ENV_FILE="$CONFIG_DIR/beagle-proxy.env"
HOST_ENV_FILE="${PVE_DCV_HOST_ENV_FILE:-$CONFIG_DIR/host.env}"
MANAGER_ENV_FILE="${PVE_DCV_BEAGLE_MANAGER_ENV_FILE:-$CONFIG_DIR/beagle-manager.env}"
LISTEN_PORT="${PVE_DCV_PROXY_LISTEN_PORT:-443}"
BACKEND_HOST="${PVE_DCV_PROXY_BACKEND_HOST:-}"
BACKEND_PORT="${PVE_DCV_PROXY_BACKEND_PORT:-443}"
BACKEND_VMID="${PVE_DCV_PROXY_VMID:-}"
BEAGLE_HOST_PROVIDER="${BEAGLE_HOST_PROVIDER:-beagle}"
SERVER_NAME="${PVE_DCV_PROXY_SERVER_NAME:-$(hostname -f 2>/dev/null || hostname)}"
DOWNLOADS_PATH="${PVE_DCV_DOWNLOADS_PATH:-/beagle-downloads}"
BEAGLE_API_UPSTREAM="${BEAGLE_API_UPSTREAM:-http://127.0.0.1:9088}"
SITE_PORT="${BEAGLE_SITE_PORT:-443}"
WEB_UI_TITLE="${BEAGLE_WEB_UI_TITLE:-Beagle OS Web UI}"
WEB_UI_TRUSTED_API_ORIGINS_RAW="${BEAGLE_WEB_UI_TRUSTED_API_ORIGINS:-}"
WEB_UI_ALLOW_HASH_TOKEN="${BEAGLE_WEB_UI_ALLOW_HASH_TOKEN:-0}"
WEB_UI_ALLOW_ABSOLUTE_API_TARGETS="${BEAGLE_WEB_UI_ALLOW_ABSOLUTE_API_TARGETS:-0}"
WEB_UI_SEND_LEGACY_API_TOKEN_HEADER="${BEAGLE_WEB_UI_SEND_LEGACY_API_TOKEN_HEADER:-0}"
WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS="${BEAGLE_WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS:-0}"
BEAGLE_CONTROL_USER="${BEAGLE_CONTROL_USER:-beagle-manager}"
CERT_FILE="${PVE_DCV_PROXY_CERT_FILE:-}"
KEY_FILE="${PVE_DCV_PROXY_KEY_FILE:-}"
STANDALONE_TLS_DIR="${BEAGLE_PROXY_TLS_DIR:-$CONFIG_DIR/tls}"
NGINX_SITE="${BEAGLE_PROXY_SITE_FILE:-/etc/nginx/sites-available/beagle-proxy.conf}"
NGINX_ENABLED="${BEAGLE_PROXY_ENABLED_FILE:-/etc/nginx/sites-enabled/beagle-proxy.conf}"

default_web_ui_url() {
  if [[ "$SITE_PORT" == "443" ]]; then
    printf 'https://%s\n' "$SERVER_NAME"
    return 0
  fi
  printf 'https://%s:%s\n' "$SERVER_NAME" "$SITE_PORT"
}

default_downloads_base_url() {
  if [[ "$SITE_PORT" == "443" ]]; then
    printf 'https://%s%s\n' "$SERVER_NAME" "$DOWNLOADS_PATH"
    return 0
  fi
  printf 'https://%s:%s%s\n' "$SERVER_NAME" "$SITE_PORT" "$DOWNLOADS_PATH"
}

WEB_UI_URL="${BEAGLE_WEB_UI_URL:-$(default_web_ui_url)}"
DOWNLOADS_BASE_URL="${PVE_DCV_DOWNLOADS_BASE_URL:-$(default_downloads_base_url)}"

host_provider_kind() {
  local kind
  kind="$(printf '%s' "${BEAGLE_HOST_PROVIDER:-beagle}" | tr '[:upper:]' '[:lower:]')"
  case "$kind" in
    "")
      printf 'beagle\n'
      ;;
    *)
      printf '%s\n' "$kind"
      ;;
  esac
}

default_cert_file() {
  printf '%s/beagle-proxy.crt\n' "$STANDALONE_TLS_DIR"
}

default_key_file() {
  printf '%s/beagle-proxy.key\n' "$STANDALONE_TLS_DIR"
}

if [[ -z "$ASSET_ROOT" ]]; then
  if [[ -d /opt/beagle/dist ]]; then
    ASSET_ROOT="/opt/beagle"
  else
    ASSET_ROOT="$ROOT_DIR"
  fi
fi

ensure_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi

  if command -v sudo >/dev/null 2>&1; then
    exec sudo \
      PVE_DCV_PROXY_CONFIG_DIR="$CONFIG_DIR" \
      PVE_DCV_HOST_ENV_FILE="$HOST_ENV_FILE" \
      PVE_DCV_BEAGLE_MANAGER_ENV_FILE="$MANAGER_ENV_FILE" \
      PVE_DCV_PROXY_LISTEN_PORT="$LISTEN_PORT" \
      PVE_DCV_PROXY_BACKEND_HOST="$BACKEND_HOST" \
      PVE_DCV_PROXY_BACKEND_PORT="$BACKEND_PORT" \
      PVE_DCV_PROXY_VMID="$BACKEND_VMID" \
      BEAGLE_HOST_PROVIDER="$BEAGLE_HOST_PROVIDER" \
      PVE_DCV_PROXY_SERVER_NAME="$SERVER_NAME" \
      PVE_DCV_DOWNLOADS_PATH="$DOWNLOADS_PATH" \
      PVE_DCV_DOWNLOADS_BASE_URL="$DOWNLOADS_BASE_URL" \
      BEAGLE_API_UPSTREAM="$BEAGLE_API_UPSTREAM" \
      BEAGLE_SITE_PORT="$SITE_PORT" \
      BEAGLE_WEB_UI_URL="$WEB_UI_URL" \
      BEAGLE_WEB_UI_TITLE="$WEB_UI_TITLE" \
      BEAGLE_PROXY_TLS_DIR="$STANDALONE_TLS_DIR" \
      PVE_DCV_PROXY_CERT_FILE="$CERT_FILE" \
      PVE_DCV_PROXY_KEY_FILE="$KEY_FILE" \
      BEAGLE_WEB_UI_TRUSTED_API_ORIGINS="$WEB_UI_TRUSTED_API_ORIGINS_RAW" \
      BEAGLE_WEB_UI_ALLOW_HASH_TOKEN="$WEB_UI_ALLOW_HASH_TOKEN" \
      BEAGLE_WEB_UI_ALLOW_ABSOLUTE_API_TARGETS="$WEB_UI_ALLOW_ABSOLUTE_API_TARGETS" \
      BEAGLE_WEB_UI_SEND_LEGACY_API_TOKEN_HEADER="$WEB_UI_SEND_LEGACY_API_TOKEN_HEADER" \
      BEAGLE_WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS="$WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS" \
      "$0" "$@"
  fi

  echo "This installer must run as root or use sudo." >&2
  exit 1
}

log() {
  echo "[beagle-proxy] $*"
}

bool_js_literal() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on)
      printf 'true\n'
      ;;
    *)
      printf 'false\n'
      ;;
  esac
}

ensure_dependencies() {
  local package=()

  command -v nginx >/dev/null 2>&1 || package+=(nginx)
  command -v python3 >/dev/null 2>&1 || package+=(python3)
  command -v openssl >/dev/null 2>&1 || package+=(openssl)
  command -v nft >/dev/null 2>&1 || package+=(nftables)
  command -v certbot >/dev/null 2>&1 || package+=(certbot)
  [[ -f /usr/lib/python3/dist-packages/certbot_nginx/__init__.py || -f /usr/lib/python3/dist-packages/certbot_nginx/_internal/configurator.py ]] || package+=(python3-certbot-nginx)

  if (( ${#package[@]} == 0 )); then
    return 0
  fi

  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y "${package[@]}"
}

load_env_file() {
  local requested_listen_port="${PVE_DCV_PROXY_LISTEN_PORT:-}"
  local requested_backend_host="${PVE_DCV_PROXY_BACKEND_HOST:-}"
  local requested_backend_port="${PVE_DCV_PROXY_BACKEND_PORT:-}"
  local requested_backend_vmid="${PVE_DCV_PROXY_VMID:-}"
  local requested_server_name="${PVE_DCV_PROXY_SERVER_NAME:-}"
  local requested_downloads_path="${PVE_DCV_DOWNLOADS_PATH:-}"
  local requested_site_port="${BEAGLE_SITE_PORT:-}"
  local requested_web_ui_url="${BEAGLE_WEB_UI_URL:-}"
  local requested_web_ui_title="${BEAGLE_WEB_UI_TITLE:-}"
  local requested_trusted_origins="${BEAGLE_WEB_UI_TRUSTED_API_ORIGINS:-}"
  local requested_allow_hash_token="${BEAGLE_WEB_UI_ALLOW_HASH_TOKEN:-}"
  local requested_allow_absolute_targets="${BEAGLE_WEB_UI_ALLOW_ABSOLUTE_API_TARGETS:-}"
  local requested_send_legacy_api_token_header="${BEAGLE_WEB_UI_SEND_LEGACY_API_TOKEN_HEADER:-}"
  local requested_allow_insecure_external_urls="${BEAGLE_WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS:-}"
  if [[ -f "$HOST_ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$HOST_ENV_FILE"
  fi
  if [[ -f "$MANAGER_ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$MANAGER_ENV_FILE"
  fi
  if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
  fi

  LISTEN_PORT="${requested_listen_port:-${PVE_DCV_PROXY_LISTEN_PORT:-${LISTEN_PORT}}}"
  BACKEND_HOST="${requested_backend_host:-${PVE_DCV_PROXY_BACKEND_HOST:-${BACKEND_HOST}}}"
  BACKEND_PORT="${requested_backend_port:-${PVE_DCV_PROXY_BACKEND_PORT:-${BACKEND_PORT}}}"
  if [[ -z "$BACKEND_HOST" && "$BACKEND_PORT" == "8443" ]]; then
    BACKEND_PORT="443"
  fi
  BACKEND_VMID="${requested_backend_vmid:-${PVE_DCV_PROXY_VMID:-${BACKEND_VMID}}}"
  BEAGLE_HOST_PROVIDER="${BEAGLE_HOST_PROVIDER:-${BEAGLE_HOST_PROVIDER}}"
  SERVER_NAME="${requested_server_name:-${PVE_DCV_PROXY_SERVER_NAME:-${SERVER_NAME}}}"
  DOWNLOADS_PATH="${requested_downloads_path:-${PVE_DCV_DOWNLOADS_PATH:-${DOWNLOADS_PATH}}}"
  DOWNLOADS_BASE_URL="$(default_downloads_base_url)"
  BEAGLE_API_UPSTREAM="${BEAGLE_API_UPSTREAM:-${BEAGLE_API_UPSTREAM}}"
  SITE_PORT="${requested_site_port:-${BEAGLE_SITE_PORT:-${SITE_PORT}}}"
  WEB_UI_URL="${requested_web_ui_url:-${BEAGLE_WEB_UI_URL:-${WEB_UI_URL}}}"
  WEB_UI_TITLE="${requested_web_ui_title:-${BEAGLE_WEB_UI_TITLE:-${WEB_UI_TITLE}}}"
  WEB_UI_TRUSTED_API_ORIGINS_RAW="${requested_trusted_origins:-${BEAGLE_WEB_UI_TRUSTED_API_ORIGINS:-${WEB_UI_TRUSTED_API_ORIGINS_RAW}}}"
  WEB_UI_ALLOW_HASH_TOKEN="${requested_allow_hash_token:-${BEAGLE_WEB_UI_ALLOW_HASH_TOKEN:-${WEB_UI_ALLOW_HASH_TOKEN}}}"
  WEB_UI_ALLOW_ABSOLUTE_API_TARGETS="${requested_allow_absolute_targets:-${BEAGLE_WEB_UI_ALLOW_ABSOLUTE_API_TARGETS:-${WEB_UI_ALLOW_ABSOLUTE_API_TARGETS}}}"
  WEB_UI_SEND_LEGACY_API_TOKEN_HEADER="${requested_send_legacy_api_token_header:-${BEAGLE_WEB_UI_SEND_LEGACY_API_TOKEN_HEADER:-${WEB_UI_SEND_LEGACY_API_TOKEN_HEADER}}}"
  WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS="${requested_allow_insecure_external_urls:-${BEAGLE_WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS:-${WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS}}}"
  CERT_FILE="${PVE_DCV_PROXY_CERT_FILE:-${CERT_FILE}}"
  KEY_FILE="${PVE_DCV_PROXY_KEY_FILE:-${KEY_FILE}}"
  STANDALONE_TLS_DIR="${BEAGLE_PROXY_TLS_DIR:-${STANDALONE_TLS_DIR}}"

  if [[ -z "$CERT_FILE" ]]; then
    CERT_FILE="$(default_cert_file)"
  fi
  if [[ -z "$KEY_FILE" ]]; then
    KEY_FILE="$(default_key_file)"
  fi
}

first_guest_ipv4() {
  local vmid="$1"
  python3 - "$PROVIDER_MODULE_PATH" "$vmid" <<'PY'
import sys
from pathlib import Path

provider_module_path = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(provider_module_path.parent))

from beagle_provider import first_guest_ipv4

ip = first_guest_ipv4(int(sys.argv[2]))
if not ip:
    raise SystemExit(1)
print(ip)
PY
}

dcv_url_matches_host() {
  local url="$1"
  local target_host="$2"
  local target_port="$3"

  python3 - "$url" "$target_host" "$target_port" <<'PY'
import sys
import urllib.parse

url = sys.argv[1]
target_host = sys.argv[2].lower()
target_port = int(sys.argv[3])
parsed = urllib.parse.urlparse(url)
host = (parsed.hostname or "").lower()
  port = parsed.port or 443
if host == target_host and port == target_port:
    raise SystemExit(0)
raise SystemExit(1)
PY
}

resolve_candidate_backend() {
  local vmid="$1"
  local meta_json dcv_url dcv_ip

  meta_json="$(python3 - "$PROVIDER_MODULE_PATH" "$vmid" <<'PY'
import sys
import json
from pathlib import Path

provider_module_path = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(provider_module_path.parent))

from beagle_provider import vm_description_meta_for_vmid

print(json.dumps(vm_description_meta_for_vmid(int(sys.argv[2]))))
PY
)"
  dcv_url="$(python3 -c 'import json,sys; print(str(json.loads(sys.stdin.read() or "{}").get("dcv-url","")))' <<<"$meta_json")"
  dcv_ip="$(python3 -c 'import json,sys; print(str(json.loads(sys.stdin.read() or "{}").get("dcv-ip","")))' <<<"$meta_json")"

  if [[ -n "$BACKEND_VMID" && "$vmid" != "$BACKEND_VMID" ]]; then
    return 1
  fi

  if [[ -z "$BACKEND_VMID" ]]; then
    [[ -n "$dcv_url" ]] || return 1
    dcv_url_matches_host "$dcv_url" "$SERVER_NAME" "$LISTEN_PORT" || return 1
  fi

  if [[ -n "$dcv_ip" ]]; then
    printf '%s\n' "$dcv_ip"
    return 0
  fi

  first_guest_ipv4 "$vmid"
}

auto_detect_backend() {
  local candidates=()
  local vmid backend
  local vm_list=""

  vm_list="$(python3 - "$PROVIDER_MODULE_PATH" <<'PY'
import sys
from pathlib import Path

provider_module_path = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(provider_module_path.parent))

from beagle_provider import list_vms

for item in list_vms():
    if item.get("type") == "qemu" and item.get("vmid") is not None:
        print(int(item["vmid"]))
PY
)"

  while IFS= read -r vmid; do
    [[ -n "$vmid" ]] || continue
    backend="$(resolve_candidate_backend "$vmid" 2>/dev/null || true)"
    [[ -n "$backend" ]] || continue
    candidates+=("${vmid}:${backend}")
  done <<< "$vm_list"

  if (( ${#candidates[@]} == 1 )); then
    BACKEND_VMID="${candidates[0]%%:*}"
    BACKEND_HOST="${candidates[0]#*:}"
    return 0
  fi

  if (( ${#candidates[@]} > 1 )); then
    log "Multiple backend candidates detected (${candidates[*]}). Set PVE_DCV_PROXY_VMID or PVE_DCV_PROXY_BACKEND_HOST explicitly."
  fi

  return 1
}

write_env_file() {
  install -d -m 0755 "$CONFIG_DIR"
  cat > "$ENV_FILE" <<EOF
PVE_DCV_PROXY_LISTEN_PORT="$LISTEN_PORT"
PVE_DCV_PROXY_BACKEND_HOST="$BACKEND_HOST"
PVE_DCV_PROXY_BACKEND_PORT="$BACKEND_PORT"
PVE_DCV_PROXY_VMID="$BACKEND_VMID"
BEAGLE_HOST_PROVIDER="$BEAGLE_HOST_PROVIDER"
PVE_DCV_PROXY_SERVER_NAME="$SERVER_NAME"
PVE_DCV_DOWNLOADS_PATH="$DOWNLOADS_PATH"
PVE_DCV_DOWNLOADS_BASE_URL="$DOWNLOADS_BASE_URL"
BEAGLE_SITE_PORT="$SITE_PORT"
BEAGLE_WEB_UI_URL="$WEB_UI_URL"
BEAGLE_WEB_UI_TITLE="$WEB_UI_TITLE"
BEAGLE_WEB_UI_TRUSTED_API_ORIGINS="$WEB_UI_TRUSTED_API_ORIGINS_RAW"
BEAGLE_WEB_UI_ALLOW_HASH_TOKEN="$WEB_UI_ALLOW_HASH_TOKEN"
BEAGLE_WEB_UI_ALLOW_ABSOLUTE_API_TARGETS="$WEB_UI_ALLOW_ABSOLUTE_API_TARGETS"
BEAGLE_WEB_UI_SEND_LEGACY_API_TOKEN_HEADER="$WEB_UI_SEND_LEGACY_API_TOKEN_HEADER"
BEAGLE_WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS="$WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS"
BEAGLE_PROXY_TLS_DIR="$STANDALONE_TLS_DIR"
PVE_DCV_PROXY_CERT_FILE="$CERT_FILE"
PVE_DCV_PROXY_KEY_FILE="$KEY_FILE"
EOF
}

sync_host_env_proxy_defaults() {
  install -d -m 0755 "$CONFIG_DIR"
  python3 - "$HOST_ENV_FILE" "$SERVER_NAME" "$LISTEN_PORT" "$SITE_PORT" "$DOWNLOADS_PATH" "$DOWNLOADS_BASE_URL" "$WEB_UI_URL" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
updates = {
    "PVE_DCV_PROXY_SERVER_NAME": sys.argv[2],
    "PVE_DCV_PROXY_LISTEN_PORT": sys.argv[3],
    "BEAGLE_SITE_PORT": sys.argv[4],
    "PVE_DCV_DOWNLOADS_PATH": sys.argv[5],
    "PVE_DCV_DOWNLOADS_BASE_URL": sys.argv[6],
    "BEAGLE_WEB_UI_URL": sys.argv[7],
    "PVE_DCV_USB_INSTALLER_URL": "https://{host}/beagle-api/api/v1/vms/{vmid}/installer.sh",
}

lines: list[str] = []
seen: set[str] = set()
if path.exists():
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            lines.append(raw_line)
            continue
        key, _value = stripped.split("=", 1)
        key = key.strip()
        if key in updates:
            lines.append(f'{key}="{updates[key]}"')
            seen.add(key)
        else:
            lines.append(raw_line)
for key, value in updates.items():
    if key not in seen:
        lines.append(f'{key}="{value}"')
path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
PY
}

tls_subject_alt_name() {
  if [[ "$SERVER_NAME" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf 'IP:%s,IP:127.0.0.1\n' "$SERVER_NAME"
    return 0
  fi
  printf 'DNS:%s,IP:127.0.0.1\n' "$SERVER_NAME"
}

ensure_tls_directory_permissions() {
  mkdir -p "$STANDALONE_TLS_DIR"
  chown "$BEAGLE_CONTROL_USER":"$BEAGLE_CONTROL_USER" "$STANDALONE_TLS_DIR"
  chmod 0750 "$STANDALONE_TLS_DIR"
}

ensure_tls_materials() {
  ensure_tls_directory_permissions

  if [[ -r "$CERT_FILE" && -r "$KEY_FILE" ]]; then
    return 0
  fi

  openssl req \
    -x509 \
    -nodes \
    -newkey rsa:2048 \
    -days 3650 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -subj "/CN=${SERVER_NAME}" \
    -addext "subjectAltName=$(tls_subject_alt_name)" >/dev/null 2>&1
  chown "$BEAGLE_CONTROL_USER":"$BEAGLE_CONTROL_USER" "$KEY_FILE" "$CERT_FILE"
  chmod 0600 "$KEY_FILE"
  chmod 0644 "$CERT_FILE"
  log "Generated standalone TLS certificate at $CERT_FILE"
}

write_web_ui_config() {
  install -d -m 0755 "${ASSET_ROOT}/website"
  cat > "${ASSET_ROOT}/website/beagle-web-ui-config.js" <<EOF
window.BEAGLE_WEB_UI_CONFIG = {
  title: ${WEB_UI_TITLE@Q},
  webUiUrl: ${WEB_UI_URL@Q},
  apiBase: '/beagle-api/api/v1',
  downloadsBase: ${DOWNLOADS_PATH@Q},
  trustedApiOrigins: ${WEB_UI_TRUSTED_API_ORIGINS_RAW@Q},
  allowHashToken: $(bool_js_literal "$WEB_UI_ALLOW_HASH_TOKEN"),
  allowAbsoluteApiTargets: $(bool_js_literal "$WEB_UI_ALLOW_ABSOLUTE_API_TARGETS"),
  sendLegacyApiTokenHeader: $(bool_js_literal "$WEB_UI_SEND_LEGACY_API_TOKEN_HEADER"),
  allowInsecureExternalUrls: $(bool_js_literal "$WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS")
};
EOF
}

cleanup_legacy_port_forward() {
  local rule delete_rule
  local prerouting_rules=""
  local forward_rules=""

  prerouting_rules="$(iptables -t nat -S PREROUTING 2>/dev/null || true)"

  while IFS= read -r rule; do
    [[ "$rule" == *"--dport $LISTEN_PORT"* ]] || continue
    [[ "$rule" == *"--to-destination ${BACKEND_HOST}:${BACKEND_PORT}"* ]] || continue
    delete_rule="${rule/-A /-D }"
    iptables -t nat $delete_rule
  done <<< "$prerouting_rules"

  forward_rules="$(iptables -S FORWARD 2>/dev/null || true)"

  while IFS= read -r rule; do
    [[ "$rule" == *"--dport $LISTEN_PORT"* ]] || continue
    [[ "$rule" == *"-d ${BACKEND_HOST}/32"* ]] || continue
    delete_rule="${rule/-A /-D }"
    iptables $delete_rule
  done <<< "$forward_rules"
}

write_nginx_config() {
  local web_redirect_target
  if [[ "$SITE_PORT" == "443" ]]; then
    web_redirect_target="https://\$host\$request_uri"
  else
    web_redirect_target="https://\$host:${SITE_PORT}\$request_uri"
  fi

  cat > "$NGINX_SITE" <<EOF
server {
  listen 80 default_server;
  listen [::]:80 default_server;
    server_name _;

    # ACME HTTP-01 challenge: served before the HTTPS redirect so certbot
    # --webroot can obtain Let's Encrypt certificates without nginx plugin.
    location ^~ /.well-known/acme-challenge/ {
      root /var/lib/beagle/acme-webroot;
        default_type text/plain;
        allow all;
    }

    location / {
      return 301 ${web_redirect_target};
    }
}

limit_req_zone \$binary_remote_addr zone=beagle_auth:10m rate=120r/m;
limit_req_zone \$binary_remote_addr zone=beagle_api:20m rate=1800r/m;

server {
  listen ${SITE_PORT} ssl default_server;
  listen [::]:${SITE_PORT} ssl default_server;
    server_name _;

    ssl_certificate ${CERT_FILE};
    ssl_certificate_key ${KEY_FILE};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_session_tickets off;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_session_timeout 1d;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header X-Frame-Options "DENY" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    add_header Cross-Origin-Opener-Policy "same-origin" always;
    add_header Cross-Origin-Resource-Policy "same-origin" always;

    root ${ASSET_ROOT}/website;
    index index.html;

    location = /beagle-downloads {
        return 302 /beagle-downloads/;
    }

    location ^~ /beagle-downloads/ {
        alias ${ASSET_ROOT}/dist/;
        index beagle-downloads-index.html;
        add_header Cache-Control "no-store";
        autoindex on;
        types {
            application/x-sh sh;
            text/plain txt;
        }
    }

    location = /metrics {
      limit_req zone=beagle_api burst=1200 nodelay;
      proxy_pass ${BEAGLE_API_UPSTREAM}/metrics;
      proxy_http_version 1.1;
      proxy_set_header Host \$host;
      proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto https;
      proxy_read_timeout 60;
      proxy_send_timeout 60;
    }

    location ^~ /beagle-api/api/v1/auth/ {
      limit_req zone=beagle_auth burst=120 nodelay;
      proxy_pass ${BEAGLE_API_UPSTREAM}/api/v1/auth/;
      proxy_http_version 1.1;
      proxy_set_header Host \$host;
      proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto https;
      proxy_read_timeout 900;
      proxy_send_timeout 900;
    }

    location /beagle-api/ {
      limit_req zone=beagle_api burst=1200 nodelay;
        proxy_pass ${BEAGLE_API_UPSTREAM}/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 900;
        proxy_send_timeout 900;
    }

    # Legacy compatibility for older/cached WebUI clients still calling /api/* directly.
    location ^~ /api/v1/auth/ {
      limit_req zone=beagle_auth burst=120 nodelay;
      proxy_pass ${BEAGLE_API_UPSTREAM}/api/v1/auth/;
      proxy_http_version 1.1;
      proxy_set_header Host \$host;
      proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto https;
      proxy_read_timeout 900;
      proxy_send_timeout 900;
    }

    location /api/ {
      limit_req zone=beagle_api burst=1200 nodelay;
      proxy_pass ${BEAGLE_API_UPSTREAM}/api/;
      proxy_http_version 1.1;
      proxy_set_header Host \$host;
      proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto https;
      proxy_read_timeout 900;
      proxy_send_timeout 900;
    }

    location ^~ /novnc/ {
      alias /usr/share/novnc/;
      index vnc.html;
      add_header Cache-Control "no-store";
    }

    location = /beagle-novnc/websockify {
      proxy_pass http://127.0.0.1:6080;
      proxy_http_version 1.1;
      proxy_set_header Upgrade \$http_upgrade;
      proxy_set_header Connection "upgrade";
      proxy_set_header Host \$host;
      proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto https;
      proxy_read_timeout 3600;
      proxy_send_timeout 3600;
    }

    location = /favicon.svg {
        try_files /favicon.svg =404;
        add_header Cache-Control "public, max-age=3600";
    }

    location = /core/platform/browser-common.js {
        alias ${ASSET_ROOT}/core/platform/browser-common.js;
        add_header Cache-Control "no-store";
    }

    location = /beagle-web-ui-config.js {
        alias ${ASSET_ROOT}/website/beagle-web-ui-config.js;
        add_header Cache-Control "no-store";
    }

    location / {
      add_header Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; worker-src 'self' blob:; connect-src 'self' wss:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests" always;
      add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
      add_header X-Content-Type-Options "nosniff" always;
      add_header Referrer-Policy "no-referrer" always;
      add_header X-Frame-Options "DENY" always;
      add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
      add_header Cross-Origin-Opener-Policy "same-origin" always;
      add_header Cross-Origin-Resource-Policy "same-origin" always;
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
}

link_nginx_config() {
  ln -sfn "$NGINX_SITE" "$NGINX_ENABLED"
  if [[ -f /etc/nginx/sites-enabled/default ]]; then
    rm -f /etc/nginx/sites-enabled/default
  fi
  if [[ -L /etc/nginx/sites-enabled/pve-dcv-integration-dcv-proxy.conf ]]; then
    rm -f /etc/nginx/sites-enabled/pve-dcv-integration-dcv-proxy.conf
  fi
}

running_in_chroot() {
  if command -v ischroot >/dev/null 2>&1; then
    ischroot
    return $?
  fi
  [[ "$(readlink /proc/1/root 2>/dev/null || true)" != "/" ]]
}

apply_nginx_service_state() {
  if running_in_chroot; then
    # During installer chroot phase we only enable the unit on disk.
    # Starting/reloading would target the live installer PID1 instead.
    systemctl enable nginx >/dev/null 2>&1 || true
    log "Detected chroot install context; skipped nginx start/reload (will start on first boot)."
    return 0
  fi

  systemctl enable --now nginx
  systemctl reload nginx
}

ensure_root "$@"
load_env_file
ensure_dependencies



ensure_tls_materials

if [[ -z "$BACKEND_HOST" ]]; then
  if ! auto_detect_backend; then
    log "No backend detected. Configuring downloads-only HTTPS endpoint on https://${SERVER_NAME}${DOWNLOADS_PATH}/."
  fi
fi

write_env_file
sync_host_env_proxy_defaults
write_web_ui_config
cleanup_legacy_port_forward
write_nginx_config
link_nginx_config
nginx -t
apply_nginx_service_state

# Create ACME webroot directory used by certbot --webroot for Let's Encrypt.
mkdir -p /var/lib/beagle/acme-webroot
mkdir -p /var/lib/beagle/acme-webroot/.well-known/acme-challenge
chown -R beagle-manager:beagle-manager /var/lib/beagle/acme-webroot
chgrp -R www-data /var/lib/beagle/acme-webroot
chmod 2775 /var/lib/beagle/acme-webroot
chmod 2775 /var/lib/beagle/acme-webroot/.well-known
chmod 2775 /var/lib/beagle/acme-webroot/.well-known/acme-challenge

# Allow beagle-manager service user to reload nginx and run nginx -t without
# interactive D-Bus / polkit authentication (the service runs with NoNewPrivileges=yes).
cat > /etc/sudoers.d/beagle-nginx-reload <<'SUDOERS'
# Managed by install-beagle-proxy.sh — do not edit by hand.
beagle-manager ALL=(root) NOPASSWD: /usr/sbin/nginx -t, /bin/systemctl reload nginx
SUDOERS
chmod 0440 /etc/sudoers.d/beagle-nginx-reload

log "Configured host-local HTTPS downloads on ${DOWNLOADS_BASE_URL%/}/"
