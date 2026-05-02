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

lock_screen_runtime_info_file_path() {
  printf '%s\n' "${BEAGLE_LOCK_SCREEN_RUNTIME_INFO_FILE:-$(beagle_state_dir)/device-lock-screen.env}"
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

lock_screen_session_type() {
  printf '%s\n' "${XDG_SESSION_TYPE:-x11}"
}

lock_screen_display() {
  printf '%s\n' "${DISPLAY:-:0}"
}

lock_screen_x11_displays() {
  local configured primary
  configured="${BEAGLE_LOCK_SCREEN_X11_DISPLAYS:-}"
  if [[ -n "$configured" ]]; then
    printf '%s\n' "$configured" | tr ',' '\n' | awk 'NF {print $0}'
    return 0
  fi
  primary="$(lock_screen_display)"
  printf '%s\n' "$primary"
}

lock_screen_runtime_dir() {
  printf '%s\n' "${XDG_RUNTIME_DIR:-/run/user/$(id -u 2>/dev/null || echo 1000)}"
}

lock_screen_wayland_backend() {
  if command -v swaylock >/dev/null 2>&1; then
    printf '%s\n' "swaylock"
    return 0
  fi
  if command -v gtklock >/dev/null 2>&1; then
    printf '%s\n' "gtklock"
    return 0
  fi
  if command -v waylock >/dev/null 2>&1; then
    printf '%s\n' "waylock"
    return 0
  fi
  return 1
}

lock_screen_x11_backend() {
  if command -v zenity >/dev/null 2>&1; then
    printf '%s\n' "zenity"
    return 0
  fi
  if command -v yad >/dev/null 2>&1; then
    printf '%s\n' "yad"
    return 0
  fi
  if command -v xmessage >/dev/null 2>&1; then
    printf '%s\n' "xmessage"
    return 0
  fi
  if command -v xterm >/dev/null 2>&1; then
    printf '%s\n' "xterm"
    return 0
  fi
  return 1
}

lock_screen_backend() {
  if [[ "${BEAGLE_LOCK_SCREEN_SIMULATE:-0}" == "1" ]]; then
    printf '%s\n' "simulate"
    return 0
  fi
  case "$(lock_screen_session_type)" in
    wayland)
      if lock_screen_wayland_backend >/dev/null 2>&1; then
        printf '%s\n' "wayland"
        return 0
      fi
      ;;
    x11|*)
      if lock_screen_x11_backend >/dev/null 2>&1; then
        printf '%s\n' "x11"
        return 0
      fi
      ;;
  esac
  printf '%s\n' "headless"
}

lock_screen_kill_active_clients() {
  pkill -f '/usr/local/lib/pve-thin-client/runtime/launch-beagle-stream-client.sh' >/dev/null 2>&1 || true
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

lock_screen_write_runtime_info() {
  local backend="${1:-}" session_type="${2:-}" displays="${3:-}"
  local info_file
  info_file="$(lock_screen_runtime_info_file_path)"
  mkdir -p "$(dirname "$info_file")" >/dev/null 2>&1 || true
  {
    printf 'BEAGLE_LOCK_SCREEN_RUNTIME_BACKEND=%q\n' "$backend"
    printf 'BEAGLE_LOCK_SCREEN_RUNTIME_SESSION_TYPE=%q\n' "$session_type"
    printf 'BEAGLE_LOCK_SCREEN_RUNTIME_DISPLAYS=%q\n' "$displays"
  } >"$info_file"
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
  local title pid_file backend wayland_backend x11_backend displays
  title="$(lock_screen_title)"
  pid_file="$(lock_screen_pid_file_path)"
  backend="$(lock_screen_backend)"
  displays="$(lock_screen_x11_displays | paste -sd, -)"
  mkdir -p "$(dirname "$pid_file")" >/dev/null 2>&1 || true
  lock_screen_write_runtime_info "$backend" "$(lock_screen_session_type)" "$displays"

  if [[ "$backend" == "simulate" ]]; then
    lock_screen_write_marker "active"
    printf '%s\n' "$$" >"$pid_file"
    return 0
  fi

  if [[ "$backend" == "wayland" ]]; then
    wayland_backend="$(lock_screen_wayland_backend || true)"
    (
      export XDG_RUNTIME_DIR="$(lock_screen_runtime_dir)"
      while device_lock_active; do
        case "$wayland_backend" in
          swaylock)
            swaylock -f -c 111111 -s fill >/dev/null 2>&1 || true
            ;;
          gtklock)
            gtklock >/dev/null 2>&1 || true
            ;;
          waylock)
            waylock >/dev/null 2>&1 || true
            ;;
        esac
        sleep 1
      done
    ) &
    printf '%s\n' "$!" >"$pid_file"
    return 0
  fi

  if [[ "$backend" == "x11" ]]; then
    x11_backend="$(lock_screen_x11_backend || true)"
    (
      export XDG_RUNTIME_DIR="$(lock_screen_runtime_dir)"
      while device_lock_active; do
        while IFS= read -r display_value; do
          [[ -n "$display_value" ]] || continue
          export DISPLAY="$display_value"
          case "$x11_backend" in
            zenity)
              zenity --info --title="$title" --width=960 --height=420 --no-wrap --text="$(lock_screen_text)" >/dev/null 2>&1 || true
              ;;
            yad)
              yad --info --title="$title" --text="$(lock_screen_text)" --width=960 --height=420 --center >/dev/null 2>&1 || true
              ;;
            xmessage)
              xmessage -center -title "$title" "$(lock_screen_text)" >/dev/null 2>&1 || true
              ;;
            xterm)
              xterm -geometry 120x26+0+0 -T "$title" -fa Monospace -fs 13 -fg white -bg black -e /bin/sh -lc "printf '%s\n' \"$(lock_screen_text)\"; while sleep 3600; do :; done" >/dev/null 2>&1 || true
              ;;
          esac
        done < <(lock_screen_x11_displays)
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
    rm -f "$(lock_screen_runtime_info_file_path)" >/dev/null 2>&1 || true
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
  rm -f "$(lock_screen_runtime_info_file_path)" >/dev/null 2>&1 || true
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
