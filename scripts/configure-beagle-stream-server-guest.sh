#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib/trace-guard.sh"
beagle_trace_guard_disable_xtrace_if_sensitive
source "$SCRIPT_DIR/lib/provider_shell.sh"
LOCAL_PROVIDER_MODULE_PATH="${BEAGLE_PROVIDER_MODULE_PATH:-$SCRIPT_DIR/lib/beagle_provider.py}"
REMOTE_INSTALL_DIR="${BEAGLE_REMOTE_INSTALL_DIR:-/opt/beagle}"
REMOTE_PROVIDER_MODULE_PATH="${BEAGLE_REMOTE_PROVIDER_MODULE_PATH:-${REMOTE_INSTALL_DIR%/}/scripts/lib/beagle_provider.py}"
PROVIDER_HELPER_AVAILABLE_CACHE="${PROVIDER_HELPER_AVAILABLE_CACHE:-}"

# Ensure provider imports can resolve top-level repo modules (e.g. core/*) on live hosts.
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

BEAGLE_HOST="${BEAGLE_HOST:-beagle.local}"
VMID="${VMID:-}"
GUEST_USER="${GUEST_USER:-beagle}"
BEAGLE_MANAGER_URL="${BEAGLE_MANAGER_URL:-}"
VMID="${VMID:-}"
GUEST_PASSWORD="${GUEST_PASSWORD:-}"
IDENTITY_LOCALE="${IDENTITY_LOCALE:-de_DE.UTF-8}"
IDENTITY_LANGUAGE="${IDENTITY_LANGUAGE:-de_DE:de}"
IDENTITY_KEYMAP="${IDENTITY_KEYMAP:-de}"
DESKTOP_ID="${DESKTOP_ID:-plasma-cyberpunk}"
DESKTOP_LABEL="${DESKTOP_LABEL:-}"
DESKTOP_SESSION="${DESKTOP_SESSION:-}"
BEAGLE_USER="${BEAGLE_USER:-}"
BEAGLE_PASSWORD="${BEAGLE_PASSWORD:-}"
BEAGLE_TOKEN="${BEAGLE_TOKEN:-}"
GUEST_IP_OVERRIDE="${GUEST_IP_OVERRIDE:-}"
BEAGLE_STREAM_SERVER_USER="${BEAGLE_STREAM_SERVER_USER:-beagle-stream-server}"
BEAGLE_STREAM_SERVER_PASSWORD="${BEAGLE_STREAM_SERVER_PASSWORD:-}"
BEAGLE_STREAM_SERVER_TOKEN="${BEAGLE_STREAM_SERVER_TOKEN:-}"
BEAGLE_STREAM_SERVER_PORT="${BEAGLE_STREAM_SERVER_PORT:-50000}"
BEAGLE_STREAM_SERVER_DEFAULT_URL="https://github.com/meinzeug/beagle-stream-server/releases/download/beagle-phase-a/beagle-stream-server-latest-ubuntu-24.04-amd64.deb"
BEAGLE_STREAM_SERVER_URL="${BEAGLE_STREAM_SERVER_URL:-$BEAGLE_STREAM_SERVER_DEFAULT_URL}"
BEAGLE_STREAM_SERVER_SHA256="${BEAGLE_STREAM_SERVER_SHA256:-}"
BEAGLE_STREAM_SERVER_NATIVE_SOURCE_DIR_DEFAULT="/opt/beagle/forks/beagle-stream-server"
BEAGLE_STREAM_SERVER_NATIVE_SOURCE_DIR="${BEAGLE_STREAM_SERVER_NATIVE_SOURCE_DIR:-$BEAGLE_STREAM_SERVER_NATIVE_SOURCE_DIR_DEFAULT}"
BEAGLE_STREAM_SERVER_NATIVE_DEPS_DIR="${BEAGLE_STREAM_SERVER_NATIVE_DEPS_DIR:-${BEAGLE_STREAM_SERVER_NATIVE_SOURCE_DIR%/}/build-beagle/_deps}"
BEAGLE_STREAM_SERVER_INSTALL_MODE="${BEAGLE_STREAM_SERVER_INSTALL_MODE:-}"
BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED="${BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED:-wan}"
BEAGLE_STREAM_SERVER_ALLOWED_CIDRS="${BEAGLE_STREAM_SERVER_ALLOWED_CIDRS:-10.88.0.0/16}"
BEAGLE_STREAM_SERVER_HEALTHCHECK_INTERVAL_SEC="${BEAGLE_STREAM_SERVER_HEALTHCHECK_INTERVAL_SEC:-15}"
BEAGLE_STREAM_SERVER_HEALTHCHECK_BOOT_DELAY_SEC="${BEAGLE_STREAM_SERVER_HEALTHCHECK_BOOT_DELAY_SEC:-20}"
BEAGLE_STREAM_SERVER_GUARD_INTERVAL_SEC="${BEAGLE_STREAM_SERVER_GUARD_INTERVAL_SEC:-10}"
BEAGLE_STREAM_SERVER_GUARD_REBOOT_THRESHOLD="${BEAGLE_STREAM_SERVER_GUARD_REBOOT_THRESHOLD:-18}"
BEAGLE_USB_MICROPHONE_VOLUME="${BEAGLE_USB_MICROPHONE_VOLUME:-250%}"
BEAGLE_CAMERA_STREAM_PORT="${BEAGLE_CAMERA_STREAM_PORT:-8091}"
PUBLIC_STREAM_HOST_RAW="${PUBLIC_STREAM_HOST:-}"
UPDATE_METADATA="${UPDATE_METADATA:-1}"
VM_REBOOT="${VM_REBOOT:-1}"
DESKTOP_PACKAGES=()
SOFTWARE_PACKAGES=()
PACKAGE_PRESETS=()
EXTRA_PACKAGES=()

resolve_public_stream_host() {
  python3 - "$1" <<'PY'
import ipaddress
import socket
import sys

host = str(sys.argv[1] or "").strip()
if not host:
    print("")
    raise SystemExit(0)
try:
    ipaddress.ip_address(host)
except ValueError:
    pass
else:
    print(host)
    raise SystemExit(0)

try:
    infos = socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
except socket.gaierror:
    print(host)
    raise SystemExit(0)

for item in infos:
    ip = str(item[4][0]).strip()
    if ip:
        print(ip)
        raise SystemExit(0)
print(host)
PY
}

PUBLIC_STREAM_HOST="$(resolve_public_stream_host "$PUBLIC_STREAM_HOST_RAW")"
STREAM_RUNTIME_STATUS_FILE="/etc/beagle/stream-runtime.env"

usage() {
  cat <<EOF
Usage: $0 --vmid VMID [--beagle-host HOST] [--guest-user USER] [--guest-password PASS] [--identity-locale LOCALE] [--identity-keymap KEYMAP] [--desktop-id ID] [--desktop-label LABEL] [--desktop-session SESSION] [--desktop-package PKG]... [--software-package PKG]... [--package-preset ID]... [--extra-package PKG]... [--beagle-user USER@REALM] [--beagle-password PASS|--beagle-token TOKEN] [--beagle-stream-server-user USER] --beagle-stream-server-password PASS --beagle-stream-server-token TOKEN [--beagle-stream-server-port PORT] [--public-stream-host HOST]
EOF
}

write_stream_runtime_status() {
  local variant="$1"
  local package_url="$2"

  install -d -m 0755 /etc/beagle
  cat > "$STREAM_RUNTIME_STATUS_FILE" <<EOF
BEAGLE_STREAM_RUNTIME_VARIANT=${variant}
BEAGLE_STREAM_RUNTIME_PACKAGE_URL=${package_url}
BEAGLE_STREAM_RUNTIME_UPDATED_AT=$(date -Iseconds)
EOF
  chmod 0644 "$STREAM_RUNTIME_STATUS_FILE"
}

resolve_beagle_stream_server_install_mode() {
  if [[ -n "$BEAGLE_STREAM_SERVER_INSTALL_MODE" ]]; then
    printf '%s\n' "$BEAGLE_STREAM_SERVER_INSTALL_MODE"
    return 0
  fi

  if [[ -d "$BEAGLE_STREAM_SERVER_NATIVE_SOURCE_DIR" && -d "$BEAGLE_STREAM_SERVER_NATIVE_DEPS_DIR/boost-src" ]]; then
    printf '%s\n' "native"
    return 0
  fi

  printf '%s\n' "package"
}

write_beagle_stream_server_broker_env() {
  install -d -m 0755 /etc/beagle
  cat > /etc/beagle/stream-server.env <<EOF
BEAGLE_CONTROL_PLANE=${BEAGLE_MANAGER_URL}
BEAGLE_STREAM_TOKEN=${BEAGLE_STREAM_SERVER_TOKEN}
BEAGLE_VM_ID=${VMID}
EOF
  chmod 0600 /etc/beagle/stream-server.env
}

