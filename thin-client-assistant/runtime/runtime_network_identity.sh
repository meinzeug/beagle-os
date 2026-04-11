#!/usr/bin/env bash

runtime_sys_class_net_dir() {
  printf '%s\n' "${BEAGLE_SYS_CLASS_NET_DIR:-/sys/class/net}"
}

runtime_ip_bin() {
  printf '%s\n' "${BEAGLE_IP_BIN:-ip}"
}

runtime_hostnamectl_bin() {
  printf '%s\n' "${BEAGLE_HOSTNAMECTL_BIN:-hostnamectl}"
}

runtime_hostname_bin() {
  printf '%s\n' "${BEAGLE_HOSTNAME_BIN:-hostname}"
}

runtime_hostname_file() {
  printf '%s\n' "${PVE_THIN_CLIENT_HOSTNAME_FILE:-/etc/hostname}"
}

pick_interface() {
  local candidate="${PVE_THIN_CLIENT_NETWORK_INTERFACE:-}"
  local iface sys_class_net

  sys_class_net="$(runtime_sys_class_net_dir)"
  if [[ -n "$candidate" && -d "$sys_class_net/$candidate" ]]; then
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
  done < <(ls "$sys_class_net")

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

apply_hostname() {
  local hostname_value="${PVE_THIN_CLIENT_HOSTNAME:-}"
  local hostnamectl_bin hostname_bin hostname_file

  [[ -n "$hostname_value" ]] || return 0
  hostnamectl_bin="$(runtime_hostnamectl_bin)"
  hostname_bin="$(runtime_hostname_bin)"
  hostname_file="$(runtime_hostname_file)"

  if command -v "$hostnamectl_bin" >/dev/null 2>&1; then
    "$hostnamectl_bin" set-hostname "$hostname_value" >/dev/null 2>&1 || true
  else
    printf '%s\n' "$hostname_value" >"$hostname_file"
    "$hostname_bin" "$hostname_value" >/dev/null 2>&1 || true
  fi
}

ensure_static_routes() {
  local iface="$1"
  local static_cidr gateway address ip_bin

  [[ "${PVE_THIN_CLIENT_NETWORK_MODE:-dhcp}" == "static" ]] || return 0
  address="${PVE_THIN_CLIENT_NETWORK_STATIC_ADDRESS:-}"
  [[ -n "$address" ]] || return 0

  ip_bin="$(runtime_ip_bin)"
  static_cidr="$(static_ipv4_cidr 2>/dev/null || true)"
  gateway="${PVE_THIN_CLIENT_NETWORK_GATEWAY:-}"

  if [[ -n "$static_cidr" ]]; then
    "$ip_bin" route replace "$static_cidr" dev "$iface" src "$address" >/dev/null 2>&1 || true
  fi
  if [[ -n "$gateway" ]]; then
    "$ip_bin" route replace default via "$gateway" dev "$iface" >/dev/null 2>&1 || true
  fi
}

apply_static_address() {
  local iface="$1"
  local address prefix ip_bin

  [[ "${PVE_THIN_CLIENT_NETWORK_MODE:-dhcp}" == "static" ]] || return 0
  address="${PVE_THIN_CLIENT_NETWORK_STATIC_ADDRESS:-}"
  prefix="${PVE_THIN_CLIENT_NETWORK_STATIC_PREFIX:-24}"
  [[ -n "$address" ]] || return 0

  ip_bin="$(runtime_ip_bin)"
  "$ip_bin" link set "$iface" up >/dev/null 2>&1 || true
  "$ip_bin" addr replace "${address}/${prefix}" dev "$iface" >/dev/null 2>&1 || true
}
