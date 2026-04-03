#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_runtime_config >/dev/null 2>&1 || true

GFN_APP_ID="${PVE_THIN_CLIENT_GFN_APP_ID:-com.nvidia.geforcenow}"
GFN_REMOTE_NAME="${PVE_THIN_CLIENT_GFN_REMOTE_NAME:-GeForceNOW}"
GFN_REMOTE_URL="${PVE_THIN_CLIENT_GFN_REMOTE_URL:-https://international.download.nvidia.com/GFNLinux/flatpak/geforcenow.flatpakrepo}"
FLATHUB_REMOTE_NAME="${PVE_THIN_CLIENT_GFN_FLATHUB_REMOTE_NAME:-flathub}"
FLATHUB_REMOTE_URL="${PVE_THIN_CLIENT_GFN_FLATHUB_REMOTE_URL:-https://dl.flathub.org/repo/flathub.flatpakrepo}"
GFN_RUNTIME_REF="${PVE_THIN_CLIENT_GFN_RUNTIME_REF:-org.freedesktop.Platform//24.08}"
GFN_INSTALL_SCOPE="${PVE_THIN_CLIENT_GFN_INSTALL_SCOPE:---user}"
GFN_DRY_RUN="${PVE_THIN_CLIENT_GFN_DRY_RUN:-0}"

usage() {
  cat <<'EOF'
Usage: install-geforcenow.sh [--ensure-only] [--dry-run]
EOF
}

scope_flag() {
  case "${GFN_INSTALL_SCOPE}" in
    user|--user|"")
      printf '%s\n' "--user"
      ;;
    system|--system)
      printf '%s\n' "--system"
      ;;
    *)
      echo "Unsupported GeForce NOW install scope: ${GFN_INSTALL_SCOPE}" >&2
      exit 1
      ;;
  esac
}

run_cmd() {
  if [[ "$GFN_DRY_RUN" == "1" ]]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi

  "$@"
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

GFN_INSTALL_SCOPE="$(scope_flag)"
if [[ "$GFN_INSTALL_SCOPE" == "--system" && "$(id -u)" != "0" ]]; then
  echo "System-wide GeForce NOW installation requires root." >&2
  exit 1
fi

if ! command -v flatpak >/dev/null 2>&1; then
  if [[ "$GFN_DRY_RUN" == "1" ]]; then
    echo "# flatpak is not installed on this machine; continuing because this is a dry-run"
  else
    echo "flatpak is not installed in this Beagle OS image." >&2
    exit 1
  fi
fi

GFN_RUNTIME_HOME="${HOME:-/home/$(runtime_user_name)}"
if ! prepare_geforcenow_environment "$GFN_RUNTIME_HOME"; then
  echo "Unable to prepare persistent GeForce NOW storage." >&2
  exit 1
fi

beagle_log_event "gfn.install.start" "scope=${GFN_INSTALL_SCOPE} app_id=${GFN_APP_ID} dry_run=${GFN_DRY_RUN} storage=${PVE_THIN_CLIENT_GFN_STORAGE_ROOT:-unknown}"
run_cmd flatpak remote-add "$GFN_INSTALL_SCOPE" --if-not-exists "$FLATHUB_REMOTE_NAME" "$FLATHUB_REMOTE_URL"
run_cmd flatpak install -y "$GFN_INSTALL_SCOPE" "$FLATHUB_REMOTE_NAME" "$GFN_RUNTIME_REF"
run_cmd flatpak remote-add "$GFN_INSTALL_SCOPE" --if-not-exists "$GFN_REMOTE_NAME" "$GFN_REMOTE_URL"
run_cmd flatpak install -y "$GFN_INSTALL_SCOPE" "$GFN_REMOTE_NAME" "$GFN_APP_ID"
beagle_log_event "gfn.install.ready" "scope=${GFN_INSTALL_SCOPE} app_id=${GFN_APP_ID} storage=${PVE_THIN_CLIENT_GFN_STORAGE_ROOT:-unknown}"

case "$ACTION" in
  --ensure-only)
    exit 0
    ;;
esac
