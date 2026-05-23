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

beagle_launch_beagle_stream_client_session() {
  local launcher_status=127
  local relaunch_enabled="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RELAUNCH:-1}"
  local relaunch_delay="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RELAUNCH_DELAY_SECONDS:-3}"
  local relaunch_max_delay="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RELAUNCH_MAX_DELAY_SECONDS:-30}"
  local quick_exit_window="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_QUICK_EXIT_WINDOW_SECONDS:-45}"
  local quick_exit_limit="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_QUICK_EXIT_LIMIT:-6}"
  local quick_exit_count=0
  local launch_started_at=0
  local launch_ended_at=0
  local launch_runtime=0
  local sleep_for=0

  while true; do
    launch_started_at="$(date +%s)"
    if bash "$SCRIPT_DIR/launch-beagle-stream-client.sh"; then
      launcher_status=0
    else
      launcher_status=$?
    fi
    launch_ended_at="$(date +%s)"
    launch_runtime=$((launch_ended_at - launch_started_at))

    if [[ "$relaunch_enabled" != "1" ]]; then
      return "$launcher_status"
    fi
    if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_QUIT_AFTER:-0}" == "1" && "$launcher_status" -eq 0 ]]; then
      return 0
    fi

    sleep_for="$relaunch_delay"
    if [[ "$launcher_status" -eq 0 ]]; then
      if (( launch_runtime < quick_exit_window )); then
        quick_exit_count=$((quick_exit_count + 1))
        sleep_for=$((relaunch_delay * (quick_exit_count + 1)))
        if (( sleep_for > relaunch_max_delay )); then
          sleep_for="$relaunch_max_delay"
        fi
        beagle_log_event "launch-session.beagle-stream-client" "state=clean-exit relaunch=1 runtime=${launch_runtime}s quick_exits=${quick_exit_count} sleep=${sleep_for}s"
        if (( quick_exit_count >= quick_exit_limit )); then
          beagle_log_event "launch-session.beagle-stream-client" "state=clean-exit-loop status=0 runtime=${launch_runtime}s quick_exits=${quick_exit_count} action=abort-relaunch"
          return 75
        fi
      else
        quick_exit_count=0
        beagle_log_event "launch-session.beagle-stream-client" "state=clean-exit relaunch=1 runtime=${launch_runtime}s"
      fi
    else
      quick_exit_count=0
      beagle_log_event "launch-session.beagle-stream-client" "state=failed status=${launcher_status} relaunch=1 runtime=${launch_runtime}s"
    fi
    sleep "$sleep_for"
  done
}
