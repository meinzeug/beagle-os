#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_SCRIPT="$ROOT_DIR/scripts/install-beagle-host.sh"
CHECK_SCRIPT="$ROOT_DIR/scripts/check-beagle-host.sh"

usage() {
  cat <<'EOF'
Usage: setup-beagle-host.sh

Installs Beagle OS host services on the current machine and runs a post-install health check.

Environment variables:
  INSTALL_DIR                     Target install directory on the Beagle host.
  PVE_DCV_PROXY_SERVER_NAME       Public Beagle host name.
  PVE_DCV_PROXY_LISTEN_PORT       HTTPS port for Beagle API/downloads.
  BEAGLE_SITE_PORT                HTTPS port for the Beagle Web UI.
  BEAGLE_WEB_UI_URL               Public Beagle Web UI URL.
  BEAGLE_HOST_PROVIDER            Active host provider kind. Defaults to `proxmox`.
  PVE_DCV_DOWNLOADS_PATH          Hosted download path.
EOF
}

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
esac

"$INSTALL_SCRIPT" "$@"
"$CHECK_SCRIPT"
