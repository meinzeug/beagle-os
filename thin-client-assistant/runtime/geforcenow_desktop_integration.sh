#!/usr/bin/env bash

gfn_update_desktop_database_bin() {
  printf '%s\n' "${BEAGLE_UPDATE_DESKTOP_DATABASE_BIN:-update-desktop-database}"
}

gfn_xdg_mime_bin() {
  printf '%s\n' "${BEAGLE_XDG_MIME_BIN:-xdg-mime}"
}

gfn_wrapper_target() {
  printf '%s\n' "${BEAGLE_GFN_XDG_OPEN_WRAPPER_TARGET:-/usr/local/lib/pve-thin-client/runtime/launch-geforcenow.sh}"
}

gfn_browser_target() {
  printf '%s\n' "${BEAGLE_GFN_BROWSER_OPEN_TARGET:-/usr/local/lib/pve-thin-client/runtime/open-browser-url.sh}"
}

gfn_host_xdg_open_path() {
  printf '%s\n' "${BEAGLE_GFN_HOST_XDG_OPEN_PATH:-/usr/local/bin/xdg-open}"
}

gfn_host_xdg_open_log_dir() {
  printf '%s\n' "${BEAGLE_GFN_HOST_XDG_OPEN_LOG_DIR:-/home/thinclient/.cache/beagle-os}"
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

install_gfn_xdg_open_wrapper() {
  local wrapper_path wrapper_dir

  wrapper_dir="${GFN_HOST_HOME}/.local/bin"
  wrapper_path="${wrapper_dir}/xdg-open"
  ensure_runtime_owned_dir "$wrapper_dir" 0755
  ensure_runtime_owned_file "$wrapper_path" 0755
  cat >"$wrapper_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail

target="\${1:-}"
log_dir="\${HOME:-/tmp}/.cache/beagle-os"
log_file="\${log_dir}/gfn-xdg-open.log"
mkdir -p "\$log_dir" >/dev/null 2>&1 || true
printf '[%s] xdg-open %s\n' "\$(date -Iseconds 2>/dev/null || date)" "\$target" >>"\$log_file" 2>/dev/null || true

case "\$target" in
  geforcenow:*|com.nvidia.geforcenow:*|nvidia-gfn:*)
    exec $(gfn_wrapper_target) "\$target"
    ;;
esac

if [[ -n "\$target" && "\$target" == http://localhost:2259* ]]; then
  printf '[%s] localhost-callback %s\n' "\$(date -Iseconds 2>/dev/null || date)" "\$target" >>"\$log_file" 2>/dev/null || true
fi

exec /usr/bin/xdg-open "\$@"
EOF
  chmod 0755 "$wrapper_path"
}

install_gfn_host_xdg_open_shim() {
  local shim_path log_dir

  shim_path="$(gfn_host_xdg_open_path)"
  log_dir="$(gfn_host_xdg_open_log_dir)"
  cat >"$shim_path" <<EOF
#!/usr/bin/env bash
set -euo pipefail

target="\${1:-}"
log_dir="$(printf '%q' "$log_dir")"
log_file="\${log_dir}/host-xdg-open.log"
mkdir -p "\$log_dir" >/dev/null 2>&1 || true
printf '[%s] host-xdg-open %s\n' "\$(date -Iseconds 2>/dev/null || date)" "\$target" >>"\$log_file" 2>/dev/null || true

case "\$target" in
  geforcenow:*|com.nvidia.geforcenow:*|nvidia-gfn:*)
    exec $(gfn_wrapper_target) "\$target"
    ;;
  http://*|https://*)
    exec $(gfn_browser_target) "\$target"
    ;;
esac

exec /usr/bin/xdg-open "\$@"
EOF
  chmod 0755 "$shim_path"
}

ensure_gfn_desktop_integration() {
  install_gfn_url_handler
  install_gfn_xdg_open_wrapper
  if [[ "$(id -u)" == "0" ]]; then
    install_gfn_host_xdg_open_shim
  elif command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    sudo -n bash -c "$(declare -f gfn_host_xdg_open_path gfn_host_xdg_open_log_dir gfn_wrapper_target gfn_browser_target install_gfn_host_xdg_open_shim); install_gfn_host_xdg_open_shim"
  fi
}
