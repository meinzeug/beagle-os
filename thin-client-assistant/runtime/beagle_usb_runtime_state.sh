#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEAGLE_USB_RUNTIME_PAYLOADS_SH="${BEAGLE_USB_RUNTIME_PAYLOADS_SH:-$SCRIPT_DIR/beagle_usb_runtime_payloads.sh}"
# shellcheck disable=SC1090
source "$BEAGLE_USB_RUNTIME_PAYLOADS_SH"

usb_state_root() {
  printf '%s\n' "${BEAGLE_USB_STATE_DIR:-/var/lib/beagle-os/usb}"
}

usb_state_file() {
  local state_root
  state_root="$(usb_state_root)"
  printf '%s\n' "$state_root/state.env"
}

usb_enabled() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_ENABLED:-1}"
}

usb_host() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_HOST:-}"
}

usb_user() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_USER:-beagle}"
}

usb_port() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PORT:-}"
}

usb_attach_host() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_ATTACH_HOST:-10.10.10.1}"
}

usb_key_file() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PRIVATE_KEY_FILE:-/etc/pve-thin-client/usb-tunnel.key}"
}

usb_known_hosts_file() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_KNOWN_HOSTS_FILE:-/etc/pve-thin-client/usb-tunnel-known_hosts}"
}

usbip_bin() {
  printf '%s\n' "${BEAGLE_USBIP_BIN:-usbip}"
}

pgrep_bin() {
  printf '%s\n' "${BEAGLE_PGREP_BIN:-pgrep}"
}

ensure_usb_state_root() {
  install -d -m 0755 "$(usb_state_root)"
}

state_bound_busids() {
  local state_file

  state_file="$(usb_state_file)"
  if [[ -r "$state_file" ]]; then
    # shellcheck disable=SC1090
    source "$state_file"
  fi
  printf '%s\n' "${BEAGLE_USB_BOUND_BUSIDS:-}"
}

write_state() {
  local busids="$1"
  local state_file

  ensure_usb_state_root
  state_file="$(usb_state_file)"
  cat >"$state_file" <<STATE
BEAGLE_USB_BOUND_BUSIDS=${busids@Q}
STATE
  chmod 0644 "$state_file"
}

bound_contains() {
  local needle="$1"
  local item
  for item in $(state_bound_busids); do
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
}

bound_add() {
  local needle="$1"
  local item out=""
  if bound_contains "$needle"; then
    write_state "$(state_bound_busids)"
    return 0
  fi
  for item in $(state_bound_busids); do
    out+="$item "
  done
  out+="$needle"
  write_state "${out%" "}"
}

bound_remove() {
  local needle="$1"
  local item out=""
  for item in $(state_bound_busids); do
    [[ "$item" == "$needle" ]] && continue
    out+="$item "
  done
  write_state "${out%" "}"
}

require_enabled() {
  [[ "$(usb_enabled)" == "1" ]] || {
    echo "usb disabled" >&2
    exit 0
  }
}
