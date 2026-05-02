#!/usr/bin/env bash

beagle_stream_client_pairing_timeout() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_TIMEOUT:-30}"
}

ensure_paired() {
  local bin host port pin pair_pid paired_ok attempt pair_status target pairing_token

  bin="$(beagle_stream_client_bin)"
  host="$(beagle_stream_client_connect_host)"
  port="$(beagle_stream_client_port)"
  pin="${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PIN:-}"
  target="$(beagle_stream_client_target "$host" "$port")"

  beagle_stream_client_list && return 0

  if register_beagle_stream_client_via_manager; then
    beagle_log_event "beagle-stream-client.registered" "host=${host} port=${port:-default}"
    beagle_stream_client_list && return 0
  fi

  [[ -n "$target" ]] || return 1

  if request_beagle_stream_client_pairing_token_via_manager; then
    pairing_token="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_TOKEN:-}"
    pin="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_PIN:-}"
  else
    pairing_token=""
  fi

  [[ -n "$pin" ]] || return 1

  # Pre-submit the PIN to Beagle Stream Server before starting beagle-stream-client pair (timing fix:
  # Beagle Stream Server requires the PIN to be submitted before the pairing handshake
  # completes, so submitting upfront avoids a race condition where the PIN
  # arrives too late and pairing times out.)
  submit_beagle_stream_server_pin || true

  if command -v timeout >/dev/null 2>&1; then
    timeout --preserve-status "$(beagle_stream_client_pairing_timeout)" "$bin" pair "$target" --pin "$pin" >"${BEAGLE_STREAM_CLIENT_PAIR_LOG:-/dev/null}" 2>&1 &
  else
    "$bin" pair "$target" --pin "$pin" >"${BEAGLE_STREAM_CLIENT_PAIR_LOG:-/dev/null}" 2>&1 &
  fi
  pair_pid=$!
  paired_ok="0"

  for attempt in $(seq 1 20); do
    if ! kill -0 "$pair_pid" >/dev/null 2>&1; then
      break
    fi
    if [[ -n "$pairing_token" ]]; then
      if exchange_beagle_stream_client_pairing_token_via_manager "$pairing_token"; then
        paired_ok="1"
        break
      fi
    elif submit_beagle_stream_server_pin; then
      paired_ok="1"
      break
    fi
    sleep 1
  done

  pair_status=0
  wait "$pair_pid" || pair_status=$?

  [[ "$pair_status" == "0" ]] || return "$pair_status"
  [[ "$paired_ok" == "1" ]] || return 1
  beagle_stream_client_list
}
