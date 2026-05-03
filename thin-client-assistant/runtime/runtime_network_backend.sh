#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_NETWORK_CONFIG_FILES_SH="${RUNTIME_NETWORK_CONFIG_FILES_SH:-$SCRIPT_DIR/runtime_network_config_files.sh}"
# shellcheck disable=SC1090
source "$RUNTIME_NETWORK_CONFIG_FILES_SH"

restart_networkd() {
  local systemctl_bin networkctl_bin
  systemctl_bin="$(runtime_systemctl_bin)"
  networkctl_bin="${BEAGLE_NETWORKCTL_BIN:-networkctl}"

  if command -v "$systemctl_bin" >/dev/null 2>&1 && "$systemctl_bin" is-enabled systemd-networkd.service >/dev/null 2>&1; then
    "$systemctl_bin" restart systemd-networkd.service >/dev/null 2>&1 || true
  elif command -v "$systemctl_bin" >/dev/null 2>&1 && "$systemctl_bin" is-active systemd-networkd.service >/dev/null 2>&1; then
    "$systemctl_bin" restart systemd-networkd.service >/dev/null 2>&1 || true
  fi

  if command -v "$networkctl_bin" >/dev/null 2>&1; then
    "$networkctl_bin" reload >/dev/null 2>&1 || true
  fi
}

refresh_networkd_link() {
  local iface="$1"
  local networkctl_bin="${BEAGLE_NETWORKCTL_BIN:-networkctl}"

  [[ -n "$iface" ]] || return 0
  command -v "$networkctl_bin" >/dev/null 2>&1 || return 0
  "$networkctl_bin" reconfigure "$iface" >/dev/null 2>&1 || true
  "$networkctl_bin" renew "$iface" >/dev/null 2>&1 || true
}

acquire_dhcp_ipv4_fallback() {
  local iface="$1"
  local dhclient_bin="${BEAGLE_DHCLIENT_BIN:-dhclient}"
  local udhcpc_bin="${BEAGLE_UDHCPC_BIN:-udhcpc}"
  local busybox_bin="${BEAGLE_BUSYBOX_BIN:-busybox}"

  [[ -n "$iface" ]] || return 1
  ip link set "$iface" up >/dev/null 2>&1 || true

  if command -v "$dhclient_bin" >/dev/null 2>&1; then
    "$dhclient_bin" -4 -r "$iface" >/dev/null 2>&1 || true
    "$dhclient_bin" -4 -1 -v "$iface" >/dev/null 2>&1 && return 0
  fi

  if command -v "$udhcpc_bin" >/dev/null 2>&1; then
    "$udhcpc_bin" -i "$iface" -n -q -t 5 -T 3 >/dev/null 2>&1 && return 0
  fi

  if command -v "$busybox_bin" >/dev/null 2>&1 && "$busybox_bin" --list 2>/dev/null | grep -qx udhcpc; then
    "$busybox_bin" udhcpc -i "$iface" -n -q -t 5 -T 3 >/dev/null 2>&1 && return 0
  fi

  return 1
}

have_networkmanager() {
  local nmcli_bin="${BEAGLE_NMCLI_BIN:-nmcli}"
  if command -v "$nmcli_bin" >/dev/null 2>&1; then
    return 0
  fi
  beagle_unit_file_present "NetworkManager.service"
}

restart_networkmanager() {
  local systemctl_bin nmcli_bin
  systemctl_bin="$(runtime_systemctl_bin)"
  nmcli_bin="${BEAGLE_NMCLI_BIN:-nmcli}"

  if command -v "$systemctl_bin" >/dev/null 2>&1; then
    "$systemctl_bin" enable NetworkManager.service >/dev/null 2>&1 || true
    "$systemctl_bin" restart NetworkManager.service >/dev/null 2>&1 || true
  fi

  if command -v "$nmcli_bin" >/dev/null 2>&1; then
    "$nmcli_bin" connection reload >/dev/null 2>&1 || true
    "$nmcli_bin" connection up beagle-thinclient >/dev/null 2>&1 || true
  fi
}
