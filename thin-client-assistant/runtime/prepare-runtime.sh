#!/usr/bin/env bash
set -euo pipefail

STATUS_DIR="${STATUS_DIR:-/var/lib/pve-thin-client}"
STATUS_FILE="$STATUS_DIR/runtime.status"
# Debian 13 Trixie live-boot overlayfs fix: copy runtime scripts to /run (tmpfs)
# before sourcing so bash reads from tmpfs, not squashfs-via-overlayfs which can
# fail with I/O errors on some kernel/squashfs combinations.
_rt_orig="${BEAGLE_RUNTIME_SCRIPT_DIR:-/usr/local/lib/pve-thin-client/runtime}"
_rt_run="/run/pve-thin-client/runtime"
if [[ ! -f "${_rt_run}/common.sh" ]]; then
  mkdir -p "$_rt_run" 2>/dev/null || true
  cp -a "${_rt_orig}/." "$_rt_run/" 2>/dev/null || true
fi
[[ -f "${_rt_run}/common.sh" ]] && _rt_orig="$_rt_run"
SCRIPT_DIR="$_rt_orig"
export RUNTIME_SCRIPT_DIR="$_rt_orig"
unset _rt_orig _rt_run
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

ensure_wireguard_runtime_guard() {
  local guard_script guard_log guard_unit systemctl_bin
  guard_script="${BEAGLE_WG_RUNTIME_GUARD_SH:-$SCRIPT_DIR/wireguard_runtime_guard.sh}"
  guard_log="${BEAGLE_WG_RUNTIME_GUARD_LOG:-/var/log/beagle-wg-runtime-guard.log}"
  guard_unit="${BEAGLE_WG_RUNTIME_GUARD_UNIT:-beagle-wg-runtime-guard.service}"
  systemctl_bin="${BEAGLE_SYSTEMCTL_BIN:-systemctl}"

  [[ -r "$guard_script" ]] || return 0

  if command -v "$systemctl_bin" >/dev/null 2>&1 && "$systemctl_bin" list-unit-files "$guard_unit" >/dev/null 2>&1; then
    "$systemctl_bin" enable "$guard_unit" >/dev/null 2>&1 || true
    "$systemctl_bin" restart --no-block "$guard_unit" >/dev/null 2>&1 || true
    beagle_log_event "prepare-runtime.wg-guard" "status=service script=${guard_script} unit=${guard_unit}"
    return 0
  fi

  nohup bash "$guard_script" >>"$guard_log" 2>&1 &
  disown || true
  beagle_log_event "prepare-runtime.wg-guard" "status=fallback script=${guard_script}"
}

wireguard_peer_restore_state_file() {
  printf '%s\n' "${BEAGLE_WG_PEER_RESTORE_STATE_FILE:-/run/beagle/wg-beagle-peer.env}"
}

wireguard_conf_value() {
  local key conf_file
  key="$1"
  conf_file="$2"
  awk -v key="$key" '
    /^\[Peer\]/{p=1; next}
    /^\[/{p=0}
    p && index($0, "=") {
      lhs=substr($0, 1, index($0, "=") - 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", lhs)
      if (lhs == key) {
        value=substr($0, index($0, "=") + 1)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
        print value
        exit
      }
    }
  ' "$conf_file"
}

write_wireguard_peer_restore_state() {
  local wg_conf state_file state_dir tmp_file pubkey endpoint allowed_ips keepalive
  wg_conf="${WG_CONF:-/etc/wireguard/wg-beagle.conf}"
  [[ -r "$wg_conf" ]] || return 0

  pubkey="$(wireguard_conf_value PublicKey "$wg_conf")"
  endpoint="$(wireguard_conf_value Endpoint "$wg_conf")"
  allowed_ips="$(wireguard_conf_value AllowedIPs "$wg_conf" | tr -d '[:space:]')"
  keepalive="$(wireguard_conf_value PersistentKeepalive "$wg_conf")"
  [[ -n "$pubkey" ]] || return 0

  state_file="$(wireguard_peer_restore_state_file)"
  state_dir="$(dirname "$state_file")"
  install -d -m 0755 "$state_dir" >/dev/null 2>&1 || mkdir -p "$state_dir"
  tmp_file="${state_file}.tmp.$$"
  {
    printf 'WG_PEER_PUBLIC_KEY=%s\n' "$pubkey"
    printf 'WG_PEER_ENDPOINT=%s\n' "$endpoint"
    printf 'WG_PEER_ALLOWED_IPS=%s\n' "$allowed_ips"
    printf 'WG_PEER_KEEPALIVE=%s\n' "$keepalive"
  } >"$tmp_file"
  chmod 0644 "$tmp_file" >/dev/null 2>&1 || true
  mv -f "$tmp_file" "$state_file"
  beagle_log_event "prepare-runtime.wg-peer-restore-state" "status=ready file=$state_file"
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

if [[ "$prepare_runtime_reentry" -eq 0 && -r "$SCRIPT_DIR/apply-network-config.sh" ]]; then
  plymouth_status "Configuring network..."
  beagle_log_event "prepare-runtime.network" "applying network configuration"
  bash "$SCRIPT_DIR/apply-network-config.sh" || beagle_log_event "prepare-runtime.network-error" "network configuration failed"
  write_runtime_debug_report "after-network" || true
fi

ensure_wireguard_runtime_capabilities

plymouth_status "Connecting device to Beagle Manager..."
enroll_endpoint_if_needed || beagle_log_event "prepare-runtime.enroll-error" "endpoint enrollment failed"
enroll_wireguard_if_needed || beagle_log_event "prepare-runtime.wireguard-error" "wireguard enrollment failed"
write_wireguard_peer_restore_state || beagle_log_event "prepare-runtime.wg-peer-restore-state-error" "write failed"
ensure_wireguard_runtime_guard || beagle_log_event "prepare-runtime.wg-guard-error" "wireguard guard start failed"
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
