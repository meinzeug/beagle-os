#!/usr/bin/env bash

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

rewrite_url_host() {
  python3 - "$1" "$2" <<'PY'
from urllib.parse import urlsplit, urlunsplit
import sys

url = (sys.argv[1] or "").strip()
host = (sys.argv[2] or "").strip()
if not url or not host:
    raise SystemExit(1)

parts = urlsplit(url)
if not parts.scheme or not parts.netloc:
    raise SystemExit(1)

userinfo = ""
if "@" in parts.netloc:
    userinfo, _, _ = parts.netloc.rpartition("@")
    userinfo = f"{userinfo}@"

port = f":{parts.port}" if parts.port else ""
netloc = f"{userinfo}{host}{port}"
print(urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment)))
PY
}

sunshine_api_url() {
  local configured host
  configured="$(render_template "${PVE_THIN_CLIENT_SUNSHINE_API_URL:-}" 2>/dev/null || true)"
  if [[ -n "$configured" ]]; then
    printf '%s\n' "$configured"
    return 0
  fi

  host="$(moonlight_host)"
  if [[ -n "$host" ]]; then
    printf 'https://%s:47990\n' "$host"
  fi
}

probe_stream_target() {
  local api_url host port connect_host effective_api_url
  local -a curl_opts tls_args
  local username password

  api_url="$1"
  host="$2"
  port="$(moonlight_port)"
  connect_host="${3:-$(moonlight_primary_connect_host)}"
  effective_api_url="$api_url"
  curl_opts=(-fsS -o /dev/null --connect-timeout 2 --max-time 4)
  username="${PVE_THIN_CLIENT_SUNSHINE_USERNAME:-}"
  password="${PVE_THIN_CLIENT_SUNSHINE_PASSWORD:-}"
  if prefer_ipv4 && [[ -n "$connect_host" ]] && [[ "$connect_host" != "$host" ]]; then
    curl_opts+=(-4)
    if [[ -n "$api_url" ]]; then
      effective_api_url="$(rewrite_url_host "$api_url" "$connect_host" 2>/dev/null || printf '%s\n' "$api_url")"
    fi
  fi
  if [[ -n "$username" && -n "$password" ]]; then
    curl_opts+=(--user "${username}:${password}")
  fi
  if [[ -n "$effective_api_url" ]]; then
    mapfile -t tls_args < <(beagle_curl_tls_args "$effective_api_url" "${PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY:-}" "${PVE_THIN_CLIENT_SUNSHINE_CA_CERT:-}")
    curl_opts+=("${tls_args[@]}")
    if [[ -n "$effective_api_url" ]]; then
      curl "${curl_opts[@]}" "${effective_api_url%/}/api/apps" && return 0
    fi
  fi

  [[ -n "$host" ]] || return 1

  if [[ -n "$port" ]]; then
    python3 - "$host" "$port" "$connect_host" <<'PY' && return 0
import socket
import sys

candidates = [value for value in sys.argv[1:] if value]
port = int(candidates[1]) if len(candidates) > 1 else 0
hosts = [candidates[0]]
if len(candidates) > 2 and candidates[2] not in hosts:
    hosts.insert(0, candidates[2])

for host in hosts:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        continue
    for family, socktype, proto, _, sockaddr in infos:
        try:
            with socket.socket(family, socktype, proto) as sock:
                sock.settimeout(2.5)
                sock.connect(sockaddr)
            raise SystemExit(0)
        except OSError:
            continue

raise SystemExit(1)
PY
  fi

  return 1
}

probe_stream_candidate() {
  local candidate api_url effective_api_url

  candidate="$1"
  api_url="${2:-}"
  [[ -n "$candidate" ]] || return 1

  effective_api_url="$api_url"
  if [[ -n "$effective_api_url" ]]; then
    effective_api_url="$(rewrite_url_host "$effective_api_url" "$candidate" 2>/dev/null || printf '%s\n' "$effective_api_url")"
  fi

  probe_stream_target "$effective_api_url" "$candidate" "$candidate"
}

effective_sunshine_api_url() {
  local api_url host connect_host rewritten

  api_url="$1"
  host="$2"
  connect_host="${3:-}"

  [[ -n "$api_url" ]] || return 1
  [[ -n "$host" ]] || {
    printf '%s\n' "$api_url"
    return 0
  }

  if prefer_ipv4 && [[ -n "$connect_host" ]] && [[ "$connect_host" != "$host" ]]; then
    rewritten="$(rewrite_url_host "$api_url" "$connect_host" 2>/dev/null || true)"
    if [[ -n "$rewritten" ]]; then
      printf '%s\n' "$rewritten"
      return 0
    fi
  fi

  printf '%s\n' "$api_url"
}

selected_sunshine_api_url() {
  local api_url host connect_host effective_api_url

  api_url="$(sunshine_api_url)"
  host="$(moonlight_host)"
  connect_host="$(moonlight_connect_host)"
  effective_api_url="$(effective_sunshine_api_url "$api_url" "$host" "$connect_host" 2>/dev/null || printf '%s\n' "$api_url")"
  printf '%s\n' "$effective_api_url"
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

moonlight_target_reachable() {
  local host connect_host api_url

  host="$(moonlight_host)"
  connect_host="$(moonlight_connect_host)"
  api_url="$(selected_sunshine_api_url)"
  probe_stream_target "$api_url" "$host" "$connect_host"
}

wait_for_stream_target() {
  local attempts delay attempt host connect_host port

  attempts="${PVE_THIN_CLIENT_STREAM_WAIT_RETRIES:-15}"
  delay="${PVE_THIN_CLIENT_STREAM_WAIT_DELAY:-2}"
  host="$(moonlight_host)"
  connect_host="$(moonlight_connect_host)"
  port="$(moonlight_port)"

  for attempt in $(seq 1 "$attempts"); do
    if moonlight_target_reachable; then
      beagle_log_event "moonlight.reachable" "host=${host} connect_host=${connect_host:-$host} port=${port:-default} attempt=${attempt}"
      return 0
    fi
    beagle_log_event "moonlight.waiting" "host=${host} connect_host=${connect_host:-$host} port=${port:-default} attempt=${attempt}/${attempts}"
    [[ "$attempt" -lt "$attempts" ]] || break
    sleep "$delay"
  done

  return 1
}
