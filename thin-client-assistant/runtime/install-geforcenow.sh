#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEFORCENOW_DESKTOP_INTEGRATION_SH="${GEFORCENOW_DESKTOP_INTEGRATION_SH:-$SCRIPT_DIR/geforcenow_desktop_integration.sh}"
GEFORCENOW_FLATPAK_SH="${GEFORCENOW_FLATPAK_SH:-$SCRIPT_DIR/geforcenow_flatpak.sh}"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
# shellcheck disable=SC1090
source "$GEFORCENOW_DESKTOP_INTEGRATION_SH"
# shellcheck disable=SC1090
source "$GEFORCENOW_FLATPAK_SH"

load_runtime_config >/dev/null 2>&1 || true

GFN_APP_ID="${PVE_THIN_CLIENT_GFN_APP_ID:-com.nvidia.geforcenow}"
GFN_REMOTE_NAME="${PVE_THIN_CLIENT_GFN_REMOTE_NAME:-GeForceNOW}"
GFN_REMOTE_URL="${PVE_THIN_CLIENT_GFN_REMOTE_URL:-https://international.download.nvidia.com/GFNLinux/flatpak/geforcenow.flatpakrepo}"
FLATHUB_REMOTE_NAME="${PVE_THIN_CLIENT_GFN_FLATHUB_REMOTE_NAME:-flathub}"
FLATHUB_REMOTE_URL="${PVE_THIN_CLIENT_GFN_FLATHUB_REMOTE_URL:-https://dl.flathub.org/repo/flathub.flatpakrepo}"
GFN_RUNTIME_REF="${PVE_THIN_CLIENT_GFN_RUNTIME_REF:-org.freedesktop.Platform//24.08}"
GFN_INSTALL_SCOPE="${PVE_THIN_CLIENT_GFN_INSTALL_SCOPE:---user}"
GFN_DRY_RUN="${PVE_THIN_CLIENT_GFN_DRY_RUN:-0}"
GFN_HOST_HOME="${PVE_THIN_CLIENT_GFN_HOST_HOME:-$(runtime_user_home)}"
GFN_RUNTIME_HOME="${PVE_THIN_CLIENT_GFN_RUNTIME_HOME:-$GFN_HOST_HOME}"

usage() {
  cat <<'EOF'
Usage: install-geforcenow.sh [--ensure-only] [--dry-run]
EOF
}

ACTION="--ensure-only"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ensure-only)
      ACTION="$1"
      shift
      ;;
    --dry-run)
      GFN_DRY_RUN="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unsupported argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

GFN_INSTALL_SCOPE="$(resolve_gfn_install_scope)"
ensure_gfn_install_scope_permissions

if ! prepare_geforcenow_environment "$GFN_RUNTIME_HOME"; then
  echo "Unable to prepare persistent GeForce NOW storage." >&2
  exit 1
fi

beagle_log_event "gfn.install.start" "scope=${GFN_INSTALL_SCOPE} app_id=${GFN_APP_ID} dry_run=${GFN_DRY_RUN} storage=${PVE_THIN_CLIENT_GFN_STORAGE_ROOT:-unknown}"
ensure_gfn_flatpak_installation
ensure_gfn_desktop_integration
beagle_log_event "gfn.install.ready" "scope=${GFN_INSTALL_SCOPE} app_id=${GFN_APP_ID} storage=${PVE_THIN_CLIENT_GFN_STORAGE_ROOT:-unknown}"

case "$ACTION" in
  --ensure-only)
    exit 0
    ;;
esac
