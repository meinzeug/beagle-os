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

load_runtime_config_with_retry() {
  local attempts interval attempt
  attempts="${PVE_THIN_CLIENT_CONFIG_RETRY_ATTEMPTS:-30}"
  interval="${PVE_THIN_CLIENT_CONFIG_RETRY_INTERVAL:-1}"

  for attempt in $(seq 1 "$attempts"); do
    if load_runtime_config >/dev/null 2>&1; then
      return 0
    fi
    sleep "$interval"
  done

  load_runtime_config
}

load_runtime_config_with_retry
BOOT_MODE="${PVE_THIN_CLIENT_BOOT_MODE:-$(/usr/local/bin/pve-thin-client-boot-mode 2>/dev/null || printf 'runtime')}"
beagle_log_event "prepare-runtime.start" "profile=${PVE_THIN_CLIENT_PROFILE_NAME:-default} mode=${PVE_THIN_CLIENT_MODE:-UNSET}"

plymouth_status() {
  local message="$1"
  command -v plymouth >/dev/null 2>&1 || return 0
  plymouth --ping >/dev/null 2>&1 || return 0
  plymouth display-message --text="$message" >/dev/null 2>&1 || true
}

ensure_kiosk_runtime() {
  [[ "$BOOT_MODE" == "runtime" ]] || return 0
  [[ "${PVE_THIN_CLIENT_MODE:-MOONLIGHT}" == "KIOSK" ]] || return 0
  command -v /usr/local/sbin/beagle-kiosk-install >/dev/null 2>&1 || return 0

  plymouth_status "Preparing Beagle OS Gaming..."
  if ! /usr/local/sbin/beagle-kiosk-install --ensure >/dev/null 2>&1; then
    beagle_log_event "prepare-runtime.kiosk-error" "kiosk installation/update failed"
    return 1
  fi

  beagle_log_event "prepare-runtime.kiosk-ready" "beagle-kiosk ensured"
}

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
adjust_secret_permissions
ensure_runtime_ssh_host_keys
persist_runtime_config_to_live_state
ensure_beagle_management_units
ensure_usb_tunnel_service
ensure_kiosk_runtime || true
if [[ -x /usr/local/sbin/beagle-identity-apply ]]; then
  plymouth_status "Applying system identity..."
  /usr/local/sbin/beagle-identity-apply >/dev/null 2>&1 || true
fi
if [[ -x /usr/local/sbin/beagle-egress-apply ]]; then
  plymouth_status "Preparing secure connection..."
  /usr/local/sbin/beagle-egress-apply >/dev/null 2>&1 || true
fi
beagle_log_event "prepare-runtime.system" "runtime_user=${PVE_THIN_CLIENT_RUNTIME_USER:-UNSET} hostname=${PVE_THIN_CLIENT_HOSTNAME:-UNSET}"

mkdir -p "$STATUS_DIR"
chmod 0755 "$STATUS_DIR"

required_binary=""
binary_available="0"
if [[ "$BOOT_MODE" == "installer" ]]; then
  required_binary="installer-mode"
  binary_available="1"
else
  case "${PVE_THIN_CLIENT_MODE:-MOONLIGHT}" in
    MOONLIGHT)
      required_binary="${PVE_THIN_CLIENT_MOONLIGHT_BIN:-moonlight}"
      ;;
    KIOSK)
      required_binary="/usr/local/sbin/beagle-kiosk-launch"
      ;;
    GFN)
      required_binary="flatpak"
      ;;
    *)
      echo "Unsupported mode for Beagle OS: ${PVE_THIN_CLIENT_MODE:-UNSET}" >&2
      exit 1
      ;;
  esac
fi

{
  if [[ "$BOOT_MODE" == "installer" ]]; then
    binary_available="1"
  elif [[ "$required_binary" == */* ]]; then
    if [[ -x "$required_binary" ]]; then
      binary_available="1"
    else
      binary_available="0"
    fi
  elif command -v "$required_binary" >/dev/null 2>&1; then
    binary_available="1"
  else
    binary_available="0"
  fi
  python3 "$STATUS_WRITER_PY" runtime-status \
    --path "$STATUS_FILE" \
    --boot-mode "$BOOT_MODE" \
    --mode "${PVE_THIN_CLIENT_MODE:-UNSET}" \
    --runtime-user "${PVE_THIN_CLIENT_RUNTIME_USER:-UNSET}" \
    --connection-method "${PVE_THIN_CLIENT_CONNECTION_METHOD:-UNSET}" \
    --profile-name "${PVE_THIN_CLIENT_PROFILE_NAME:-UNSET}" \
    --required-binary "$required_binary" \
    --moonlight-host "${PVE_THIN_CLIENT_MOONLIGHT_HOST:-UNSET}" \
    --moonlight-app "${PVE_THIN_CLIENT_MOONLIGHT_APP:-Desktop}" \
    --binary-available "$binary_available"
} >/dev/null

chmod 0644 "$STATUS_FILE"
beagle_log_event "prepare-runtime.ready" "binary=${required_binary} binary_available=${binary_available}"
