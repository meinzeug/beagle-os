#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOONLIGHT_CONFIG_STATE_SH="${MOONLIGHT_CONFIG_STATE_SH:-$SCRIPT_DIR/moonlight_config_state.sh}"
MOONLIGHT_REMOTE_API_SH="${MOONLIGHT_REMOTE_API_SH:-$SCRIPT_DIR/moonlight_remote_api.sh}"
# shellcheck disable=SC1090
source "$MOONLIGHT_CONFIG_STATE_SH"
# shellcheck disable=SC1090
source "$MOONLIGHT_REMOTE_API_SH"

moonlight_list_timeout() {
  printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_LIST_TIMEOUT:-12}"
}

moonlight_bootstrap_timeout() {
  printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_BOOTSTRAP_TIMEOUT:-3}"
}

moonlight_list() {
  local bin host port timeout_value target
  bin="$(moonlight_bin)"
  host="$(moonlight_connect_host)"
  port="$(moonlight_port)"
  timeout_value="$(moonlight_list_timeout)"
  target="$(format_moonlight_target "$host" "$port")"

  if command -v timeout >/dev/null 2>&1; then
    timeout --preserve-status "$timeout_value" "$bin" list "$target" >"$MOONLIGHT_LIST_LOG" 2>&1
    return $?
  fi

  "$bin" list "$target" >"$MOONLIGHT_LIST_LOG" 2>&1
}

ensure_paired() {
  local bin host port pin pair_pid paired_ok attempt pair_status target

  bin="$(moonlight_bin)"
  host="$(moonlight_connect_host)"
  port="$(moonlight_port)"
  pin="${PVE_THIN_CLIENT_SUNSHINE_PIN:-}"
  target="$(format_moonlight_target "$host" "$port")"

  moonlight_list && return 0

  if register_moonlight_client_via_manager; then
    beagle_log_event "moonlight.registered" "host=${host} port=${port:-default}"
    if moonlight_list; then
      return 0
    fi
  fi

  [[ -n "$pin" ]] || return 1

  if command -v timeout >/dev/null 2>&1; then
    timeout --preserve-status "$(moonlight_list_timeout)" "$bin" pair "$target" --pin "$pin" >"$MOONLIGHT_PAIR_LOG" 2>&1 &
  else
    "$bin" pair "$target" --pin "$pin" >"$MOONLIGHT_PAIR_LOG" 2>&1 &
  fi
  pair_pid=$!
  paired_ok="0"

  for attempt in $(seq 1 20); do
    sleep 1
    if submit_sunshine_pin; then
      paired_ok="1"
      break
    fi
  done

  pair_status=0
  wait "$pair_pid" || pair_status=$?

  [[ "$pair_status" == "0" ]] || return "$pair_status"
  [[ "$paired_ok" == "1" ]] || return 1
  moonlight_list
}
