#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEAGLE_STREAM_CLIENT_REACHABILITY_SH="${BEAGLE_STREAM_CLIENT_REACHABILITY_SH:-$SCRIPT_DIR/beagle_stream_client_reachability.sh}"
BEAGLE_STREAM_CLIENT_CONNECT_HOST_SH="${BEAGLE_STREAM_CLIENT_CONNECT_HOST_SH:-$SCRIPT_DIR/beagle_stream_client_connect_host.sh}"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_REACHABILITY_SH"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_CONNECT_HOST_SH"

prefer_ipv4() {
  [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PREFER_IPV4:-1}" == "1" ]]
}

beagle_stream_connection_method() {
  render_template "${PVE_THIN_CLIENT_CONNECTION_METHOD:-direct}"
}

beagle_stream_broker_connection() {
  [[ "$(beagle_stream_connection_method)" == "broker" ]]
}

is_ip_literal() {
  python3 - "$1" <<'PY'
import ipaddress
import sys

try:
    ipaddress.ip_address(sys.argv[1].strip("[]"))
except ValueError:
    raise SystemExit(1)
PY
}

beagle_stream_client_host() {
  local host fallback_host

  if beagle_stream_broker_connection; then
    return 0
  fi

  host="$(render_template "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST:-}" 2>/dev/null || true)"
  if [[ -n "$host" ]]; then
    printf '%s\n' "$host"
    return 0
  fi

  fallback_host="$(render_template "${PVE_THIN_CLIENT_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST:-}" 2>/dev/null || true)"
  printf '%s\n' "$fallback_host"
}

beagle_stream_client_local_host() {
  render_template "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LOCAL_HOST:-}"
}

beagle_stream_client_port() {
  render_template "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PORT:-50000}"
}

format_beagle_stream_client_target() {
  local host="$1"
  local port="$2"

  [[ -n "$host" ]] || return 1
  if [[ -z "$port" ]]; then
    printf '%s\n' "$host"
    return 0
  fi

  if [[ "$host" == \[*\] ]]; then
    printf '%s:%s\n' "$host" "$port"
    return 0
  fi

  if [[ "$host" == *:* ]]; then
    printf '[%s]:%s\n' "$host" "$port"
    return 0
  fi

  printf '%s:%s\n' "$host" "$port"
}
