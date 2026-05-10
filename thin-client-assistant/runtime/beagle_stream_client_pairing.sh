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
  local bin host port paired_ok attempt target pairing_token

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
  else
    pairing_token=""
  fi

  [[ -n "$pairing_token" ]] || return 1

  paired_ok="0"
  attempt=0
  while [[ "$attempt" -lt "$(beagle_stream_client_pairing_timeout)" ]]; do
    # The client certificate can rotate between startup phases on some images.
    # Re-register before each exchange attempt so manager/host state stays in sync.
    register_beagle_stream_client_via_manager >/dev/null 2>&1 || true
    if exchange_beagle_stream_client_pairing_token_via_manager "$pairing_token"; then
      if beagle_stream_client_pair_status_ready || beagle_stream_client_stream_ready; then
        paired_ok="1"
        break
      fi
    fi
    if submit_beagle_stream_server_pairing_token; then
      if beagle_stream_client_pair_status_ready || beagle_stream_client_stream_ready; then
        paired_ok="1"
        break
      fi
    fi
    attempt=$((attempt + 1))
    sleep 1
  done

  [[ "$paired_ok" == "1" ]] || return 1

  # Pairing can take a few moments to propagate. Require a real ready signal.
  attempt=0
  while [[ "$attempt" -lt 10 ]]; do
    if beagle_stream_client_stream_ready || beagle_stream_client_pair_status_ready; then
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 1
  done

  return 1
}
