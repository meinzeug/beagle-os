#!/usr/bin/env bash

moonlight_list_timeout() {
  printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_LIST_TIMEOUT:-12}"
}

moonlight_bootstrap_timeout() {
  printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_BOOTSTRAP_TIMEOUT:-3}"
}

moonlight_target() {
  local host port

  host="${1:-$(moonlight_connect_host)}"
  port="${2:-$(moonlight_port)}"
  format_moonlight_target "$host" "$port"
}

run_moonlight_cli_with_timeout() {
  local timeout_value="${1:-}"
  local log_file="${2:-}"
  local bin

  shift 2 || true
  bin="$(moonlight_bin)"
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

moonlight_list() {
  local target

  target="$(moonlight_target)"
  [[ -n "$target" ]] || return 1

  run_moonlight_cli_with_timeout \
    "$(moonlight_list_timeout)" \
    "${MOONLIGHT_LIST_LOG:-/dev/null}" \
    list "$target"
}

bootstrap_moonlight_client_probe() {
  local target

  target="$(moonlight_target)"
  [[ -n "$target" ]] || return 1

  run_moonlight_cli_with_timeout \
    "$(moonlight_bootstrap_timeout)" \
    "/dev/null" \
    list "$target" || true
}
