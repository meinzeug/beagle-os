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

device_wipe_report_file_path() {
  printf '%s/device-wipe-report.json\n' "$(beagle_state_dir)"
}

device_wipe_actions_file_path() {
  printf '%s/device-wipe-actions.log\n' "$(beagle_state_dir)"
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
    "${state_dir}/device-wipe-actions.log" \
    >/dev/null 2>&1 || true

  rm -rf \
    "${user_home}/.config/Moonlight Game Streaming Project" \
    "${user_home}/.cache/moonlight" \
    "${state_dir}/gfn" \
    >/dev/null 2>&1 || true
}

reset_device_wipe_actions() {
  local actions_file
  actions_file="$(device_wipe_actions_file_path)"
  mkdir -p "$(dirname "$actions_file")" >/dev/null 2>&1 || true
  : >"$actions_file"
}

record_device_wipe_action() {
  local action_name="${1:-}"
  local status="${2:-}"
  local detail="${3:-}"
  local required="${4:-0}"
  local target="${5:-}"
  local actions_file
  actions_file="$(device_wipe_actions_file_path)"
  mkdir -p "$(dirname "$actions_file")" >/dev/null 2>&1 || true
  printf '%s\t%s\t%s\t%s\t%s\n' "$action_name" "$status" "$required" "$target" "$detail" >>"$actions_file"
}

runtime_install_device() {
  local configured config_file value
  configured="${PVE_THIN_CLIENT_INSTALL_DEVICE:-}"
  if [[ -n "$configured" ]]; then
    printf '%s\n' "$configured"
    return 0
  fi
  config_file="$(runtime_thinclient_config_file)"
  if [[ -r "$config_file" ]]; then
    value="$(awk -F= '/^PVE_THIN_CLIENT_INSTALL_DEVICE=/{print substr($0, index($0, "=")+1)}' "$config_file" | tail -n 1 | tr -d '"' || true)"
    if [[ -n "$value" ]]; then
      printf '%s\n' "$value"
      return 0
    fi
  fi
  return 1
}

device_path_is_wipeable_target() {
  local path="${1:-}"
  [[ -n "$path" ]] || return 1
  if [[ -b "$path" ]]; then
    return 0
  fi
  [[ "${BEAGLE_WIPE_ALLOW_REGULAR_FILE:-0}" == "1" && -f "$path" ]]
}

clear_tpm_state() {
  if ! command -v tpm2_clear >/dev/null 2>&1; then
    record_device_wipe_action "tpm_clear" "skipped" "tpm2_clear unavailable" "0" ""
    return 2
  fi
  if beagle_run_privileged tpm2_clear >/dev/null 2>&1; then
    record_device_wipe_action "tpm_clear" "completed" "tpm state cleared" "0" ""
    return 0
  fi
  record_device_wipe_action "tpm_clear" "failed" "tpm2_clear failed" "0" ""
  return 1
}

wipe_install_device_metadata() {
  local install_device dd_count
  install_device="$(runtime_install_device || true)"
  if [[ -z "$install_device" ]]; then
    record_device_wipe_action "storage_wipe" "skipped" "install device unknown" "1" ""
    return 2
  fi
  if ! device_path_is_wipeable_target "$install_device"; then
    record_device_wipe_action "storage_wipe" "failed" "target is not wipeable" "1" "$install_device"
    return 1
  fi
  if command -v blkdiscard >/dev/null 2>&1; then
    if beagle_run_privileged blkdiscard -f "$install_device" >/dev/null 2>&1; then
      record_device_wipe_action "storage_wipe" "completed" "blkdiscard" "1" "$install_device"
      return 0
    fi
  fi
  if command -v wipefs >/dev/null 2>&1; then
    beagle_run_privileged wipefs -a "$install_device" >/dev/null 2>&1 || true
  fi
  dd_count="${BEAGLE_WIPE_ZERO_MIB:-16}"
  if command -v dd >/dev/null 2>&1; then
    if beagle_run_privileged dd if=/dev/zero of="$install_device" bs=1M count="$dd_count" conv=fsync status=none >/dev/null 2>&1; then
      record_device_wipe_action "storage_wipe" "completed" "zeroed-first-${dd_count}MiB" "1" "$install_device"
      return 0
    fi
  fi
  record_device_wipe_action "storage_wipe" "failed" "no storage wipe strategy succeeded" "1" "$install_device"
  return 1
}

