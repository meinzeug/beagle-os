#!/usr/bin/env bash

beagle_wait_for_stream_end() {
  while beagle_streaming_session_active; do
    sleep 1
  done
}

beagle_ensure_kiosk_runtime() {
  if command -v /usr/local/sbin/beagle-kiosk-install >/dev/null 2>&1; then
    /usr/local/sbin/beagle-kiosk-install --ensure >/dev/null 2>&1 || true
  fi
}

beagle_launch_kiosk_session() {
  local launcher_status=127
  local failure_count=0

  beagle_ensure_kiosk_runtime

  while true; do
    if beagle_streaming_session_active; then
      beagle_log_event "launch-session.kiosk" "state=waiting-for-stream-end"
      beagle_wait_for_stream_end
      beagle_log_event "launch-session.kiosk" "state=stream-ended relaunch=1"
    fi

    if /usr/local/sbin/beagle-kiosk-launch; then
      launcher_status=0
    else
      launcher_status=$?
    fi

    if beagle_streaming_session_active; then
      beagle_log_event "launch-session.kiosk" "state=closed-for-stream status=${launcher_status}"
      failure_count=0
      continue
    fi

    if [[ "$launcher_status" -eq 0 ]]; then
      beagle_log_event "launch-session.kiosk" "state=clean-exit relaunch=1"
      failure_count=0
      sleep 1
      continue
    fi

    failure_count=$((failure_count + 1))
    beagle_log_event "launch-session.kiosk" "state=failed status=${launcher_status} failures=${failure_count}"
    if (( failure_count >= 3 )); then
      return "$launcher_status"
    fi
    sleep 2
  done
}

beagle_launch_moonlight_session() {
  local launcher_status=127
  local relaunch_enabled="${PVE_THIN_CLIENT_MOONLIGHT_RELAUNCH:-1}"
  local relaunch_delay="${PVE_THIN_CLIENT_MOONLIGHT_RELAUNCH_DELAY_SECONDS:-3}"

  while true; do
    if "$SCRIPT_DIR/launch-moonlight.sh"; then
      launcher_status=0
    else
      launcher_status=$?
    fi

    if [[ "$relaunch_enabled" != "1" ]]; then
      return "$launcher_status"
    fi
    if [[ "${PVE_THIN_CLIENT_MOONLIGHT_QUIT_AFTER:-0}" == "1" && "$launcher_status" -eq 0 ]]; then
      return 0
    fi

    if [[ "$launcher_status" -eq 0 ]]; then
      beagle_log_event "launch-session.moonlight" "state=clean-exit relaunch=1"
    else
      beagle_log_event "launch-session.moonlight" "state=failed status=${launcher_status} relaunch=1"
    fi
    sleep "$relaunch_delay"
  done
}
