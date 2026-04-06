#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_runtime_config
beagle_log_event "gfn.start" "profile=${PVE_THIN_CLIENT_PROFILE_NAME:-default}"

GFN_APP_ID="${PVE_THIN_CLIENT_GFN_APP_ID:-com.nvidia.geforcenow}"
GFN_INSTALL_SCOPE="${PVE_THIN_CLIENT_GFN_INSTALL_SCOPE:---user}"
HOST_HOME="${PVE_THIN_CLIENT_GFN_HOST_HOME:-$(runtime_user_home)}"
RUNTIME_HOME="${PVE_THIN_CLIENT_GFN_RUNTIME_HOME:-$HOST_HOME}"
HOME="$RUNTIME_HOME"
DISPLAY="${DISPLAY:-:0}"
XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export HOME DISPLAY XDG_RUNTIME_DIR
export PVE_THIN_CLIENT_GFN_HOST_HOME="$HOST_HOME"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
export XDG_SESSION_TYPE="${XDG_SESSION_TYPE:-x11}"
export BROWSER="/usr/local/lib/pve-thin-client/runtime/open-browser-url.sh %s"
unset WAYLAND_DISPLAY
unset CHROME_DESKTOP

GFN_STREAM_OPTIMIZE="${PVE_THIN_CLIENT_GFN_STREAM_OPTIMIZE:-1}"
GFN_STREAM_PAUSE_DELAY_SECONDS="${PVE_THIN_CLIENT_GFN_KIOSK_SUSPEND_DELAY_SECONDS:-12}"
STREAM_KIOSK_STOP_PID=""
STREAM_OPTIMIZATION_ACTIVE="0"

log_launch_target() {
  local target="${1:-}"
  [[ -n "$target" ]] || return 0
  case "$target" in
    geforcenow:*|com.nvidia.geforcenow:*|nvidia-gfn:*|http://localhost:2259*)
      beagle_log_event "gfn.callback" "target=${target%%\?*}"
      ;;
  esac
}

is_gfn_callback_target() {
  local target="${1:-}"
  case "$target" in
    geforcenow:*|com.nvidia.geforcenow:*|nvidia-gfn:*|http://localhost:2259*)
      return 0
      ;;
  esac
  return 1
}

stream_stop_kiosk_after_delay() {
  local delay_seconds="${1:-0}"

  if [[ "$delay_seconds" =~ ^[0-9]+$ ]] && (( delay_seconds > 0 )); then
    sleep "$delay_seconds"
  fi

  beagle_stop_kiosk_for_stream || true
}

start_stream_optimization() {
  local target="${1:-}"

  [[ "$GFN_STREAM_OPTIMIZE" == "1" ]] || return 0
  is_gfn_callback_target "$target" && return 0

  beagle_suspend_management_activity || true
  stream_stop_kiosk_after_delay "$GFN_STREAM_PAUSE_DELAY_SECONDS" >/dev/null 2>&1 &
  STREAM_KIOSK_STOP_PID="$!"
  STREAM_OPTIMIZATION_ACTIVE="1"
  beagle_log_event "gfn.stream-optimization" "mode=active kiosk-stop-delay=${GFN_STREAM_PAUSE_DELAY_SECONDS}"
}

stop_stream_optimization() {
  [[ "$STREAM_OPTIMIZATION_ACTIVE" == "1" ]] || return 0

  if [[ -n "$STREAM_KIOSK_STOP_PID" ]]; then
    kill "$STREAM_KIOSK_STOP_PID" >/dev/null 2>&1 || true
    wait "$STREAM_KIOSK_STOP_PID" 2>/dev/null || true
    STREAM_KIOSK_STOP_PID=""
  fi

  beagle_resume_management_activity || true
  STREAM_OPTIMIZATION_ACTIVE="0"
  beagle_log_event "gfn.stream-optimization" "mode=inactive"
}

select_xauthority() {
  local candidate

  for candidate in \
    "${XAUTHORITY:-}" \
    "$HOME/.Xauthority" \
    "/home/${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}/.Xauthority"
  do
    [[ -n "$candidate" && -r "$candidate" ]] || continue
    printf '%s\n' "$candidate"
    return 0
  done

  candidate="$(find /tmp -maxdepth 1 -type f -name 'serverauth.*' 2>/dev/null | head -n 1 || true)"
  if [[ -n "$candidate" ]]; then
    printf '%s\n' "$candidate"
    return 0
  fi

  printf '%s\n' "$HOME/.Xauthority"
}

wait_for_x_display() {
  local attempts attempt auth_candidate

  attempts="${PVE_THIN_CLIENT_X11_READY_RETRIES:-20}"
  auth_candidate="$1"

  if ! command -v xset >/dev/null 2>&1; then
    return 0
  fi

  for attempt in $(seq 1 "$attempts"); do
    if DISPLAY="$DISPLAY" XAUTHORITY="$auth_candidate" xset q >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  return 1
}

flatpak_scope_flag() {
  case "${GFN_INSTALL_SCOPE}" in
    user|--user|"")
      printf '%s\n' "--user"
      ;;
    system|--system)
      printf '%s\n' "--system"
      ;;
    *)
      echo "Unsupported GeForce NOW install scope: ${GFN_INSTALL_SCOPE}" >&2
      exit 1
      ;;
  esac
}

XAUTHORITY="$(select_xauthority)"
export XAUTHORITY
wait_for_x_display "$XAUTHORITY"

prepare_geforcenow_environment "$RUNTIME_HOME"
export DISPLAY XDG_RUNTIME_DIR XAUTHORITY
export PATH="${HOST_HOME}/.local/bin:${PATH}"
beagle_log_event "gfn.storage.ready" "storage=${PVE_THIN_CLIENT_GFN_STORAGE_ROOT:-unknown}"
launch_target="${1:-}"
log_launch_target "$launch_target"

if command -v /usr/local/bin/pve-thin-client-audio-init >/dev/null 2>&1; then
  /usr/local/bin/pve-thin-client-audio-init >/dev/null 2>&1 || true
  pkill -f '^bash /usr/local/bin/pve-thin-client-audio-init --watch' >/dev/null 2>&1 || true
  /usr/local/bin/pve-thin-client-audio-init --watch "${PVE_THIN_CLIENT_AUDIO_WATCH_LOOPS:-0}" >/dev/null 2>&1 &
fi

"$SCRIPT_DIR/install-geforcenow.sh" --ensure-only

scope_flag="$(flatpak_scope_flag)"
beagle_log_event "gfn.exec" "scope=${scope_flag} app_id=${GFN_APP_ID}"
start_stream_optimization "$launch_target"
trap stop_stream_optimization EXIT INT TERM

if command -v dbus-run-session >/dev/null 2>&1 && [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]]; then
  dbus-run-session -- flatpak run "$scope_flag" "$GFN_APP_ID" "$@"
  exit $?
fi

flatpak run "$scope_flag" "$GFN_APP_ID" "$@"
