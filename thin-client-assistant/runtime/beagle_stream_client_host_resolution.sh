#!/usr/bin/env bash

resolve_ipv4_host() {
  python3 - "$1" <<'PY'
import socket
import sys

host = sys.argv[1]
seen = set()
for entry in socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM):
    address = entry[4][0]
    if address not in seen:
        seen.add(address)
        print(address)
        raise SystemExit(0)

raise SystemExit(1)
PY
}

resolve_preferred_beagle_stream_client_host() {
  local host resolved
  host="$1"
  [[ -n "$host" ]] || return 0
  if prefer_ipv4 && ! is_ip_literal "$host"; then
    resolved="$(resolve_ipv4_host "$host" 2>/dev/null || true)"
    if [[ -n "$resolved" ]]; then
      printf '%s\n' "$resolved"
      return 0
    fi
  fi
  printf '%s\n' "$host"
}
