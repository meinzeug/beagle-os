#!/usr/bin/env bash

beagle_stream_client_list_timeout() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LIST_TIMEOUT:-12}"
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
