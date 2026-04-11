#!/usr/bin/env bash

beagle_kiosk_runtime_patterns() {
  cat <<'EOF'
/opt/beagle-kiosk/launch.sh
/opt/beagle-kiosk/beagle-kiosk
appimage_extracted_.*/beagle-kiosk
--app-path=.*beagle-kiosk
EOF
}

beagle_kiosk_runtime_running() {
  local runtime_user pattern

  runtime_user="$(runtime_user_name)"
  while IFS= read -r pattern; do
    [[ -n "$pattern" ]] || continue
    if pgrep -u "$runtime_user" -f "$pattern" >/dev/null 2>&1; then
      return 0
    fi
  done < <(beagle_kiosk_runtime_patterns)

  return 1
}

beagle_close_kiosk_window_for_stream() {
  local title timeout_cycles

  title="${PVE_THIN_CLIENT_GFN_KIOSK_WINDOW_TITLE:-Beagle OS Gaming}"
  timeout_cycles="${PVE_THIN_CLIENT_GFN_KIOSK_WINDOW_CLOSE_WAIT_CYCLES:-40}"

  command -v wmctrl >/dev/null 2>&1 || return 1
  DISPLAY="${DISPLAY:-:0}" wmctrl -c "$title" >/dev/null 2>&1 || return 1

  while (( timeout_cycles > 0 )); do
    if ! beagle_kiosk_runtime_running; then
      return 0
    fi
    sleep 0.25
    timeout_cycles=$((timeout_cycles - 1))
  done

  return 1
}

beagle_stop_kiosk_for_stream() {
  local runtime_user pattern wait_cycles

  runtime_user="$(runtime_user_name)"
  wait_cycles="${PVE_THIN_CLIENT_GFN_KIOSK_STOP_WAIT_CYCLES:-40}"

  beagle_log_event "streaming.kiosk-stop" "mode=requested user=${runtime_user}"

  if beagle_close_kiosk_window_for_stream; then
    beagle_log_event "streaming.kiosk-stop" "mode=graceful-close"
    return 0
  fi

  beagle_log_event "streaming.kiosk-stop" "mode=fallback-hardkill"

  while IFS= read -r pattern; do
    [[ -n "$pattern" ]] || continue
    pkill -TERM -u "$runtime_user" -f "$pattern" >/dev/null 2>&1 || true
  done < <(beagle_kiosk_runtime_patterns)

  while (( wait_cycles > 0 )); do
    if ! beagle_kiosk_runtime_running; then
      beagle_log_event "streaming.kiosk-stop" "mode=complete"
      return 0
    fi
    sleep 0.25
    wait_cycles=$((wait_cycles - 1))
  done

  while IFS= read -r pattern; do
    [[ -n "$pattern" ]] || continue
    pkill -KILL -u "$runtime_user" -f "$pattern" >/dev/null 2>&1 || true
  done < <(beagle_kiosk_runtime_patterns)

  beagle_log_event "streaming.kiosk-stop" "mode=forced"
}
