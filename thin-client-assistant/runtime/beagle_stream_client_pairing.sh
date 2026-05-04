#!/usr/bin/env bash

beagle_stream_client_pairing_timeout() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_TIMEOUT:-30}"
}

beagle_stream_client_pair_status() {
  local host port target response

  host="$(beagle_stream_client_connect_host)"
  port="$(beagle_stream_client_port)"
  [[ -n "$host" && -n "$port" ]] || return 1
  target="http://${host}:${port}/serverinfo"

  response="$(curl -fsS --connect-timeout 2 --max-time 5 "$target" 2>/dev/null || true)"
  [[ -n "$response" ]] || return 1

  python3 - "$response" <<'PY'
import re
import sys

match = re.search(r"<PairStatus>([^<]+)</PairStatus>", sys.argv[1] or "")
if not match:
    raise SystemExit(1)
print(match.group(1).strip())
PY
}

beagle_stream_client_pair_status_ready() {
  [[ "$(beagle_stream_client_pair_status 2>/dev/null || true)" == "1" ]]
}

beagle_stream_client_list_ready() {
  beagle_stream_client_list
}

beagle_stream_client_stream_ready() {
  beagle_stream_client_list_ready
}

ensure_paired() {
  local bin host port pair_pid paired_ok attempt pair_status target pairing_token pairing_pin

  bin="$(beagle_stream_client_bin)"
  host="$(beagle_stream_client_connect_host)"
  port="$(beagle_stream_client_port)"
  target="$(beagle_stream_client_target "$host" "$port")"

  if beagle_stream_client_stream_ready; then
    return 0
  fi

  if register_beagle_stream_client_via_manager; then
    beagle_log_event "beagle-stream-client.registered" "host=${host} port=${port:-default}"
    if beagle_stream_client_stream_ready; then
      return 0
    fi
  fi

  [[ -n "$target" ]] || return 1

  if request_beagle_stream_client_pairing_token_via_manager; then
    pairing_token="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_TOKEN:-}"
    pairing_pin="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_PIN:-}"
  else
    pairing_token=""
    pairing_pin=""
  fi

  [[ -n "$pairing_token" ]] || return 1
  [[ -n "$pairing_pin" ]] || pairing_pin="$pairing_token"

  submit_beagle_stream_server_pairing_token || true

  if command -v timeout >/dev/null 2>&1; then
    timeout --preserve-status "$(beagle_stream_client_pairing_timeout)" "$bin" pair "$target" --pin "$pairing_pin" >"${BEAGLE_STREAM_CLIENT_PAIR_LOG:-/dev/null}" 2>&1 &
  else
    "$bin" pair "$target" --pin "$pairing_pin" >"${BEAGLE_STREAM_CLIENT_PAIR_LOG:-/dev/null}" 2>&1 &
  fi
  pair_pid=$!
  paired_ok="0"

  for attempt in $(seq 1 20); do
    if ! kill -0 "$pair_pid" >/dev/null 2>&1; then
      break
    fi
    if exchange_beagle_stream_client_pairing_token_via_manager "$pairing_token"; then
      paired_ok="1"
      break
    fi
    sleep 1
  done

  pair_status=0
  wait "$pair_pid" || pair_status=$?

  [[ "$pair_status" == "0" ]] || return "$pair_status"
  [[ "$paired_ok" == "1" ]] || return 1
  beagle_stream_client_stream_ready
}
