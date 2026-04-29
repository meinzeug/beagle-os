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
source "$DEVICE_SYNC_SH"

load_runtime_config_with_retry
BOOT_MODE="${PVE_THIN_CLIENT_BOOT_MODE:-$(detect_runtime_boot_mode)}"
beagle_log_event "prepare-runtime.start" "profile=${PVE_THIN_CLIENT_PROFILE_NAME:-default} mode=${PVE_THIN_CLIENT_MODE:-UNSET}"

plymouth_status "Loading Beagle OS profile..."
sync_runtime_config_to_system
ensure_runtime_user
adjust_secret_permissions
persist_runtime_config_to_live_state
sync_local_hostname
apply_runtime_ssh_config
ensure_getty_overrides
normalize_boot_services

if [[ -x "$SCRIPT_DIR/apply-network-config.sh" ]]; then
  plymouth_status "Configuring network..."
  beagle_log_event "prepare-runtime.network" "applying network configuration"
  "$SCRIPT_DIR/apply-network-config.sh" || beagle_log_event "prepare-runtime.network-error" "network configuration failed"
fi

plymouth_status "Connecting device to Beagle Manager..."
enroll_endpoint_if_needed || beagle_log_event "prepare-runtime.enroll-error" "endpoint enrollment failed"
enroll_wireguard_if_needed || beagle_log_event "prepare-runtime.wireguard-error" "wireguard enrollment failed"
adjust_secret_permissions
ensure_runtime_ssh_host_keys
persist_runtime_config_to_live_state
ensure_beagle_management_units
ensure_usb_tunnel_service
ensure_kiosk_runtime || true
run_optional_runtime_hook "/usr/local/sbin/beagle-identity-apply" "Applying system identity..."
run_optional_runtime_hook "/usr/local/sbin/beagle-egress-apply" "Preparing secure connection..."
sync_device_runtime_state || beagle_log_event "prepare-runtime.device-sync-error" "initial sync failed"
beagle_log_event "prepare-runtime.system" "runtime_user=${PVE_THIN_CLIENT_RUNTIME_USER:-UNSET} hostname=${PVE_THIN_CLIENT_HOSTNAME:-UNSET}"

required_binary="$(runtime_required_binary "$BOOT_MODE")"
binary_available="$(runtime_binary_available "$required_binary" "$BOOT_MODE")"
write_prepare_runtime_status "$BOOT_MODE" "$required_binary" "$binary_available"
beagle_log_event "prepare-runtime.ready" "binary=${required_binary} binary_available=${binary_available}"
