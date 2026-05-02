#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env-defaults.sh"
apply_installer_env_defaults
BEAGLE_HOST="${BEAGLE_HOST:-beagle.example.internal}"
BEAGLE_NODE="${BEAGLE_NODE:-pve01}"
BEAGLE_VMID="${BEAGLE_VMID:-100}"
BEAGLE_STREAM_SERVER_PIN="${BEAGLE_STREAM_SERVER_PIN:-1234}"

tty_printf() {
  printf '%s' "$*" >&2
}

tty_read() {
  local value=""
  IFS= read -r value || true
  printf '%s\n' "$value"
}

prompt() {
  local label="$1"
  local default_value="$2"
  local value=""
  tty_printf "$label [$default_value]: "
  value="$(tty_read)"
  if [[ -n "$value" ]]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$default_value"
  fi
}

prompt_secret() {
  local label="$1"
  local default_value="$2"
  local value=""
  read -r -s -p "$label [hidden]: " value || true
  printf '\n' >&2
  if [[ -n "$value" ]]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$default_value"
  fi
}

choose_numeric() {
  local prompt_text="$1"
  shift
  local options=("$@")
  local answer
  while true; do
    tty_printf "$prompt_text"$'\n'
    tty_printf "Choice: "
    answer="$(tty_read)"
    if [[ "$answer" =~ ^[0-9]+$ ]] && (( answer >= 1 && answer <= ${#options[@]} )); then
      printf '%s\n' "${options[$((answer - 1))]}"
      return 0
    fi
  done
}

emit_var() {
  local key="$1"
  local value="$2"
  printf '%s=%q\n' "$key" "$value"
}

if [[ -z "$MODE" ]]; then
  MODE="BEAGLE_STREAM_CLIENT"
fi

if [[ "$MODE" != "BEAGLE_STREAM_CLIENT" ]]; then
  echo "Beagle OS supports only Beagle Stream Client + Beagle Stream Server." >&2
  exit 1
fi

if [[ -z "$CONNECTION_METHOD" ]]; then
  CONNECTION_METHOD="direct"
fi

PROFILE_NAME="$(prompt "Profile name" "$PROFILE_NAME")"
RUNTIME_USER="$(prompt "Runtime user" "$RUNTIME_USER")"
HOSTNAME_VALUE="$(prompt "Hostname" "$HOSTNAME_VALUE")"
AUTOSTART="$(prompt "Autostart after boot (1/0)" "$AUTOSTART")"
if [[ "$NETWORK_MODE" != "dhcp" && "$NETWORK_MODE" != "static" ]]; then
  NETWORK_MODE="$(choose_numeric $'Network mode:\n  1) DHCP\n  2) Static IPv4' dhcp static)"
fi
NETWORK_INTERFACE="$(prompt "Primary network interface" "$NETWORK_INTERFACE")"

if [[ "$NETWORK_MODE" == "static" ]]; then
  NETWORK_STATIC_ADDRESS="$(prompt "Static IPv4 address" "${NETWORK_STATIC_ADDRESS:-192.168.10.50}")"
  NETWORK_STATIC_PREFIX="$(prompt "Static IPv4 prefix" "$NETWORK_STATIC_PREFIX")"
  NETWORK_GATEWAY="$(prompt "Default gateway" "${NETWORK_GATEWAY:-192.168.10.1}")"
  NETWORK_DNS_SERVERS="$(prompt "DNS servers (space separated)" "$NETWORK_DNS_SERVERS")"
fi

BEAGLE_STREAM_CLIENT_HOST="$(prompt "Beagle Stream Client target host" "${BEAGLE_STREAM_CLIENT_HOST:-${BEAGLE_HOST:-beagle-stream-client.local}}")"
BEAGLE_STREAM_CLIENT_PORT="$(prompt "Beagle Stream Client stream port (leer = Standard)" "$BEAGLE_STREAM_CLIENT_PORT")"
BEAGLE_STREAM_CLIENT_APP="$(prompt "Beagle Stream Server app name" "$BEAGLE_STREAM_CLIENT_APP")"
if [[ -z "$BEAGLE_STREAM_SERVER_API_URL" && -n "$BEAGLE_STREAM_CLIENT_PORT" ]]; then
  BEAGLE_STREAM_SERVER_API_URL="https://${BEAGLE_STREAM_CLIENT_HOST}:$((BEAGLE_STREAM_CLIENT_PORT + 1))"
fi
BEAGLE_STREAM_SERVER_API_URL="$(prompt "Beagle Stream Server API URL" "${BEAGLE_STREAM_SERVER_API_URL:-https://${BEAGLE_STREAM_CLIENT_HOST}:47990}")"
BEAGLE_STREAM_SERVER_USERNAME="$(prompt "Beagle Stream Server admin username" "${BEAGLE_STREAM_SERVER_USERNAME:-beagle-stream-server}")"
BEAGLE_STREAM_SERVER_PASSWORD="$(prompt_secret "Beagle Stream Server admin password" "$BEAGLE_STREAM_SERVER_PASSWORD")"
BEAGLE_STREAM_SERVER_PIN="$(prompt "Beagle Stream Client pairing PIN" "$BEAGLE_STREAM_SERVER_PIN")"
BEAGLE_STREAM_CLIENT_RESOLUTION="$(prompt "Beagle Stream Client resolution (auto/720/1080/1440/4K/custom)" "$BEAGLE_STREAM_CLIENT_RESOLUTION")"
BEAGLE_STREAM_CLIENT_FPS="$(prompt "Beagle Stream Client FPS" "$BEAGLE_STREAM_CLIENT_FPS")"
BEAGLE_STREAM_CLIENT_BITRATE="$(prompt "Beagle Stream Client bitrate Kbps" "$BEAGLE_STREAM_CLIENT_BITRATE")"
BEAGLE_STREAM_CLIENT_VIDEO_CODEC="$(prompt "Beagle Stream Client video codec" "$BEAGLE_STREAM_CLIENT_VIDEO_CODEC")"
BEAGLE_STREAM_CLIENT_VIDEO_DECODER="$(prompt "Beagle Stream Client video decoder" "$BEAGLE_STREAM_CLIENT_VIDEO_DECODER")"
BEAGLE_STREAM_CLIENT_AUDIO_CONFIG="$(prompt "Beagle Stream Client audio config" "$BEAGLE_STREAM_CLIENT_AUDIO_CONFIG")"

emit_var MODE "$MODE"
emit_var CONNECTION_METHOD "$CONNECTION_METHOD"
emit_var PROFILE_NAME "$PROFILE_NAME"
emit_var RUNTIME_USER "$RUNTIME_USER"
emit_var HOSTNAME_VALUE "$HOSTNAME_VALUE"
emit_var AUTOSTART "$AUTOSTART"
emit_var NETWORK_MODE "$NETWORK_MODE"
emit_var NETWORK_INTERFACE "$NETWORK_INTERFACE"
emit_var NETWORK_STATIC_ADDRESS "$NETWORK_STATIC_ADDRESS"
emit_var NETWORK_STATIC_PREFIX "$NETWORK_STATIC_PREFIX"
emit_var NETWORK_GATEWAY "$NETWORK_GATEWAY"
emit_var NETWORK_DNS_SERVERS "$NETWORK_DNS_SERVERS"
emit_var BEAGLE_STREAM_CLIENT_HOST "$BEAGLE_STREAM_CLIENT_HOST"
emit_var BEAGLE_STREAM_CLIENT_PORT "$BEAGLE_STREAM_CLIENT_PORT"
emit_var BEAGLE_STREAM_CLIENT_APP "$BEAGLE_STREAM_CLIENT_APP"
emit_var BEAGLE_STREAM_CLIENT_BIN "$BEAGLE_STREAM_CLIENT_BIN"
emit_var BEAGLE_STREAM_CLIENT_RESOLUTION "$BEAGLE_STREAM_CLIENT_RESOLUTION"
emit_var BEAGLE_STREAM_CLIENT_FPS "$BEAGLE_STREAM_CLIENT_FPS"
emit_var BEAGLE_STREAM_CLIENT_BITRATE "$BEAGLE_STREAM_CLIENT_BITRATE"
emit_var BEAGLE_STREAM_CLIENT_VIDEO_CODEC "$BEAGLE_STREAM_CLIENT_VIDEO_CODEC"
emit_var BEAGLE_STREAM_CLIENT_VIDEO_DECODER "$BEAGLE_STREAM_CLIENT_VIDEO_DECODER"
emit_var BEAGLE_STREAM_CLIENT_AUDIO_CONFIG "$BEAGLE_STREAM_CLIENT_AUDIO_CONFIG"
emit_var BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE "$BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE"
emit_var BEAGLE_STREAM_CLIENT_QUIT_AFTER "$BEAGLE_STREAM_CLIENT_QUIT_AFTER"
emit_var BEAGLE_STREAM_SERVER_API_URL "$BEAGLE_STREAM_SERVER_API_URL"
emit_var BEAGLE_SCHEME "$BEAGLE_SCHEME"
emit_var BEAGLE_HOST "$BEAGLE_HOST"
emit_var BEAGLE_PORT "$BEAGLE_PORT"
emit_var BEAGLE_NODE "$BEAGLE_NODE"
emit_var BEAGLE_VMID "$BEAGLE_VMID"
emit_var BEAGLE_REALM "$BEAGLE_REALM"
emit_var BEAGLE_VERIFY_TLS "$BEAGLE_VERIFY_TLS"
emit_var CONNECTION_USERNAME "$CONNECTION_USERNAME"
emit_var CONNECTION_PASSWORD "$CONNECTION_PASSWORD"
emit_var CONNECTION_TOKEN "$CONNECTION_TOKEN"
emit_var BEAGLE_STREAM_SERVER_USERNAME "$BEAGLE_STREAM_SERVER_USERNAME"
emit_var BEAGLE_STREAM_SERVER_PASSWORD "$BEAGLE_STREAM_SERVER_PASSWORD"
emit_var BEAGLE_STREAM_SERVER_PIN "$BEAGLE_STREAM_SERVER_PIN"
