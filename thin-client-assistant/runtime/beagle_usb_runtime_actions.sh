#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEAGLE_USB_RUNTIME_USBIPD_SH="${BEAGLE_USB_RUNTIME_USBIPD_SH:-$SCRIPT_DIR/beagle_usb_runtime_usbipd.sh}"
# shellcheck disable=SC1090
source "$BEAGLE_USB_RUNTIME_USBIPD_SH"

usbipd_bin() {
  printf '%s\n' "${BEAGLE_USBIPD_BIN:-usbipd}"
}

pkill_bin() {
  printf '%s\n' "${BEAGLE_PKILL_BIN:-pkill}"
}

modprobe_bin() {
  printf '%s\n' "${BEAGLE_MODPROBE_BIN:-modprobe}"
}

systemctl_bin() {
  printf '%s\n' "${BEAGLE_SYSTEMCTL_BIN:-systemctl}"
}

ssh_bin() {
  printf '%s\n' "${BEAGLE_SSH_BIN:-ssh}"
}

sleep_bin() {
  printf '%s\n' "${BEAGLE_SLEEP_BIN:-sleep}"
}

usb_tunnel_service_name() {
  printf '%s\n' "${BEAGLE_USB_TUNNEL_SERVICE:-beagle-usb-tunnel.service}"
}

usb_tunnel_state() {
  is_tunnel_running && printf 'up\n' || printf 'down\n'
}

usb_list_json() {
  local payload

  ensure_usbipd >/dev/null 2>&1 || true
  payload="$(list_local_usb_json)"
  render_usb_list_json "$(usb_tunnel_state)" "$payload"
}

bind_usb_device() {
  local busid="$1"
  local usbip_cmd systemctl_cmd

  require_enabled
  usbip_cmd="$(usbip_bin)"
  systemctl_cmd="$(systemctl_bin)"
  ensure_usbipd
  "$usbip_cmd" unbind -b "$busid" >/dev/null 2>&1 || true
  "$usbip_cmd" bind -b "$busid" >/dev/null 2>&1 || true
  bound_add "$busid"
  restart_usbipd
  "$systemctl_cmd" restart --no-block "$(usb_tunnel_service_name)" >/dev/null 2>&1 || true
  usb_list_json
}

unbind_usb_device() {
  local busid="$1"
  local usbip_cmd

  require_enabled
  usbip_cmd="$(usbip_bin)"
  "$usbip_cmd" unbind -b "$busid" >/dev/null 2>&1 || true
  bound_remove "$busid"
  restart_usbipd
  usb_list_json
}

usb_status_json() {
  render_usb_status_json "$(usb_tunnel_state)"
}

run_usb_tunnel_daemon() {
  local ssh_cmd

  require_enabled
  [[ -n "$(usb_host)" && -n "$(usb_port)" && -n "$(usb_user)" ]] || exit 0
  [[ -r "$(usb_key_file)" && -r "$(usb_known_hosts_file)" ]] || exit 0
  ssh_cmd="$(ssh_bin)"
  sync_bound_devices
  exec "$ssh_cmd" -N \
    -o BatchMode=yes \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=20 \
    -o ServerAliveCountMax=3 \
    -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="$(usb_known_hosts_file)" \
    -i "$(usb_key_file)" \
    -R "$(usb_attach_host):$(usb_port):127.0.0.1:3240" \
    "$(usb_user)@$(usb_host)"
}