apply_desktop_defaults() {
  case "${DESKTOP_ID:-plasma-cyberpunk}" in
    xfce)
      DESKTOP_LABEL="${DESKTOP_LABEL:-XFCE}"
      DESKTOP_SESSION="${DESKTOP_SESSION:-xfce}"
      if [[ ${#DESKTOP_PACKAGES[@]} -eq 0 ]]; then
        DESKTOP_PACKAGES=(xfce4 xfce4-goodies)
      fi
      ;;
    gnome)
      DESKTOP_LABEL="${DESKTOP_LABEL:-GNOME}"
      DESKTOP_SESSION="${DESKTOP_SESSION:-ubuntu-xorg}"
      if [[ ${#DESKTOP_PACKAGES[@]} -eq 0 ]]; then
        DESKTOP_PACKAGES=(ubuntu-desktop-minimal)
      fi
      ;;
    plasma|plasma-*|kde|kde-plasma)
      DESKTOP_LABEL="${DESKTOP_LABEL:-Beagle Desktop}"
      DESKTOP_SESSION="${DESKTOP_SESSION:-plasma}"
      if [[ ${#DESKTOP_PACKAGES[@]} -eq 0 ]]; then
        DESKTOP_PACKAGES=(plasma-desktop kwin-x11 plasma-nm plasma-pa plasma-widgets-addons konsole dolphin)
      fi
      ;;
    mate)
      DESKTOP_LABEL="${DESKTOP_LABEL:-MATE}"
      DESKTOP_SESSION="${DESKTOP_SESSION:-mate}"
      if [[ ${#DESKTOP_PACKAGES[@]} -eq 0 ]]; then
        DESKTOP_PACKAGES=(mate-desktop-environment-core mate-terminal caja)
      fi
      ;;
    lxqt)
      DESKTOP_LABEL="${DESKTOP_LABEL:-LXQt}"
      DESKTOP_SESSION="${DESKTOP_SESSION:-lxqt}"
      if [[ ${#DESKTOP_PACKAGES[@]} -eq 0 ]]; then
        DESKTOP_PACKAGES=(lxqt qterminal pcmanfm-qt)
      fi
      ;;
    *)
      echo "Unsupported desktop-id: ${DESKTOP_ID}" >&2
      exit 1
      ;;
  esac
}

join_words() {
  local IFS=' '
  printf '%s' "$*"
}

join_csv() {
  local IFS=','
  printf '%s' "$*"
}

require_tool() {
  local tool="$1"
  command -v "$tool" >/dev/null 2>&1 || {
    echo "Missing required tool: $tool" >&2
    exit 1
  }
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --beagle-host|--beagle-host) BEAGLE_HOST="$2"; shift 2 ;; # --beagle-host kept for backwards compat
      --vmid) VMID="$2"; shift 2 ;;
      --guest-user) GUEST_USER="$2"; shift 2 ;;
      --guest-password) GUEST_PASSWORD="$2"; shift 2 ;;
      --guest-ip) GUEST_IP_OVERRIDE="$2"; shift 2 ;;
      --identity-locale) IDENTITY_LOCALE="$2"; shift 2 ;;
      --identity-keymap) IDENTITY_KEYMAP="$2"; shift 2 ;;
      --desktop-id) DESKTOP_ID="$2"; shift 2 ;;
      --desktop-label) DESKTOP_LABEL="$2"; shift 2 ;;
      --desktop-session) DESKTOP_SESSION="$2"; shift 2 ;;
      --desktop-package) DESKTOP_PACKAGES+=("$2"); shift 2 ;;
      --software-package) SOFTWARE_PACKAGES+=("$2"); shift 2 ;;
      --package-preset) PACKAGE_PRESETS+=("$2"); shift 2 ;;
      --extra-package) EXTRA_PACKAGES+=("$2"); shift 2 ;;
      --beagle-user) BEAGLE_USER="$2"; shift 2 ;;
      --beagle-password) BEAGLE_PASSWORD="$2"; shift 2 ;;
      --beagle-token) BEAGLE_TOKEN="$2"; shift 2 ;;
      --beagle-stream-server-user) BEAGLE_STREAM_SERVER_USER="$2"; shift 2 ;;
      --beagle-stream-server-password) BEAGLE_STREAM_SERVER_PASSWORD="$2"; shift 2 ;;
      --beagle-stream-server-token) BEAGLE_STREAM_SERVER_TOKEN="$2"; shift 2 ;;
      --beagle-stream-server-port) BEAGLE_STREAM_SERVER_PORT="$2"; shift 2 ;;
      --beagle-camera-stream-port) BEAGLE_CAMERA_STREAM_PORT="$2"; shift 2 ;;
      --beagle-stream-server-url) BEAGLE_STREAM_SERVER_URL="$2"; shift 2 ;;
      --beagle-stream-server-origin-web-ui-allowed) BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED="$2"; shift 2 ;;
      --beagle-stream-server-allowed-cidrs) BEAGLE_STREAM_SERVER_ALLOWED_CIDRS="$2"; shift 2 ;;
      --public-stream-host) PUBLIC_STREAM_HOST="$2"; shift 2 ;;
      --no-metadata) UPDATE_METADATA="0"; shift ;;
      --no-reboot) VM_REBOOT="0"; shift ;;
      -h|--help) usage; exit 0 ;;
      *)
        echo "Unknown argument: $1" >&2
        usage
        exit 1
        ;;
    esac
  done
  IDENTITY_LANGUAGE="${IDENTITY_LOCALE%%_*}:${IDENTITY_LOCALE%%_*}"
  apply_desktop_defaults
}

qm_guest_exec_sync() {
  local command="$1"
  beagle_provider_guest_exec_sync_bash "$VMID" "$command"
}

guest_copy_file() {
  local local_path="$1"
  local remote_path="$2"
  local remote_dir=""
  local guest_ip=""
  local file_b64=""
  local chunk=""
  local chunk_size=3000

  [[ -f "$local_path" ]] || {
    echo "guest_copy_file: local file missing: $local_path" >&2
    return 1
  }

  remote_dir="$(dirname "$remote_path")"
  guest_ip="$GUEST_IP_OVERRIDE"
  if [[ -z "$guest_ip" ]]; then
    guest_ip="$(detect_guest_ip | tail -n1 | tr -d '\r' || true)"
  fi

  if [[ -n "$GUEST_PASSWORD" && -n "$guest_ip" ]] && command -v sshpass >/dev/null 2>&1; then
    local ssh_target="${GUEST_USER}@${guest_ip}"
    printf '%s\n' "$GUEST_PASSWORD" | SSHPASS="$GUEST_PASSWORD" sshpass -e ssh \
      -o StrictHostKeyChecking=no \
      -o UserKnownHostsFile=/dev/null \
      -o PreferredAuthentications=password \
      -o PubkeyAuthentication=no \
      -o ConnectTimeout=10 \
      "$ssh_target" "sudo -S -p '' mkdir -p '$remote_dir' && sudo -S -p '' rm -f '$remote_path'" >/dev/null
    SSHPASS="$GUEST_PASSWORD" sshpass -e scp \
      -o StrictHostKeyChecking=no \
      -o UserKnownHostsFile=/dev/null \
      -o PreferredAuthentications=password \
      -o PubkeyAuthentication=no \
      -o ConnectTimeout=10 \
      "$local_path" "${ssh_target}:${remote_path}.tmp" >/dev/null
    printf '%s\n' "$GUEST_PASSWORD" | SSHPASS="$GUEST_PASSWORD" sshpass -e ssh \
      -o StrictHostKeyChecking=no \
      -o UserKnownHostsFile=/dev/null \
      -o PreferredAuthentications=password \
      -o PubkeyAuthentication=no \
      -o ConnectTimeout=10 \
      "$ssh_target" "sudo -S -p '' install -m 0644 '${remote_path}.tmp' '$remote_path' && rm -f '${remote_path}.tmp'" >/dev/null
    return 0
  fi

  file_b64="$(base64 -w0 "$local_path")"
  qm_guest_exec_sync "mkdir -p '$remote_dir' && rm -f '${remote_path}.b64' '$remote_path' && touch '${remote_path}.b64' && chmod 600 '${remote_path}.b64'" >/dev/null
  while [[ -n "$file_b64" ]]; do
    chunk="${file_b64:0:$chunk_size}"
    file_b64="${file_b64:$chunk_size}"
    qm_guest_exec_sync "printf '%s' '$chunk' >> '${remote_path}.b64'" >/dev/null
  done
  qm_guest_exec_sync "base64 -d '${remote_path}.b64' > '$remote_path' && chmod 0644 '$remote_path' && rm -f '${remote_path}.b64'" >/dev/null
}

guest_exec_script() {
  local script="$1"
  local guest_ip=""
  local script_b64
  local chunk=""
  local chunk_size=3000

  guest_ip="$GUEST_IP_OVERRIDE"
  if [[ -z "$guest_ip" ]]; then
    guest_ip="$(detect_guest_ip | tail -n1 | tr -d '\r' || true)"
  fi
  if [[ -n "$GUEST_PASSWORD" && -n "$guest_ip" ]] && command -v sshpass >/dev/null 2>&1; then
    local ssh_target="${GUEST_USER}@${guest_ip}"
    local tmp_script
    local remote_script_path="/home/${GUEST_USER}/pve-beagle-stream-server-setup.sh"
    tmp_script="$(mktemp)"
    printf '%s' "$script" >"$tmp_script"
    SSHPASS="$GUEST_PASSWORD" sshpass -e scp \
      -o StrictHostKeyChecking=no \
      -o UserKnownHostsFile=/dev/null \
      -o PreferredAuthentications=password \
      -o PubkeyAuthentication=no \
      -o ConnectTimeout=10 \
      "$tmp_script" "${ssh_target}:${remote_script_path}" >/dev/null
    printf '%s\n' "$GUEST_PASSWORD" | SSHPASS="$GUEST_PASSWORD" sshpass -e ssh \
      -o StrictHostKeyChecking=no \
      -o UserKnownHostsFile=/dev/null \
      -o PreferredAuthentications=password \
      -o PubkeyAuthentication=no \
      -o ConnectTimeout=10 \
      "$ssh_target" "sudo -S -p '' bash ${remote_script_path} && rm -f ${remote_script_path}" >/dev/null
    rm -f "$tmp_script"
    return 0
  fi

  script_b64="$(printf '%s' "$script" | base64 -w0)"

  qm_guest_exec_sync "rm -f /tmp/pve-beagle-stream-server-setup.sh /tmp/pve-beagle-stream-server-setup.sh.b64 && touch /tmp/pve-beagle-stream-server-setup.sh.b64 && chmod 600 /tmp/pve-beagle-stream-server-setup.sh.b64" >/dev/null
  while [[ -n "$script_b64" ]]; do
    chunk="${script_b64:0:$chunk_size}"
    script_b64="${script_b64:$chunk_size}"
    qm_guest_exec_sync "printf '%s' '$chunk' >> /tmp/pve-beagle-stream-server-setup.sh.b64" >/dev/null
  done
  qm_guest_exec_sync "base64 -d /tmp/pve-beagle-stream-server-setup.sh.b64 >/tmp/pve-beagle-stream-server-setup.sh && chmod +x /tmp/pve-beagle-stream-server-setup.sh && /tmp/pve-beagle-stream-server-setup.sh" >/dev/null
}

detect_guest_ip() {
  beagle_provider_guest_ipv4 "$VMID"
}

current_vm_description() {
  beagle_provider_vm_description "$VMID"
}

set_current_vm_description_b64() {
  local description_b64="$1"
  beagle_provider_set_vm_description_b64 "$VMID" "$description_b64"
}

reboot_current_vm() {
  beagle_provider_reboot_vm "$VMID"
}

