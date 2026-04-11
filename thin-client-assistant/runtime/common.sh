#!/usr/bin/env bash
set -euo pipefail

DEFAULT_CONFIG_DIR="/etc/pve-thin-client"
LIVE_STATE_DIR_DEFAULT="/run/live/medium/pve-thin-client/state"
LIVE_PRESET_FILE_DEFAULT="/run/live/medium/pve-thin-client/preset.env"
BEAGLE_STATE_DIR_DEFAULT="/var/lib/beagle-os"
PRESET_STATE_DIR_DEFAULT="/run/beagle-os/preset-state"
BEAGLE_TRACE_FILE_DEFAULT="$BEAGLE_STATE_DIR_DEFAULT/runtime-trace.log"
BEAGLE_LAST_MARKER_FILE_DEFAULT="$BEAGLE_STATE_DIR_DEFAULT/last-marker.env"
RUNTIME_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE_OVERRIDES_PY="${MODE_OVERRIDES_PY:-$RUNTIME_SCRIPT_DIR/mode_overrides.py}"
CONFIG_DISCOVERY_PY="${CONFIG_DISCOVERY_PY:-$RUNTIME_SCRIPT_DIR/config_discovery.py}"
CONFIG_LOADER_SH="${CONFIG_LOADER_SH:-$RUNTIME_SCRIPT_DIR/config_loader.sh}"
RUNTIME_CORE_SH="${RUNTIME_CORE_SH:-$RUNTIME_SCRIPT_DIR/runtime_core.sh}"
RUNTIME_VALUE_HELPERS_SH="${RUNTIME_VALUE_HELPERS_SH:-$RUNTIME_SCRIPT_DIR/runtime_value_helpers.sh}"
X11_DISPLAY_SH="${X11_DISPLAY_SH:-$RUNTIME_SCRIPT_DIR/x11_display.sh}"
STREAM_STATE_SH="${STREAM_STATE_SH:-$RUNTIME_SCRIPT_DIR/stream_state.sh}"
RUNTIME_OWNERSHIP_SH="${RUNTIME_OWNERSHIP_SH:-$RUNTIME_SCRIPT_DIR/runtime_ownership.sh}"
KIOSK_RUNTIME_SH="${KIOSK_RUNTIME_SH:-$RUNTIME_SCRIPT_DIR/kiosk_runtime.sh}"

# shellcheck disable=SC1090
source "$CONFIG_LOADER_SH"
# shellcheck disable=SC1090
source "$RUNTIME_CORE_SH"
# shellcheck disable=SC1090
source "$RUNTIME_VALUE_HELPERS_SH"
# shellcheck disable=SC1090
source "$X11_DISPLAY_SH"
# shellcheck disable=SC1090
source "$STREAM_STATE_SH"
# shellcheck disable=SC1090
source "$RUNTIME_OWNERSHIP_SH"
# shellcheck disable=SC1090
source "$KIOSK_RUNTIME_SH"

find_live_state_dir() {
  [[ -r "$CONFIG_DISCOVERY_PY" ]] || return 1
  python3 "$CONFIG_DISCOVERY_PY" find-live-state-dir \
    --live-state-dir "${LIVE_STATE_DIR:-}" \
    --live-state-dir-default "$LIVE_STATE_DIR_DEFAULT"
}

apply_runtime_mode_overrides() {
  local key value
  [[ -r "$MODE_OVERRIDES_PY" ]] || return 0

  while IFS=$'\t' read -r key value; do
    [[ "$key" =~ ^PVE_THIN_CLIENT_[A-Z0-9_]+$ ]] || continue
    printf -v "$key" '%s' "$value"
  done < <(
    python3 "$MODE_OVERRIDES_PY" \
      --current-mode "${PVE_THIN_CLIENT_MODE:-}" \
      --current-boot-profile "${PVE_THIN_CLIENT_BOOT_PROFILE:-}" \
      --current-client-mode "${PVE_THIN_CLIENT_CLIENT_MODE:-}"
  )
}

find_config_dir() {
  local installer_dir installer_script runtime_user preset_state_dir
  [[ -r "$CONFIG_DISCOVERY_PY" ]] || return 1
  installer_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../installer" && pwd)"
  installer_script="$installer_dir/write-config.sh"
  runtime_user="${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}"
  preset_state_dir="${PRESET_STATE_DIR:-$PRESET_STATE_DIR_DEFAULT}"

  python3 "$CONFIG_DISCOVERY_PY" find-config-dir \
    --config-dir "${CONFIG_DIR:-}" \
    --default-config-dir "$DEFAULT_CONFIG_DIR" \
    --live-state-dir "${LIVE_STATE_DIR:-}" \
    --live-state-dir-default "$LIVE_STATE_DIR_DEFAULT" \
    --preset-file "${PVE_THIN_CLIENT_PRESET_FILE:-}" \
    --live-preset-file-default "$LIVE_PRESET_FILE_DEFAULT" \
    --preset-state-dir "$preset_state_dir" \
    --runtime-user "$runtime_user" \
    --installer-script "$installer_script"
}
