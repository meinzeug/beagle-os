#!/usr/bin/env bash

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

beagle_management_timer_units() {
  cat <<'EOF'
beagle-endpoint-report.timer
beagle-endpoint-dispatch.timer
beagle-runtime-heartbeat.timer
beagle-healthcheck.timer
beagle-update-scan.timer
beagle-kiosk-update-catalog.timer
EOF
}

beagle_management_service_units() {
  cat <<'EOF'
beagle-endpoint-report.service
beagle-endpoint-dispatch.service
beagle-runtime-heartbeat.service
beagle-healthcheck.service
beagle-update-scan.service
beagle-kiosk-update-catalog.service
EOF
}

beagle_suspend_management_activity() {
  local units_file unit active_state

  ensure_beagle_stream_state_dir || return 0
  units_file="$(beagle_stream_suspended_units_file)"
  : >"$units_file" 2>/dev/null || true
  beagle_mark_streaming_session 1 "gfn-stream"

  while IFS= read -r unit; do
    [[ -n "$unit" ]] || continue
    beagle_unit_file_present "$unit" || continue
    active_state="$(systemctl is-active "$unit" 2>/dev/null || true)"
    case "$active_state" in
      active|activating)
        printf '%s\n' "$unit" >>"$units_file" 2>/dev/null || true
        beagle_run_privileged systemctl stop --no-block "$unit" >/dev/null 2>&1 || true
        ;;
    esac
  done < <(beagle_management_timer_units)

  while IFS= read -r unit; do
    [[ -n "$unit" ]] || continue
    beagle_unit_file_present "$unit" || continue
    active_state="$(systemctl is-active "$unit" 2>/dev/null || true)"
    case "$active_state" in
      active|activating)
        beagle_run_privileged systemctl stop --no-block "$unit" >/dev/null 2>&1 || true
        ;;
    esac
  done < <(beagle_management_service_units)

  if [[ -f "$units_file" ]]; then
    sort -u -o "$units_file" "$units_file" >/dev/null 2>&1 || true
  fi
  beagle_log_event "streaming.management-suspended" "timers_stopped=1"
}

beagle_resume_management_activity() {
  local units_file unit

  units_file="$(beagle_stream_suspended_units_file)"
  if [[ -r "$units_file" ]]; then
    while IFS= read -r unit; do
      [[ -n "$unit" ]] || continue
      beagle_unit_file_present "$unit" || continue
      beagle_run_privileged systemctl start --no-block "$unit" >/dev/null 2>&1 || true
    done <"$units_file"
    rm -f "$units_file" >/dev/null 2>&1 || true
  fi

  beagle_mark_streaming_session 0 "gfn-stream-ended"
  beagle_log_event "streaming.management-resumed" "timers_started=1"
}
