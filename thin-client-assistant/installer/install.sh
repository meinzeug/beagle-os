#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env-defaults.sh"
CONFIG_DIR="/etc/pve-thin-client"
CONFIG_FILE="$CONFIG_DIR/thinclient.conf"
INSTALL_ROOT="/usr/local/lib/pve-thin-client"
BIN_DIR="/usr/local/bin"
AUTOSTART_DIR="/etc/xdg/autostart"
SYSTEMD_DIR="/etc/systemd/system"
apply_installer_env_defaults

usage() {
  cat <<EOF
Usage: $0 [--mode MOONLIGHT] [--runtime-user USER] [--moonlight-host HOST] [--moonlight-local-host HOST] [--moonlight-app APP] [--sunshine-api-url URL]
EOF
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "This installer must run as root." >&2
    exit 1
  fi
}

copy_file() {
  local src="$1"
  local dst="$2"
  install -D -m 0755 "$src" "$dst"
}

copy_readonly() {
  local src="$1"
  local dst="$2"
  install -D -m 0644 "$src" "$dst"
}

apply_shell_assignments() {
  local payload="$1"
  local key value

  while IFS=$'\t' read -r key value; do
    [[ "$key" =~ ^[A-Z0-9_]+$ ]] || continue
    declare -p "$key" >/dev/null 2>&1 || continue
    printf -v "$key" '%s' "$value"
  done < <(
    printf '%s\n' "$payload" | python3 - <<'PY'
import shlex
import sys

for raw_line in sys.stdin:
    line = raw_line.strip()
    if not line:
        continue
    parts = shlex.split(line, posix=True)
    if len(parts) != 1 or "=" not in parts[0]:
        continue
    key, value = parts[0].split("=", 1)
    print(f"{key}\t{value}")
PY
  )
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mode) MODE="$2"; shift 2 ;;
      --connection-method) CONNECTION_METHOD="$2"; shift 2 ;;
      --profile-name) PROFILE_NAME="$2"; shift 2 ;;
      --runtime-user) RUNTIME_USER="$2"; shift 2 ;;
      --hostname) HOSTNAME_VALUE="$2"; shift 2 ;;
      --autostart) AUTOSTART="$2"; shift 2 ;;
      --network-mode) NETWORK_MODE="$2"; shift 2 ;;
      --network-interface) NETWORK_INTERFACE="$2"; shift 2 ;;
      --network-address) NETWORK_STATIC_ADDRESS="$2"; shift 2 ;;
      --network-prefix) NETWORK_STATIC_PREFIX="$2"; shift 2 ;;
      --network-gateway) NETWORK_GATEWAY="$2"; shift 2 ;;
      --network-dns) NETWORK_DNS_SERVERS="$2"; shift 2 ;;
      --moonlight-host) MOONLIGHT_HOST="$2"; shift 2 ;;
      --moonlight-local-host) MOONLIGHT_LOCAL_HOST="$2"; shift 2 ;;
      --moonlight-port) MOONLIGHT_PORT="$2"; shift 2 ;;
      --moonlight-app) MOONLIGHT_APP="$2"; shift 2 ;;
      --moonlight-bin) MOONLIGHT_BIN="$2"; shift 2 ;;
      --moonlight-resolution) MOONLIGHT_RESOLUTION="$2"; shift 2 ;;
      --moonlight-fps) MOONLIGHT_FPS="$2"; shift 2 ;;
      --moonlight-bitrate) MOONLIGHT_BITRATE="$2"; shift 2 ;;
      --moonlight-video-codec) MOONLIGHT_VIDEO_CODEC="$2"; shift 2 ;;
      --moonlight-video-decoder) MOONLIGHT_VIDEO_DECODER="$2"; shift 2 ;;
      --moonlight-audio-config) MOONLIGHT_AUDIO_CONFIG="$2"; shift 2 ;;
      --moonlight-absolute-mouse) MOONLIGHT_ABSOLUTE_MOUSE="$2"; shift 2 ;;
      --moonlight-quit-after) MOONLIGHT_QUIT_AFTER="$2"; shift 2 ;;
      --sunshine-api-url) SUNSHINE_API_URL="$2"; shift 2 ;;
      --proxmox-scheme) PROXMOX_SCHEME="$2"; shift 2 ;;
      --proxmox-host) PROXMOX_HOST="$2"; shift 2 ;;
      --proxmox-port) PROXMOX_PORT="$2"; shift 2 ;;
      --proxmox-node) PROXMOX_NODE="$2"; shift 2 ;;
      --proxmox-vmid) PROXMOX_VMID="$2"; shift 2 ;;
      --proxmox-realm) PROXMOX_REALM="$2"; shift 2 ;;
      --proxmox-verify-tls) PROXMOX_VERIFY_TLS="$2"; shift 2 ;;
      --connection-username) CONNECTION_USERNAME="$2"; shift 2 ;;
      --connection-password) CONNECTION_PASSWORD="$2"; shift 2 ;;
      --connection-token) CONNECTION_TOKEN="$2"; shift 2 ;;
      --sunshine-username) SUNSHINE_USERNAME="$2"; shift 2 ;;
      --sunshine-password) SUNSHINE_PASSWORD="$2"; shift 2 ;;
      --sunshine-pin) SUNSHINE_PIN="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *)
        echo "Unknown argument: $1" >&2
        usage
        exit 1
        ;;
    esac
  done
}

