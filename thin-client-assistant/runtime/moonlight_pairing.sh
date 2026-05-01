#!/usr/bin/env bash

moonlight_pairing_timeout() {
  printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_PAIRING_TIMEOUT:-30}"
}

ensure_paired() {
  local bin host port pin pair_pid paired_ok attempt pair_status target pairing_token

  bin="$(moonlight_bin)"
  host="$(moonlight_connect_host)"
  port="$(moonlight_port)"
  pin="${PVE_THIN_CLIENT_SUNSHINE_PIN:-}"
  target="$(moonlight_target "$host" "$port")"

  moonlight_list && return 0

  if register_moonlight_client_via_manager; then
    beagle_log_event "moonlight.registered" "host=${host} port=${port:-default}"
    moonlight_list && return 0
  fi

  [[ -n "$target" ]] || return 1

  if request_moonlight_pairing_token_via_manager; then
    pairing_token="${PVE_THIN_CLIENT_MOONLIGHT_PAIRING_TOKEN:-}"
    pin="${PVE_THIN_CLIENT_MOONLIGHT_PAIRING_PIN:-}"
  else
    pairing_token=""
  fi

  [[ -n "$pin" ]] || return 1

  # Pre-submit the PIN to Sunshine before starting moonlight pair (timing fix:
  # Sunshine requires the PIN to be submitted before the pairing handshake
  # completes, so submitting upfront avoids a race condition where the PIN
  # arrives too late and pairing times out.)
  submit_sunshine_pin || true

  if command -v timeout >/dev/null 2>&1; then
    timeout --preserve-status "$(moonlight_pairing_timeout)" "$bin" pair "$target" --pin "$pin" >"${MOONLIGHT_PAIR_LOG:-/dev/null}" 2>&1 &
  else
    "$bin" pair "$target" --pin "$pin" >"${MOONLIGHT_PAIR_LOG:-/dev/null}" 2>&1 &
  fi
  pair_pid=$!
  paired_ok="0"

  for attempt in $(seq 1 20); do
    if ! kill -0 "$pair_pid" >/dev/null 2>&1; then
      break
    fi
    if [[ -n "$pairing_token" ]]; then
      if exchange_moonlight_pairing_token_via_manager "$pairing_token"; then
        paired_ok="1"
        break
      fi
    elif submit_sunshine_pin; then
      paired_ok="1"
      break
    fi
    sleep 1
  done

  pair_status=0
  wait "$pair_pid" || pair_status=$?

  [[ "$pair_status" == "0" ]] || return "$pair_status"
  [[ "$paired_ok" == "1" ]] || return 1
  moonlight_list
}
