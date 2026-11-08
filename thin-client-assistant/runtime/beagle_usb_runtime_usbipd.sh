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

audio_input_bridge_enabled() {
  [[ "${PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_BRIDGE_ENABLED:-1}" == "1" ]]
}

_usb_device_identity_has_camera_hint() {
  local busid="$1"
  local devpath="/sys/bus/usb/devices/$busid"
  local text=""

  for field in product manufacturer; do
    [[ -r "$devpath/$field" ]] || continue
    text+=" $(tr '[:upper:]' '[:lower:]' < "$devpath/$field" 2>/dev/null || true)"
  done
  grep -Eq '(camera|webcam|video|uvc|cam)' <<<"$text"
}

_usb_device_has_storage_interface() {
  local busid="$1"
  local iface_class_file iface_class

  for iface_class_file in /sys/bus/usb/devices/${busid}:*/bInterfaceClass; do
    [[ -f "$iface_class_file" ]] || continue
    iface_class="$(tr '[:upper:]' '[:lower:]' < "$iface_class_file" 2>/dev/null | tr -d '[:space:]')"
    [[ "$iface_class" == "08" ]] && return 0
  done
  return 1
}

_usb_device_has_block_child() {
  local busid="$1"
  local devpath="/sys/bus/usb/devices/$busid"
  local block_dir node part

  for block_dir in "$devpath"/*/block/* "$devpath"/block/*; do
    [[ -d "$block_dir" ]] || continue
    for node in "$block_dir" "$block_dir"/*; do
      [[ -e "$node" ]] || continue
      part="$(basename "$node")"
      [[ -b "/dev/$part" ]] && return 0
    done
  done
  return 1
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
  if declare -F modprobe_bin >/dev/null; then
    modprobe_cmd="$(modprobe_bin)"
  else
    modprobe_cmd="$(command -v modprobe || printf /usr/sbin/modprobe)"
  fi
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
  local class iface_class_file iface_class has_useful has_interface

  [[ -f "$devpath/bDeviceClass" ]] || return 1
  _usb_device_has_block_child "$busid" && return 1
  _usb_device_has_storage_interface "$busid" && return 1
  _usb_device_has_mounted_block_child "$busid" && return 1
  class="$(tr '[:upper:]' '[:lower:]' < "$devpath/bDeviceClass" 2>/dev/null | tr -d '[:space:]')"

  case "$class" in
    09|e0) return 1 ;;  # Hub, Wireless/BT: always skip
    03) return 1 ;;  # Any HID interface can be keyboard/mouse: keep local.
    00|ef)
      # Class 00 = look at interface classes
      # Class EF (IAD composite, e.g. webcams/microphones) also requires
      # interface inspection.
      has_useful=0
      has_interface=0
      for iface_class_file in /sys/bus/usb/devices/${busid}:*/bInterfaceClass; do
        [[ -f "$iface_class_file" ]] || continue
        has_interface=1
        iface_class="$(tr '[:upper:]' '[:lower:]' < "$iface_class_file" 2>/dev/null | tr -d '[:space:]')"
        case "$iface_class" in
          01) audio_input_bridge_enabled && continue ;;  # USB audio stays local unless the device also has another useful interface.
          0e) return 1 ;;  # Webcams stay local so beagle-camera-stream can expose them to the VM reliably.
          03) continue ;;  # Ignore HID sub-interfaces on composite devices.
          e0) return 1 ;;  # Bluetooth controllers must stay local.
        esac
        # Audio(01), Printer(07), Imaging(06),
        # CDC(0a/0b), Vendor(ff)
        case "$iface_class" in
          01|06|07|0a|0b|ff) has_useful=1 ;;
        esac
      done
      if [[ "$has_interface" != "1" ]]; then
        [[ "$class" == "ef" ]] && _usb_device_identity_has_camera_hint "$busid" && return 1
        return 1
      fi
      [[ "$has_useful" == "1" ]] || return 1
      ;;
  esac
  return 0
}