load_answers() {
  local output
  output="$(
    MODE="$MODE" \
    CONNECTION_METHOD="$CONNECTION_METHOD" \
    PROFILE_NAME="$PROFILE_NAME" \
    RUNTIME_USER="$RUNTIME_USER" \
    HOSTNAME_VALUE="$HOSTNAME_VALUE" \
    AUTOSTART="$AUTOSTART" \
    NETWORK_MODE="$NETWORK_MODE" \
    NETWORK_INTERFACE="$NETWORK_INTERFACE" \
    NETWORK_STATIC_ADDRESS="$NETWORK_STATIC_ADDRESS" \
    NETWORK_STATIC_PREFIX="$NETWORK_STATIC_PREFIX" \
    NETWORK_GATEWAY="$NETWORK_GATEWAY" \
    NETWORK_DNS_SERVERS="$NETWORK_DNS_SERVERS" \
    MOONLIGHT_HOST="$MOONLIGHT_HOST" \
    MOONLIGHT_PORT="$MOONLIGHT_PORT" \
    MOONLIGHT_APP="$MOONLIGHT_APP" \
    MOONLIGHT_BIN="$MOONLIGHT_BIN" \
    MOONLIGHT_RESOLUTION="$MOONLIGHT_RESOLUTION" \
    MOONLIGHT_FPS="$MOONLIGHT_FPS" \
    MOONLIGHT_BITRATE="$MOONLIGHT_BITRATE" \
    MOONLIGHT_VIDEO_CODEC="$MOONLIGHT_VIDEO_CODEC" \
    MOONLIGHT_VIDEO_DECODER="$MOONLIGHT_VIDEO_DECODER" \
    MOONLIGHT_AUDIO_CONFIG="$MOONLIGHT_AUDIO_CONFIG" \
    MOONLIGHT_ABSOLUTE_MOUSE="$MOONLIGHT_ABSOLUTE_MOUSE" \
    MOONLIGHT_QUIT_AFTER="$MOONLIGHT_QUIT_AFTER" \
    SUNSHINE_API_URL="$SUNSHINE_API_URL" \
    PROXMOX_SCHEME="$PROXMOX_SCHEME" \
    PROXMOX_HOST="$PROXMOX_HOST" \
    PROXMOX_PORT="$PROXMOX_PORT" \
    PROXMOX_NODE="$PROXMOX_NODE" \
    PROXMOX_VMID="$PROXMOX_VMID" \
    PROXMOX_REALM="$PROXMOX_REALM" \
    PROXMOX_VERIFY_TLS="$PROXMOX_VERIFY_TLS" \
    CONNECTION_USERNAME="$CONNECTION_USERNAME" \
    CONNECTION_PASSWORD="$CONNECTION_PASSWORD" \
    CONNECTION_TOKEN="$CONNECTION_TOKEN" \
    SUNSHINE_USERNAME="$SUNSHINE_USERNAME" \
    SUNSHINE_PASSWORD="$SUNSHINE_PASSWORD" \
    SUNSHINE_PIN="$SUNSHINE_PIN" \
    "$ROOT_DIR/installer/setup-menu.sh"
  )"
  apply_shell_assignments "$output"
}

install_runtime_assets() {
  install -d -m 0755 "$INSTALL_ROOT"
  cp -a "$ROOT_DIR/runtime" "$INSTALL_ROOT/"
  cp -a "$ROOT_DIR/installer" "$INSTALL_ROOT/"
  cp -a "$ROOT_DIR/templates" "$INSTALL_ROOT/"
  copy_file "$ROOT_DIR/runtime/launch-session.sh" "$INSTALL_ROOT/launch-session.sh"
  copy_file "$ROOT_DIR/runtime/prepare-runtime.sh" "$INSTALL_ROOT/prepare-runtime.sh"
  copy_file "$ROOT_DIR/runtime/launch-moonlight.sh" "$INSTALL_ROOT/launch-moonlight.sh"
  copy_file "$ROOT_DIR/runtime/common.sh" "$INSTALL_ROOT/common.sh"
  copy_file "$ROOT_DIR/runtime/apply-network-config.sh" "$INSTALL_ROOT/apply-network-config.sh"
  copy_file "$ROOT_DIR/installer/setup-menu.sh" "$INSTALL_ROOT/setup-menu.sh"
  copy_file "$ROOT_DIR/installer/write-config.sh" "$INSTALL_ROOT/write-config.sh"
  copy_readonly "$ROOT_DIR/systemd/pve-thin-client-prepare.service" "$SYSTEMD_DIR/pve-thin-client-prepare.service"
  copy_readonly "$ROOT_DIR/templates/pve-thin-client.desktop" "$AUTOSTART_DIR/pve-thin-client.desktop"
  install -d -m 0755 "$BIN_DIR"
  ln -sf "$INSTALL_ROOT/launch-session.sh" "$BIN_DIR/pve-thin-client-launch"
  ln -sf "$INSTALL_ROOT/setup-menu.sh" "$BIN_DIR/pve-thin-client-setup"
}

