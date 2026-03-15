#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_runtime_config

RUNTIME_NETWORK_DIR="${RUNTIME_NETWORK_DIR:-/run/systemd/network}"
NETWORK_FILE="$RUNTIME_NETWORK_DIR/90-pve-thin-client.network"

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

write_network_file() {
  local iface="$1"
  install -d -m 0755 "$RUNTIME_NETWORK_DIR"

  {
    echo "[Match]"
    echo "Name=$iface"
    echo
    echo "[Network]"
    if [[ "${PVE_THIN_CLIENT_NETWORK_MODE:-dhcp}" == "static" ]]; then
      echo "Address=${PVE_THIN_CLIENT_NETWORK_STATIC_ADDRESS}/${PVE_THIN_CLIENT_NETWORK_STATIC_PREFIX:-24}"
      [[ -n "${PVE_THIN_CLIENT_NETWORK_GATEWAY:-}" ]] && echo "Gateway=${PVE_THIN_CLIENT_NETWORK_GATEWAY}"
      for dns in ${PVE_THIN_CLIENT_NETWORK_DNS_SERVERS:-}; do
        echo "DNS=$dns"
      done
      echo "DHCP=no"
    else
      echo "DHCP=yes"
    fi
  } >"$NETWORK_FILE"
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

restart_networkd() {
  if command -v systemctl >/dev/null 2>&1 && systemctl is-enabled systemd-networkd.service >/dev/null 2>&1; then
    systemctl restart systemd-networkd.service >/dev/null 2>&1 || true
  elif command -v systemctl >/dev/null 2>&1 && systemctl is-active systemd-networkd.service >/dev/null 2>&1; then
    systemctl restart systemd-networkd.service >/dev/null 2>&1 || true
  fi
}

main() {
  local iface

  iface="$(pick_interface)" || exit 0
  write_network_file "$iface"
  apply_hostname
  restart_networkd
}

main "$@"
