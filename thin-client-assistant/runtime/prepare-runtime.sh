#!/usr/bin/env bash
set -euo pipefail

STATUS_DIR="${STATUS_DIR:-/var/lib/pve-thin-client}"
STATUS_FILE="$STATUS_DIR/runtime.status"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATUS_WRITER_PY="$SCRIPT_DIR/status_writer.py"
APPLY_ENROLLMENT_CONFIG_PY="$SCRIPT_DIR/apply_enrollment_config.py"
RUNTIME_CONFIG_PERSISTENCE_SH="${RUNTIME_CONFIG_PERSISTENCE_SH:-$SCRIPT_DIR/runtime_config_persistence.sh}"
RUNTIME_USER_SETUP_SH="${RUNTIME_USER_SETUP_SH:-$SCRIPT_DIR/runtime_user_setup.sh}"
RUNTIME_BOOTSTRAP_SERVICES_SH="${RUNTIME_BOOTSTRAP_SERVICES_SH:-$SCRIPT_DIR/runtime_bootstrap_services.sh}"
RUNTIME_ENDPOINT_ENROLLMENT_SH="${RUNTIME_ENDPOINT_ENROLLMENT_SH:-$SCRIPT_DIR/runtime_endpoint_enrollment.sh}"
RUNTIME_PREPARE_FLOW_SH="${RUNTIME_PREPARE_FLOW_SH:-$SCRIPT_DIR/runtime_prepare_flow.sh}"
RUNTIME_PREPARE_STATUS_SH="${RUNTIME_PREPARE_STATUS_SH:-$SCRIPT_DIR/runtime_prepare_status.sh}"
RUNTIME_DEBUG_REPORT_SH="${RUNTIME_DEBUG_REPORT_SH:-$SCRIPT_DIR/runtime_debug_report.sh}"
DEVICE_SYNC_SH="${DEVICE_SYNC_SH:-$SCRIPT_DIR/device_sync.sh}"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
# shellcheck disable=SC1090
source "$RUNTIME_CONFIG_PERSISTENCE_SH"
# shellcheck disable=SC1090
source "$RUNTIME_USER_SETUP_SH"
# shellcheck disable=SC1090
source "$RUNTIME_BOOTSTRAP_SERVICES_SH"
# shellcheck disable=SC1090
source "$RUNTIME_ENDPOINT_ENROLLMENT_SH"
# shellcheck disable=SC1090
source "$RUNTIME_PREPARE_FLOW_SH"
# shellcheck disable=SC1090
source "$RUNTIME_PREPARE_STATUS_SH"
# shellcheck disable=SC1090
source "$RUNTIME_DEBUG_REPORT_SH"
# shellcheck disable=SC1090
source "$DEVICE_SYNC_SH"

load_runtime_config_with_retry
BOOT_MODE="${PVE_THIN_CLIENT_BOOT_MODE:-$(detect_runtime_boot_mode)}"

prepare_runtime_state_file() {
  local state_dir
  ensure_beagle_state_dir
  state_dir="$(beagle_state_dir)"
  printf '%s/prepare-runtime-state.env\n' "$state_dir"
}

prepare_runtime_current_boot_id() {
  runtime_boot_id 2>/dev/null || cat /proc/sys/kernel/random/boot_id 2>/dev/null || true
}

prepare_runtime_already_ready() {
  local state_file current_boot recorded_boot recorded_state
  [[ "${PVE_THIN_CLIENT_FORCE_PREPARE_RECONFIGURE:-0}" == "1" ]] && return 1
  state_file="$(prepare_runtime_state_file)"
  [[ -r "$state_file" ]] || return 1
  current_boot="$(prepare_runtime_current_boot_id)"
  recorded_boot="$(awk -F= '$1=="boot_id" {print substr($0, index($0, "=")+1); exit}' "$state_file")"
  recorded_state="$(awk -F= '$1=="state" {print substr($0, index($0, "=")+1); exit}' "$state_file")"
  [[ -n "$current_boot" && "$recorded_boot" == "$current_boot" && "$recorded_state" == "ready" ]]
}

prepare_runtime_mark_ready() {
  local state_file current_boot
  state_file="$(prepare_runtime_state_file)"
  current_boot="$(prepare_runtime_current_boot_id)"
  {
    printf 'boot_id=%s\n' "$current_boot"
    printf 'state=ready\n'
    printf 'updated_at=%s\n' "$(date -Iseconds 2>/dev/null || date)"
  } >"$state_file"
  chmod 0644 "$state_file" >/dev/null 2>&1 || true
}