write_config() {
  MODE="$MODE" \
  CONNECTION_METHOD="$CONNECTION_METHOD" \
  PROFILE_NAME="$PROFILE_NAME" \
  RUNTIME_USER="$RUNTIME_USER" \
  HOSTNAME_VALUE="$HOSTNAME_VALUE" \
  AUTOSTART="$AUTOSTART" \
  NETWORK_MODE="$NETWORK_MODE" \
  NETWORK_INTERFACE="$NETWORK_INTERFACE" \
  NETWORK_STATIC_ADDRESS="$NETWORK_STATIC_ADDRESS" \
  NETWORK_STATIC_PREFIX="$NETWORK_STATIC_PREFIX" \
  NETWORK_GATEWAY="$NETWORK_GATEWAY" \
  NETWORK_DNS_SERVERS="$NETWORK_DNS_SERVERS" \
  MOONLIGHT_HOST="$MOONLIGHT_HOST" \
  MOONLIGHT_LOCAL_HOST="$MOONLIGHT_LOCAL_HOST" \
  MOONLIGHT_PORT="$MOONLIGHT_PORT" \
  MOONLIGHT_APP="$MOONLIGHT_APP" \
  MOONLIGHT_BIN="$MOONLIGHT_BIN" \
  MOONLIGHT_RESOLUTION="$MOONLIGHT_RESOLUTION" \
  MOONLIGHT_FPS="$MOONLIGHT_FPS" \
  MOONLIGHT_BITRATE="$MOONLIGHT_BITRATE" \
  MOONLIGHT_VIDEO_CODEC="$MOONLIGHT_VIDEO_CODEC" \
  MOONLIGHT_VIDEO_DECODER="$MOONLIGHT_VIDEO_DECODER" \
  MOONLIGHT_AUDIO_CONFIG="$MOONLIGHT_AUDIO_CONFIG" \
  MOONLIGHT_ABSOLUTE_MOUSE="$MOONLIGHT_ABSOLUTE_MOUSE" \
  MOONLIGHT_QUIT_AFTER="$MOONLIGHT_QUIT_AFTER" \
  SUNSHINE_API_URL="$SUNSHINE_API_URL" \
  PROXMOX_SCHEME="$PROXMOX_SCHEME" \
  PROXMOX_HOST="$PROXMOX_HOST" \
  PROXMOX_PORT="$PROXMOX_PORT" \
  PROXMOX_NODE="$PROXMOX_NODE" \
  PROXMOX_VMID="$PROXMOX_VMID" \
  PROXMOX_REALM="$PROXMOX_REALM" \
  PROXMOX_VERIFY_TLS="$PROXMOX_VERIFY_TLS" \
  CONNECTION_USERNAME="$CONNECTION_USERNAME" \
  CONNECTION_PASSWORD="$CONNECTION_PASSWORD" \
  CONNECTION_TOKEN="$CONNECTION_TOKEN" \
  SUNSHINE_USERNAME="$SUNSHINE_USERNAME" \
  SUNSHINE_PASSWORD="$SUNSHINE_PASSWORD" \
  SUNSHINE_PIN="$SUNSHINE_PIN" \
  "$ROOT_DIR/installer/write-config.sh" "$CONFIG_DIR"
}

ensure_user_exists() {
  if id "$RUNTIME_USER" >/dev/null 2>&1; then
    return 0
  fi
  echo "Runtime user '$RUNTIME_USER' does not exist." >&2
  echo "Create the account before first boot or adjust the config." >&2
}

install_packages_hint() {
  case "$MODE" in
    MOONLIGHT)
      echo "Suggested package or wrapper: moonlight"
      ;;
    *)
      echo "Unsupported mode in summary: $MODE" >&2
      exit 1
      ;;
  esac
}

enable_services() {
  systemctl daemon-reload
  systemctl enable pve-thin-client-prepare.service >/dev/null
}

print_summary() {
  cat <<EOF
Installed pve-thin-client assets.
Config: $CONFIG_FILE
Mode: $MODE
Runtime user: $RUNTIME_USER
Connection method: $CONNECTION_METHOD
EOF
  install_packages_hint
}

require_root
parse_args "$@"
if [[ "$MODE" != "MOONLIGHT" ]]; then
  echo "Beagle OS supports only --mode MOONLIGHT." >&2
  exit 1
fi
load_answers
install_runtime_assets
write_config
ensure_user_exists
enable_services
print_summary
