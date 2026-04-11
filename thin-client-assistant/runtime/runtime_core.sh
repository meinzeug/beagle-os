#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_BEAGLE_STATE_SH="${RUNTIME_BEAGLE_STATE_SH:-$SCRIPT_DIR/runtime_beagle_state.sh}"
# shellcheck disable=SC1090
source "$RUNTIME_BEAGLE_STATE_SH"

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

live_medium_dir() {
  local medium="${PVE_THIN_CLIENT_LIVE_MEDIUM_DIR:-/run/live/medium}"

  if [[ -d "$medium" ]]; then
    printf '%s\n' "$medium"
    return 0
  fi

  return 1
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
  local systemctl_bin="${BEAGLE_SYSTEMCTL_BIN:-systemctl}"
  [[ -n "$unit" ]] || return 1
  "$systemctl_bin" list-unit-files --full --no-legend "$unit" 2>/dev/null | awk '{print $1}' | grep -Fxq "$unit"
}
