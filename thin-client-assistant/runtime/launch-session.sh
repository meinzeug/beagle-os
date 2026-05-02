#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATUS_WRITER_PY="$SCRIPT_DIR/status_writer.py"
SESSION_LAUNCHER_SH="${SESSION_LAUNCHER_SH:-$SCRIPT_DIR/session_launcher.sh}"
DEVICE_STATE_ENFORCEMENT_SH="${DEVICE_STATE_ENFORCEMENT_SH:-$SCRIPT_DIR/device_state_enforcement.sh}"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
# shellcheck disable=SC1090
source "$SESSION_LAUNCHER_SH"
if [[ -r "$DEVICE_STATE_ENFORCEMENT_SH" ]]; then
  # shellcheck disable=SC1090
  source "$DEVICE_STATE_ENFORCEMENT_SH"
fi
STATUS_DIR="${PVE_THIN_CLIENT_STATUS_DIR:-${XDG_RUNTIME_DIR:-/tmp}/pve-thin-client}"
LAUNCH_STATUS_FILE="$STATUS_DIR/launch.status.json"

load_runtime_config
beagle_log_event "launch-session.start" "mode=${PVE_THIN_CLIENT_MODE:-MOONLIGHT} profile=${PVE_THIN_CLIENT_PROFILE_NAME:-default}"

if [[ "${PVE_THIN_CLIENT_AUTOSTART:-1}" != "1" ]]; then
  exit 0
fi

if declare -F enforce_device_state_before_session >/dev/null 2>&1; then
  enforce_device_state_before_session || status=$?
  if [[ "${status:-0}" == "10" ]]; then
    exit 0
  fi
  if [[ "${status:-0}" != "0" ]]; then
    exit "${status}"
  fi
fi

write_launch_status() {
  local mode="$1"
  local method="$2"
  local binary="$3"
  local target="$4"

  mkdir -p "$STATUS_DIR" 2>/dev/null || return 0

  python3 "$STATUS_WRITER_PY" launch-status \
    --path "$LAUNCH_STATUS_FILE" \
    --mode "$mode" \
    --method "$method" \
    --binary "$binary" \
    --target "$target" \
    --profile-name "${PVE_THIN_CLIENT_PROFILE_NAME:-default}" \
    --runtime-user "${PVE_THIN_CLIENT_RUNTIME_USER:-}" || true
}

launch_moonlight() {
  local host app binary target
  host="$(render_template "${PVE_THIN_CLIENT_MOONLIGHT_HOST:-}")"
  app="$(render_template "${PVE_THIN_CLIENT_MOONLIGHT_APP:-Desktop}")"
  binary="${PVE_THIN_CLIENT_MOONLIGHT_BIN:-moonlight}"
  target="${host}:${app}"
  if [[ -z "$host" && -r /etc/beagle/enrollment.conf ]]; then
    binary="${PVE_THIN_CLIENT_MOONLIGHT_BIN:-beagle-stream}"
    target="broker:${app}"
  fi
  write_launch_status "MOONLIGHT" "sunshine" "$binary" "$target"
  beagle_log_event "launch-session.exec" "binary=${binary} target=${target}"
  beagle_launch_moonlight_session
}

launch_kiosk() {
  write_launch_status "KIOSK" "beagle-kiosk" "/usr/local/sbin/beagle-kiosk-launch" "Beagle OS Gaming"
  beagle_log_event "launch-session.exec" "binary=/usr/local/sbin/beagle-kiosk-launch target=Beagle-OS-Gaming"
  beagle_launch_kiosk_session
}

launch_geforcenow() {
  write_launch_status "GFN" "geforcenow" "flatpak run com.nvidia.geforcenow" "GeForce NOW"
  beagle_log_event "launch-session.exec" "binary=flatpak target=com.nvidia.geforcenow"
  exec "$SCRIPT_DIR/launch-geforcenow.sh"
}

case "${PVE_THIN_CLIENT_MODE:-MOONLIGHT}" in
  MOONLIGHT)
    launch_moonlight
    ;;
  KIOSK)
    launch_kiosk
    ;;
  GFN)
    launch_geforcenow
    ;;
  *)
    echo "Unsupported mode for Beagle OS: ${PVE_THIN_CLIENT_MODE:-UNSET}" >&2
    exit 1
    ;;
esac
