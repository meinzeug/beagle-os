#!/usr/bin/env bash
set -euo pipefail

STATUS_DIR="${STATUS_DIR:-/var/lib/pve-thin-client}"
STATUS_FILE="$STATUS_DIR/runtime.status"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_runtime_config

if [[ -x "$SCRIPT_DIR/apply-network-config.sh" ]]; then
  "$SCRIPT_DIR/apply-network-config.sh"
fi

mkdir -p "$STATUS_DIR"
chmod 0755 "$STATUS_DIR"

required_binary=""
case "${PVE_THIN_CLIENT_MODE:-}" in
  SPICE) required_binary="${PVE_THIN_CLIENT_REMOTE_VIEWER_BIN:-remote-viewer}" ;;
  NOVNC) required_binary="${PVE_THIN_CLIENT_BROWSER_BIN:-chromium}" ;;
  DCV) required_binary="${PVE_THIN_CLIENT_DCV_VIEWER_BIN:-dcvviewer}" ;;
  *)
    echo "Unsupported mode: ${PVE_THIN_CLIENT_MODE:-UNSET}" >&2
    exit 1
    ;;
esac

{
  echo "timestamp=$(date -Iseconds)"
  echo "mode=${PVE_THIN_CLIENT_MODE:-UNSET}"
  echo "runtime_user=${PVE_THIN_CLIENT_RUNTIME_USER:-UNSET}"
  echo "connection_method=${PVE_THIN_CLIENT_CONNECTION_METHOD:-UNSET}"
  echo "profile_name=${PVE_THIN_CLIENT_PROFILE_NAME:-UNSET}"
  echo "required_binary=$required_binary"
  if command -v "$required_binary" >/dev/null 2>&1; then
    echo "binary_available=1"
  else
    echo "binary_available=0"
  fi
} > "$STATUS_FILE"

chmod 0644 "$STATUS_FILE"
