#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROVIDER_MODULE_PATH="${BEAGLE_PROVIDER_MODULE_PATH:-$ROOT_DIR/scripts/lib/beagle_provider.py}"
ASSET_ROOT="${PVE_DCV_PROXY_ASSET_ROOT:-}"
CONFIG_DIR="${PVE_DCV_PROXY_CONFIG_DIR:-/etc/beagle}"
ENV_FILE="$CONFIG_DIR/beagle-proxy.env"
LISTEN_PORT="${PVE_DCV_PROXY_LISTEN_PORT:-8443}"
BACKEND_HOST="${PVE_DCV_PROXY_BACKEND_HOST:-}"
BACKEND_PORT="${PVE_DCV_PROXY_BACKEND_PORT:-8443}"
BACKEND_VMID="${PVE_DCV_PROXY_VMID:-}"
SERVER_NAME="${PVE_DCV_PROXY_SERVER_NAME:-$(hostname -f 2>/dev/null || hostname)}"
DOWNLOADS_PATH="${PVE_DCV_DOWNLOADS_PATH:-/beagle-downloads}"
DOWNLOADS_BASE_URL="${PVE_DCV_DOWNLOADS_BASE_URL:-https://${SERVER_NAME}:${LISTEN_PORT}${DOWNLOADS_PATH}}"
BEAGLE_API_UPSTREAM="${BEAGLE_API_UPSTREAM:-http://127.0.0.1:9088}"
SITE_PORT="${BEAGLE_SITE_PORT:-443}"
WEB_UI_TITLE="${BEAGLE_WEB_UI_TITLE:-Beagle OS Web UI}"
CERT_FILE="${PVE_DCV_PROXY_CERT_FILE:-/etc/pve/local/pveproxy-ssl.pem}"
KEY_FILE="${PVE_DCV_PROXY_KEY_FILE:-/etc/pve/local/pveproxy-ssl.key}"
NGINX_SITE="/etc/nginx/sites-available/beagle-proxy.conf"
NGINX_ENABLED="/etc/nginx/sites-enabled/beagle-proxy.conf"

default_web_ui_url() {
  if [[ "$SITE_PORT" == "443" ]]; then
    printf 'https://%s\n' "$SERVER_NAME"
    return 0
  fi
  printf 'https://%s:%s\n' "$SERVER_NAME" "$SITE_PORT"
}

WEB_UI_URL="${BEAGLE_WEB_UI_URL:-$(default_web_ui_url)}"

if [[ -z "$ASSET_ROOT" ]]; then
  if [[ -d /opt/beagle/dist && -f /opt/beagle/proxmox-ui/beagle-autologin.js ]]; then
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
      PVE_DCV_PROXY_LISTEN_PORT="$LISTEN_PORT" \
      PVE_DCV_PROXY_BACKEND_HOST="$BACKEND_HOST" \
      PVE_DCV_PROXY_BACKEND_PORT="$BACKEND_PORT" \
      PVE_DCV_PROXY_VMID="$BACKEND_VMID" \
      PVE_DCV_PROXY_SERVER_NAME="$SERVER_NAME" \
      PVE_DCV_DOWNLOADS_PATH="$DOWNLOADS_PATH" \
      PVE_DCV_DOWNLOADS_BASE_URL="$DOWNLOADS_BASE_URL" \
      BEAGLE_API_UPSTREAM="$BEAGLE_API_UPSTREAM" \
      BEAGLE_SITE_PORT="$SITE_PORT" \
      BEAGLE_WEB_UI_URL="$WEB_UI_URL" \
      BEAGLE_WEB_UI_TITLE="$WEB_UI_TITLE" \
      PVE_DCV_PROXY_CERT_FILE="$CERT_FILE" \
      PVE_DCV_PROXY_KEY_FILE="$KEY_FILE" \
      "$0" "$@"
  fi

  echo "This installer must run as root or use sudo." >&2
  exit 1
}

log() {
  echo "[beagle-proxy] $*"
}

