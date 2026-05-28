#!/usr/bin/env bash

beagle_stream_client_list_timeout() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LIST_TIMEOUT:-6}"
}

beagle_stream_client_bootstrap_timeout() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BOOTSTRAP_TIMEOUT:-3}"
}

beagle_stream_client_target() {
  local host port

  host="${1:-$(beagle_stream_client_connect_host)}"
  port="${2:-$(beagle_stream_client_port)}"
  format_beagle_stream_client_target "$host" "$port"
}

beagle_stream_client_prepare_cli_environment() {
  export HOME="${HOME:-/home/${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}}"
  export DISPLAY="${DISPLAY:-:0}"
  if declare -F select_xauthority >/dev/null 2>&1; then
    export XAUTHORITY="${XAUTHORITY:-$(select_xauthority)}"
  elif [[ -z "${XAUTHORITY:-}" && -r "${HOME}/.Xauthority" ]]; then
    export XAUTHORITY="${HOME}/.Xauthority"
  fi
  export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
  export XDG_SESSION_TYPE="${XDG_SESSION_TYPE:-x11}"
  export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-x11}"
  unset WAYLAND_DISPLAY 2>/dev/null || true
}

run_beagle_stream_client_cli_with_timeout() {
  local timeout_value="${1:-}"
  local log_file="${2:-}"
  local bin

  shift 2 || true
  bin="$(beagle_stream_client_bin)"
  [[ -n "$bin" && "$#" -gt 0 ]] || return 1

  if [[ -z "$log_file" ]]; then
    log_file="/dev/null"
  fi

  beagle_stream_client_prepare_cli_environment

  if command -v timeout >/dev/null 2>&1 && [[ -n "$timeout_value" ]]; then
    timeout --preserve-status "$timeout_value" "$bin" "$@" >"$log_file" 2>&1
    return $?
  fi

  "$bin" "$@" >"$log_file" 2>&1
}

beagle_stream_client_list() {
  local target

  target="$(beagle_stream_client_target)"
  [[ -n "$target" ]] || return 1

  run_beagle_stream_client_cli_with_timeout \
    "$(beagle_stream_client_list_timeout)" \
    "${BEAGLE_STREAM_CLIENT_LIST_LOG:-/dev/null}" \
    list "$target"
}

bootstrap_beagle_stream_client_probe() {
  local target

  target="$(beagle_stream_client_target)"
  [[ -n "$target" ]] || return 1

  run_beagle_stream_client_cli_with_timeout \
    "$(beagle_stream_client_bootstrap_timeout)" \
    "/dev/null" \
    list "$target" || true
}
