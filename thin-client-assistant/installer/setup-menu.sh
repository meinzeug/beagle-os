#!/usr/bin/env bash
set -euo pipefail

MODE="${MODE:-}"
CONNECTION_METHOD="${CONNECTION_METHOD:-}"
PROFILE_NAME="${PROFILE_NAME:-default}"
RUNTIME_USER="${RUNTIME_USER:-thinclient}"
HOSTNAME_VALUE="${HOSTNAME_VALUE:-pve-thin-client}"
AUTOSTART="${AUTOSTART:-1}"
NETWORK_MODE="${NETWORK_MODE:-dhcp}"
NETWORK_INTERFACE="${NETWORK_INTERFACE:-eth0}"
NETWORK_STATIC_ADDRESS="${NETWORK_STATIC_ADDRESS:-}"
NETWORK_STATIC_PREFIX="${NETWORK_STATIC_PREFIX:-24}"
NETWORK_GATEWAY="${NETWORK_GATEWAY:-}"
NETWORK_DNS_SERVERS="${NETWORK_DNS_SERVERS:-1.1.1.1 8.8.8.8}"
SPICE_URL="${SPICE_URL:-}"
NOVNC_URL="${NOVNC_URL:-}"
DCV_URL="${DCV_URL:-}"
REMOTE_VIEWER_BIN="${REMOTE_VIEWER_BIN:-remote-viewer}"
BROWSER_BIN="${BROWSER_BIN:-chromium}"
BROWSER_FLAGS="${BROWSER_FLAGS:---kiosk --incognito --no-first-run --disable-session-crashed-bubble}"
DCV_VIEWER_BIN="${DCV_VIEWER_BIN:-dcvviewer}"
PROXMOX_SCHEME="${PROXMOX_SCHEME:-https}"
PROXMOX_HOST="${PROXMOX_HOST:-proxmox.example.internal}"
PROXMOX_PORT="${PROXMOX_PORT:-8006}"
PROXMOX_NODE="${PROXMOX_NODE:-pve01}"
PROXMOX_VMID="${PROXMOX_VMID:-100}"
PROXMOX_REALM="${PROXMOX_REALM:-pam}"
PROXMOX_VERIFY_TLS="${PROXMOX_VERIFY_TLS:-0}"
CONNECTION_USERNAME="${CONNECTION_USERNAME:-}"
CONNECTION_PASSWORD="${CONNECTION_PASSWORD:-}"
CONNECTION_TOKEN="${CONNECTION_TOKEN:-}"

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
  MODE="$(choose_numeric $'Select target mode:\n  1) SPICE\n  2) noVNC\n  3) DCV' SPICE NOVNC DCV)"
fi

if [[ -z "$CONNECTION_METHOD" ]]; then
  case "$MODE" in
    SPICE)
      CONNECTION_METHOD="$(choose_numeric $'Connection source:\n  1) Direct URL\n  2) Proxmox API ticket' direct proxmox-ticket)"
      ;;
    *)
      CONNECTION_METHOD="direct"
      ;;
  esac
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

case "$MODE" in
  SPICE)
    if [[ "$CONNECTION_METHOD" == "proxmox-ticket" ]]; then
      PROXMOX_HOST="$(prompt "Proxmox host" "$PROXMOX_HOST")"
      PROXMOX_PORT="$(prompt "Proxmox port" "$PROXMOX_PORT")"
      PROXMOX_NODE="$(prompt "Proxmox node" "$PROXMOX_NODE")"
      PROXMOX_VMID="$(prompt "VMID" "$PROXMOX_VMID")"
      CONNECTION_USERNAME="$(prompt "Proxmox username" "${CONNECTION_USERNAME:-root}")"
      PROXMOX_REALM="$(prompt "Proxmox realm" "$PROXMOX_REALM")"
      CONNECTION_PASSWORD="$(prompt_secret "Proxmox password" "$CONNECTION_PASSWORD")"
      PROXMOX_VERIFY_TLS="$(prompt "Verify Proxmox TLS (1/0)" "$PROXMOX_VERIFY_TLS")"
    else
      SPICE_URL="$(prompt "SPICE URL or .vv target" "${SPICE_URL:-spice://proxmox.example.internal:3128}")"
      CONNECTION_USERNAME="$(prompt "Optional connection username" "$CONNECTION_USERNAME")"
      CONNECTION_PASSWORD="$(prompt_secret "Optional connection password" "$CONNECTION_PASSWORD")"
    fi
    ;;
  NOVNC)
    NOVNC_URL="$(prompt "noVNC kiosk URL" "${NOVNC_URL:-https://proxmox.example.internal:8006/?console=kvm}")"
    BROWSER_BIN="$(prompt "Browser binary" "$BROWSER_BIN")"
    BROWSER_FLAGS="$(prompt "Browser flags" "$BROWSER_FLAGS")"
    CONNECTION_USERNAME="$(prompt "Optional URL username placeholder" "$CONNECTION_USERNAME")"
    CONNECTION_PASSWORD="$(prompt_secret "Optional URL password placeholder" "$CONNECTION_PASSWORD")"
    CONNECTION_TOKEN="$(prompt_secret "Optional URL token placeholder" "$CONNECTION_TOKEN")"
    ;;
  DCV)
    DCV_URL="$(prompt "DCV server URL or host" "${DCV_URL:-dcv://dcv-gateway.example.internal/session/example}")"
    CONNECTION_USERNAME="$(prompt "DCV username" "$CONNECTION_USERNAME")"
    CONNECTION_PASSWORD="$(prompt_secret "DCV password" "$CONNECTION_PASSWORD")"
    CONNECTION_TOKEN="$(prompt_secret "Optional DCV auth token" "$CONNECTION_TOKEN")"
    ;;
  *)
    echo "Unsupported mode: $MODE" >&2
    exit 1
    ;;
esac

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
emit_var SPICE_URL "$SPICE_URL"
emit_var NOVNC_URL "$NOVNC_URL"
emit_var DCV_URL "$DCV_URL"
emit_var REMOTE_VIEWER_BIN "$REMOTE_VIEWER_BIN"
emit_var BROWSER_BIN "$BROWSER_BIN"
emit_var BROWSER_FLAGS "$BROWSER_FLAGS"
emit_var DCV_VIEWER_BIN "$DCV_VIEWER_BIN"
emit_var PROXMOX_SCHEME "$PROXMOX_SCHEME"
emit_var PROXMOX_HOST "$PROXMOX_HOST"
emit_var PROXMOX_PORT "$PROXMOX_PORT"
emit_var PROXMOX_NODE "$PROXMOX_NODE"
emit_var PROXMOX_VMID "$PROXMOX_VMID"
emit_var PROXMOX_REALM "$PROXMOX_REALM"
emit_var PROXMOX_VERIFY_TLS "$PROXMOX_VERIFY_TLS"
emit_var CONNECTION_USERNAME "$CONNECTION_USERNAME"
emit_var CONNECTION_PASSWORD "$CONNECTION_PASSWORD"
emit_var CONNECTION_TOKEN "$CONNECTION_TOKEN"
