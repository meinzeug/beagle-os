#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOONLIGHT_REACHABILITY_SH="${MOONLIGHT_REACHABILITY_SH:-$SCRIPT_DIR/moonlight_reachability.sh}"
MOONLIGHT_CONNECT_HOST_SH="${MOONLIGHT_CONNECT_HOST_SH:-$SCRIPT_DIR/moonlight_connect_host.sh}"
# shellcheck disable=SC1090
source "$MOONLIGHT_REACHABILITY_SH"
# shellcheck disable=SC1090
source "$MOONLIGHT_CONNECT_HOST_SH"

prefer_ipv4() {
  [[ "${PVE_THIN_CLIENT_MOONLIGHT_PREFER_IPV4:-1}" == "1" ]]
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

moonlight_host() {
  render_template "${PVE_THIN_CLIENT_MOONLIGHT_HOST:-}"
}

moonlight_local_host() {
  render_template "${PVE_THIN_CLIENT_MOONLIGHT_LOCAL_HOST:-}"
}

moonlight_port() {
  render_template "${PVE_THIN_CLIENT_MOONLIGHT_PORT:-}"
}

format_moonlight_target() {
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
