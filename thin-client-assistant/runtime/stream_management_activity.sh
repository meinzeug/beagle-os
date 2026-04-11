#!/usr/bin/env bash

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