update_vm_metadata() {
  local guest_ip="$1"
  local stream_host="${PUBLIC_STREAM_HOST:-$guest_ip}"
  local stream_port="${BEAGLE_STREAM_SERVER_PORT:-}"
  local stream_api_url=""
  local encoded_desc new_desc_b64
  if [[ -n "$stream_port" ]]; then
    stream_api_url="https://${stream_host}:$((stream_port + 1))"
  else
    stream_api_url="https://${stream_host}:47990"
  fi
  encoded_desc="$(current_vm_description)"

  new_desc_b64="$(
    python3 - "$encoded_desc" "$guest_ip" "$stream_host" "$stream_port" "$stream_api_url" "$BEAGLE_STREAM_SERVER_USER" "$BEAGLE_STREAM_SERVER_PASSWORD" "$BEAGLE_USER" "$BEAGLE_PASSWORD" "$BEAGLE_TOKEN" "$GUEST_USER" "$IDENTITY_LOCALE" "$IDENTITY_KEYMAP" "$DESKTOP_ID" "$DESKTOP_LABEL" "$DESKTOP_SESSION" "$(join_csv "${PACKAGE_PRESETS[@]}")" "$(join_csv "${EXTRA_PACKAGES[@]}")" <<'PY'
import base64
import sys
from urllib.parse import unquote

(
    encoded,
    guest_ip,
    stream_host,
    stream_port,
    stream_api_url,
    beagle_stream_server_user,
    beagle_stream_server_password,
    beagle_user,
    beagle_password,
    beagle_token,
    guest_user,
    identity_locale,
    identity_keymap,
    desktop_id,
    desktop_label,
    desktop_session,
    package_presets,
    extra_packages,
) = sys.argv[1:19]
skip = {
    "beagle-stream-server-guest-user",
    "beagle-stream-server-host",
    "beagle-stream-server-ip",
    "beagle-stream-server-api-url",
    "beagle-stream-server-user",
    "beagle-stream-server-password",
    "beagle-user",
    "beagle-password",
    "beagle-token",
    "beagle-public-stream-host",
    "beagle-public-beagle-stream-client-port",
    "beagle-public-beagle-stream-server-api-url",
    "beagle-stream-server-app",
    "beagle-stream-client-host",
    "beagle-stream-client-port",
    "beagle-stream-client-app",
    "beagle-stream-client-resolution",
    "beagle-stream-client-fps",
    "beagle-stream-client-bitrate",
    "beagle-stream-client-video-codec",
    "beagle-stream-client-video-decoder",
    "beagle-stream-client-audio-config",
    "thinclient-default-mode",
    "beagle-identity-locale",
    "beagle-identity-keymap",
    "beagle-desktop",
    "beagle-desktop-id",
    "beagle-desktop-session",
    "beagle-package-presets",
    "beagle-extra-packages",
}

text = unquote(encoded) if encoded else ""
lines = []
for raw_line in text.splitlines():
    line = raw_line.strip()
    if ":" in line:
        key = line.split(":", 1)[0].strip().lower()
        if key in skip:
            continue
    if line:
        lines.append(raw_line)

lines.extend(
    [
        f"beagle-stream-server-guest-user: {guest_user}",
        f"beagle-stream-server-host: {stream_host}",
        f"beagle-stream-server-ip: {guest_ip}",
        f"beagle-stream-server-api-url: {stream_api_url}",
        "beagle-stream-server-app: Desktop",
        f"beagle-stream-client-host: {stream_host}",
        f"beagle-stream-client-port: {stream_port}",
        "beagle-stream-client-app: Desktop",
        "beagle-stream-client-resolution: auto",
        "beagle-stream-client-fps: 60",
        "beagle-stream-client-bitrate: 32000",
        "beagle-stream-client-video-codec: H.264",
        "beagle-stream-client-video-decoder: software",
        "beagle-stream-client-audio-config: stereo",
        "thinclient-default-mode: BEAGLE_STREAM_CLIENT",
        f"beagle-identity-locale: {identity_locale}",
        f"beagle-identity-keymap: {identity_keymap}",
        f"beagle-desktop: {desktop_label}",
        f"beagle-desktop-id: {desktop_id}",
        f"beagle-desktop-session: {desktop_session}",
    ]
)
if package_presets:
    lines.append(f"beagle-package-presets: {package_presets}")
if extra_packages:
    lines.append(f"beagle-extra-packages: {extra_packages}")
if stream_port:
    lines.extend(
        [
            f"beagle-public-stream-host: {stream_host}",
            f"beagle-public-beagle-stream-client-port: {stream_port}",
            f"beagle-public-beagle-stream-server-api-url: {stream_api_url}",
        ]
    )

payload = "\n".join(lines).strip() + "\n"
print(base64.b64encode(payload.encode("utf-8")).decode("ascii"))
PY
  )"

  set_current_vm_description_b64 "$new_desc_b64"
}

main() {
  local guest_script guest_ip install_mode native_artifact_dir native_source_archive native_deps_archive
  local usb_attach_script_b64 usb_attach_service_b64 mic_bridge_script_b64 mic_bridge_service_b64

  require_tool ssh
  require_tool python3
  require_tool base64

  parse_args "$@"
  install_mode="$(resolve_beagle_stream_server_install_mode)"

  [[ -f "$SCRIPT_DIR/lib/beagle-usb-attach" ]] || {
    echo "Missing required asset: $SCRIPT_DIR/lib/beagle-usb-attach" >&2
    exit 1
  }
  [[ -f "$SCRIPT_DIR/lib/beagle-usb-attach.service" ]] || {
    echo "Missing required asset: $SCRIPT_DIR/lib/beagle-usb-attach.service" >&2
    exit 1
  }
  [[ -f "$SCRIPT_DIR/lib/beagle-tc-mic-bridge" ]] || {
    echo "Missing required asset: $SCRIPT_DIR/lib/beagle-tc-mic-bridge" >&2
    exit 1
  }
  [[ -f "$SCRIPT_DIR/lib/beagle-tc-mic-bridge.service" ]] || {
    echo "Missing required asset: $SCRIPT_DIR/lib/beagle-tc-mic-bridge.service" >&2
    exit 1
  }
  usb_attach_script_b64="$(base64 -w0 "$SCRIPT_DIR/lib/beagle-usb-attach")"
  usb_attach_service_b64="$(base64 -w0 "$SCRIPT_DIR/lib/beagle-usb-attach.service")"
  mic_bridge_script_b64="$(base64 -w0 "$SCRIPT_DIR/lib/beagle-tc-mic-bridge")"
  mic_bridge_service_b64="$(base64 -w0 "$SCRIPT_DIR/lib/beagle-tc-mic-bridge.service")"

  [[ -n "$VMID" ]] || {
    echo "--vmid is required" >&2
    exit 1
  }
  [[ -n "$BEAGLE_STREAM_SERVER_PASSWORD" ]] || {
    echo "--beagle-stream-server-password is required" >&2
    exit 1
  }
  [[ -n "$BEAGLE_STREAM_SERVER_TOKEN" ]] || {
    echo "--beagle-stream-server-token is required" >&2
    exit 1
  }

  native_artifact_dir="$(mktemp -d)"
  trap '[[ -n "${native_artifact_dir:-}" ]] && rm -rf "${native_artifact_dir}"' EXIT
  native_source_archive="/tmp/beagle-stream-server-src.tar.gz"
  native_deps_archive="/tmp/beagle-stream-server-deps.tar.gz"
  if [[ "$install_mode" == "native" ]]; then
    [[ -d "$BEAGLE_STREAM_SERVER_NATIVE_SOURCE_DIR" ]] || {
      echo "native install mode requested but source dir missing: $BEAGLE_STREAM_SERVER_NATIVE_SOURCE_DIR" >&2
      exit 1
    }
    [[ -d "$BEAGLE_STREAM_SERVER_NATIVE_DEPS_DIR/boost-src" ]] || {
      echo "native install mode requested but deps cache missing: $BEAGLE_STREAM_SERVER_NATIVE_DEPS_DIR" >&2
      exit 1
    }
    tar -C "$(dirname "$BEAGLE_STREAM_SERVER_NATIVE_SOURCE_DIR")" \
      --exclude='beagle-stream-server/.git' \
      --exclude='beagle-stream-server/build*' \
      -czf "$native_artifact_dir/beagle-stream-server-src.tar.gz" \
      "$(basename "$BEAGLE_STREAM_SERVER_NATIVE_SOURCE_DIR")"
    tar -C "$BEAGLE_STREAM_SERVER_NATIVE_DEPS_DIR" \
      -czf "$native_artifact_dir/beagle-stream-server-deps.tar.gz" \
      boost-src boost-build json-src json-build ffmpeg ffmpeg-latest
  fi

  guest_script="$(cat <<EOF
#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
GUEST_USER='${GUEST_USER}'
VMID='${VMID}'
BEAGLE_MANAGER_URL='${BEAGLE_MANAGER_URL}'
IDENTITY_LOCALE='${IDENTITY_LOCALE:-de_DE.UTF-8}'
IDENTITY_LANGUAGE='${IDENTITY_LANGUAGE:-de:de}'
IDENTITY_KEYMAP='${IDENTITY_KEYMAP:-de}'
DESKTOP_ID='${DESKTOP_ID}'
DESKTOP_SESSION='${DESKTOP_SESSION}'
DESKTOP_PACKAGES='$(join_words "${DESKTOP_PACKAGES[@]}")'
SOFTWARE_PACKAGES='$(join_words "${SOFTWARE_PACKAGES[@]}")'
BEAGLE_STREAM_SERVER_USER='${BEAGLE_STREAM_SERVER_USER}'
BEAGLE_STREAM_SERVER_PASSWORD='${BEAGLE_STREAM_SERVER_PASSWORD}'
BEAGLE_STREAM_SERVER_TOKEN='${BEAGLE_STREAM_SERVER_TOKEN}'
BEAGLE_STREAM_SERVER_PORT='${BEAGLE_STREAM_SERVER_PORT}'
BEAGLE_STREAM_SERVER_URL='${BEAGLE_STREAM_SERVER_URL}'
BEAGLE_STREAM_SERVER_SHA256='${BEAGLE_STREAM_SERVER_SHA256}'
BEAGLE_STREAM_SERVER_INSTALL_MODE='${install_mode}'
BEAGLE_STREAM_SERVER_NATIVE_SOURCE_ARCHIVE='${native_source_archive}'
BEAGLE_STREAM_SERVER_NATIVE_DEPS_ARCHIVE='${native_deps_archive}'
BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED='${BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED}'
BEAGLE_STREAM_SERVER_ALLOWED_CIDRS='${BEAGLE_STREAM_SERVER_ALLOWED_CIDRS}'
BEAGLE_STREAM_SERVER_HEALTHCHECK_INTERVAL_SEC='${BEAGLE_STREAM_SERVER_HEALTHCHECK_INTERVAL_SEC}'
BEAGLE_STREAM_SERVER_HEALTHCHECK_BOOT_DELAY_SEC='${BEAGLE_STREAM_SERVER_HEALTHCHECK_BOOT_DELAY_SEC}'
BEAGLE_STREAM_SERVER_GUARD_INTERVAL_SEC='${BEAGLE_STREAM_SERVER_GUARD_INTERVAL_SEC}'
BEAGLE_STREAM_SERVER_GUARD_REBOOT_THRESHOLD='${BEAGLE_STREAM_SERVER_GUARD_REBOOT_THRESHOLD}'
BEAGLE_CAMERA_STREAM_PORT='${BEAGLE_CAMERA_STREAM_PORT}'
BEAGLE_USB_ATTACH_SCRIPT_B64='${usb_attach_script_b64}'
BEAGLE_USB_ATTACH_SERVICE_B64='${usb_attach_service_b64}'
BEAGLE_TC_MIC_BRIDGE_SCRIPT_B64='${mic_bridge_script_b64}'
BEAGLE_TC_MIC_BRIDGE_SERVICE_B64='${mic_bridge_service_b64}'
BEAGLE_TC_MIC_BRIDGE_PORT="\${BEAGLE_TC_MIC_BRIDGE_PORT:-\$((43000 + VMID + 100))}"

configure_system_locale() {
  local locale="\${IDENTITY_LOCALE:-de_DE.UTF-8}"
  local language="\${IDENTITY_LANGUAGE:-de_DE:de}"
  local language_code="\${locale%%_*}"
  local escaped_locale=""

  apt-get install -y --no-install-recommends locales
  case "\$language_code" in
    de)
      # Ubuntu language-pack packages are optional and not present on Debian hosts.
      if apt-cache show language-pack-de >/dev/null 2>&1 && apt-cache show language-pack-gnome-de >/dev/null 2>&1; then
        apt-get install -y --no-install-recommends language-pack-de language-pack-gnome-de || true
      fi
      ;;
  esac

  escaped_locale="\$(printf '%s\n' "\$locale" | sed 's/[.[\\*^$()+?{}|]/\\\\&/g')"
  if grep -q "^# \$escaped_locale UTF-8" /etc/locale.gen 2>/dev/null; then
    sed -i "s/^# \$escaped_locale UTF-8/\$locale UTF-8/" /etc/locale.gen
  elif ! grep -q "^\$escaped_locale UTF-8" /etc/locale.gen 2>/dev/null; then
    printf '%s UTF-8\n' "\$locale" >> /etc/locale.gen
  fi

  locale-gen "\$locale" >/dev/null 2>&1 || true
  update-locale LANG="\$locale" LANGUAGE="\$language" >/dev/null 2>&1 || true
  cat > /etc/default/locale <<LOCALECONF
LANG=\$locale
LANGUAGE=\$language
LOCALECONF

  install -d -m 0755 /var/lib/AccountsService/users
  cat > "/var/lib/AccountsService/users/\$GUEST_USER" <<ACCOUNTCONF
[User]
Language=\$locale
XSession=\${DESKTOP_SESSION}
ACCOUNTCONF

  cat > "/home/\$GUEST_USER/.dmrc" <<DMRCCONF
[Desktop]
Language=\$locale
Session=\${DESKTOP_SESSION}
DMRCCONF
  chown "\$GUEST_USER:\$GUEST_USER" "/home/\$GUEST_USER/.dmrc"
}

