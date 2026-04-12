#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOONLIGHT_CONFIG_STATE_SH="${MOONLIGHT_CONFIG_STATE_SH:-$SCRIPT_DIR/moonlight_config_state.sh}"
MOONLIGHT_CLI_SH="${MOONLIGHT_CLI_SH:-$SCRIPT_DIR/moonlight_cli.sh}"
MOONLIGHT_REMOTE_API_SH="${MOONLIGHT_REMOTE_API_SH:-$SCRIPT_DIR/moonlight_remote_api.sh}"
# shellcheck disable=SC1090
source "$MOONLIGHT_CONFIG_STATE_SH"
# shellcheck disable=SC1090
source "$MOONLIGHT_CLI_SH"
# shellcheck disable=SC1090
source "$MOONLIGHT_REMOTE_API_SH"

start_moonlight_pair_with_pin() {
  local pin="${1:-}"
  local target="${2:-}"
  local pair_timeout

  [[ -n "$pin" && -n "$target" ]] || return 1
  pair_timeout="$(moonlight_list_timeout)"

  run_moonlight_cli_with_timeout \
    "$pair_timeout" \
    "${MOONLIGHT_PAIR_LOG:-/dev/null}" \
    pair "$target" --pin "$pin" &
}

ensure_paired() {
  local host port pin pair_pid paired_ok attempt pair_status target

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

  start_moonlight_pair_with_pin "$pin" "$target"
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
