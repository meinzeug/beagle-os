#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_runtime_config
beagle_log_event "gfn.start" "profile=${PVE_THIN_CLIENT_PROFILE_NAME:-default}"

GFN_APP_ID="${PVE_THIN_CLIENT_GFN_APP_ID:-com.nvidia.geforcenow}"
GFN_INSTALL_SCOPE="${PVE_THIN_CLIENT_GFN_INSTALL_SCOPE:---user}"
HOME="${HOME:-/home/${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}}"
DISPLAY="${DISPLAY:-:0}"
XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export HOME DISPLAY XDG_RUNTIME_DIR
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
export XDG_SESSION_TYPE="${XDG_SESSION_TYPE:-x11}"
unset WAYLAND_DISPLAY

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

"$SCRIPT_DIR/install-geforcenow.sh" --ensure-only

scope_flag="$(flatpak_scope_flag)"
beagle_log_event "gfn.exec" "scope=${scope_flag} app_id=${GFN_APP_ID}"

if command -v dbus-run-session >/dev/null 2>&1 && [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]]; then
  exec dbus-run-session -- flatpak run "$scope_flag" "$GFN_APP_ID"
fi

exec flatpak run "$scope_flag" "$GFN_APP_ID"