configure_keyboard_layout() {
  local keymap="\${IDENTITY_KEYMAP:-de}"

  cat > /etc/default/keyboard <<KEYBOARDCONF
XKBMODEL="pc105"
XKBLAYOUT="\${keymap}"
XKBVARIANT=""
XKBOPTIONS=""
BACKSPACE="guess"
KEYBOARDCONF

  install -d -m 0755 /etc/X11/xorg.conf.d
  cat > /etc/X11/xorg.conf.d/00-keyboard.conf <<KEYMAPCONF
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "\${keymap}"
    Option "XkbModel" "pc105"
EndSection
KEYMAPCONF
}

install_google_chrome() {
  install -d -m 0755 /etc/apt/keyrings
  apt-get install -y --no-install-recommends gnupg xdg-utils
  curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
    | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg.tmp
  install -m 0644 /etc/apt/keyrings/google-chrome.gpg.tmp /etc/apt/keyrings/google-chrome.gpg
  rm -f /etc/apt/keyrings/google-chrome.gpg.tmp
  cat > /etc/apt/sources.list.d/google-chrome.list <<'CHROMEREPO'
deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main
CHROMEREPO
  apt-get update
  apt-get install -y --no-install-recommends google-chrome-stable
}

install_visual_studio_code_repo() {
  install -d -m 0755 /etc/apt/keyrings
  apt-get install -y --no-install-recommends gnupg
  curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor -o /etc/apt/keyrings/packages.microsoft.gpg.tmp
  install -m 0644 /etc/apt/keyrings/packages.microsoft.gpg.tmp /etc/apt/keyrings/packages.microsoft.gpg
  rm -f /etc/apt/keyrings/packages.microsoft.gpg.tmp
  cat > /etc/apt/sources.list.d/vscode.list <<'VSCODEREPO'
deb [arch=amd64 signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main
VSCODEREPO
  apt-get update
}

configure_default_browser() {
  install -d -m 0700 -o "\$GUEST_USER" -g "\$GUEST_USER" \
    "/home/\$GUEST_USER/.config" \
    "/home/\$GUEST_USER/.config/xfce4"
  update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/bin/google-chrome-stable 200 >/dev/null 2>&1 || true
  update-alternatives --install /usr/bin/gnome-www-browser gnome-www-browser /usr/bin/google-chrome-stable 200 >/dev/null 2>&1 || true
  update-alternatives --set x-www-browser /usr/bin/google-chrome-stable >/dev/null 2>&1 || true
  update-alternatives --set gnome-www-browser /usr/bin/google-chrome-stable >/dev/null 2>&1 || true
  cat > "/home/\$GUEST_USER/.config/xfce4/helpers.rc" <<'HELPERS'
WebBrowser=google-chrome
MailReader=thunderbird
TerminalEmulator=xfce4-terminal
FileManager=thunar
HELPERS
  cat > "/home/\$GUEST_USER/.config/mimeapps.list" <<'MIMEAPPS'
[Default Applications]
x-scheme-handler/http=google-chrome.desktop
x-scheme-handler/https=google-chrome.desktop
text/html=google-chrome.desktop
application/xhtml+xml=google-chrome.desktop
x-scheme-handler/about=google-chrome.desktop
x-scheme-handler/unknown=google-chrome.desktop
MIMEAPPS
  chown "\$GUEST_USER:\$GUEST_USER" \
    "/home/\$GUEST_USER/.config/xfce4/helpers.rc" \
    "/home/\$GUEST_USER/.config/mimeapps.list"
}

echo 'lightdm shared/default-x-display-manager select lightdm' | debconf-set-selections
apt-get update
install_visual_studio_code_repo
apt-get install -y \
  x11-xserver-utils \
  lightdm \
  lightdm-gtk-greeter \
  curl \
  ca-certificates \
  nftables \
  pipewire \
  pipewire-pulse \
  wireplumber \
  pulseaudio-utils \
  xdg-utils \
  usbutils \
  linux-tools-generic \
  build-essential \
  cmake \
  ninja-build \
  pkg-config \
  git \
  python3-jinja2 \
  python3-setuptools \
  libcap-dev \
  libdrm-dev \
  libevdev-dev \
  libminiupnpc-dev \
  libnotify-dev \
  libpipewire-0.3-dev \
  libva-dev \
  libwayland-dev \
  wayland-protocols \
  libx11-dev
if ! apt-get install -y --no-install-recommends usbip-utils >/dev/null 2>&1; then
  apt-get install -y --no-install-recommends usbip >/dev/null 2>&1 || true
fi
if [[ -n "\$DESKTOP_PACKAGES" ]]; then
  apt-get install -y \$DESKTOP_PACKAGES
fi
if [[ -n "\$SOFTWARE_PACKAGES" ]]; then
  apt-get install -y \$SOFTWARE_PACKAGES
fi

tmpdir=\$(mktemp -d)
trap 'rm -rf "\$tmpdir"' EXIT
stream_runtime_package_url="\$BEAGLE_STREAM_SERVER_URL"
stream_runtime_variant="beagle-stream-server"
if [[ "\${BEAGLE_STREAM_SERVER_INSTALL_MODE:-package}" == "native" ]]; then
  stream_runtime_variant="beagle-stream-server-native"
  stream_runtime_package_url="native:\$BEAGLE_STREAM_SERVER_NATIVE_SOURCE_ARCHIVE"
  install -d -m 0755 /opt/beagle-build/src /opt/beagle-build/cache
  rm -rf /opt/beagle-build/src/beagle-stream-server /opt/beagle-build/build-beagle-stream-server
  mkdir -p /opt/beagle-build/src/beagle-stream-server /opt/beagle-build/build-beagle-stream-server/_deps
  tar -xzf "\$BEAGLE_STREAM_SERVER_NATIVE_SOURCE_ARCHIVE" -C /opt/beagle-build/src/beagle-stream-server --strip-components=1
  tar -xzf "\$BEAGLE_STREAM_SERVER_NATIVE_DEPS_ARCHIVE" -C /opt/beagle-build/build-beagle-stream-server/_deps
  cd /opt/beagle-build/build-beagle-stream-server
  cmake -GNinja \
    -DCMAKE_BUILD_TYPE=Release \
    -DBEAGLE_INTEGRATION=ON \
    -DBUILD_DOCS=OFF \
    -DBUILD_TESTS=OFF \
    -DSUNSHINE_ENABLE_TRAY=OFF \
    -DSUNSHINE_ENABLE_CUDA=OFF \
    -DFFMPEG_PREPARED_BINARIES=/opt/beagle-build/build-beagle-stream-server/_deps/ffmpeg \
    /opt/beagle-build/src/beagle-stream-server
  ninja -j"\$(nproc)" sunshine
  install -m 0755 sunshine /usr/local/bin/sunshine
else
  curl -fL \
    --retry 8 \
    --retry-delay 3 \
    --retry-connrefused \
    --retry-all-errors \
    --continue-at - \
    --speed-limit 5000 \
    --speed-time 30 \
    -o "\$tmpdir/beagle-stream-server.deb" \
    "\$BEAGLE_STREAM_SERVER_URL"
  if [[ -n "\$BEAGLE_STREAM_SERVER_SHA256" ]]; then
    actual_sha="\$(sha256sum "\$tmpdir/beagle-stream-server.deb" | awk '{print \$1}')"
    if [[ "\$actual_sha" != "\$BEAGLE_STREAM_SERVER_SHA256" ]]; then
      echo "Checksum mismatch for beagle-stream-server package: expected \$BEAGLE_STREAM_SERVER_SHA256, got \$actual_sha" >&2
      exit 1
    fi
  fi
  apt-get install -y "\$tmpdir/beagle-stream-server.deb"
fi
install -d -m 0755 /etc/beagle
cat > /etc/beagle/stream-runtime.env <<RUNTIMEENV
BEAGLE_STREAM_RUNTIME_VARIANT=\${stream_runtime_variant}
BEAGLE_STREAM_RUNTIME_PACKAGE_URL=\${stream_runtime_package_url}
BEAGLE_STREAM_RUNTIME_UPDATED_AT=\$(date -Iseconds)
RUNTIMEENV
chmod 0644 /etc/beagle/stream-runtime.env
BEAGLE_STREAM_SERVER_EXEC="\$(command -v beagle-stream-server 2>/dev/null || echo /usr/bin/beagle-stream-server)"
if [[ -x /usr/local/bin/sunshine || -n "\$(command -v sunshine 2>/dev/null || true)" ]]; then
cat > /usr/local/bin/beagle-stream-server <<'BEAGLEWRAP'
#!/usr/bin/env bash
if [[ -x /usr/local/bin/sunshine ]]; then
  exec /usr/local/bin/sunshine "\$@"
fi
exec "\$(command -v sunshine)" "\$@"
BEAGLEWRAP
chmod 0755 /usr/local/bin/beagle-stream-server
BEAGLE_STREAM_SERVER_EXEC="/usr/local/bin/beagle-stream-server"
fi
configure_system_locale
configure_keyboard_layout
install_google_chrome

install -d -m 0755 /etc/lightdm/lightdm.conf.d
rm -f /etc/lightdm/lightdm.conf.d/60-pve-thin-client.conf
cat > /etc/lightdm/lightdm.conf.d/60-beagle.conf <<GUESTCFG
[Seat:*]
autologin-user=${GUEST_USER}
autologin-session=${DESKTOP_SESSION}
user-session=${DESKTOP_SESSION}
greeter-session=lightdm-gtk-greeter
GUESTCFG

install -d -m 0700 -o "\$GUEST_USER" -g "\$GUEST_USER" \
  "/home/\$GUEST_USER/.config" \
  "/home/\$GUEST_USER/.config/autostart" \
  "/home/\$GUEST_USER/.config/beagle-stream-server" \
  "/home/\$GUEST_USER/.local" \
  "/home/\$GUEST_USER/.local/state" \
  "/home/\$GUEST_USER/.local/state/wireplumber" \
  "/home/\$GUEST_USER/.config/xfce4/xfconf/xfce-perchannel-xml"
if [[ -d "/home/\$GUEST_USER/.config/sunshine" && ! -e "/home/\$GUEST_USER/.config/beagle-stream-server" ]]; then
  mv "/home/\$GUEST_USER/.config/sunshine" "/home/\$GUEST_USER/.config/beagle-stream-server"
fi
if [[ -e "/home/\$GUEST_USER/.config/sunshine" && ! -L "/home/\$GUEST_USER/.config/sunshine" ]]; then
  cp -a "/home/\$GUEST_USER/.config/sunshine/." "/home/\$GUEST_USER/.config/beagle-stream-server/" 2>/dev/null || true
  rm -rf "/home/\$GUEST_USER/.config/sunshine"
fi
ln -sfn "/home/\$GUEST_USER/.config/beagle-stream-server" "/home/\$GUEST_USER/.config/sunshine"
install -d -m 0755 /etc/X11/xorg.conf.d
GUEST_UID="\$(id -u "\$GUEST_USER")"

cat > /etc/X11/xorg.conf.d/20-beagle-software-cursor.conf <<'XORGCONF'
Section "Device"
  Identifier "Beagle Virtio GPU Software Cursor"
  Driver "modesetting"
  Option "SWCursor" "true"
EndSection
XORGCONF

cat > /etc/X11/xorg.conf.d/90-beagle-ignore-virtual-input.conf <<'XORGCONF'
Section "InputClass"
    Identifier "beagle-ignore-touch-passthrough"
    MatchProduct "Touch passthrough"
    Option "Ignore" "on"
EndSection

Section "InputClass"
    Identifier "beagle-ignore-pen-passthrough"
    MatchProduct "Pen passthrough"
    Option "Ignore" "on"
EndSection
XORGCONF

cat > /etc/X11/Xsession.d/19-beagle-lightdm-session-compat <<'XSESSIONCOMPAT'
#!/bin/sh
# LightDM may source Xsession.d snippets directly without the helpers from
# /etc/X11/Xsession. Provide safe fallbacks so downstream snippets stay valid.

: "\${OPTIONFILE:=/etc/X11/Xsession.options}"
: "\${SYSRESOURCES:=/etc/X11/Xresources}"
: "\${USRRESOURCES:=\$HOME/.Xresources}"
: "\${USERXSESSION:=\$HOME/.xsession}"
: "\${USERXSESSIONRC:=\$HOME/.xsessionrc}"
: "\${ALTUSERXSESSION:=\$HOME/.Xsession}"

if ! type has_option >/dev/null 2>&1; then
  OPTIONS="$({
    [ -r "\$OPTIONFILE" ] && cat "\$OPTIONFILE"
    if [ -d /etc/X11/Xsession.options.d ]; then
      run-parts --list --regex '\\.conf$' /etc/X11/Xsession.options.d | xargs -d '\n' cat
    fi
  } 2>/dev/null)"

  has_option() {
    if [ "$(echo "\$OPTIONS" | grep -Eo "^(no-)?\$1\\>" | tail -n 1)" = "\$1" ]; then
      return 0
    fi
    return 1
  }
