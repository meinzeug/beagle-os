#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_SH="${COMMON_SH:-$SCRIPT_DIR/common.sh}"
DEVICE_SYNC_SH="${DEVICE_SYNC_SH:-$SCRIPT_DIR/device_sync.sh}"
RUNTIME_ENDPOINT_ENROLLMENT_SH="${RUNTIME_ENDPOINT_ENROLLMENT_SH:-$SCRIPT_DIR/runtime_endpoint_enrollment.sh}"

if [[ -r "$COMMON_SH" ]]; then
  # shellcheck disable=SC1090
  source "$COMMON_SH"
fi
if [[ -r "$RUNTIME_ENDPOINT_ENROLLMENT_SH" ]]; then
  # shellcheck disable=SC1090
  source "$RUNTIME_ENDPOINT_ENROLLMENT_SH"
fi
if [[ -r "$DEVICE_SYNC_SH" ]]; then
  # shellcheck disable=SC1090
  source "$DEVICE_SYNC_SH"
fi

device_lock_file_path() {
  printf '%s/device.locked\n' "$(beagle_state_dir)"
}

device_wipe_file_path() {
  printf '%s/device.wipe-pending\n' "$(beagle_state_dir)"
}

device_lock_active() {
  [[ -f "$(device_lock_file_path)" ]]
}

device_wipe_pending() {
  [[ -f "$(device_wipe_file_path)" ]]
}

clear_device_runtime_secrets() {
  local state_dir wg_iface user_home
  state_dir="$(beagle_state_dir)"
  wg_iface="${WG_IFACE:-wg-beagle}"
  user_home="$(runtime_user_home)"

  rm -f \
    "$(runtime_credentials_file)" \
    "$(runtime_thinclient_config_file)" \
    "/etc/beagle/enrollment.conf" \
    "/etc/wireguard/${wg_iface}.conf" \
    "${state_dir}/device.locked" \
    "${state_dir}/device-policy.json" \
    "${state_dir}/runtime-heartbeat.status" \
    "${state_dir}/runtime-heartbeat.prev" \
    "${state_dir}/last-marker.env" \
    >/dev/null 2>&1 || true

  rm -rf \
    "${user_home}/.config/Moonlight Game Streaming Project" \
    "${user_home}/.cache/moonlight" \
    "${state_dir}/gfn" \
    >/dev/null 2>&1 || true
}

stop_device_wireguard() {
  local wg_iface="${WG_IFACE:-wg-beagle}"
  if command -v wg-quick >/dev/null 2>&1; then
    beagle_run_privileged wg-quick down "$wg_iface" >/dev/null 2>&1 || true
  fi
}

request_reboot_after_wipe() {
  [[ "${BEAGLE_WIPE_REBOOT:-1}" == "1" ]] || return 1
  if command -v systemctl >/dev/null 2>&1; then
    beagle_run_privileged systemctl reboot --force >/dev/null 2>&1 || true
  elif command -v reboot >/dev/null 2>&1; then
    beagle_run_privileged reboot -f >/dev/null 2>&1 || true
  fi
}

perform_device_wipe() {
  local device_id
  device_id="$(runtime_device_id)"
  beagle_log_event "device.wipe.start" "device_id=${device_id}"
  stop_device_wireguard
  clear_device_runtime_secrets
  if declare -F confirm_device_wiped_runtime >/dev/null 2>&1; then
    confirm_device_wiped_runtime "$device_id" || true
  fi
  rm -f "$(device_wipe_file_path)" >/dev/null 2>&1 || true
  beagle_log_event "device.wipe.complete" "device_id=${device_id}"
  request_reboot_after_wipe || true
}

wait_for_device_unlock() {
  local interval notified
  interval="${BEAGLE_DEVICE_LOCK_POLL_INTERVAL:-15}"
  notified=0
  while device_lock_active; do
    if [[ "$notified" == "0" ]]; then
      beagle_log_event "device.lock.active" "device_id=$(runtime_device_id)"
      notified=1
    fi
    if declare -F sync_device_runtime_state >/dev/null 2>&1; then
      sync_device_runtime_state >/dev/null 2>&1 || true
    fi
    sleep "$interval"
  done
  if [[ "$notified" == "1" ]]; then
    beagle_log_event "device.lock.cleared" "device_id=$(runtime_device_id)"
  fi
}

enforce_device_state_before_session() {
  if device_wipe_pending; then
    perform_device_wipe
    return 10
  fi
  if device_lock_active; then
    wait_for_device_unlock
  fi
  return 0
}
