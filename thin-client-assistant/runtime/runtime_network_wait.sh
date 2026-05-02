#!/usr/bin/env bash

network_is_ip_literal() {
  python3 - "$1" <<'PY'
import ipaddress
import sys

try:
    ipaddress.ip_address(sys.argv[1].strip("[]"))
except ValueError:
    raise SystemExit(1)
PY
}

extract_host_from_url() {
  python3 - "$1" <<'PY'
from urllib.parse import urlparse
import sys

text = (sys.argv[1] or "").strip()
if not text:
    raise SystemExit(0)

parsed = urlparse(text if "://" in text else f"https://{text}")
if parsed.hostname:
    print(parsed.hostname)
PY
}

dns_wait_targets() {
  local host
  local -a raw_targets=(
    "${PVE_THIN_CLIENT_BEAGLE_HOST:-}"
    "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST:-}"
    "$(extract_host_from_url "${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_API_URL:-}" 2>/dev/null || true)"
  )

  for host in "${raw_targets[@]}"; do
    [[ -n "$host" ]] || continue
    printf '%s\n' "$host"
  done | awk '!seen[$0]++'
}

host_has_ipv4() {
  local host="$1"
  local getent_bin

  [[ -n "$host" ]] || return 0
  if network_is_ip_literal "$host"; then
    return 0
  fi

  getent_bin="$(runtime_getent_bin)"
  "$getent_bin" ahostsv4 "$host" >/dev/null 2>&1
}

wait_for_default_route() {
  local iface="$1"
  local remaining ip_bin

  remaining="$(runtime_network_wait_timeout)"
  ip_bin="$(runtime_ip_bin)"
  while (( remaining > 0 )); do
    if "$ip_bin" route show default 2>/dev/null | grep -q .; then
      return 0
    fi
    ensure_static_routes "$iface"
    sleep 1
    remaining=$((remaining - 1))
  done
  return 1
}

wait_for_dns_targets() {
  local remaining target unresolved

  remaining="$(runtime_network_wait_timeout)"
  while (( remaining > 0 )); do
    unresolved=""
    while IFS= read -r target; do
      [[ -n "$target" ]] || continue
      if ! host_has_ipv4 "$target"; then
        unresolved="$target"
        break
      fi
    done < <(dns_wait_targets)

    [[ -z "$unresolved" ]] && return 0
    sleep 1
    remaining=$((remaining - 1))
  done

  return 1
}
