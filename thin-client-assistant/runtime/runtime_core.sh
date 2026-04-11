#!/usr/bin/env bash

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
