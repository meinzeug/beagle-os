#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
STATUS_DIR="${PVE_THIN_CLIENT_STATUS_DIR:-/var/lib/pve-thin-client}"
LAUNCH_STATUS_FILE="$STATUS_DIR/launch.status.json"

load_runtime_config

if [[ "${PVE_THIN_CLIENT_AUTOSTART:-1}" != "1" ]]; then
  exit 0
fi

have_binary() {
  command -v "$1" >/dev/null 2>&1
}

write_launch_status() {
  local mode="$1"
  local method="$2"
  local binary="$3"
  local target="$4"

  mkdir -p "$STATUS_DIR"
  chmod 0755 "$STATUS_DIR"

  python3 - "$LAUNCH_STATUS_FILE" "$mode" "$method" "$binary" "$target" "${PVE_THIN_CLIENT_PROFILE_NAME:-default}" "${PVE_THIN_CLIENT_RUNTIME_USER:-}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
mode = sys.argv[2]
method = sys.argv[3]
binary = sys.argv[4]
target = sys.argv[5]
profile = sys.argv[6]
runtime_user = sys.argv[7]

payload = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "mode": mode,
    "launch_method": method,
    "binary": binary,
    "target": target,
    "profile_name": profile,
    "runtime_user": runtime_user,
}
path.write_text(json.dumps(payload, indent=2) + "\n")
PY
}

launch_spice() {
  local url
  url="$(render_template "${PVE_THIN_CLIENT_SPICE_URL:-}")"

  if [[ "${PVE_THIN_CLIENT_CONNECTION_METHOD:-direct}" == "proxmox-ticket" ]]; then
    write_launch_status "SPICE" "proxmox-ticket" "$SCRIPT_DIR/connect-proxmox-spice.sh" "${PVE_THIN_CLIENT_PROXMOX_HOST:-}"
    exec "$SCRIPT_DIR/connect-proxmox-spice.sh"
  fi

  write_launch_status "SPICE" "direct" "${PVE_THIN_CLIENT_REMOTE_VIEWER_BIN:-remote-viewer}" "$url"
  exec "${PVE_THIN_CLIENT_REMOTE_VIEWER_BIN:-remote-viewer}" "$url"
}

launch_novnc() {
  local url
  url="$(render_template "${PVE_THIN_CLIENT_NOVNC_URL:-}")"
  BROWSER_FLAG_ARRAY=()
  split_browser_flags

  write_launch_status "NOVNC" "browser" "${PVE_THIN_CLIENT_BROWSER_BIN}" "$url"
  exec "${PVE_THIN_CLIENT_BROWSER_BIN}" \
    "${BROWSER_FLAG_ARRAY[@]}" \
    "$url"
}

launch_dcv() {
  local connection_file viewer url
  viewer="${PVE_THIN_CLIENT_DCV_VIEWER_BIN:-dcvviewer}"
  url="$(render_template "${PVE_THIN_CLIENT_DCV_URL:-}")"

  if have_binary "$viewer"; then
    connection_file="$("$SCRIPT_DIR/build-dcv-connection-file.sh")"
    write_launch_status "DCV" "native-viewer" "$viewer" "$connection_file"
    exec "$viewer" "$connection_file"
  fi

  if [[ "$url" =~ ^https?:// ]] && have_binary "${PVE_THIN_CLIENT_BROWSER_BIN:-chromium}"; then
    BROWSER_FLAG_ARRAY=()
    split_browser_flags
    write_launch_status "DCV" "browser-fallback" "${PVE_THIN_CLIENT_BROWSER_BIN:-chromium}" "$url"
    exec "${PVE_THIN_CLIENT_BROWSER_BIN:-chromium}" \
      "${BROWSER_FLAG_ARRAY[@]}" \
      "$url"
  fi

  echo "DCV launch failed: '$viewer' is unavailable and no browser fallback can open '$url'." >&2
  exit 1
}

case "${PVE_THIN_CLIENT_MODE:-}" in
  SPICE) launch_spice ;;
  NOVNC) launch_novnc ;;
  DCV) launch_dcv ;;
  *)
    echo "Unsupported mode: ${PVE_THIN_CLIENT_MODE:-UNSET}" >&2
    exit 1
    ;;
esac
