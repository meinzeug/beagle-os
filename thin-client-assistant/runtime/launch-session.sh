#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_runtime_config

if [[ "${PVE_THIN_CLIENT_AUTOSTART:-1}" != "1" ]]; then
  exit 0
fi

launch_spice() {
  local url
  url="$(render_template "${PVE_THIN_CLIENT_SPICE_URL:-}")"

  if [[ "${PVE_THIN_CLIENT_CONNECTION_METHOD:-direct}" == "proxmox-ticket" ]]; then
    exec "$SCRIPT_DIR/connect-proxmox-spice.sh"
  fi

  exec "${PVE_THIN_CLIENT_REMOTE_VIEWER_BIN:-remote-viewer}" "$url"
}

launch_novnc() {
  local url
  url="$(render_template "${PVE_THIN_CLIENT_NOVNC_URL:-}")"
  BROWSER_FLAG_ARRAY=()
  split_browser_flags

  exec "${PVE_THIN_CLIENT_BROWSER_BIN}" \
    "${BROWSER_FLAG_ARRAY[@]}" \
    "$url"
}

launch_dcv() {
  local connection_file
  connection_file="$("$SCRIPT_DIR/build-dcv-connection-file.sh")"
  exec "${PVE_THIN_CLIENT_DCV_VIEWER_BIN:-dcvviewer}" "$connection_file"
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