ensure_wireguard_runtime_capabilities() {
  local wg_bin current_caps

  command -v setcap >/dev/null 2>&1 || return 0
  wg_bin="$(command -v wg 2>/dev/null || true)"
  [[ -n "$wg_bin" ]] || return 0

  if command -v getcap >/dev/null 2>&1; then
    current_caps="$(getcap "$wg_bin" 2>/dev/null || true)"
    if [[ "$current_caps" == *"cap_net_admin=ep"* ]]; then
      beagle_log_event "prepare-runtime.wg-capability" "status=ok binary=$wg_bin capability=cap_net_admin"
      return 0
    fi
  fi

  if setcap cap_net_admin+ep "$wg_bin" >/dev/null 2>&1; then
    beagle_log_event "prepare-runtime.wg-capability" "status=applied binary=$wg_bin capability=cap_net_admin"
  else
    beagle_log_event "prepare-runtime.wg-capability-error" "binary=$wg_bin capability=cap_net_admin"
  fi
}

prepare_runtime_reentry=0
if prepare_runtime_already_ready; then
  prepare_runtime_reentry=1
fi

beagle_log_event "prepare-runtime.start" "profile=${PVE_THIN_CLIENT_PROFILE_NAME:-default} mode=${PVE_THIN_CLIENT_MODE:-UNSET}"
write_runtime_debug_report "prepare-start" || true

plymouth_status "Loading Beagle OS profile..."
sync_runtime_config_to_system
if [[ "$prepare_runtime_reentry" -eq 0 ]]; then
  ensure_runtime_user
else
  beagle_log_event "prepare-runtime.reentry" "skipping password rotation and network/ssh reconfigure for current boot"
fi
adjust_secret_permissions
persist_runtime_config_to_live_state
sync_local_hostname
if [[ "$prepare_runtime_reentry" -eq 0 ]]; then
  apply_runtime_ssh_config
fi
ensure_getty_overrides || beagle_log_event "prepare-runtime.getty-overrides-error" "getty override setup failed"
normalize_boot_services || beagle_log_event "prepare-runtime.boot-services-error" "boot service normalization failed"
if command -v ip >/dev/null 2>&1; then
  stale_wg_iface="${PVE_THIN_CLIENT_BEAGLE_EGRESS_INTERFACE:-wg-beagle}"
  ip route delete 0.0.0.0/1 dev "$stale_wg_iface" 2>/dev/null || true
  ip route delete 128.0.0.0/1 dev "$stale_wg_iface" 2>/dev/null || true
  ip -6 route delete ::/1 dev "$stale_wg_iface" 2>/dev/null || true
  ip -6 route delete 8000::/1 dev "$stale_wg_iface" 2>/dev/null || true
fi

if [[ "$prepare_runtime_reentry" -eq 0 && -x "$SCRIPT_DIR/apply-network-config.sh" ]]; then
  plymouth_status "Configuring network..."
  beagle_log_event "prepare-runtime.network" "applying network configuration"
  "$SCRIPT_DIR/apply-network-config.sh" || beagle_log_event "prepare-runtime.network-error" "network configuration failed"
  write_runtime_debug_report "after-network" || true
fi

ensure_wireguard_runtime_capabilities

plymouth_status "Connecting device to Beagle Manager..."
enroll_endpoint_if_needed || beagle_log_event "prepare-runtime.enroll-error" "endpoint enrollment failed"
enroll_wireguard_if_needed || beagle_log_event "prepare-runtime.wireguard-error" "wireguard enrollment failed"
adjust_secret_permissions
if [[ "$prepare_runtime_reentry" -eq 0 ]]; then
  ensure_runtime_ssh_host_keys
fi
persist_runtime_config_to_live_state
ensure_usb_tunnel_service
ensure_kiosk_runtime || true
run_optional_runtime_hook "/usr/local/sbin/beagle-identity-apply" "Applying system identity..."
run_optional_runtime_hook "/usr/local/sbin/beagle-egress-apply" "Preparing secure connection..."
prepare_runtime_mark_ready
sync_device_runtime_state || beagle_log_event "prepare-runtime.device-sync-error" "initial sync failed"
ensure_beagle_management_units
beagle_log_event "prepare-runtime.system" "runtime_user=${PVE_THIN_CLIENT_RUNTIME_USER:-UNSET} hostname=${PVE_THIN_CLIENT_HOSTNAME:-UNSET}"
write_runtime_debug_report "prepare-ready" || true

required_binary="$(runtime_required_binary "$BOOT_MODE")"
binary_available="$(runtime_binary_available "$required_binary" "$BOOT_MODE")"
write_prepare_runtime_status "$BOOT_MODE" "$required_binary" "$binary_available"
beagle_log_event "prepare-runtime.ready" "binary=${required_binary} binary_available=${binary_available}"
