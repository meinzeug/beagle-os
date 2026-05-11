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

# Determine whether a USB busid should be auto-bound for VM forwarding.
# Returns 0 (eligible) or 1 (skip: hub, HID/input-only, Bluetooth).
_is_eligible_for_autobind() {
  local busid="$1"
  local devpath="/sys/bus/usb/devices/$busid"
  local class iface_class_file iface_class has_useful

  [[ -f "$devpath/bDeviceClass" ]] || return 1
  class="$(tr '[:upper:]' '[:lower:]' < "$devpath/bDeviceClass" 2>/dev/null | tr -d '[:space:]')"

  case "$class" in
    09|e0) return 1 ;;  # Hub, Wireless/BT: always skip
    03)    return 1 ;;  # Pure HID (keyboard, mouse): skip
    00)
      # Class 00 = look at interface classes
      has_useful=0
      for iface_class_file in "$devpath"/${busid}:*/bInterfaceClass; do
        [[ -f "$iface_class_file" ]] || continue
        iface_class="$(tr '[:upper:]' '[:lower:]' < "$iface_class_file" 2>/dev/null | tr -d '[:space:]')"
        # Audio(01), Storage(08), Video(0e), Printer(07), Imaging(06), Vendor(ff)
        case "$iface_class" in
          01|06|07|08|0a|0b|0e|ff) has_useful=1 ;;
        esac
      done
      [[ "$has_useful" == "1" ]] || return 1
      ;;
  esac
  return 0
}

# Bind all USB devices that are eligible for VM forwarding (auto-bind mode).
# Skips devices that are already exported by usbip-host.
auto_bind_eligible_devices() {
  local usbip_cmd busid devpath

  [[ "$(usb_auto_bind)" == "1" ]] || return 0
  usbip_cmd="$(usbip_bin)"
  require_enabled
  ensure_usbipd

  for devpath in /sys/bus/usb/devices/*/; do
    busid="$(basename "$devpath")"
    # Only top-level devices: digits, dash, digits, optional dot-digits (1-2.1.3)
    [[ "$busid" =~ ^[0-9]+-[0-9]+(\.[0-9]+)*$ ]] || continue
    _is_eligible_for_autobind "$busid" || continue
    # Skip if already bound to usbip-host
    [[ -e "/sys/bus/usb/drivers/usbip-host/$busid" ]] && continue
    "$usbip_cmd" unbind -b "$busid" >/dev/null 2>&1 || true
    "$usbip_cmd" bind   -b "$busid" >/dev/null 2>&1 && \
      echo "beagle-usb: auto-bound $busid" >&2 || true
  done
}

# Bind a single newly-plugged device (called from udev hotplug helper).
autobind_hotplug_device() {
  local busid="$1"
  local usbip_cmd

  [[ "$(usb_auto_bind)" == "1" ]] || return 0
  require_enabled
  _is_eligible_for_autobind "$busid" || return 0
  [[ -e "/sys/bus/usb/drivers/usbip-host/$busid" ]] && return 0
  usbip_cmd="$(usbip_bin)"
  ensure_usbipd
  "$usbip_cmd" unbind -b "$busid" >/dev/null 2>&1 || true
  "$usbip_cmd" bind   -b "$busid" >/dev/null 2>&1 && \
    echo "beagle-usb: hotplug-bound $busid" >&2 || true
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
