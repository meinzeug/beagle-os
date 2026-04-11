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

resolve_preferred_moonlight_host() {
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

moonlight_local_host_is_direct() {
  local local_host route_line

  local_host="$(moonlight_local_host)"
  [[ -n "$local_host" ]] || return 1
  command -v ip >/dev/null 2>&1 || return 1

  route_line="$(ip route get "$local_host" 2>/dev/null | head -n1 || true)"
  [[ -n "$route_line" ]] || return 1

  if grep -q ' via ' <<<"$route_line"; then
    return 1
  fi

  return 0
}

usable_moonlight_local_host() {
  local local_host

  local_host="$(moonlight_local_host)"
  [[ -n "$local_host" ]] || return 1
  moonlight_local_host_is_direct || return 1
  printf '%s\n' "$local_host"
}

moonlight_gateway_fallback_host() {
  local gateway host
  gateway="${PVE_THIN_CLIENT_NETWORK_GATEWAY:-}"
  host="$(moonlight_host)"

  [[ -n "$gateway" ]] || return 1
  [[ "$gateway" != "$host" ]] || return 1
  printf '%s\n' "$gateway"
}

moonlight_primary_connect_host() {
  local host local_host
  local_host="$(moonlight_local_host)"
  if [[ -n "$local_host" ]]; then
    resolve_preferred_moonlight_host "$local_host"
    return 0
  fi
  host="$(moonlight_host)"
  resolve_preferred_moonlight_host "$host"
}

moonlight_public_connect_host() {
  local host
  host="$(moonlight_host)"
  resolve_preferred_moonlight_host "$host"
}

moonlight_connect_host() {
  local host local_host public_host fallback_host api_url candidate last_candidate
  local -a candidates=()

  host="$(moonlight_host)"
  api_url="$(sunshine_api_url)"

  local_host="$(usable_moonlight_local_host 2>/dev/null || true)"
  public_host="$(moonlight_public_connect_host)"

  if [[ -n "$local_host" ]]; then
    candidates+=("$(resolve_preferred_moonlight_host "$local_host")")
  fi

  if [[ -n "$public_host" ]]; then
    candidates+=("$public_host")
  fi

  last_candidate=""
  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" ]] || continue
    if [[ "$candidate" == "$last_candidate" ]]; then
      continue
    fi
    if probe_stream_candidate "$candidate" "$api_url"; then
      printf '%s\n' "$candidate"
      return 0
    fi
    last_candidate="$candidate"
  done

  fallback_host="$(moonlight_gateway_fallback_host 2>/dev/null || true)"
  if [[ -n "$fallback_host" ]] && probe_stream_candidate "$fallback_host" "$api_url"; then
    printf '%s\n' "$fallback_host"
    return 0
  fi

  if [[ -n "$public_host" ]]; then
    printf '%s\n' "$public_host"
    return 0
  fi

  if [[ -n "$local_host" ]]; then
    resolve_preferred_moonlight_host "$local_host"
    return 0
  fi

  printf '%s\n' "$host"
}
