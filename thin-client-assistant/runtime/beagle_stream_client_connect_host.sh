#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEAGLE_STREAM_CLIENT_HOST_RESOLUTION_SH="${BEAGLE_STREAM_CLIENT_HOST_RESOLUTION_SH:-$SCRIPT_DIR/beagle_stream_client_host_resolution.sh}"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_HOST_RESOLUTION_SH"

beagle_stream_client_local_host_is_direct() {
  local local_host route_line

  local_host="$(beagle_stream_client_local_host)"
  [[ -n "$local_host" ]] || return 1
  command -v ip >/dev/null 2>&1 || return 1

  route_line="$(ip route get "$local_host" 2>/dev/null | head -n1 || true)"
  [[ -n "$route_line" ]] || return 1

  if grep -q ' via ' <<<"$route_line"; then
    return 1
  fi

  return 0
}

usable_beagle_stream_client_local_host() {
  local local_host

  local_host="$(beagle_stream_client_local_host)"
  [[ -n "$local_host" ]] || return 1
  beagle_stream_client_local_host_is_direct || return 1
  printf '%s\n' "$local_host"
}

beagle_stream_client_gateway_fallback_host() {
  local gateway host
  gateway="${PVE_THIN_CLIENT_NETWORK_GATEWAY:-}"
  host="$(beagle_stream_client_host)"

  [[ -n "$gateway" ]] || return 1
  [[ "$gateway" != "$host" ]] || return 1
  printf '%s\n' "$gateway"
}

beagle_stream_client_primary_connect_host() {
  local host local_host
  local_host="$(beagle_stream_client_local_host)"
  if [[ -n "$local_host" ]]; then
    resolve_preferred_beagle_stream_client_host "$local_host"
    return 0
  fi
  host="$(beagle_stream_client_host)"
  resolve_preferred_beagle_stream_client_host "$host"
}

beagle_stream_client_public_connect_host() {
  local host
  host="$(beagle_stream_client_host)"
  resolve_preferred_beagle_stream_client_host "$host"
}

beagle_stream_client_connect_host() {
  local host local_host public_host fallback_host api_url candidate last_candidate
  local -a candidates=()

  host="$(beagle_stream_client_host)"
  api_url="$(beagle_stream_server_api_url)"

  local_host="$(usable_beagle_stream_client_local_host 2>/dev/null || true)"
  public_host="$(beagle_stream_client_public_connect_host)"

  if [[ -n "$local_host" ]]; then
    candidates+=("$(resolve_preferred_beagle_stream_client_host "$local_host")")
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

  fallback_host="$(beagle_stream_client_gateway_fallback_host 2>/dev/null || true)"
  if [[ -n "$fallback_host" ]] && probe_stream_candidate "$fallback_host" "$api_url"; then
    printf '%s\n' "$fallback_host"
    return 0
  fi

  if [[ -n "$public_host" ]]; then
    printf '%s\n' "$public_host"
    return 0
  fi

  if [[ -n "$local_host" ]]; then
    resolve_preferred_beagle_stream_client_host "$local_host"
    return 0
  fi

  printf '%s\n' "$host"
}

ensure_beagle_stream_client_local_host_route() {
  local local_host connect_host route_line

  local_host="$(beagle_stream_client_local_host)"
  connect_host="$(beagle_stream_client_connect_host)"

  [[ -n "$local_host" && -n "$connect_host" ]] || return 1
  [[ "$local_host" != "$connect_host" ]] || return 1
  command -v ip >/dev/null 2>&1 || return 1

  if route_line="$(ip route get "$local_host" 2>/dev/null | head -n1 || true)"; then
    if grep -q " via ${connect_host} " <<<"$route_line"; then
      return 0
    fi
  fi

  sudo ip route replace "${local_host}/32" via "$connect_host" >/dev/null 2>&1 || return 1
  return 0
}
