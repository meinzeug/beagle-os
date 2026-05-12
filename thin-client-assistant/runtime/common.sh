#!/usr/bin/env bash
set -euo pipefail

DEFAULT_CONFIG_DIR="/etc/pve-thin-client"
LIVE_STATE_DIR_DEFAULT="/run/live/medium/pve-thin-client/state"
LIVE_PRESET_FILE_DEFAULT="/run/live/medium/pve-thin-client/preset.env"
BEAGLE_STATE_DIR_DEFAULT="/var/lib/beagle-os"
PRESET_STATE_DIR_DEFAULT="/run/beagle-os/preset-state"
BEAGLE_TRACE_FILE_DEFAULT="$BEAGLE_STATE_DIR_DEFAULT/runtime-trace.log"
BEAGLE_LAST_MARKER_FILE_DEFAULT="$BEAGLE_STATE_DIR_DEFAULT/last-marker.env"
RUNTIME_TMPFS_DIR_DEFAULT="/run/pve-thin-client/runtime"
RUNTIME_COMMON_SOURCE="${BASH_SOURCE[0]:-$0}"
RUNTIME_COMMON_DIR="${RUNTIME_COMMON_SOURCE%/*}"
if [[ "$RUNTIME_COMMON_DIR" == "$RUNTIME_COMMON_SOURCE" ]]; then
  RUNTIME_COMMON_DIR="."
fi

runtime_normalize_script_dir() {
  local script_dir="${1:-/usr/local/lib/pve-thin-client/runtime}"
  if [[ "$script_dir" == /var/local/* ]]; then
    printf '/usr/local/%s\n' "${script_dir#/var/local/}"
  else
    printf '%s\n' "$script_dir"
  fi
}

runtime_first_readable_file() {
  local candidate
  for candidate in "$@"; do
    [[ -r "$candidate" ]] || continue
    printf '%s\n' "$candidate"
    return 0
  done
  return 1
}

runtime_resolve_source_dir() {
  local configured="${BEAGLE_RUNTIME_SCRIPT_DIR:-${RUNTIME_SCRIPT_DIR:-}}"
  [[ -n "$configured" ]] || configured="$RUNTIME_COMMON_DIR"
  runtime_normalize_script_dir "${configured:-/usr/local/lib/pve-thin-client/runtime}"
}

runtime_stage_dir_to_tmpfs() {
  local source_dir="${1:-}"
  local target_dir="${2:-$RUNTIME_TMPFS_DIR_DEFAULT}"

  [[ -n "$source_dir" && -d "$source_dir" ]] || return 1
  [[ "$source_dir" != "$target_dir" ]] || return 0
  [[ "${BEAGLE_RUNTIME_TMPFS_STAGE:-1}" == "1" ]] || return 1

  mkdir -p "$target_dir" 2>/dev/null || return 1
  if [[ -r "$target_dir/common.sh" && -r "$target_dir/runtime_value_helpers.sh" ]]; then
    return 0
  fi
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$source_dir/" "$target_dir/" >/dev/null 2>&1 || return 1
  else
    cp -a "$source_dir/." "$target_dir/" >/dev/null 2>&1 || return 1
  fi
  [[ -r "$target_dir/common.sh" ]]
}

runtime_resolve_helper_path() {
  local helper_name="$1"
  runtime_first_readable_file \
    "${RUNTIME_SCRIPT_DIR:-$RUNTIME_TMPFS_DIR_DEFAULT}/$helper_name" \
    "$(runtime_resolve_source_dir)/$helper_name"
}

# Debian 13 Trixie live-boot overlayfs fix: hardcode install path and reject
# /var/local/ paths which indicate the overlayfs lower-layer path resolution bug
# where bash's `pwd` after `cd` or realpath through overlay returns /var/local/
# instead of /usr/local/.  RUNTIME_SCRIPT_DIR may still be overridden via env
# for development, but /var/local/ overrides are silently corrected.
if [[ "${RUNTIME_SCRIPT_DIR:-}" == /var/local/* ]]; then
  RUNTIME_SCRIPT_DIR="/usr/local/${RUNTIME_SCRIPT_DIR#/var/local/}"
fi
RUNTIME_SOURCE_SCRIPT_DIR="$(runtime_resolve_source_dir)"
RUNTIME_SCRIPT_DIR="${RUNTIME_SCRIPT_DIR:-$RUNTIME_SOURCE_SCRIPT_DIR}"
RUNTIME_SCRIPT_DIR="$(runtime_normalize_script_dir "$RUNTIME_SCRIPT_DIR")"
if runtime_stage_dir_to_tmpfs "$RUNTIME_SOURCE_SCRIPT_DIR" "${RUNTIME_TMPFS_DIR:-$RUNTIME_TMPFS_DIR_DEFAULT}"; then
  RUNTIME_SCRIPT_DIR="${RUNTIME_TMPFS_DIR:-$RUNTIME_TMPFS_DIR_DEFAULT}"
fi
SCRIPT_DIR="$RUNTIME_SCRIPT_DIR"
export RUNTIME_SCRIPT_DIR
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
if ! source "$RUNTIME_VALUE_HELPERS_SH"; then
  render_template() {
    printf '%s\n' "${1:-}"
  }

  beagle_curl_tls_args() {
    local _url="${1:-}"
    local _pinned="${2:-}"
    local _ca_cert="${3:-}"

    [[ "$_url" == https://* ]] || return 0
    if [[ -n "$_pinned" ]]; then
      printf '%s\n' "-k" "--pinnedpubkey" "$_pinned"
    elif [[ -n "$_ca_cert" && -f "$_ca_cert" ]]; then
      printf '%s\n' "--cacert" "$_ca_cert"
    else
      printf '%s\n' "-k"
    fi
  }
fi
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
