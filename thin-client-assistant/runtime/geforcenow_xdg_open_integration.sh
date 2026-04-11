#!/usr/bin/env bash

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

ensure_gfn_xdg_open_integration() {
  install_gfn_xdg_open_wrapper
  if [[ "$(id -u)" == "0" ]]; then
    install_gfn_host_xdg_open_shim
  elif command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    sudo -n bash -c "$(declare -f gfn_host_xdg_open_path gfn_host_xdg_open_log_dir gfn_wrapper_target gfn_browser_target install_gfn_host_xdg_open_shim); install_gfn_host_xdg_open_shim"
  fi
}
