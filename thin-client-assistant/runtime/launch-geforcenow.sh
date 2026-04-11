#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEFORCENOW_FLATPAK_SH="${GEFORCENOW_FLATPAK_SH:-$SCRIPT_DIR/geforcenow_flatpak.sh}"
GEFORCENOW_STREAM_OPTIMIZATION_SH="${GEFORCENOW_STREAM_OPTIMIZATION_SH:-$SCRIPT_DIR/geforcenow_stream_optimization.sh}"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
# shellcheck disable=SC1090
source "$GEFORCENOW_FLATPAK_SH"
# shellcheck disable=SC1090
source "$GEFORCENOW_STREAM_OPTIMIZATION_SH"

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

XAUTHORITY="$(select_xauthority)"
export XAUTHORITY
wait_for_x_display_selected "$XAUTHORITY"

prepare_geforcenow_environment "$RUNTIME_HOME"
export DISPLAY XDG_RUNTIME_DIR XAUTHORITY
export PATH="${HOST_HOME}/.local/bin:${PATH}"
beagle_log_event "gfn.storage.ready" "storage=${PVE_THIN_CLIENT_GFN_STORAGE_ROOT:-unknown}"
launch_target="${1:-}"
log_gfn_launch_target "$launch_target"

if command -v /usr/local/bin/pve-thin-client-audio-init >/dev/null 2>&1; then
  /usr/local/bin/pve-thin-client-audio-init >/dev/null 2>&1 || true
  pkill -f '^bash /usr/local/bin/pve-thin-client-audio-init --watch' >/dev/null 2>&1 || true
  /usr/local/bin/pve-thin-client-audio-init --watch "${PVE_THIN_CLIENT_AUDIO_WATCH_LOOPS:-0}" >/dev/null 2>&1 &
fi

"$SCRIPT_DIR/install-geforcenow.sh" --ensure-only

scope_flag="$(resolve_gfn_install_scope)"
beagle_log_event "gfn.exec" "scope=${scope_flag} app_id=${GFN_APP_ID}"
start_gfn_stream_optimization "$launch_target"
trap stop_gfn_stream_optimization EXIT INT TERM

if command -v dbus-run-session >/dev/null 2>&1 && [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]]; then
  dbus-run-session -- flatpak run "$scope_flag" "$GFN_APP_ID" "$@"
  exit $?
fi

flatpak run "$scope_flag" "$GFN_APP_ID" "$@"
