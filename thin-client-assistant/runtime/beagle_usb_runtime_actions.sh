#!/usr/bin/env bash

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

have_usbipd() {
  local pgrep_cmd
  pgrep_cmd="$(pgrep_bin)"
  "$pgrep_cmd" -x usbipd >/dev/null 2>&1
}

restart_usbipd() {
  local pkill_cmd usbipd_cmd sleep_cmd
  pkill_cmd="$(pkill_bin)"
  usbipd_cmd="$(usbipd_bin)"
  sleep_cmd="$(sleep_bin)"

  "$pkill_cmd" -x usbipd >/dev/null 2>&1 || true
  "$sleep_cmd" 1
  "$usbipd_cmd" -D >/dev/null 2>&1 || true
  "$sleep_cmd" 1
}

have_exportable_devices() {
  local output usbip_cmd
  usbip_cmd="$(usbip_bin)"
  output="$("$usbip_cmd" list -r 127.0.0.1 2>/dev/null || true)"
  grep -q "^ - 127\\.0\\.0\\.1" <<<"$output"
}

ensure_usbipd() {
  local modprobe_cmd

  require_enabled
  modprobe_cmd="$(modprobe_bin)"
  "$modprobe_cmd" usbip-host >/dev/null 2>&1 || true
  if ! have_usbipd; then
    restart_usbipd
  fi
}

sync_bound_devices() {
  local item usbip_cmd sleep_cmd

  usbip_cmd="$(usbip_bin)"
  sleep_cmd="$(sleep_bin)"
  ensure_usbipd
  for item in $(state_bound_busids); do
    [[ -n "$item" ]] || continue
    "$usbip_cmd" unbind -b "$item" >/dev/null 2>&1 || true
    "$usbip_cmd" bind -b "$item" >/dev/null 2>&1 || true
  done
  "$sleep_cmd" 1
  restart_usbipd
  if [[ -n "$(state_bound_busids)" ]] && ! have_exportable_devices; then
    for item in $(state_bound_busids); do
      [[ -n "$item" ]] || continue
      "$usbip_cmd" unbind -b "$item" >/dev/null 2>&1 || true
      "$sleep_cmd" 1
      "$usbip_cmd" bind -b "$item" >/dev/null 2>&1 || true
    done
    "$sleep_cmd" 1
    restart_usbipd
  fi
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