fi

if ! type message >/dev/null 2>&1; then
  message() {
    echo "Xsession: \$*" >&2
  }
fi

if ! type errormsg >/dev/null 2>&1; then
  errormsg() {
    message "$*"
    return 1
  }
fi
XSESSIONCOMPAT
chmod 0755 /etc/X11/Xsession.d/19-beagle-lightdm-session-compat

cat > /etc/X11/Xsession.d/90-beagle-disable-display-idle <<'XSESSIONIDLE'
#!/bin/sh
if command -v xset >/dev/null 2>&1; then
  xset -dpms >/dev/null 2>&1 || true
  xset s off >/dev/null 2>&1 || true
  xset s noblank >/dev/null 2>&1 || true
fi
XSESSIONIDLE
chmod 0755 /etc/X11/Xsession.d/90-beagle-disable-display-idle

cat > "/home/\$GUEST_USER/.xprofile" <<'XPROFILE'
#!/bin/sh
if command -v xset >/dev/null 2>&1; then
  xset -dpms >/dev/null 2>&1 || true
  xset s off >/dev/null 2>&1 || true
  xset s noblank >/dev/null 2>&1 || true
fi
XPROFILE
chmod 0755 "/home/\$GUEST_USER/.xprofile"

cat > "/home/\$GUEST_USER/.config/beagle-stream-server/beagle-stream-server.conf" <<SUNCONF
beagle_stream_server_name = ${GUEST_USER}-beagle-stream-server
min_log_level = info
origin_web_ui_allowed = ${BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED}
origin_pin_allowed = ${BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED}
encoder = software
sw_preset = ultrafast
sw_tune = zerolatency
capture = kms
hevc_mode = 0
av1_mode = 0
minimum_fps_target = 60
max_bitrate = 35000
$( printf 'port = %s\n' "${BEAGLE_STREAM_SERVER_PORT:-50000}" )
SUNCONF
cp "/home/\$GUEST_USER/.config/beagle-stream-server/beagle-stream-server.conf" "/home/\$GUEST_USER/.config/beagle-stream-server/sunshine.conf"

cat > "/home/\$GUEST_USER/.config/beagle-stream-server/apps.json" <<'APPS'
{
  "env": {
    "PATH": "\$(PATH):\$(HOME)/.local/bin"
  },
  "apps": [
    {
      "name": "Desktop",
      "image-path": "desktop.png"
    }
  ]
}
APPS

python3 - "/home/\$GUEST_USER/.config/beagle-stream-server/sunshine_state.json" <<'PY'
import json
import sys
import uuid
from pathlib import Path

state_path = Path(sys.argv[1])
payload = {}
if state_path.exists():
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
root = payload.setdefault("root", {})
named = root.get("named_devices")
if not isinstance(named, list):
    root["named_devices"] = []
root["uniqueid"] = str(root.get("uniqueid") or "").strip() or str(uuid.uuid4()).upper()
state_path.parent.mkdir(parents=True, exist_ok=True)
state_path.write_text(json.dumps(payload, indent=4) + "\n", encoding="utf-8")
PY
ln -sfn "/home/\$GUEST_USER/.config/beagle-stream-server/sunshine_state.json" "/home/\$GUEST_USER/.config/beagle-stream-server/beagle_stream_server_state.json"
chown -h "\$GUEST_USER:\$GUEST_USER" "/home/\$GUEST_USER/.config/beagle-stream-server/beagle_stream_server_state.json" >/dev/null 2>&1 || true
chown "\$GUEST_USER:\$GUEST_USER" "/home/\$GUEST_USER/.config/beagle-stream-server/sunshine_state.json" >/dev/null 2>&1 || true
chmod 0600 "/home/\$GUEST_USER/.config/beagle-stream-server/sunshine_state.json" >/dev/null 2>&1 || true

if [[ "\$DESKTOP_ID" == "xfce" ]]; then
cat > "/home/\$GUEST_USER/.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml" <<'XFWM4'
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfwm4" version="1.0">
  <property name="general" type="empty">
    <property name="use_compositing" type="bool" value="false"/>
    <property name="vblank_mode" type="string" value="off"/>
  </property>
</channel>
XFWM4

