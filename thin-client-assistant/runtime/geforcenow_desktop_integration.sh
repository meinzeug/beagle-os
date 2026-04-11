#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEFORCENOW_XDG_OPEN_INTEGRATION_SH="${GEFORCENOW_XDG_OPEN_INTEGRATION_SH:-$SCRIPT_DIR/geforcenow_xdg_open_integration.sh}"
# shellcheck disable=SC1090
source "$GEFORCENOW_XDG_OPEN_INTEGRATION_SH"

gfn_update_desktop_database_bin() {
  printf '%s\n' "${BEAGLE_UPDATE_DESKTOP_DATABASE_BIN:-update-desktop-database}"
}

gfn_xdg_mime_bin() {
  printf '%s\n' "${BEAGLE_XDG_MIME_BIN:-xdg-mime}"
}

register_gfn_mime_handler() {
  local handler="$1"
  local xdg_mime_cmd

  xdg_mime_cmd="$(gfn_xdg_mime_bin)"
  HOME="$GFN_HOST_HOME" \
  XDG_CONFIG_HOME="$GFN_HOST_HOME/.config" \
  XDG_DATA_HOME="$GFN_HOST_HOME/.local/share" \
    "$xdg_mime_cmd" default com.nvidia.geforcenow.desktop "$handler" >/dev/null 2>&1 || true
}

install_gfn_url_handler() {
  local apps_dir desktop_file mimeapps_file update_desktop_cmd

  apps_dir="${GFN_HOST_HOME}/.local/share/applications"
  mimeapps_file="${GFN_HOST_HOME}/.config/mimeapps.list"
  desktop_file="${apps_dir}/com.nvidia.geforcenow.desktop"
  update_desktop_cmd="$(gfn_update_desktop_database_bin)"

  ensure_runtime_owned_dir "$apps_dir" 0755
  ensure_runtime_owned_dir "${GFN_HOST_HOME}/.config" 0700
  ensure_runtime_owned_file "$desktop_file" 0644
  ensure_runtime_owned_file "$mimeapps_file" 0644

  cat >"$desktop_file" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=NVIDIA GeForce NOW
GenericName=NVIDIA GeForce NOW
Exec=$(gfn_wrapper_target) %u
Icon=com.nvidia.geforcenow
Categories=Network;Game;
NoDisplay=true
MimeType=x-scheme-handler/geforcenow;x-scheme-handler/com.nvidia.geforcenow;x-scheme-handler/nvidia-gfn;
EOF

  "$update_desktop_cmd" "$apps_dir" >/dev/null 2>&1 || true
  register_gfn_mime_handler "x-scheme-handler/geforcenow"
  register_gfn_mime_handler "x-scheme-handler/com.nvidia.geforcenow"
  register_gfn_mime_handler "x-scheme-handler/nvidia-gfn"

  if ! grep -q 'x-scheme-handler/geforcenow=com.nvidia.geforcenow.desktop' "$mimeapps_file" 2>/dev/null; then
    cat >>"$mimeapps_file" <<'EOF'

[Default Applications]
x-scheme-handler/geforcenow=com.nvidia.geforcenow.desktop
x-scheme-handler/com.nvidia.geforcenow=com.nvidia.geforcenow.desktop
x-scheme-handler/nvidia-gfn=com.nvidia.geforcenow.desktop
EOF
  fi
}

ensure_gfn_desktop_integration() {
  install_gfn_url_handler
  ensure_gfn_xdg_open_integration
}