_usb_device_has_mounted_block_child() {
  local busid="$1"
  local devpath="/sys/bus/usb/devices/$busid"
  local block_dir node part

  for block_dir in "$devpath"/*/block/* "$devpath"/block/*; do
    [[ -d "$block_dir" ]] || continue
    for node in "$block_dir" "$block_dir"/*; do
      [[ -e "$node" ]] || continue
      part="$(basename "$node")"
      [[ -b "/dev/$part" ]] || continue
      if command -v findmnt >/dev/null 2>&1 && findmnt -rn -S "/dev/$part" >/dev/null 2>&1; then
        return 0
      fi
      if grep -qE "^/dev/${part}[[:space:]]" /proc/mounts 2>/dev/null; then
        return 0
      fi
    done
  done
  return 1
}

is_bound_to_usbip_host() {
  local busid="$1"
  [[ -e "/sys/bus/usb/drivers/usbip-host/$busid" ]]
}

# Serialize hotplug and startup reconciliation: binding itself can cause more
# udev events. Never disconnect a device already in use by a guest.
autobind_hotplug_device() (
  local busid="$1" usbip_cmd attempt_file now window count
  [[ "$busid" =~ ^[0-9]+-[0-9]+(\.[0-9]+)*$ ]] || return 1
  [[ "$(usb_auto_bind)" == "1" || "${2:-}" == "restore" ]] || return 0
  require_enabled
  mkdir -p /run/lock
  exec 9>/run/lock/beagle-usb-autobind.lock
  flock -x 9
  if is_bound_to_usbip_host "$busid"; then
    bound_add "$busid" >/dev/null 2>&1 || true
    return 0
  fi
  _is_eligible_for_autobind "$busid" || return 0
  # A device that resets itself after binding can emit endless add events.
  # Limit attempts in a rolling minute; a later physical replug can retry.
  mkdir -p /run/beagle-usb
  attempt_file="/run/beagle-usb/attempt-${busid}"
  now=$(date +%s)
  window=0; count=0
  if [[ -r "$attempt_file" ]]; then
    read -r window count < "$attempt_file" || true
  fi
  [[ "$window" =~ ^[0-9]+$ && "$count" =~ ^[0-9]+$ ]] || { window=0; count=0; }
  if (( now - window >= 60 || now < window )); then window=$now; count=0; fi
  if (( count >= 3 )); then
    echo "beagle-usb: repeated reset for $busid; waiting for a later replug" >&2
    return 1
  fi
  printf '%s %s\n' "$window" "$((count + 1))" > "$attempt_file"
  usbip_cmd="$(usbip_bin)"
  ensure_usbipd
  if "$usbip_cmd" bind -b "$busid" >/dev/null 2>&1; then
    bound_add "$busid" >/dev/null 2>&1 || true
    echo "beagle-usb: hotplug-bound $busid" >&2
  fi
)

auto_bind_eligible_devices() {
  local busid devpath
  [[ "$(usb_auto_bind)" == "1" ]] || return 0
  for devpath in /sys/bus/usb/devices/*/; do
    busid="$(basename "$devpath")"
    [[ "$busid" =~ ^[0-9]+-[0-9]+(\.[0-9]+)*$ ]] || continue
    autobind_hotplug_device "$busid" || true
  done
}

# The list of available exports does not include devices already attached by a
# guest. Never interpret an empty list as a reason to restart or rebind them.
sync_bound_devices() {
  local item
  ensure_usbipd
  for item in $(state_bound_busids); do
    [[ -n "$item" ]] || continue
    if is_bound_to_usbip_host "$item"; then
      continue
    fi
    if ! _is_eligible_for_autobind "$item"; then
      bound_remove "$item" >/dev/null 2>&1 || true
      continue
    fi
    autobind_hotplug_device "$item" restore || true
  done
}