cat > "/home/\$GUEST_USER/.config/autostart/light-locker.desktop" <<'AUTOSTARTLOCK'
[Desktop Entry]
Type=Application
Name=Light Locker
Exec=light-locker
Hidden=true
X-GNOME-Autostart-enabled=false
AUTOSTARTLOCK

cat > "/home/\$GUEST_USER/.config/autostart/xfce4-power-manager.desktop" <<'AUTOSTARTPOWER'
[Desktop Entry]
Type=Application
Name=XFCE Power Manager
Hidden=true
AUTOSTARTPOWER

cat > "/home/\$GUEST_USER/.config/autostart/xfce4-screensaver.desktop" <<'AUTOSTARTSCREENSAVER'
[Desktop Entry]
Type=Application
Name=XFCE Screensaver
Hidden=true
AUTOSTARTSCREENSAVER
fi

chown -R "\$GUEST_USER:\$GUEST_USER" "/home/\$GUEST_USER/.config" "/home/\$GUEST_USER/.local"
chown "\$GUEST_USER:\$GUEST_USER" "/home/\$GUEST_USER/.xprofile"
configure_default_browser

cat > /etc/systemd/system/beagle-stream-server.service <<BEAGLE_STREAM_SERVERSVC
[Unit]
Description=Beagle Beagle Stream Server
After=network-online.target display-manager.service graphical.target sound.target
Wants=network-online.target
StartLimitIntervalSec=0
OnFailure=beagle-stream-server-healthcheck.service

[Service]
Type=simple
User=\$GUEST_USER
Group=\$GUEST_USER
SupplementaryGroups=video render input
CapabilityBoundingSet=CAP_SYS_ADMIN CAP_SYS_NICE CAP_SETPCAP CAP_DAC_OVERRIDE CAP_CHOWN CAP_FOWNER CAP_KILL CAP_SETGID CAP_SETUID
AmbientCapabilities=CAP_SYS_ADMIN CAP_SYS_NICE
LimitNICE=-15
Nice=-10
CPUWeight=10000
Environment=HOME=/home/\$GUEST_USER
Environment=XDG_CONFIG_HOME=/home/\$GUEST_USER/.config
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/\$GUEST_USER/.Xauthority
Environment=XDG_RUNTIME_DIR=/run/user/\$GUEST_UID
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/\$GUEST_UID/bus
Environment=PULSE_SERVER=unix:/run/user/\$GUEST_UID/pulse/native
EnvironmentFile=-/etc/beagle/stream-server.env
ExecStartPre=/usr/local/bin/beagle-stream-server-preflight
ExecStartPre=/bin/bash -lc 'pulse_socket="/run/user/\$GUEST_UID/pulse/native"; for _ in {1..180}; do if [[ -S /tmp/.X11-unix/X0 && -s /home/\$GUEST_USER/.Xauthority && -d /run/user/\$GUEST_UID && -S /run/user/\$GUEST_UID/bus && -S "\\\$pulse_socket" ]] && DISPLAY=:0 XAUTHORITY=/home/\$GUEST_USER/.Xauthority xrandr --query >/dev/null 2>&1 && DISPLAY=:0 XAUTHORITY=/home/\$GUEST_USER/.Xauthority xrandr --query | grep -q " connected"; then sleep 5; exit 0; fi; sleep 1; done; echo "Timed out waiting for an active graphical/audio session on :0" >&2; exit 1'
ExecStart=\$BEAGLE_STREAM_SERVER_EXEC
Restart=always
RestartSec=3
TimeoutStartSec=210

[Install]
WantedBy=graphical.target
BEAGLE_STREAM_SERVERSVC

install -d -m 0755 /etc/beagle
cat > /etc/beagle/stream-server.env <<BROKERENV
BEAGLE_CONTROL_PLANE=\$BEAGLE_MANAGER_URL
BEAGLE_STREAM_TOKEN=\$BEAGLE_STREAM_SERVER_TOKEN
BEAGLE_VM_ID=\$VMID
BROKERENV
chmod 0600 /etc/beagle/stream-server.env
cat > /etc/beagle/beagle-stream-server-healthcheck.env <<HEALTHENV
BEAGLE_STREAM_SERVER_USER=\$BEAGLE_STREAM_SERVER_USER
BEAGLE_STREAM_SERVER_PASSWORD=\$BEAGLE_STREAM_SERVER_PASSWORD
BEAGLE_STREAM_SERVER_PORT=\$BEAGLE_STREAM_SERVER_PORT
GUEST_USER=\$GUEST_USER
GUEST_UID=\$GUEST_UID
BEAGLE_STREAM_SERVER_GUARD_INTERVAL_SEC=\$BEAGLE_STREAM_SERVER_GUARD_INTERVAL_SEC
BEAGLE_STREAM_SERVER_GUARD_REBOOT_THRESHOLD=\$BEAGLE_STREAM_SERVER_GUARD_REBOOT_THRESHOLD
HEALTHENV
chmod 0600 /etc/beagle/beagle-stream-server-healthcheck.env

cat > /usr/local/bin/beagle-stream-server-preflight <<'PREFLIGHT'
#!/usr/bin/env bash
set -euo pipefail

stream_port="\${BEAGLE_STREAM_SERVER_PORT:-50000}"
if ! [[ "\$stream_port" =~ ^[0-9]+$ ]]; then
  stream_port="50000"
fi
rtsp_port="\$((stream_port + 21))"

# Sunshine can leave stale helper instances that keep RTSP bound.
pkill -x sunshine >/dev/null 2>&1 || true
sleep 1

# Best-effort cleanup for any remaining listener before start.
if command -v fuser >/dev/null 2>&1; then
  fuser -k "\${rtsp_port}/tcp" >/dev/null 2>&1 || true
fi

if ss -H -ltn "( sport = :\${rtsp_port} )" 2>/dev/null | grep -q .; then
  echo "beagle-stream-server-preflight: RTSP port \${rtsp_port} still busy" >&2
  exit 1
fi
PREFLIGHT
chmod 0755 /usr/local/bin/beagle-stream-server-preflight

cat > /usr/local/bin/beagle-stream-server-healthcheck <<'HEALTHCHECK'
#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="/etc/beagle/beagle-stream-server-healthcheck.env"
[[ -r "\$ENV_FILE" ]] || exit 1
# shellcheck disable=SC1090
source "\$ENV_FILE"

BEAGLE_STREAM_SERVER_USER="\${BEAGLE_STREAM_SERVER_USER:-beagle-stream-server}"
BEAGLE_STREAM_SERVER_PASSWORD="\${BEAGLE_STREAM_SERVER_PASSWORD:-}"
BEAGLE_STREAM_SERVER_PORT="\${BEAGLE_STREAM_SERVER_PORT:-}"
GUEST_USER="\${GUEST_USER:-beagle}"
GUEST_UID="\${GUEST_UID:-\$(id -u "\$GUEST_USER" 2>/dev/null || echo 1000)}"

repair="\${1:-}"
api_port=47990
if [[ -n "\$BEAGLE_STREAM_SERVER_PORT" ]]; then
  api_port="\$((BEAGLE_STREAM_SERVER_PORT + 1))"
fi
rtsp_port=50021
if [[ -n "\$BEAGLE_STREAM_SERVER_PORT" && "\$BEAGLE_STREAM_SERVER_PORT" =~ ^[0-9]+$ ]]; then
  rtsp_port="\$((BEAGLE_STREAM_SERVER_PORT + 21))"
fi

ensure_runtime() {
  local runtime_dir="/run/user/\${GUEST_UID}"
  if [[ ! -d "\$runtime_dir" ]]; then
    loginctl enable-linger "\$GUEST_USER" >/dev/null 2>&1 || true
  fi
}

restart_stack() {
  ensure_runtime
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable beagle-stream-server.service >/dev/null 2>&1 || true
  systemctl restart beagle-stream-server.service >/dev/null 2>&1 || true
}

ensure_timer() {
  systemctl enable --now beagle-stream-server-healthcheck.timer >/dev/null 2>&1 || true
}

is_api_ready() {
  [[ -n "\$BEAGLE_STREAM_SERVER_PASSWORD" ]] || return 1
  curl -kfsS --connect-timeout 3 --max-time 5 --user "\${BEAGLE_STREAM_SERVER_USER}:\${BEAGLE_STREAM_SERVER_PASSWORD}" "https://127.0.0.1:\${api_port}/api/apps" >/dev/null # tls-bypass-allowlist: loopback health check against local Beagle Stream Server self-signed API
}

has_rtsp_port_conflict() {
  local listeners sunshine_count

  listeners="\$(ss -lntp 2>/dev/null | awk -v p=":\${rtsp_port}" '\$4 ~ p"\$" {print \$0}')"
  [[ -n "\$listeners" ]] || return 1

  sunshine_count="\$(pgrep -x sunshine 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "\${sunshine_count:-0}" -gt 1 ]]; then
    return 0
  fi

  if printf '%s\n' "\$listeners" | grep -q "sunshine"; then
    return 1
  fi
  return 0
}

ensure_timer

if [[ "\$repair" == "--repair-only" ]]; then
  restart_stack
  exit 0
fi

if ! systemctl is-active --quiet beagle-stream-server.service; then
  restart_stack
  exit 0
fi

if ! pgrep -x sunshine >/dev/null 2>&1 && ! pgrep -x beagle-stream-server >/dev/null 2>&1; then
  restart_stack
  exit 0
fi

if has_rtsp_port_conflict; then
  restart_stack
  exit 0
fi

if ! is_api_ready; then
  restart_stack
fi
HEALTHCHECK
chmod 0755 /usr/local/bin/beagle-stream-server-healthcheck

cat > /etc/systemd/system/beagle-stream-server-healthcheck.service <<'HEALTHSVC'
[Unit]
Description=Beagle Beagle Stream Server Healthcheck and Repair
After=network-online.target beagle-stream-server.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/beagle-stream-server-healthcheck
HEALTHSVC

cat > /etc/systemd/system/beagle-stream-server-healthcheck.timer <<HEALTHTIMER
[Unit]
Description=Run Beagle Beagle Stream Server healthcheck periodically

[Timer]
OnBootSec=\${BEAGLE_STREAM_SERVER_HEALTHCHECK_BOOT_DELAY_SEC}s
OnUnitActiveSec=\${BEAGLE_STREAM_SERVER_HEALTHCHECK_INTERVAL_SEC}s
Persistent=true
RandomizedDelaySec=5s
Unit=beagle-stream-server-healthcheck.service

