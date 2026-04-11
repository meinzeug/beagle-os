#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATUS_WRITER_PY="$SCRIPT_DIR/status_writer.py"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
STATUS_DIR="${PVE_THIN_CLIENT_STATUS_DIR:-${XDG_RUNTIME_DIR:-/tmp}/pve-thin-client}"
LAUNCH_STATUS_FILE="$STATUS_DIR/launch.status.json"

load_runtime_config
beagle_log_event "launch-session.start" "mode=${PVE_THIN_CLIENT_MODE:-MOONLIGHT} profile=${PVE_THIN_CLIENT_PROFILE_NAME:-default}"

if [[ "${PVE_THIN_CLIENT_AUTOSTART:-1}" != "1" ]]; then
  exit 0
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
  local host app
  host="$(render_template "${PVE_THIN_CLIENT_MOONLIGHT_HOST:-}")"
  app="$(render_template "${PVE_THIN_CLIENT_MOONLIGHT_APP:-Desktop}")"
  write_launch_status "MOONLIGHT" "sunshine" "${PVE_THIN_CLIENT_MOONLIGHT_BIN:-moonlight}" "${host}:${app}"
  beagle_log_event "launch-session.exec" "binary=${PVE_THIN_CLIENT_MOONLIGHT_BIN:-moonlight} target=${host}:${app}"
  exec "$SCRIPT_DIR/launch-moonlight.sh"
}

launch_kiosk() {
  local launcher_status=127
  local failure_count=0

  write_launch_status "KIOSK" "beagle-kiosk" "/usr/local/sbin/beagle-kiosk-launch" "Beagle OS Gaming"
  beagle_log_event "launch-session.exec" "binary=/usr/local/sbin/beagle-kiosk-launch target=Beagle-OS-Gaming"
  if command -v /usr/local/sbin/beagle-kiosk-install >/dev/null 2>&1; then
    /usr/local/sbin/beagle-kiosk-install --ensure >/dev/null 2>&1 || true
  fi

  while true; do
    if beagle_streaming_session_active; then
      beagle_log_event "launch-session.kiosk" "state=waiting-for-stream-end"
      while beagle_streaming_session_active; do
        sleep 1
      done
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
