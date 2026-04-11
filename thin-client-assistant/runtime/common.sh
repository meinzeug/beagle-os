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
STREAM_STATE_SH="${STREAM_STATE_SH:-$RUNTIME_SCRIPT_DIR/stream_state.sh}"
RUNTIME_OWNERSHIP_SH="${RUNTIME_OWNERSHIP_SH:-$RUNTIME_SCRIPT_DIR/runtime_ownership.sh}"
KIOSK_RUNTIME_SH="${KIOSK_RUNTIME_SH:-$RUNTIME_SCRIPT_DIR/kiosk_runtime.sh}"

# shellcheck disable=SC1090
source "$CONFIG_LOADER_SH"
# shellcheck disable=SC1090
source "$STREAM_STATE_SH"
# shellcheck disable=SC1090
source "$RUNTIME_OWNERSHIP_SH"
# shellcheck disable=SC1090
source "$KIOSK_RUNTIME_SH"

beagle_state_dir() {
  printf '%s\n' "${BEAGLE_STATE_DIR:-$BEAGLE_STATE_DIR_DEFAULT}"
}

beagle_trace_file() {
  local state_dir
  state_dir="$(beagle_state_dir)"
  printf '%s\n' "${BEAGLE_TRACE_FILE:-$state_dir/runtime-trace.log}"
}

beagle_last_marker_file() {
  local state_dir
  state_dir="$(beagle_state_dir)"
  printf '%s\n' "${BEAGLE_LAST_MARKER_FILE:-$state_dir/last-marker.env}"
}

runtime_user_uid() {
  local user uid_entry

  user="$(runtime_user_name)"
  uid_entry="$(id -u "$user" 2>/dev/null || true)"
  if [[ -n "$uid_entry" ]]; then
    printf '%s\n' "$uid_entry"
    return 0
  fi

  printf '%s\n' "1000"
}

ensure_beagle_state_dir() {
  local state_dir candidate
  state_dir="$(beagle_state_dir)"

  for candidate in \
    "$state_dir" \
    "/run/beagle-os" \
    "${XDG_RUNTIME_DIR:-/run/user/$(id -u 2>/dev/null || echo 1000)}/beagle-os" \
    "/tmp/beagle-os"
  do
    [[ -n "$candidate" ]] || continue
    if mkdir -p "$candidate" >/dev/null 2>&1 && touch "$candidate/.write-test" >/dev/null 2>&1; then
      rm -f "$candidate/.write-test" >/dev/null 2>&1 || true
      export BEAGLE_STATE_DIR="$candidate"
      return 0
    fi
  done
}

beagle_log_event() {
  local phase="${1:-event}"
  shift || true
  local message="${*:-}"
  local timestamp trace_file marker_file

  timestamp="$(date -Iseconds 2>/dev/null || date)"
  ensure_beagle_state_dir
  trace_file="$(beagle_trace_file)"
  marker_file="$(beagle_last_marker_file)"

  printf '[%s] phase=%s %s\n' "$timestamp" "$phase" "$message" >>"$trace_file" 2>/dev/null || true
  {
    printf 'timestamp=%q\n' "$timestamp"
    printf 'phase=%q\n' "$phase"
    printf 'message=%q\n' "$message"
  } >"$marker_file" 2>/dev/null || true

  if command -v logger >/dev/null 2>&1; then
    logger -t beagle-runtime "phase=$phase $message" >/dev/null 2>&1 || true
  fi
}

beagle_run_privileged() {
  if [[ "$(id -u)" == "0" ]]; then
    "$@"
    return $?
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo -n "$@"
    return $?
  fi

  return 1
}

beagle_unit_file_present() {
  local unit="${1:-}"
  [[ -n "$unit" ]] || return 1
  systemctl list-unit-files --full --no-legend "$unit" 2>/dev/null | awk '{print $1}' | grep -Fxq "$unit"
}

beagle_curl_tls_args() {
  local url="${1:-}"
  local pinned_pubkey="${2:-}"
  local ca_cert="${3:-}"
  local -a args=()

  if [[ "$url" == https://* ]]; then
    if [[ -n "$ca_cert" && -r "$ca_cert" ]]; then
      args+=(--cacert "$ca_cert")
      if [[ -n "$pinned_pubkey" ]]; then
        args+=(--pinnedpubkey "$pinned_pubkey")
      fi
    elif [[ -n "$pinned_pubkey" ]]; then
      args+=(-k --pinnedpubkey "$pinned_pubkey")
    fi
  fi

  printf '%s\n' "${args[@]}"
}

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

runtime_user_name() {
  printf '%s\n' "${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}"
}

runtime_group_name() {
  printf '%s\n' "${PVE_THIN_CLIENT_RUNTIME_GROUP:-$(runtime_user_name)}"
}

runtime_user_home() {
  local user home_entry

  user="$(runtime_user_name)"
  home_entry="$(getent passwd "$user" 2>/dev/null | awk -F: '{print $6}' | head -n 1 || true)"
  if [[ -n "$home_entry" ]]; then
    printf '%s\n' "$home_entry"
    return 0
  fi

  printf '/home/%s\n' "$user"
}

live_medium_dir() {
  local medium="${PVE_THIN_CLIENT_LIVE_MEDIUM_DIR:-/run/live/medium}"

  if [[ -d "$medium" ]]; then
    printf '%s\n' "$medium"
    return 0
  fi

  return 1
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

render_template() {
  local template="$1"
  local output="$template"

  output="${output//\{mode\}/${PVE_THIN_CLIENT_MODE:-}}"
  output="${output//\{username\}/${PVE_THIN_CLIENT_CONNECTION_USERNAME:-}}"
  output="${output//\{password\}/${PVE_THIN_CLIENT_CONNECTION_PASSWORD:-}}"
  output="${output//\{token\}/${PVE_THIN_CLIENT_CONNECTION_TOKEN:-}}"
  output="${output//\{host\}/${PVE_THIN_CLIENT_PROXMOX_HOST:-}}"
  output="${output//\{node\}/${PVE_THIN_CLIENT_PROXMOX_NODE:-}}"
  output="${output//\{vmid\}/${PVE_THIN_CLIENT_PROXMOX_VMID:-}}"
  output="${output//\{moonlight_host\}/${PVE_THIN_CLIENT_MOONLIGHT_HOST:-}}"
  output="${output//\{moonlight_local_host\}/${PVE_THIN_CLIENT_MOONLIGHT_LOCAL_HOST:-}}"
  output="${output//\{moonlight_port\}/${PVE_THIN_CLIENT_MOONLIGHT_PORT:-}}"
  output="${output//\{sunshine_api_url\}/${PVE_THIN_CLIENT_SUNSHINE_API_URL:-}}"

  printf '%s\n' "$output"
}

split_browser_flags() {
  local flags="${PVE_THIN_CLIENT_BROWSER_FLAGS:-}"
  if [[ -z "$flags" ]]; then
    return 0
  fi

  # shellcheck disable=SC2206
  BROWSER_FLAG_ARRAY=($flags)
}
