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
Usage: $0 [--mode BEAGLE_STREAM_CLIENT] [--runtime-user USER] [--beagle-stream-client-host HOST] [--beagle-stream-client-local-host HOST] [--beagle-stream-client-app APP] [--beagle-stream-server-api-url URL]
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
    python3 - "$payload" <<'PY'
import shlex
import sys

for raw_line in sys.argv[1].splitlines():
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
      --beagle-stream-client-host) BEAGLE_STREAM_CLIENT_HOST="$2"; shift 2 ;;
      --beagle-stream-client-local-host) BEAGLE_STREAM_CLIENT_LOCAL_HOST="$2"; shift 2 ;;
      --beagle-stream-client-port) BEAGLE_STREAM_CLIENT_PORT="$2"; shift 2 ;;
      --beagle-stream-client-app) BEAGLE_STREAM_CLIENT_APP="$2"; shift 2 ;;
      --beagle-stream-client-bin) BEAGLE_STREAM_CLIENT_BIN="$2"; shift 2 ;;
      --beagle-stream-client-resolution) BEAGLE_STREAM_CLIENT_RESOLUTION="$2"; shift 2 ;;
      --beagle-stream-client-fps) BEAGLE_STREAM_CLIENT_FPS="$2"; shift 2 ;;
      --beagle-stream-client-bitrate) BEAGLE_STREAM_CLIENT_BITRATE="$2"; shift 2 ;;
      --beagle-stream-client-video-codec) BEAGLE_STREAM_CLIENT_VIDEO_CODEC="$2"; shift 2 ;;
      --beagle-stream-client-video-decoder) BEAGLE_STREAM_CLIENT_VIDEO_DECODER="$2"; shift 2 ;;
      --beagle-stream-client-audio-config) BEAGLE_STREAM_CLIENT_AUDIO_CONFIG="$2"; shift 2 ;;
      --beagle-stream-client-absolute-mouse) BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE="$2"; shift 2 ;;
      --beagle-stream-client-quit-after) BEAGLE_STREAM_CLIENT_QUIT_AFTER="$2"; shift 2 ;;
      --beagle-stream-server-api-url) BEAGLE_STREAM_SERVER_API_URL="$2"; shift 2 ;;
      --beagle-scheme) BEAGLE_SCHEME="$2"; shift 2 ;;
      --beagle-host) BEAGLE_HOST="$2"; shift 2 ;;
      --beagle-port) BEAGLE_PORT="$2"; shift 2 ;;
      --beagle-node) BEAGLE_NODE="$2"; shift 2 ;;
      --beagle-vmid) BEAGLE_VMID="$2"; shift 2 ;;
      --beagle-realm) BEAGLE_REALM="$2"; shift 2 ;;
      --beagle-verify-tls) BEAGLE_VERIFY_TLS="$2"; shift 2 ;;
      --connection-username) CONNECTION_USERNAME="$2"; shift 2 ;;
      --connection-password) CONNECTION_PASSWORD="$2"; shift 2 ;;
      --connection-token) CONNECTION_TOKEN="$2"; shift 2 ;;
      --beagle-stream-server-username) BEAGLE_STREAM_SERVER_USERNAME="$2"; shift 2 ;;
      --beagle-stream-server-password) BEAGLE_STREAM_SERVER_PASSWORD="$2"; shift 2 ;;
      --beagle-stream-server-pin) BEAGLE_STREAM_SERVER_PIN="$2"; shift 2 ;;
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
    BEAGLE_STREAM_CLIENT_HOST="$BEAGLE_STREAM_CLIENT_HOST" \
    BEAGLE_STREAM_CLIENT_PORT="$BEAGLE_STREAM_CLIENT_PORT" \
    BEAGLE_STREAM_CLIENT_APP="$BEAGLE_STREAM_CLIENT_APP" \
    BEAGLE_STREAM_CLIENT_BIN="$BEAGLE_STREAM_CLIENT_BIN" \
    BEAGLE_STREAM_CLIENT_RESOLUTION="$BEAGLE_STREAM_CLIENT_RESOLUTION" \
    BEAGLE_STREAM_CLIENT_FPS="$BEAGLE_STREAM_CLIENT_FPS" \
    BEAGLE_STREAM_CLIENT_BITRATE="$BEAGLE_STREAM_CLIENT_BITRATE" \
    BEAGLE_STREAM_CLIENT_VIDEO_CODEC="$BEAGLE_STREAM_CLIENT_VIDEO_CODEC" \
    BEAGLE_STREAM_CLIENT_VIDEO_DECODER="$BEAGLE_STREAM_CLIENT_VIDEO_DECODER" \
    BEAGLE_STREAM_CLIENT_AUDIO_CONFIG="$BEAGLE_STREAM_CLIENT_AUDIO_CONFIG" \
    BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE="$BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE" \
    BEAGLE_STREAM_CLIENT_QUIT_AFTER="$BEAGLE_STREAM_CLIENT_QUIT_AFTER" \
    BEAGLE_STREAM_SERVER_API_URL="$BEAGLE_STREAM_SERVER_API_URL" \
    BEAGLE_SCHEME="$BEAGLE_SCHEME" \
    BEAGLE_HOST="$BEAGLE_HOST" \
    BEAGLE_PORT="$BEAGLE_PORT" \
    BEAGLE_NODE="$BEAGLE_NODE" \
    BEAGLE_VMID="$BEAGLE_VMID" \
    BEAGLE_REALM="$BEAGLE_REALM" \
    BEAGLE_VERIFY_TLS="$BEAGLE_VERIFY_TLS" \
    CONNECTION_USERNAME="$CONNECTION_USERNAME" \
    CONNECTION_PASSWORD="$CONNECTION_PASSWORD" \
    CONNECTION_TOKEN="$CONNECTION_TOKEN" \
    BEAGLE_STREAM_SERVER_USERNAME="$BEAGLE_STREAM_SERVER_USERNAME" \
    BEAGLE_STREAM_SERVER_PASSWORD="$BEAGLE_STREAM_SERVER_PASSWORD" \
    BEAGLE_STREAM_SERVER_PIN="$BEAGLE_STREAM_SERVER_PIN" \
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
  copy_file "$ROOT_DIR/runtime/launch-beagle-stream-client.sh" "$INSTALL_ROOT/launch-beagle-stream-client.sh"
  copy_file "$ROOT_DIR/runtime/common.sh" "$INSTALL_ROOT/common.sh"
  copy_file "$ROOT_DIR/runtime/apply-network-config.sh" "$INSTALL_ROOT/apply-network-config.sh"
  copy_file "$ROOT_DIR/installer/setup-menu.sh" "$INSTALL_ROOT/setup-menu.sh"
  copy_file "$ROOT_DIR/installer/write-config.sh" "$INSTALL_ROOT/write-config.sh"
  copy_readonly "$ROOT_DIR/systemd/beagle-thin-client-prepare.service" "$SYSTEMD_DIR/beagle-thin-client-prepare.service"
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
  BEAGLE_STREAM_CLIENT_HOST="$BEAGLE_STREAM_CLIENT_HOST" \
  BEAGLE_STREAM_CLIENT_LOCAL_HOST="$BEAGLE_STREAM_CLIENT_LOCAL_HOST" \
  BEAGLE_STREAM_CLIENT_PORT="$BEAGLE_STREAM_CLIENT_PORT" \
  BEAGLE_STREAM_CLIENT_APP="$BEAGLE_STREAM_CLIENT_APP" \
  BEAGLE_STREAM_CLIENT_BIN="$BEAGLE_STREAM_CLIENT_BIN" \
  BEAGLE_STREAM_CLIENT_RESOLUTION="$BEAGLE_STREAM_CLIENT_RESOLUTION" \
  BEAGLE_STREAM_CLIENT_FPS="$BEAGLE_STREAM_CLIENT_FPS" \
  BEAGLE_STREAM_CLIENT_BITRATE="$BEAGLE_STREAM_CLIENT_BITRATE" \
  BEAGLE_STREAM_CLIENT_VIDEO_CODEC="$BEAGLE_STREAM_CLIENT_VIDEO_CODEC" \
  BEAGLE_STREAM_CLIENT_VIDEO_DECODER="$BEAGLE_STREAM_CLIENT_VIDEO_DECODER" \
  BEAGLE_STREAM_CLIENT_AUDIO_CONFIG="$BEAGLE_STREAM_CLIENT_AUDIO_CONFIG" \
  BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE="$BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE" \
  BEAGLE_STREAM_CLIENT_QUIT_AFTER="$BEAGLE_STREAM_CLIENT_QUIT_AFTER" \
  BEAGLE_STREAM_SERVER_API_URL="$BEAGLE_STREAM_SERVER_API_URL" \
  BEAGLE_SCHEME="$BEAGLE_SCHEME" \
  BEAGLE_HOST="$BEAGLE_HOST" \
  BEAGLE_PORT="$BEAGLE_PORT" \
  BEAGLE_NODE="$BEAGLE_NODE" \
  BEAGLE_VMID="$BEAGLE_VMID" \
  BEAGLE_REALM="$BEAGLE_REALM" \
  BEAGLE_VERIFY_TLS="$BEAGLE_VERIFY_TLS" \
  CONNECTION_USERNAME="$CONNECTION_USERNAME" \
  CONNECTION_PASSWORD="$CONNECTION_PASSWORD" \
  CONNECTION_TOKEN="$CONNECTION_TOKEN" \
  BEAGLE_STREAM_SERVER_USERNAME="$BEAGLE_STREAM_SERVER_USERNAME" \
  BEAGLE_STREAM_SERVER_PASSWORD="$BEAGLE_STREAM_SERVER_PASSWORD" \
  BEAGLE_STREAM_SERVER_PIN="$BEAGLE_STREAM_SERVER_PIN" \
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
    BEAGLE_STREAM_CLIENT)
      echo "Suggested package or wrapper: beagle-stream-client"
      ;;
    *)
      echo "Unsupported mode in summary: $MODE" >&2
      exit 1
      ;;
  esac
}

enable_services() {
  systemctl daemon-reload
  if systemctl list-unit-files beagle-thin-client-prepare.service >/dev/null 2>&1; then
    systemctl enable beagle-thin-client-prepare.service >/dev/null
  else
    systemctl enable pve-thin-client-prepare.service >/dev/null
  fi
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
if [[ "$MODE" != "BEAGLE_STREAM_CLIENT" ]]; then
  echo "Beagle OS supports only --mode BEAGLE_STREAM_CLIENT." >&2
  exit 1
fi
load_answers
install_runtime_assets
write_config
ensure_user_exists
enable_services
print_summary