[Install]
WantedBy=timers.target
HEALTHTIMER

cat > /usr/local/bin/beagle-stream-server-guardian <<'GUARDIAN'
#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="/etc/beagle/beagle-stream-server-healthcheck.env"
[[ -r "\$ENV_FILE" ]] || exit 1
# shellcheck disable=SC1090
source "\$ENV_FILE"

BEAGLE_STREAM_SERVER_USER="\${BEAGLE_STREAM_SERVER_USER:-beagle-stream-server}"
BEAGLE_STREAM_SERVER_PASSWORD="\${BEAGLE_STREAM_SERVER_PASSWORD:-}"
BEAGLE_STREAM_SERVER_PORT="\${BEAGLE_STREAM_SERVER_PORT:-50000}"
BEAGLE_STREAM_SERVER_GUARD_INTERVAL_SEC="\${BEAGLE_STREAM_SERVER_GUARD_INTERVAL_SEC:-10}"
BEAGLE_STREAM_SERVER_GUARD_REBOOT_THRESHOLD="\${BEAGLE_STREAM_SERVER_GUARD_REBOOT_THRESHOLD:-18}"

api_port="\$((BEAGLE_STREAM_SERVER_PORT + 1))"
consecutive_failures=0

api_ready() {
  [[ -n "\$BEAGLE_STREAM_SERVER_PASSWORD" ]] || return 1
  curl -kfsS --connect-timeout 3 --max-time 5 --user "\${BEAGLE_STREAM_SERVER_USER}:\${BEAGLE_STREAM_SERVER_PASSWORD}" "https://127.0.0.1:\${api_port}/api/apps" >/dev/null # tls-bypass-allowlist: loopback health check against local Beagle Stream Server self-signed API
}

while :; do
  /usr/local/bin/beagle-stream-server-healthcheck >/dev/null 2>&1 || true

  if systemctl is-active --quiet beagle-stream-server.service && api_ready; then
    consecutive_failures=0
  else
    consecutive_failures=\$((consecutive_failures + 1))
    systemctl restart beagle-stream-server.service >/dev/null 2>&1 || true

    if [[ "\$consecutive_failures" -ge "\$BEAGLE_STREAM_SERVER_GUARD_REBOOT_THRESHOLD" ]]; then
      logger -t beagle-stream-server-guardian "stream offline for \${consecutive_failures} checks; rebooting guest"
      systemctl reboot >/dev/null 2>&1 || /sbin/reboot >/dev/null 2>&1 || true
      sleep 120
    fi
  fi

  sleep "\$BEAGLE_STREAM_SERVER_GUARD_INTERVAL_SEC"
done
GUARDIAN
chmod 0755 /usr/local/bin/beagle-stream-server-guardian

cat > /etc/systemd/system/beagle-stream-server-guardian.service <<'GUARDSVC'
[Unit]
Description=Beagle Stream Server Uptime Guardian
After=network-online.target beagle-stream-server.service
Wants=network-online.target beagle-stream-server.service

[Service]
Type=simple
ExecStart=/usr/local/bin/beagle-stream-server-guardian
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
GUARDSVC

configure_stream_port_guard() {
  local stream_port="\${BEAGLE_STREAM_SERVER_PORT:-50000}"
  local api_port="50001"
  local rtsp_port="50021"
  local https_port="49995"
  local allowed_raw="\${BEAGLE_STREAM_SERVER_ALLOWED_CIDRS:-10.88.0.0/16}"
  local default_gateway=""
  local default_gateway_cidr=""
  local cidr=""
  local cidr_csv=""

  if [[ "\$stream_port" =~ ^[0-9]+$ ]]; then
    api_port="\$((stream_port + 1))"
    rtsp_port="\$((stream_port + 21))"
    if [[ "\$stream_port" -gt 5 ]]; then
      https_port="\$((stream_port - 5))"
    fi
  else
    stream_port="50000"
  fi

  for cidr in \$(printf '%s' "\$allowed_raw" | tr ',;' '  '); do
    if [[ "\$cidr" =~ ^([0-9]{1,3}\\.){3}[0-9]{1,3}(/[0-9]{1,2})?$ ]]; then
      if [[ -n "\$cidr_csv" ]]; then
        cidr_csv+=", "
      fi
      cidr_csv+="\$cidr"
    fi
  done
  if [[ -z "\$cidr_csv" ]]; then
    cidr_csv="10.88.0.0/16"
  fi

  default_gateway="\$(ip route show default 2>/dev/null | awk '/default/ {print \$3; exit}')"
  if [[ "\$default_gateway" =~ ^([0-9]{1,3}\\.){3}[0-9]{1,3}$ ]]; then
    default_gateway_cidr="\${default_gateway}/32"
    cidr_csv+=", \${default_gateway_cidr}"
  fi

  install -d -m 0755 /etc/beagle
  cat > /etc/beagle/beagle-stream-guest-guard.nft <<NFTGUARD
table inet beagle_stream_guest_guard {
  chain input {
    type filter hook input priority -5; policy accept;

    iifname "lo" accept
    ct state { established, related } accept

    iifname "wg-beagle" tcp dport { \${https_port}, \${stream_port}, \${api_port}, \${rtsp_port} } accept
    ip saddr { \${cidr_csv} } tcp dport { \${https_port}, \${stream_port}, \${api_port}, \${rtsp_port} } accept
    ip6 saddr ::1 tcp dport { \${https_port}, \${stream_port}, \${api_port}, \${rtsp_port} } accept

    tcp dport { \${https_port}, \${stream_port}, \${api_port}, \${rtsp_port} } drop
  }
}
NFTGUARD

  systemctl enable nftables >/dev/null 2>&1 || true
  nft delete table inet beagle_stream_guest_guard >/dev/null 2>&1 || true
  nft -f /etc/beagle/beagle-stream-guest-guard.nft >/dev/null 2>&1 || true
}

install_usb_microphone_normalizer() {
  cat > /usr/local/bin/beagle-normalize-usb-microphones <<'MICNORM'
#!/usr/bin/env bash
set -euo pipefail

volume="\${BEAGLE_USB_MICROPHONE_VOLUME:-250%}"
if ! command -v pactl >/dev/null 2>&1; then
  exit 0
fi

bridge_source="\$(pactl list short sources 2>/dev/null | awk '\$2 == "beagle_tc_microphone" {print \$2; exit}')"
if [[ -n "\$bridge_source" ]]; then
  pactl set-default-source "\$bridge_source" >/dev/null 2>&1 || true
  pactl set-source-mute "\$bridge_source" 0 >/dev/null 2>&1 || true
  pactl set-source-volume "\$bridge_source" 100% >/dev/null 2>&1 || true
  exit 0
fi

source_name="\$(pactl list short sources 2>/dev/null | awk '\$2 ~ /^alsa_input\.usb-/ && \$2 !~ /\.monitor$/ {print \$2; exit}')"
if [[ -z "\$source_name" ]]; then
  exit 0
fi

pactl set-default-source "\$source_name" >/dev/null 2>&1 || true
pactl set-source-mute "\$source_name" 0 >/dev/null 2>&1 || true
pactl set-source-volume "\$source_name" "\$volume" >/dev/null 2>&1 || true
MICNORM
  chmod 0755 /usr/local/bin/beagle-normalize-usb-microphones

  cat > /etc/systemd/system/beagle-usb-microphone-normalize.service <<MICNORMSVC
[Unit]
Description=Normalize Beagle USB microphone defaults
After=display-manager.service
Wants=display-manager.service

[Service]
Type=oneshot
User=\$GUEST_USER
Environment=HOME=/home/\$GUEST_USER
Environment=XDG_RUNTIME_DIR=/run/user/\$GUEST_UID
Environment=BEAGLE_USB_MICROPHONE_VOLUME=${BEAGLE_USB_MICROPHONE_VOLUME}
ExecStart=/usr/local/bin/beagle-normalize-usb-microphones
MICNORMSVC

  cat > /etc/systemd/system/beagle-usb-microphone-normalize.timer <<'MICNORMTIMER'
[Unit]
Description=Periodically normalize Beagle USB microphone defaults

[Timer]
OnBootSec=20s
OnUnitActiveSec=30s
AccuracySec=5s
Unit=beagle-usb-microphone-normalize.service

[Install]
WantedBy=timers.target
MICNORMTIMER

  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable --now beagle-usb-microphone-normalize.timer >/dev/null 2>&1 || true
  systemctl start beagle-usb-microphone-normalize.service >/dev/null 2>&1 || true
}

systemctl disable beagle-stream-server >/dev/null 2>&1 || true
systemctl stop beagle-stream-server >/dev/null 2>&1 || true
systemctl disable --now beagle-sunshine.service >/dev/null 2>&1 || true
systemctl disable --now beagle-sunshine-healthcheck.timer >/dev/null 2>&1 || true
systemctl stop beagle-sunshine-healthcheck.service >/dev/null 2>&1 || true
pkill -x sunshine >/dev/null 2>&1 || true
su - "\$GUEST_USER" -c "systemctl --user disable --now beagle-stream-server.service >/dev/null 2>&1 || true" || true
rm -f "/home/\$GUEST_USER/.config/autostart/beagle-stream-server.desktop"
pkill -u "\$GUEST_USER" -x beagle-stream-server >/dev/null 2>&1 || true
systemctl disable gdm3 >/dev/null 2>&1 || true
printf '/usr/sbin/lightdm\n' > /etc/X11/default-display-manager
ln -sf /usr/lib/systemd/system/lightdm.service /etc/systemd/system/display-manager.service
systemctl daemon-reload
systemctl set-default graphical.target >/dev/null

su - "\$GUEST_USER" -c "HOME=/home/\$GUEST_USER XDG_CONFIG_HOME=/home/\$GUEST_USER/.config beagle-stream-server --creds '\$BEAGLE_STREAM_SERVER_USER' '\$BEAGLE_STREAM_SERVER_PASSWORD'"
systemctl restart display-manager.service >/dev/null 2>&1 || true
loginctl enable-linger "\$GUEST_USER" >/dev/null 2>&1 || true
for _ in {1..60}; do
  if systemctl --user -M "\$GUEST_USER@" show basic.target >/dev/null 2>&1; then
    systemctl --user -M "\$GUEST_USER@" enable --now pipewire.service pipewire-pulse.service wireplumber.service >/dev/null 2>&1 || true
    break
  fi
  sleep 1
