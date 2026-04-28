#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_SH="${COMMON_SH:-$SCRIPT_DIR/common.sh}"
DEVICE_STATE_ENFORCEMENT_SH="${DEVICE_STATE_ENFORCEMENT_SH:-$SCRIPT_DIR/device_state_enforcement.sh}"

if [[ -r "$COMMON_SH" ]]; then
  # shellcheck disable=SC1090
  source "$COMMON_SH"
fi
if [[ -r "$DEVICE_STATE_ENFORCEMENT_SH" ]]; then
  # shellcheck disable=SC1090
  source "$DEVICE_STATE_ENFORCEMENT_SH"
fi

lock_screen_marker_file_path() {
  printf '%s\n' "${BEAGLE_LOCK_SCREEN_MARKER_FILE:-$(beagle_state_dir)/device-lock-screen.marker}"
}

lock_screen_pid_file_path() {
  printf '%s\n' "${BEAGLE_LOCK_SCREEN_PID_FILE:-$(beagle_state_dir)/device-lock-screen.pid}"
}

lock_screen_poll_interval() {
  printf '%s\n' "${BEAGLE_LOCK_SCREEN_POLL_INTERVAL:-2}"
}

lock_screen_title() {
  printf '%s\n' "${BEAGLE_LOCK_SCREEN_TITLE:-Beagle OS Device Locked}"
}

lock_screen_text() {
  cat <<'EOF'
Dieses Endpoint-Geraet wurde zentral gesperrt.

Die lokale Session bleibt blockiert, bis die Sperre im Beagle Manager aufgehoben wurde.
EOF
}

lock_screen_kill_active_clients() {
  pkill -f '/usr/local/lib/pve-thin-client/runtime/launch-moonlight.sh' >/dev/null 2>&1 || true
  pkill -f '/usr/local/sbin/beagle-kiosk-launch' >/dev/null 2>&1 || true
  pkill -f 'flatpak run com.nvidia.geforcenow' >/dev/null 2>&1 || true
  pkill -f '/usr/local/bin/start-pve-thin-client-kiosk-session' >/dev/null 2>&1 || true
}

lock_screen_write_marker() {
  local state
  state="${1:-active}"
  mkdir -p "$(dirname "$(lock_screen_marker_file_path)")" >/dev/null 2>&1 || true
  printf '%s\n' "$state" >"$(lock_screen_marker_file_path)"
}

lock_screen_clear_marker() {
  rm -f "$(lock_screen_marker_file_path)" >/dev/null 2>&1 || true
}

lock_screen_fullscreen_existing_window() {
  local title="${1:-}"
  command -v wmctrl >/dev/null 2>&1 || return 0
  [[ -n "$title" ]] || return 0
  wmctrl -r "$title" -b add,fullscreen,above >/dev/null 2>&1 || true
}

lock_screen_spawn_ui() {
  local title pid_file
  title="$(lock_screen_title)"
  pid_file="$(lock_screen_pid_file_path)"
  mkdir -p "$(dirname "$pid_file")" >/dev/null 2>&1 || true

  if [[ "${BEAGLE_LOCK_SCREEN_SIMULATE:-0}" == "1" ]]; then
    lock_screen_write_marker "active"
    printf '%s\n' "$$" >"$pid_file"
    return 0
  fi

  if command -v zenity >/dev/null 2>&1; then
    (
      export DISPLAY="${DISPLAY:-:0}"
      export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u 2>/dev/null || echo 1000)}"
      while device_lock_active; do
        zenity --info \
          --title="$title" \
          --width=960 \
          --height=420 \
          --no-wrap \
          --text="$(lock_screen_text)" >/dev/null 2>&1 || true
        sleep 1
      done
    ) &
    printf '%s\n' "$!" >"$pid_file"
    sleep 1
    lock_screen_fullscreen_existing_window "$title"
    return 0
  fi

  if command -v xterm >/dev/null 2>&1; then
    (
      export DISPLAY="${DISPLAY:-:0}"
      while device_lock_active; do
        xterm -geometry 120x26+0+0 -T "$title" -fa Monospace -fs 13 -fg white -bg black -e /bin/sh -lc "printf '%s\n' \"$(lock_screen_text)\"; while sleep 3600; do :; done" >/dev/null 2>&1 || true
        sleep 1
      done
    ) &
    printf '%s\n' "$!" >"$pid_file"
    sleep 1
    lock_screen_fullscreen_existing_window "$title"
    return 0
  fi

  lock_screen_write_marker "active"
  printf '%s\n' "$$" >"$pid_file"
}

lock_screen_stop_ui() {
  local pid_file pid
  pid_file="$(lock_screen_pid_file_path)"

  if [[ "${BEAGLE_LOCK_SCREEN_SIMULATE:-0}" == "1" ]]; then
    lock_screen_clear_marker
    rm -f "$pid_file" >/dev/null 2>&1 || true
    return 0
  fi

  if [[ -f "$pid_file" ]]; then
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$pid" ]]; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
    rm -f "$pid_file" >/dev/null 2>&1 || true
  fi
  lock_screen_clear_marker
}

device_lock_screen_watcher_running() {
  local pid_file pid
  pid_file="$(lock_screen_pid_file_path)"
  [[ -f "$pid_file" ]] || return 1
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" >/dev/null 2>&1
}

run_device_lock_screen_watcher() {
  local interval
  interval="$(lock_screen_poll_interval)"

  while :; do
    if device_lock_active; then
      lock_screen_kill_active_clients
      if ! device_lock_screen_watcher_running; then
        beagle_log_event "device.lock_screen.show" "device_id=$(runtime_device_id)"
        lock_screen_spawn_ui
      fi
    else
      if device_lock_screen_watcher_running || [[ -f "$(lock_screen_marker_file_path)" ]]; then
        beagle_log_event "device.lock_screen.hide" "device_id=$(runtime_device_id)"
      fi
      lock_screen_stop_ui
    fi

    if [[ "${BEAGLE_LOCK_SCREEN_ONCE:-0}" == "1" ]]; then
      break
    fi
    sleep "$interval"
  done
}
