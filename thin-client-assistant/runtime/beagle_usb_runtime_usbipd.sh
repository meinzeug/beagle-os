#!/usr/bin/env bash

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
