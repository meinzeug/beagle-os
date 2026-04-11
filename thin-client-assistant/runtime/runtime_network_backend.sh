#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_NETWORK_CONFIG_FILES_SH="${RUNTIME_NETWORK_CONFIG_FILES_SH:-$SCRIPT_DIR/runtime_network_config_files.sh}"
# shellcheck disable=SC1090
source "$RUNTIME_NETWORK_CONFIG_FILES_SH"

restart_networkd() {
  local systemctl_bin
  systemctl_bin="$(runtime_systemctl_bin)"

  if command -v "$systemctl_bin" >/dev/null 2>&1 && "$systemctl_bin" is-enabled systemd-networkd.service >/dev/null 2>&1; then
    "$systemctl_bin" restart systemd-networkd.service >/dev/null 2>&1 || true
  elif command -v "$systemctl_bin" >/dev/null 2>&1 && "$systemctl_bin" is-active systemd-networkd.service >/dev/null 2>&1; then
    "$systemctl_bin" restart systemd-networkd.service >/dev/null 2>&1 || true
  fi
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