done
configure_stream_port_guard
install_usb_microphone_normalizer

# Activate WireGuard interface for VPN access from thinclient
activate_wireguard_stream_endpoint() {
  local wg_conf="/etc/wireguard/wg-beagle.conf"
  local wg_iface="wg-beagle"
  if [[ -f "\$wg_conf" ]]; then
    echo "[beagle-stream-server] Activating WireGuard interface \$wg_iface for stream endpoint..." >&2
    systemctl enable "wg-quick@\${wg_iface}.service" >/dev/null 2>&1 || true
    systemctl start "wg-quick@\${wg_iface}.service" >/dev/null 2>&1 || wg-quick up "\$wg_iface" >/dev/null 2>&1 || true
    if ip link show "\$wg_iface" >/dev/null 2>&1; then
      echo "[beagle-stream-server] WireGuard interface \$wg_iface is active" >&2
    else
      echo "[beagle-stream-server] WARNING: WireGuard interface \$wg_iface could not be activated" >&2
    fi
  fi
}
activate_wireguard_stream_endpoint

systemctl enable --now beagle-stream-server.service >/dev/null 2>&1 || true
systemctl enable --now beagle-stream-server-healthcheck.timer >/dev/null 2>&1 || true
systemctl enable --now beagle-stream-server-guardian.service >/dev/null 2>&1 || true
/usr/local/bin/beagle-stream-server-healthcheck >/dev/null 2>&1 || true

# ── USB/IP auto-attach: forward thin-client USB devices into the VM ──────────
# Install canonical assets from scripts/lib and keep service always enabled.
printf '%s' "\$BEAGLE_USB_ATTACH_SCRIPT_B64" | base64 -d > /usr/local/bin/beagle-usb-attach
chmod 0755 /usr/local/bin/beagle-usb-attach
printf '%s' "\$BEAGLE_USB_ATTACH_SERVICE_B64" | base64 -d > /etc/systemd/system/beagle-usb-attach.service
chmod 0644 /etc/systemd/system/beagle-usb-attach.service

systemctl daemon-reload >/dev/null 2>&1 || true
systemctl enable beagle-usb-attach.service >/dev/null 2>&1 || true
systemctl restart beagle-usb-attach.service >/dev/null 2>&1 || true
echo "[beagle] USB/IP auto-attach service enabled"

# Audio-class USB devices are latency sensitive and can crackle over USB/IP.
# Receive a dedicated PCM microphone stream from the thin client instead and
# expose it as a virtual PipeWire/Pulse source for browsers inside the VM.
printf '%s' "\$BEAGLE_TC_MIC_BRIDGE_SCRIPT_B64" | base64 -d > /usr/local/bin/beagle-tc-mic-bridge
chmod 0755 /usr/local/bin/beagle-tc-mic-bridge
printf '%s' "\$BEAGLE_TC_MIC_BRIDGE_SERVICE_B64" | base64 -d > /etc/systemd/system/beagle-tc-mic-bridge.service
sed -i \
  -e "s/^User=.*/User=\$GUEST_USER/" \
  -e "s#^Environment=HOME=.*#Environment=HOME=/home/\$GUEST_USER#" \
  -e "s#^Environment=XDG_RUNTIME_DIR=.*#Environment=XDG_RUNTIME_DIR=/run/user/\$GUEST_UID#" \
  -e "s/^Environment=BEAGLE_TC_MIC_BRIDGE_PORT=.*/Environment=BEAGLE_TC_MIC_BRIDGE_PORT=\$BEAGLE_TC_MIC_BRIDGE_PORT/" \
  /etc/systemd/system/beagle-tc-mic-bridge.service
chmod 0644 /etc/systemd/system/beagle-tc-mic-bridge.service
systemctl daemon-reload >/dev/null 2>&1 || true
systemctl enable --now beagle-tc-mic-bridge.service >/dev/null 2>&1 || true
echo "[beagle] Thin-client microphone audio bridge enabled"

# ── usbipd (USB/IP daemon): export TC-side devices to VM ─────────────────────
# usbipd must run on the TC side (handled by beagle-usb-tunnel service).
# On the VM side we need the vhci-hcd kernel module loaded at boot so
# usbip attach works without manual modprobe.
if ! grep -qF 'vhci-hcd' /etc/modules 2>/dev/null; then
  echo 'vhci-hcd' >> /etc/modules
fi
modprobe vhci-hcd 2>/dev/null || true
# Install a simple usbipd.service if usbipd binary is present but no unit exists
if [[ -x /usr/bin/usbipd ]] && ! systemctl cat usbipd.service >/dev/null 2>&1; then
  cat > /etc/systemd/system/usbipd.service << 'USBIPDUNIT_EOF'
[Unit]
Description=USB/IP Daemon (kernel-side export server)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/usbipd
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
USBIPDUNIT_EOF
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable --now usbipd.service >/dev/null 2>&1 || true
  echo "[beagle] usbipd.service installed and enabled"
else
  systemctl enable --now usbipd.service >/dev/null 2>&1 || true
fi

# ── Camera stream receive: TC webcam via ffmpeg + v4l2loopback ────────────────
# UVC webcams forwarded via USB/IP fail with isoc transfer errors.  Instead the
# TC streams the camera via ffmpeg (TCP:BEAGLE_CAMERA_STREAM_PORT) and the VM receives it through a
# v4l2loopback virtual device so browsers see a normal /dev/video10 camera.
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  ffmpeg v4l2loopback-dkms 2>/dev/null || true

# Ensure beagle desktop user is in the video group
usermod -aG video beagle 2>/dev/null || true

cat > /usr/local/bin/beagle-camera-receive << 'CAMRECV_EOF'
#!/usr/bin/env bash
set -uo pipefail
ENV_FILE="/etc/beagle/camera-receive.env"
[[ -r "\$ENV_FILE" ]] && source "\$ENV_FILE"
STREAM_HOST="\${BEAGLE_CAMERA_STREAM_HOST:-192.168.123.1}"
STREAM_PORT="\${BEAGLE_CAMERA_STREAM_PORT:-${BEAGLE_CAMERA_STREAM_PORT}}"
LOOPBACK_NR="\${BEAGLE_CAMERA_LOOPBACK_DEV:-10}"
CAMERA_W="\${BEAGLE_CAMERA_WIDTH:-640}"
CAMERA_H="\${BEAGLE_CAMERA_HEIGHT:-480}"
CAMERA_FPS="\${BEAGLE_CAMERA_FPS:-15}"
CAMERA_GROUP="\${BEAGLE_CAMERA_GROUP:-video}"
POLL_INTERVAL=5
LOOPBACK_DEV="/dev/video\${LOOPBACK_NR}"
setup_loopback() {
  if ! lsmod | grep -q v4l2loopback; then
    modprobe v4l2loopback devices=1 video_nr="\$LOOPBACK_NR" card_label="Beagle Camera" exclusive_caps=1 2>/dev/null || return 1
    sleep 1
  fi
  [[ -e "\$LOOPBACK_DEV" ]] && chown root:"\$CAMERA_GROUP" "\$LOOPBACK_DEV" && chmod 660 "\$LOOPBACK_DEV" || true
  id beagle &>/dev/null && usermod -aG "\$CAMERA_GROUP" beagle 2>/dev/null || true
  return 0
}
setup_loopback || true
echo "beagle-camera-receive: \${STREAM_HOST}:\${STREAM_PORT} → \${LOOPBACK_DEV}"
while true; do
  [[ ! -e "\$LOOPBACK_DEV" ]] && { setup_loopback || true; sleep "\$POLL_INTERVAL"; continue; }
  ffmpeg -nostdin -loglevel error \
    -i "tcp://\${STREAM_HOST}:\${STREAM_PORT}" \
    -vf "scale=\${CAMERA_W}:\${CAMERA_H},format=yuv420p" \
    -f v4l2 -pix_fmt yuv420p "\$LOOPBACK_DEV" 2>/dev/null || true
  sleep "\$POLL_INTERVAL"
done
CAMRECV_EOF
chmod 0755 /usr/local/bin/beagle-camera-receive

cat > /etc/systemd/system/beagle-camera-receive.service << 'CAMSVCC_EOF'
[Unit]
Description=Beagle Camera Receive (TC webcam via v4l2loopback)
After=network.target
Wants=network.target

[Service]
Type=simple
EnvironmentFile=-/etc/beagle/camera-receive.env
ExecStart=/usr/local/bin/beagle-camera-receive
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
CAMSVCC_EOF

cat > /etc/beagle/camera-receive.env <<CAMENV_EOF
BEAGLE_CAMERA_STREAM_HOST=192.168.123.1
BEAGLE_CAMERA_STREAM_PORT=\${BEAGLE_CAMERA_STREAM_PORT}
BEAGLE_CAMERA_LOOPBACK_DEV=10
BEAGLE_CAMERA_WIDTH=640
BEAGLE_CAMERA_HEIGHT=480
BEAGLE_CAMERA_FPS=15
BEAGLE_CAMERA_GROUP=video
CAMENV_EOF

systemctl daemon-reload >/dev/null 2>&1 || true
systemctl enable --now beagle-camera-receive.service >/dev/null 2>&1 || true
echo "[beagle] Camera receive service enabled (v4l2loopback /dev/video10)"
EOF
)"

  if [[ "$install_mode" == "native" ]]; then
    guest_copy_file "$native_artifact_dir/beagle-stream-server-src.tar.gz" "$native_source_archive"
    guest_copy_file "$native_artifact_dir/beagle-stream-server-deps.tar.gz" "$native_deps_archive"
  fi

  guest_exec_script "$guest_script"
  guest_ip="$GUEST_IP_OVERRIDE"
  if [[ -z "$guest_ip" ]]; then
    guest_ip="$(detect_guest_ip 2>/dev/null | tail -n1 | tr -d '\r' || true)"
  fi
  if [[ "$UPDATE_METADATA" == "1" && -z "$guest_ip" ]]; then
    echo "Unable to determine guest IPv4 address for VM $VMID" >&2
    exit 1
  fi

  if [[ "$UPDATE_METADATA" == "1" ]]; then
    update_vm_metadata "$guest_ip"
  fi

  if [[ "$VM_REBOOT" == "1" ]]; then
    reboot_current_vm
  fi
  echo "Configured Beagle Stream Server guest VM $VMID on $BEAGLE_HOST (guest IP: ${guest_ip:-unknown})"
}

main "$@"
