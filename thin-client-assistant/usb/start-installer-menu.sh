#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="${PVE_THIN_CLIENT_USB_SCRIPT_DIR:-/usr/local/lib/pve-thin-client/usb}"
PROJECT_DIR="$SCRIPT_DIR/pve-dcv-integration"
MENU_SCRIPT="$PROJECT_DIR/thin-client-assistant/usb/pve-thin-client-live-menu.sh"

if [[ ! -x "$MENU_SCRIPT" ]]; then
  echo "Installer menu script not found: $MENU_SCRIPT" >&2
  exit 1
fi

exec "$MENU_SCRIPT" "$@"
