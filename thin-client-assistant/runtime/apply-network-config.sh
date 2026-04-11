#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_BOOTSTRAP_SERVICES_SH="${RUNTIME_BOOTSTRAP_SERVICES_SH:-$SCRIPT_DIR/runtime_bootstrap_services.sh}"
RUNTIME_PREPARE_FLOW_SH="${RUNTIME_PREPARE_FLOW_SH:-$SCRIPT_DIR/runtime_prepare_flow.sh}"
RUNTIME_NETWORK_BACKEND_SH="${RUNTIME_NETWORK_BACKEND_SH:-$SCRIPT_DIR/runtime_network_backend.sh}"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
# shellcheck disable=SC1090
source "$RUNTIME_BOOTSTRAP_SERVICES_SH"
# shellcheck disable=SC1090
source "$RUNTIME_PREPARE_FLOW_SH"
# shellcheck disable=SC1090
source "$RUNTIME_NETWORK_BACKEND_SH"

load_runtime_config_with_retry
NETWORK_WAIT_TIMEOUT="${PVE_THIN_CLIENT_NETWORK_WAIT_TIMEOUT:-20}"

pick_interface() {
  local candidate="${PVE_THIN_CLIENT_NETWORK_INTERFACE:-}"
  local iface

  if [[ -n "$candidate" && -d "/sys/class/net/$candidate" ]]; then
    printf '%s\n' "$candidate"
    return 0
  fi

  while IFS= read -r iface; do
    [[ "$iface" == "lo" ]] && continue
    case "$iface" in
      docker*|virbr*|veth*|br-*|tun*|tap*|wg*|zt*|vmnet*|tailscale*) continue ;;
    esac
    printf '%s\n' "$iface"
    return 0
  done < <(ls /sys/class/net)

  return 1
}

static_ipv4_cidr() {
  python3 - "${PVE_THIN_CLIENT_NETWORK_STATIC_ADDRESS:-}" "${PVE_THIN_CLIENT_NETWORK_STATIC_PREFIX:-24}" <<'PY'
import ipaddress
import sys

address = (sys.argv[1] or "").strip()
prefix = int((sys.argv[2] or "24").strip() or "24")

if not address:
    raise SystemExit(1)

network = ipaddress.ip_network(f"{address}/{prefix}", strict=False)
print(network.with_prefixlen)
PY
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
    "${PVE_THIN_CLIENT_PROXMOX_HOST:-}"
    "${PVE_THIN_CLIENT_MOONLIGHT_HOST:-}"
    "$(extract_host_from_url "${PVE_THIN_CLIENT_SUNSHINE_API_URL:-}" 2>/dev/null || true)"
  )

  for host in "${raw_targets[@]}"; do
    [[ -n "$host" ]] || continue
    printf '%s\n' "$host"
  done | awk '!seen[$0]++'
}

host_has_ipv4() {
  local host="$1"

  [[ -n "$host" ]] || return 0
  if is_ip_literal "$host"; then
    return 0
  fi

  getent ahostsv4 "$host" >/dev/null 2>&1
}

wait_for_default_route() {
  local iface="$1"
  local remaining="$NETWORK_WAIT_TIMEOUT"
  while (( remaining > 0 )); do
    if ip route show default 2>/dev/null | grep -q .; then
      return 0
    fi
    ensure_static_routes "$iface"
    sleep 1
    remaining=$((remaining - 1))
  done
  return 1
}

wait_for_dns_targets() {
  local remaining="$NETWORK_WAIT_TIMEOUT"
  local target unresolved

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

apply_hostname() {
  local hostname_value="${PVE_THIN_CLIENT_HOSTNAME:-}"
  [[ -n "$hostname_value" ]] || return 0

  if command -v hostnamectl >/dev/null 2>&1; then
    hostnamectl set-hostname "$hostname_value" >/dev/null 2>&1 || true
  else
    printf '%s\n' "$hostname_value" > /etc/hostname
    hostname "$hostname_value" >/dev/null 2>&1 || true
  fi
}

ensure_static_routes() {
  local iface="$1"
  local static_cidr gateway address

  [[ "${PVE_THIN_CLIENT_NETWORK_MODE:-dhcp}" == "static" ]] || return 0
  address="${PVE_THIN_CLIENT_NETWORK_STATIC_ADDRESS:-}"
  [[ -n "$address" ]] || return 0

  static_cidr="$(static_ipv4_cidr 2>/dev/null || true)"
  gateway="${PVE_THIN_CLIENT_NETWORK_GATEWAY:-}"

  if [[ -n "$static_cidr" ]]; then
    ip route replace "$static_cidr" dev "$iface" src "$address" >/dev/null 2>&1 || true
  fi
  if [[ -n "$gateway" ]]; then
    ip route replace default via "$gateway" dev "$iface" >/dev/null 2>&1 || true
  fi
}

apply_static_address() {
  local iface="$1"
  local address prefix

  [[ "${PVE_THIN_CLIENT_NETWORK_MODE:-dhcp}" == "static" ]] || return 0
  address="${PVE_THIN_CLIENT_NETWORK_STATIC_ADDRESS:-}"
  prefix="${PVE_THIN_CLIENT_NETWORK_STATIC_PREFIX:-24}"
  [[ -n "$address" ]] || return 0

  ip link set "$iface" up >/dev/null 2>&1 || true
  ip addr replace "${address}/${prefix}" dev "$iface" >/dev/null 2>&1 || true
}

main() {
  local iface

  iface="$(pick_interface)" || exit 0
  if have_networkmanager; then
    write_nmconnection "$iface"
    restart_networkmanager
  else
    write_network_file "$iface"
    restart_networkd
  fi
  apply_static_address "$iface"
  ensure_static_routes "$iface"
  apply_hostname
  write_resolv_conf || true
  wait_for_default_route "$iface" || true
  wait_for_dns_targets || true
}

main "$@"
