#!/usr/bin/env bash
set -euo pipefail

url="${1:-}"
[[ -n "$url" ]] || exit 1

runtime_user="${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}"
runtime_uid="$(id -u "$runtime_user" 2>/dev/null || id -u)"
runtime_home="$(getent passwd "$runtime_user" 2>/dev/null | awk -F: '{print $6}' | head -n 1)"

export HOME="${HOME:-${runtime_home:-/home/$runtime_user}}"
export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/${runtime_uid}}"
if [[ -S "${XDG_RUNTIME_DIR}/bus" ]]; then
  export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=${XDG_RUNTIME_DIR}/bus}"
fi

unset CHROME_DESKTOP
unset BROWSER

log_dir="${HOME}/.cache/beagle-os"
log_file="${log_dir}/browser-launch.log"
mkdir -p "$log_dir" >/dev/null 2>&1 || true
printf '[%s] browser url=%s display=%s xdg_runtime_dir=%s dbus=%s\n' \
  "$(date -Iseconds 2>/dev/null || date)" \
  "$url" \
  "${DISPLAY:-}" \
  "${XDG_RUNTIME_DIR:-}" \
  "${DBUS_SESSION_BUS_ADDRESS:-}" >>"$log_file" 2>/dev/null || true

exec /usr/bin/chromium --new-window "$url"
