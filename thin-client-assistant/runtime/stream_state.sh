#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STREAM_MANAGEMENT_ACTIVITY_SH="${STREAM_MANAGEMENT_ACTIVITY_SH:-$SCRIPT_DIR/stream_management_activity.sh}"
# shellcheck disable=SC1090
source "$STREAM_MANAGEMENT_ACTIVITY_SH"

beagle_stream_state_dir() {
  local uid candidate

  uid="$(runtime_user_uid)"
  for candidate in \
    "${XDG_RUNTIME_DIR:-}" \
    "/run/user/$uid" \
    "$(beagle_state_dir)"
  do
    [[ -n "$candidate" ]] || continue
    case "$candidate" in
      /run/user/*)
        printf '%s/beagle-os\n' "$candidate"
        ;;
      *)
        printf '%s\n' "$candidate"
        ;;
    esac
    return 0
  done
}

beagle_stream_session_file() {
  printf '%s/streaming-session.env\n' "$(beagle_stream_state_dir)"
}

beagle_stream_suspended_units_file() {
  printf '%s/streaming-suspended-units.list\n' "$(beagle_stream_state_dir)"
}

beagle_stream_suspended_pids_file() {
  printf '%s/streaming-suspended-pids.list\n' "$(beagle_stream_state_dir)"
}

ensure_beagle_stream_state_dir() {
  local dir
  dir="$(beagle_stream_state_dir)"
  [[ -n "$dir" ]] || return 1
  mkdir -p "$dir" >/dev/null 2>&1 || return 1
}

beagle_streaming_session_active() {
  local state_file

  state_file="$(beagle_stream_session_file)"
  if [[ -r "$state_file" ]] && grep -Eq '^active=1$' "$state_file"; then
    return 0
  fi

  pgrep -x GeForceNOW >/dev/null 2>&1 && return 0
  pgrep -f '/app/bin/GeForceNOW' >/dev/null 2>&1 && return 0
  return 1
}

beagle_mark_streaming_session() {
  local active="${1:-0}"
  local reason="${2:-}"
  local state_file temp_file timestamp

  ensure_beagle_stream_state_dir || return 0
  state_file="$(beagle_stream_session_file)"
  temp_file="${state_file}.$$"
  timestamp="$(date -Iseconds 2>/dev/null || date)"

  {
    printf 'active=%s\n' "$active"
    printf 'timestamp=%q\n' "$timestamp"
    printf 'reason=%q\n' "$reason"
    printf 'user=%q\n' "$(runtime_user_name)"
    printf 'pid=%q\n' "$$"
  } >"$temp_file" 2>/dev/null || return 0

  mv -f "$temp_file" "$state_file" >/dev/null 2>&1 || true
}
