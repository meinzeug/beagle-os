#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEAGLE_USB_RUNTIME_STATE_SH="${BEAGLE_USB_RUNTIME_STATE_SH:-$SCRIPT_DIR/beagle_usb_runtime_state.sh}"
BEAGLE_USB_RUNTIME_ACTIONS_SH="${BEAGLE_USB_RUNTIME_ACTIONS_SH:-$SCRIPT_DIR/beagle_usb_runtime_actions.sh}"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
# shellcheck disable=SC1090
source "$BEAGLE_USB_RUNTIME_STATE_SH"
# shellcheck disable=SC1090
source "$BEAGLE_USB_RUNTIME_ACTIONS_SH"

load_runtime_config >/dev/null 2>&1 || true

case "${1:-}" in
  daemon)
    run_usb_tunnel_daemon
    ;;
  list-json)
    usb_list_json
    ;;
  status-json)
    usb_status_json
    ;;
  bind)
    [[ -n "${2:-}" ]] || { echo 'missing busid' >&2; exit 1; }
    bind_usb_device "$2"
    ;;
  unbind)
    [[ -n "${2:-}" ]] || { echo 'missing busid' >&2; exit 1; }
    unbind_usb_device "$2"
    ;;
  *)
    echo "usage: $0 {daemon|list-json|status-json|bind BUSID|unbind BUSID}" >&2
    exit 1
    ;;
esac