write_device_wipe_report() {
  local report_file final_status confirm_attempted reboot_requested
  report_file="$(device_wipe_report_file_path)"
  final_status="${1:-completed}"
  confirm_attempted="${2:-0}"
  reboot_requested="${3:-0}"
  mkdir -p "$(dirname "$report_file")" >/dev/null 2>&1 || true
  python3 - "$report_file" "$(runtime_device_id)" "$(device_wipe_actions_file_path)" "$final_status" "$confirm_attempted" "$reboot_requested" "$(runtime_install_device || true)" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

report_file = sys.argv[1]
device_id = sys.argv[2]
actions_file = Path(sys.argv[3])
final_status = sys.argv[4]
confirm_attempted = sys.argv[5] == "1"
reboot_requested = sys.argv[6] == "1"
install_device = sys.argv[7]
actions = []
if actions_file.exists():
    for line in actions_file.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t", 4)
        if len(parts) != 5:
            continue
        actions.append(
            {
                "action": parts[0],
                "status": parts[1],
                "required": parts[2] == "1",
                "target": parts[3],
                "detail": parts[4],
            }
        )
payload = {
    "device_id": device_id,
    "status": final_status,
    "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "install_device": install_device,
    "confirm_attempted": confirm_attempted,
    "reboot_requested": reboot_requested,
    "actions": actions,
}
with open(report_file, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
PY
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
  local device_id detected_install_device reboot_requested final_status storage_result tpm_result confirm_attempted strict_mode
  device_id="$(runtime_device_id)"
  detected_install_device="$(runtime_install_device || true)"
  if [[ -n "$detected_install_device" && -z "${PVE_THIN_CLIENT_INSTALL_DEVICE:-}" ]]; then
    export PVE_THIN_CLIENT_INSTALL_DEVICE="$detected_install_device"
  fi
  reboot_requested=$([[ "${BEAGLE_WIPE_REBOOT:-1}" == "1" ]] && printf '1' || printf '0')
  confirm_attempted=0
  strict_mode="${BEAGLE_WIPE_STRICT:-0}"
  beagle_log_event "device.wipe.start" "device_id=${device_id}"
  reset_device_wipe_actions
  stop_device_wireguard
  record_device_wipe_action "wireguard_down" "completed" "wireguard stopped" "0" "${WG_IFACE:-wg-beagle}"
  clear_device_runtime_secrets
  record_device_wipe_action "runtime_secret_clear" "completed" "runtime secrets cleared" "1" ""
  storage_result=0
  tpm_result=0
  wipe_install_device_metadata || storage_result=$?
  clear_tpm_state || tpm_result=$?
  final_status="completed"
  if [[ "$storage_result" == "1" ]]; then
    final_status="failed"
  elif [[ "$storage_result" == "2" || "$tpm_result" == "1" ]]; then
    final_status="partial"
  fi
  if [[ "$strict_mode" != "1" || "$final_status" == "completed" ]]; then
    if declare -F confirm_device_wiped_runtime >/dev/null 2>&1; then
      if confirm_device_wiped_runtime "$device_id"; then
        confirm_attempted=1
      fi
    fi
  fi
  write_device_wipe_report "$final_status" "$confirm_attempted" "$reboot_requested"
  if [[ "$confirm_attempted" == "1" ]]; then
    rm -f "$(device_wipe_file_path)" >/dev/null 2>&1 || true
  fi
  beagle_log_event "device.wipe.complete" "device_id=${device_id} status=${final_status} confirm_attempted=${confirm_attempted}"
  if [[ "$final_status" != "failed" ]]; then
    request_reboot_after_wipe || true
  fi
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