ensure_dependencies() {
  local package=()

  command -v nginx >/dev/null 2>&1 || package+=(nginx)
  command -v python3 >/dev/null 2>&1 || package+=(python3)

  if (( ${#package[@]} == 0 )); then
    return 0
  fi

  apt_update_with_proxmox_fallback
  DEBIAN_FRONTEND=noninteractive apt-get install -y "${package[@]}"
}

disable_proxmox_enterprise_repo() {
  local found=0
  local file

  while IFS= read -r file; do
    grep -q 'enterprise.proxmox.com' "$file" || continue
    cp "$file" "$file.beagle-backup"
    awk '!/enterprise\.proxmox\.com/' "$file.beagle-backup" > "$file"
    found=1
  done < <(find /etc/apt -maxdepth 2 -type f \( -name '*.list' -o -name '*.sources' \) 2>/dev/null)

  return $(( ! found ))
}

restore_proxmox_enterprise_repo() {
  local backup original

  while IFS= read -r backup; do
    original="${backup%.beagle-backup}"
    mv "$backup" "$original"
  done < <(find /etc/apt -maxdepth 2 -type f -name '*.beagle-backup' 2>/dev/null)
}

apt_update_with_proxmox_fallback() {
  if apt-get update; then
    return 0
  fi

  if ! disable_proxmox_enterprise_repo; then
    echo "apt-get update failed and no Proxmox enterprise repository fallback was available." >&2
    exit 1
  fi

  if ! apt-get update; then
    restore_proxmox_enterprise_repo
    exit 1
  fi
  restore_proxmox_enterprise_repo
}

load_env_file() {
  if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
  fi

  LISTEN_PORT="${PVE_DCV_PROXY_LISTEN_PORT:-${LISTEN_PORT}}"
  BACKEND_HOST="${PVE_DCV_PROXY_BACKEND_HOST:-${BACKEND_HOST}}"
  BACKEND_PORT="${PVE_DCV_PROXY_BACKEND_PORT:-${BACKEND_PORT}}"
  BACKEND_VMID="${PVE_DCV_PROXY_VMID:-${BACKEND_VMID}}"
  SERVER_NAME="${PVE_DCV_PROXY_SERVER_NAME:-${SERVER_NAME}}"
  DOWNLOADS_PATH="${PVE_DCV_DOWNLOADS_PATH:-${DOWNLOADS_PATH}}"
  DOWNLOADS_BASE_URL="${PVE_DCV_DOWNLOADS_BASE_URL:-${DOWNLOADS_BASE_URL}}"
  BEAGLE_API_UPSTREAM="${BEAGLE_API_UPSTREAM:-${BEAGLE_API_UPSTREAM}}"
  SITE_PORT="${BEAGLE_SITE_PORT:-${SITE_PORT}}"
  WEB_UI_URL="${BEAGLE_WEB_UI_URL:-${WEB_UI_URL}}"
  WEB_UI_TITLE="${BEAGLE_WEB_UI_TITLE:-${WEB_UI_TITLE}}"
  CERT_FILE="${PVE_DCV_PROXY_CERT_FILE:-${CERT_FILE}}"
  KEY_FILE="${PVE_DCV_PROXY_KEY_FILE:-${KEY_FILE}}"
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
port = parsed.port or 8443
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

  while read -r vmid; do
    [[ -n "$vmid" ]] || continue
    backend="$(resolve_candidate_backend "$vmid" 2>/dev/null || true)"
    [[ -n "$backend" ]] || continue
    candidates+=("${vmid}:${backend}")
  done < <(python3 - "$PROVIDER_MODULE_PATH" <<'PY'
import sys
from pathlib import Path

provider_module_path = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(provider_module_path.parent))

from beagle_provider import list_vms

for item in list_vms():
    if item.get("type") == "qemu" and item.get("vmid") is not None:
        print(int(item["vmid"]))
PY
)

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
PVE_DCV_PROXY_SERVER_NAME="$SERVER_NAME"
PVE_DCV_DOWNLOADS_PATH="$DOWNLOADS_PATH"
PVE_DCV_DOWNLOADS_BASE_URL="$DOWNLOADS_BASE_URL"
BEAGLE_SITE_PORT="$SITE_PORT"
BEAGLE_WEB_UI_URL="$WEB_UI_URL"
BEAGLE_WEB_UI_TITLE="$WEB_UI_TITLE"
PVE_DCV_PROXY_CERT_FILE="$CERT_FILE"
PVE_DCV_PROXY_KEY_FILE="$KEY_FILE"
EOF
}

write_web_ui_config() {
  install -d -m 0755 "${ASSET_ROOT}/website"
  cat > "${ASSET_ROOT}/website/beagle-web-ui-config.js" <<EOF
window.BEAGLE_WEB_UI_CONFIG = {
  title: ${WEB_UI_TITLE@Q},
  webUiUrl: ${WEB_UI_URL@Q},
  apiBase: '/beagle-api/api/v1',
  downloadsBase: ${DOWNLOADS_PATH@Q}
};
EOF
}

cleanup_legacy_port_forward() {
  local rule delete_rule

  while IFS= read -r rule; do
    [[ "$rule" == *"--dport $LISTEN_PORT"* ]] || continue
    [[ "$rule" == *"--to-destination ${BACKEND_HOST}:${BACKEND_PORT}"* ]] || continue
    delete_rule="${rule/-A /-D }"
    iptables -t nat $delete_rule
  done < <(iptables -t nat -S PREROUTING 2>/dev/null || true)

  while IFS= read -r rule; do
    [[ "$rule" == *"--dport $LISTEN_PORT"* ]] || continue
    [[ "$rule" == *"-d ${BACKEND_HOST}/32"* ]] || continue
    delete_rule="${rule/-A /-D }"
    iptables $delete_rule
  done < <(iptables -S FORWARD 2>/dev/null || true)
}

write_nginx_config() {
  cat > "$NGINX_SITE" <<EOF
server {
    listen ${SITE_PORT} ssl;
    listen [::]:${SITE_PORT} ssl;
    server_name ${SERVER_NAME};

    ssl_certificate ${CERT_FILE};
    ssl_certificate_key ${KEY_FILE};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_timeout 1d;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header X-Frame-Options "DENY" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

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

    location /beagle-api/ {
        proxy_pass ${BEAGLE_API_UPSTREAM}/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 30;
        proxy_send_timeout 30;
    }

    location = /favicon.svg {
        try_files /favicon.svg =404;
        add_header Cache-Control "public, max-age=3600";
    }

    location = /core/platform/browser-common.js {
        alias ${ASSET_ROOT}/core/platform/browser-common.js;
        add_header Cache-Control "no-store";
    }

    location / {
        add_header Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests" always;
        try_files \$uri \$uri/ /index.html;
    }
}

server {
    listen ${LISTEN_PORT} ssl;
    listen [::]:${LISTEN_PORT} ssl;
    server_name ${SERVER_NAME};

    ssl_certificate ${CERT_FILE};
    ssl_certificate_key ${KEY_FILE};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_timeout 1d;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header X-Frame-Options "DENY" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    location = /beagle-autologin.js {
        alias ${ASSET_ROOT}/proxmox-ui/beagle-autologin.js;
        add_header Cache-Control "no-store";
    }

    location = ${DOWNLOADS_PATH} {
        return 302 ${DOWNLOADS_PATH}/;
    }

    location ^~ ${DOWNLOADS_PATH}/ {
        alias ${ASSET_ROOT}/dist/;
        index beagle-downloads-index.html;
        add_header Cache-Control "no-store";
        autoindex on;
        types {
            application/x-sh sh;
            text/plain txt;
        }
    }

    location = /pve-dcv-downloads {
        return 302 ${DOWNLOADS_PATH}/;
    }

    location ^~ /pve-dcv-downloads/ {
        rewrite ^/pve-dcv-downloads/(.*)$ ${DOWNLOADS_PATH}/\$1 permanent;
    }

    location /beagle-api/ {
        proxy_pass ${BEAGLE_API_UPSTREAM}/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 30;
        proxy_send_timeout 30;
    }

EOF

  if [[ -n "$BACKEND_HOST" ]]; then
    cat >> "$NGINX_SITE" <<EOF
    location / {
        return 404;
    }
}
EOF
    return 0
  fi

  cat >> "$NGINX_SITE" <<EOF
    location = / {
        return 302 https://${SERVER_NAME}:${SITE_PORT}/;
    }

    location / {
        return 404;
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

ensure_root "$@"
load_env_file
ensure_dependencies

[[ -r "$CERT_FILE" ]] || {
  echo "Certificate file not found: $CERT_FILE" >&2
  exit 1
}
[[ -r "$KEY_FILE" ]] || {
  echo "Certificate key not found: $KEY_FILE" >&2
  exit 1
}

if [[ -z "$BACKEND_HOST" ]]; then
  if ! auto_detect_backend; then
    log "No backend detected. Configuring downloads-only HTTPS endpoint on https://${SERVER_NAME}:${LISTEN_PORT}${DOWNLOADS_PATH}/."
  fi
fi

write_env_file
write_web_ui_config
cleanup_legacy_port_forward
write_nginx_config
link_nginx_config
nginx -t
systemctl enable --now nginx
systemctl reload nginx
if [[ -n "$BACKEND_HOST" ]]; then
  log "Configured Beagle proxy on https://${SERVER_NAME}:${LISTEN_PORT}/ -> https://${BACKEND_HOST}:${BACKEND_PORT}/"
else
  log "Configured host-local HTTPS downloads on ${DOWNLOADS_BASE_URL%/}/"
fi
