#!/usr/bin/env bash

beagle_stream_client_pairing_timeout() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_TIMEOUT:-30}"
}

beagle_stream_client_pairing_retry_sleep() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_RETRY_SLEEP:-3}"
}

beagle_stream_client_pair_log() {
  local message="${1:-}"
  local log_file="${BEAGLE_STREAM_CLIENT_PAIR_LOG:-}"

  [[ -n "$message" && -n "$log_file" ]] || return 0
  {
    printf '=== %s ===\n' "$(date -Iseconds)"
    printf '%s\n' "$message"
  } >>"$log_file" 2>/dev/null || true
}

beagle_stream_client_pair_status() {
  local host port api_url response

  # Try the Sunshine HTTPS API first (/serverinfo returns 404 in beagle-stream-server builds).
  # A 200 response with apps data means the client is paired; 401 means unpaired.
  api_url="$(selected_beagle_stream_server_api_url 2>/dev/null || true)"
  if [[ -n "$api_url" ]]; then
    response="$(curl -fsS -k --connect-timeout 2 --max-time 5 \
      "${api_url%/}/api/apps" 2>/dev/null || true)"
    if [[ -n "$response" ]]; then
      python3 - "$response" <<'PY'
import json, sys
try:
    d = json.loads(sys.argv[1])
    status = d.get("status", None)
    # status=True (or absent/truthy with app data) → paired
    if status is True or ("apps" in d and status is not False) or ("data" in d and status is not False):
        print("1")
        raise SystemExit(0)
    # status=False → not paired (Unauthorized)
    print("0")
    raise SystemExit(0)
except SystemExit:
    raise
except Exception:
    raise SystemExit(1)
PY
      return $?
    fi
  fi

  host="$(beagle_stream_client_connect_host)"
  port="$(beagle_stream_client_port)"
  [[ -n "$host" && -n "$port" ]] || return 1
  response="$(curl -fsS --connect-timeout 2 --max-time 5 "http://${host}:${port}/serverinfo" 2>/dev/null || true)"
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

beagle_stream_client_list_log_has_tls_or_pair_errors() {
  local start_line="${1:-1}"
  local log_file="${BEAGLE_STREAM_CLIENT_LIST_LOG:-}"

  [[ -n "$log_file" && -r "$log_file" ]] || return 1
  tail -n "+${start_line}" "$log_file" 2>/dev/null | grep -Eqi \
    'server certificate mismatch|sslhandshakefailederror|failed to find application|failed to load application|unauthorized|not paired'
}

beagle_stream_client_list_ready() {
  local log_file start_line

  log_file="${BEAGLE_STREAM_CLIENT_LIST_LOG:-}"
  start_line=1
  if [[ -n "$log_file" && -r "$log_file" ]]; then
    start_line="$(( $(wc -l < "$log_file" 2>/dev/null || printf '0') + 1 ))"
  fi

  beagle_stream_client_list || return 1
  if beagle_stream_client_list_log_has_tls_or_pair_errors "$start_line"; then
    return 1
  fi
  return 0
}

beagle_stream_client_stream_ready() {
  # PairStatus from serverinfo/API is authoritative when available.
  # Explicit "0" means unpaired and must not be overridden by list() output.
  # Only when status is unavailable do we fall back to list() heuristics.
  local pair_status

  pair_status="$(beagle_stream_client_pair_status 2>/dev/null || true)"
  if [[ "$pair_status" == "1" ]]; then
    return 0
  fi
  if [[ "$pair_status" == "0" ]]; then
    return 1
  fi

  beagle_stream_client_list_ready
}

ensure_paired() {
  local bin host port paired_ok attempt target pairing_token retry_sleep

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

  pairing_token="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_TOKEN:-}"
  retry_sleep="$(beagle_stream_client_pairing_retry_sleep)"

  paired_ok="0"
  attempt=0
  while [[ "$attempt" -lt "$(beagle_stream_client_pairing_timeout)" ]]; do
    if [[ -z "$pairing_token" ]]; then
      if request_beagle_stream_client_pairing_token_via_manager; then
        pairing_token="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_TOKEN:-}"
        beagle_stream_client_pair_log "pair-token acquired via manager"
      else
        beagle_stream_client_pair_log "pair-token request failed via manager"
      fi
    fi

    if [[ -z "$pairing_token" ]]; then
      attempt=$((attempt + 1))
      sleep "$retry_sleep"
      continue
    fi

    if [[ "$attempt" -gt 0 && $((attempt % 5)) -eq 0 ]]; then
      # Client certificates can rotate during early startup. Refresh occasionally
      # without hammering the manager into endpoint-wide rate limits.
      register_beagle_stream_client_via_manager >/dev/null 2>&1 || true
    fi
    if exchange_beagle_stream_client_pairing_token_via_manager "$pairing_token"; then
      # Manager-side exchange succeeded: Sunshine accepted the pairing token.
      # Trust the exchange result. The secondary pair_status/stream_ready checks
      # are best-effort only — they can fail legitimately (e.g. broker host not
      # yet resolved, /serverinfo 404 on beagle-stream-server builds). The token
      # is consumed after exchange, so we must not retry exchange.
      paired_ok="1"
      beagle_stream_client_pair_log "pair-exchange accepted via manager"
      beagle_stream_client_pair_status_ready >/dev/null 2>&1 || true
      beagle_stream_client_stream_ready >/dev/null 2>&1 || true
      break
    fi
    beagle_stream_client_pair_log "pair-exchange failed via manager; trying direct submit"
    if submit_beagle_stream_server_pairing_token; then
      if beagle_stream_client_pair_status_ready || beagle_stream_client_stream_ready; then
        paired_ok="1"
        beagle_stream_client_pair_log "direct pairing token submit succeeded"
        break
      fi
    fi
    beagle_stream_client_pair_log "direct pairing token submit did not produce ready state"
    # Pair tokens can be short-lived or one-shot. Refresh on next loop.
    pairing_token=""
    attempt=$((attempt + 1))
    sleep "$retry_sleep"
  done

  [[ "$paired_ok" == "1" ]] || return 1

  # Exchange succeeded — return immediately. In broker/hostless mode the host
  # is UNSET until the stream client resolves it from the session, so
  # stream_ready and pair_status_ready both fail here even after a successful
  # pairing. Requiring them would cause a spurious pairing-failed.
  return 0
}
