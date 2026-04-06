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
GFN_HOST_HOME="${PVE_THIN_CLIENT_GFN_HOST_HOME:-$(runtime_user_home)}"
GFN_RUNTIME_HOME="${PVE_THIN_CLIENT_GFN_RUNTIME_HOME:-$GFN_HOST_HOME}"

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

flatpak_is_installed() {
  local ref="$1"

  flatpak info "$GFN_INSTALL_SCOPE" "$ref" >/dev/null 2>&1
}

install_url_handler() {
  local apps_dir desktop_file mimeapps_file

  apps_dir="${GFN_HOST_HOME}/.local/share/applications"
  mimeapps_file="${GFN_HOST_HOME}/.config/mimeapps.list"
  desktop_file="${apps_dir}/com.nvidia.geforcenow.desktop"

  ensure_runtime_owned_dir "$apps_dir" 0755
  ensure_runtime_owned_dir "${GFN_HOST_HOME}/.config" 0700
  ensure_runtime_owned_file "$desktop_file" 0644
  ensure_runtime_owned_file "$mimeapps_file" 0644

  cat >"$desktop_file" <<'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=NVIDIA GeForce NOW
GenericName=NVIDIA GeForce NOW
Exec=/usr/local/lib/pve-thin-client/runtime/launch-geforcenow.sh %u
Icon=com.nvidia.geforcenow
Categories=Network;Game;
NoDisplay=true
MimeType=x-scheme-handler/geforcenow;x-scheme-handler/com.nvidia.geforcenow;x-scheme-handler/nvidia-gfn;
EOF

  update-desktop-database "$apps_dir" >/dev/null 2>&1 || true
  HOME="$GFN_HOST_HOME" \
  XDG_CONFIG_HOME="$GFN_HOST_HOME/.config" \
  XDG_DATA_HOME="$GFN_HOST_HOME/.local/share" \
    xdg-mime default com.nvidia.geforcenow.desktop x-scheme-handler/geforcenow >/dev/null 2>&1 || true
  HOME="$GFN_HOST_HOME" \
  XDG_CONFIG_HOME="$GFN_HOST_HOME/.config" \
  XDG_DATA_HOME="$GFN_HOST_HOME/.local/share" \
    xdg-mime default com.nvidia.geforcenow.desktop x-scheme-handler/com.nvidia.geforcenow >/dev/null 2>&1 || true
  HOME="$GFN_HOST_HOME" \
  XDG_CONFIG_HOME="$GFN_HOST_HOME/.config" \
  XDG_DATA_HOME="$GFN_HOST_HOME/.local/share" \
    xdg-mime default com.nvidia.geforcenow.desktop x-scheme-handler/nvidia-gfn >/dev/null 2>&1 || true

  if ! grep -q 'x-scheme-handler/geforcenow=com.nvidia.geforcenow.desktop' "$mimeapps_file" 2>/dev/null; then
    cat >>"$mimeapps_file" <<'EOF'

[Default Applications]
x-scheme-handler/geforcenow=com.nvidia.geforcenow.desktop
x-scheme-handler/com.nvidia.geforcenow=com.nvidia.geforcenow.desktop
x-scheme-handler/nvidia-gfn=com.nvidia.geforcenow.desktop
EOF
  fi
}

install_xdg_open_wrapper() {
  local wrapper_path wrapper_dir

  wrapper_dir="${GFN_HOST_HOME}/.local/bin"
  wrapper_path="${wrapper_dir}/xdg-open"
  ensure_runtime_owned_dir "$wrapper_dir" 0755
  ensure_runtime_owned_file "$wrapper_path" 0755
  cat >"$wrapper_path" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

target="${1:-}"
log_dir="${HOME:-/tmp}/.cache/beagle-os"
log_file="${log_dir}/gfn-xdg-open.log"
mkdir -p "$log_dir" >/dev/null 2>&1 || true
printf '[%s] xdg-open %s\n' "$(date -Iseconds 2>/dev/null || date)" "$target" >>"$log_file" 2>/dev/null || true

case "$target" in
  geforcenow:*|com.nvidia.geforcenow:*|nvidia-gfn:*)
    exec /usr/local/lib/pve-thin-client/runtime/launch-geforcenow.sh "$target"
    ;;
esac

if [[ -n "$target" && "$target" == http://localhost:2259* ]]; then
  printf '[%s] localhost-callback %s\n' "$(date -Iseconds 2>/dev/null || date)" "$target" >>"$log_file" 2>/dev/null || true
fi

exec /usr/bin/xdg-open "$@"
EOF
  chmod 0755 "$wrapper_path"
}

install_host_xdg_open_shim() {
  local shim_path

  shim_path="/usr/local/bin/xdg-open"
  cat >"$shim_path" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

target="${1:-}"
log_dir="/home/thinclient/.cache/beagle-os"
log_file="${log_dir}/host-xdg-open.log"
mkdir -p "$log_dir" >/dev/null 2>&1 || true
printf '[%s] host-xdg-open %s\n' "$(date -Iseconds 2>/dev/null || date)" "$target" >>"$log_file" 2>/dev/null || true

case "$target" in
  geforcenow:*|com.nvidia.geforcenow:*|nvidia-gfn:*)
    exec /usr/local/lib/pve-thin-client/runtime/launch-geforcenow.sh "$target"
    ;;
  http://*|https://*)
    exec /usr/local/lib/pve-thin-client/runtime/open-browser-url.sh "$target"
    ;;
esac

exec /usr/bin/xdg-open "$@"
EOF
  chmod 0755 "$shim_path"
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

if ! prepare_geforcenow_environment "$GFN_RUNTIME_HOME"; then
  echo "Unable to prepare persistent GeForce NOW storage." >&2
  exit 1
fi

beagle_log_event "gfn.install.start" "scope=${GFN_INSTALL_SCOPE} app_id=${GFN_APP_ID} dry_run=${GFN_DRY_RUN} storage=${PVE_THIN_CLIENT_GFN_STORAGE_ROOT:-unknown}"
run_cmd flatpak remote-add "$GFN_INSTALL_SCOPE" --if-not-exists "$FLATHUB_REMOTE_NAME" "$FLATHUB_REMOTE_URL"
run_cmd flatpak remote-add "$GFN_INSTALL_SCOPE" --if-not-exists "$GFN_REMOTE_NAME" "$GFN_REMOTE_URL"
if flatpak_is_installed "$GFN_RUNTIME_REF"; then
  beagle_log_event "gfn.install.cached-runtime" "ref=${GFN_RUNTIME_REF}"
else
  run_cmd flatpak install -y "$GFN_INSTALL_SCOPE" "$FLATHUB_REMOTE_NAME" "$GFN_RUNTIME_REF"
fi
if flatpak_is_installed "$GFN_APP_ID"; then
  beagle_log_event "gfn.install.cached-app" "app_id=${GFN_APP_ID}"
else
  run_cmd flatpak install -y "$GFN_INSTALL_SCOPE" "$GFN_REMOTE_NAME" "$GFN_APP_ID"
fi
install_url_handler
install_xdg_open_wrapper
if [[ "$(id -u)" == "0" ]]; then
  install_host_xdg_open_shim
elif command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
  sudo -n bash -c "$(declare -f install_host_xdg_open_shim); install_host_xdg_open_shim"
fi
beagle_log_event "gfn.install.ready" "scope=${GFN_INSTALL_SCOPE} app_id=${GFN_APP_ID} storage=${PVE_THIN_CLIENT_GFN_STORAGE_ROOT:-unknown}"

case "$ACTION" in
  --ensure-only)
    exit 0
    ;;
esac
