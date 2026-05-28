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
  local host port response

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

complete_beagle_stream_client_pairing_handshake() {
  local compat_pin target bin log_file pair_rc

  compat_pin="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_COMPAT_PIN:-}"
  [[ -n "$compat_pin" ]] || return 1

  target="$(beagle_stream_client_target "$(beagle_stream_client_connect_host)" "$(beagle_stream_client_port)")"
  bin="$(beagle_stream_client_bin)"
  [[ -n "$target" && -n "$bin" ]] || return 1

  log_file="${BEAGLE_STREAM_CLIENT_PAIR_LOG:-/dev/null}"
  if declare -F beagle_stream_client_prepare_cli_environment >/dev/null 2>&1; then
    beagle_stream_client_prepare_cli_environment
  else
    export HOME="${HOME:-/home/${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}}"
    export DISPLAY="${DISPLAY:-:0}"
    [[ -n "${XAUTHORITY:-}" || ! -r "${HOME}/.Xauthority" ]] || export XAUTHORITY="${HOME}/.Xauthority"
    export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
    export XDG_SESSION_TYPE="${XDG_SESSION_TYPE:-x11}"
    unset WAYLAND_DISPLAY 2>/dev/null || true
  fi
  pair_rc=0
  if command -v timeout >/dev/null 2>&1; then
    timeout 25 "$bin" pair "$target" --pin "$compat_pin" >>"$log_file" 2>&1 || pair_rc="$?"
  else
    "$bin" pair "$target" --pin "$compat_pin" >>"$log_file" 2>&1 || pair_rc="$?"
  fi
  if [[ "$pair_rc" -eq 0 ]]; then
    return 0
  fi
  if beagle_stream_client_pair_status_ready; then
    beagle_stream_client_pair_log "beagle-stream client pair command exited rc=${pair_rc} after server marked PairStatus=1"
    return 0
  fi
  return "$pair_rc"
}

ensure_paired() {
  local bin host port paired_ok attempt target pairing_token retry_sleep connection_method

  bin="$(beagle_stream_client_bin)"
  host="$(beagle_stream_client_connect_host)"
  port="$(beagle_stream_client_port)"
  target="$(beagle_stream_client_target "$host" "$port")"
  connection_method="$(beagle_stream_connection_method 2>/dev/null || true)"

  # Broker mode still requires a valid client certificate pairing for Sunshine.
  # Keep an explicit emergency bypass for controlled debugging only.
  if [[ "$connection_method" == "broker" && "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BROKER_PAIRING_BYPASS:-0}" == "1" ]]; then
    beagle_stream_client_pair_log "pairing gate bypassed in broker mode (override=1)"
    return 0
  fi

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
      beagle_stream_client_pair_log "pair-exchange accepted via manager"
      if complete_beagle_stream_client_pairing_handshake; then
        paired_ok="1"
        beagle_stream_client_pair_log "pairing handshake completed via beagle-stream client"
        beagle_stream_client_pair_status_ready >/dev/null 2>&1 || true
        beagle_stream_client_stream_ready >/dev/null 2>&1 || true
        break
      fi
      beagle_stream_client_pair_log "pair-exchange accepted but client certificate handshake failed"
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
