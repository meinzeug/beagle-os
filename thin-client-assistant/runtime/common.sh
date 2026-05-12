#!/usr/bin/env bash
set -euo pipefail

DEFAULT_CONFIG_DIR="/etc/pve-thin-client"
LIVE_STATE_DIR_DEFAULT="/run/live/medium/pve-thin-client/state"
LIVE_PRESET_FILE_DEFAULT="/run/live/medium/pve-thin-client/preset.env"
BEAGLE_STATE_DIR_DEFAULT="/var/lib/beagle-os"
PRESET_STATE_DIR_DEFAULT="/run/beagle-os/preset-state"
BEAGLE_TRACE_FILE_DEFAULT="$BEAGLE_STATE_DIR_DEFAULT/runtime-trace.log"
BEAGLE_LAST_MARKER_FILE_DEFAULT="$BEAGLE_STATE_DIR_DEFAULT/last-marker.env"

runtime_script_dir_candidates() {
  printf '%s\n' \
    "${RUNTIME_SCRIPT_DIR:-}" \
    "/run/pve-thin-client/runtime" \
    "/usr/local/lib/pve-thin-client/runtime"
}

runtime_resolve_source_dir() {
  local source_path source_dir

  source_path="${BASH_SOURCE[0]:-${0:-}}"
  if [[ -z "$source_path" ]]; then
    printf '%s\n' "/usr/local/lib/pve-thin-client/runtime"
    return 0
  fi

  case "$source_path" in
    */*) source_dir="${source_path%/*}" ;;
    *) source_dir="$PWD" ;;
  esac

  if [[ "$source_dir" != /* ]]; then
    source_dir="$(cd -- "$source_dir" 2>/dev/null && pwd -P)"
  else
    source_dir="$(cd -- "$source_dir" 2>/dev/null && pwd -P || printf '%s\n' "$source_dir")"
  fi

  printf '%s\n' "$source_dir"
}

runtime_first_readable_file() {
  local file_name candidate
  file_name="$1"

  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    if [[ "$candidate" == /var/local/* ]]; then
      candidate="/usr/local/${candidate#/var/local/}"
    fi
    candidate="${candidate%/}/$file_name"
    if [[ -r "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done < <(runtime_script_dir_candidates)

  return 1
}

runtime_resolve_helper_path() {
  local current_path file_name candidate
  current_path="${1:-}"
  file_name="$2"

  if [[ -n "$current_path" && -r "$current_path" ]]; then
    printf '%s\n' "$current_path"
    return 0
  fi

  candidate="$(runtime_first_readable_file "$file_name" 2>/dev/null || true)"
  if [[ -n "$candidate" ]]; then
    printf '%s\n' "$candidate"
    return 0
  fi

  if [[ -n "$current_path" ]]; then
    printf '%s\n' "$current_path"
    return 0
  fi

  printf '%s\n' "$RUNTIME_SCRIPT_DIR/$file_name"
}

RUNTIME_SCRIPT_DIR="${RUNTIME_SCRIPT_DIR:-$(runtime_resolve_source_dir)}"
if [[ "$RUNTIME_SCRIPT_DIR" == /var/local/* ]]; then
  RUNTIME_SCRIPT_DIR="/usr/local/${RUNTIME_SCRIPT_DIR#/var/local/}"
fi
if [[ ! -r "$RUNTIME_SCRIPT_DIR/config_loader.sh" ]]; then
  RUNTIME_SCRIPT_DIR="$(runtime_first_readable_file config_loader.sh 2>/dev/null || printf '%s\n' "$RUNTIME_SCRIPT_DIR/config_loader.sh")"
  RUNTIME_SCRIPT_DIR="${RUNTIME_SCRIPT_DIR%/config_loader.sh}"
fi
export RUNTIME_SCRIPT_DIR
MODE_OVERRIDES_PY="$(runtime_resolve_helper_path "${MODE_OVERRIDES_PY:-}" mode_overrides.py)"
CONFIG_DISCOVERY_PY="$(runtime_resolve_helper_path "${CONFIG_DISCOVERY_PY:-}" config_discovery.py)"
CONFIG_LOADER_SH="$(runtime_resolve_helper_path "${CONFIG_LOADER_SH:-}" config_loader.sh)"
RUNTIME_CORE_SH="$(runtime_resolve_helper_path "${RUNTIME_CORE_SH:-}" runtime_core.sh)"
RUNTIME_VALUE_HELPERS_SH="$(runtime_resolve_helper_path "${RUNTIME_VALUE_HELPERS_SH:-}" runtime_value_helpers.sh)"
X11_DISPLAY_SH="$(runtime_resolve_helper_path "${X11_DISPLAY_SH:-}" x11_display.sh)"
STREAM_STATE_SH="$(runtime_resolve_helper_path "${STREAM_STATE_SH:-}" stream_state.sh)"
RUNTIME_OWNERSHIP_SH="$(runtime_resolve_helper_path "${RUNTIME_OWNERSHIP_SH:-}" runtime_ownership.sh)"
KIOSK_RUNTIME_SH="$(runtime_resolve_helper_path "${KIOSK_RUNTIME_SH:-}" kiosk_runtime.sh)"

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
  installer_dir="${RUNTIME_SCRIPT_DIR:-/usr/local/lib/pve-thin-client/runtime}/../installer"
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
