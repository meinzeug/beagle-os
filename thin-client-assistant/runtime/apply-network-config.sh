#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_BOOTSTRAP_SERVICES_SH="${RUNTIME_BOOTSTRAP_SERVICES_SH:-$SCRIPT_DIR/runtime_bootstrap_services.sh}"
RUNTIME_PREPARE_FLOW_SH="${RUNTIME_PREPARE_FLOW_SH:-$SCRIPT_DIR/runtime_prepare_flow.sh}"
RUNTIME_NETWORK_BACKEND_SH="${RUNTIME_NETWORK_BACKEND_SH:-$SCRIPT_DIR/runtime_network_backend.sh}"
RUNTIME_NETWORK_RUNTIME_SH="${RUNTIME_NETWORK_RUNTIME_SH:-$SCRIPT_DIR/runtime_network_runtime.sh}"
RUNTIME_DEBUG_REPORT_SH="${RUNTIME_DEBUG_REPORT_SH:-$SCRIPT_DIR/runtime_debug_report.sh}"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
# shellcheck disable=SC1090
source "$RUNTIME_BOOTSTRAP_SERVICES_SH"
# shellcheck disable=SC1090
source "$RUNTIME_PREPARE_FLOW_SH"
# shellcheck disable=SC1090
source "$RUNTIME_NETWORK_BACKEND_SH"
# shellcheck disable=SC1090
source "$RUNTIME_NETWORK_RUNTIME_SH"
# shellcheck disable=SC1090
source "$RUNTIME_DEBUG_REPORT_SH"

load_runtime_config_with_retry

network_runtime_ready() {
  local iface="$1"
  local current_ip=""

  [[ -n "$iface" ]] || return 1
  current_ip="$(current_ipv4_address "$iface" 2>/dev/null || true)"
  [[ -n "$current_ip" ]] || return 1
  wait_for_default_route "$iface" || return 1
  wait_for_dns_targets || return 1
}

main() {
  local iface dhcp_ipv4=""

  iface="$(pick_interface)" || exit 0
  if [[ "${PVE_THIN_CLIENT_NETWORK_MODE:-dhcp}" == "dhcp" ]] && network_runtime_ready "$iface"; then
    beagle_log_event "network.reuse" "iface=${iface} mode=dhcp ipv4=$(current_ipv4_address "$iface" 2>/dev/null || true)"
    write_runtime_debug_report "network-applied" "$iface" || true
    return 0
  fi
  if have_networkmanager; then
    write_networkmanager_no_random_mac_config || true
    write_nmconnection "$iface"
    restart_networkmanager
  else
    if [[ "${PVE_THIN_CLIENT_NETWORK_TYPE:-ethernet}" == "wifi" ]]; then
      write_wifi_wpa_supplicant_config
      start_wifi_wpa_supplicant "$iface" || beagle_log_event "network.wifi-error" "wpa_supplicant failed for $iface"
    fi
    write_network_file "$iface"
    restart_networkd
    refresh_networkd_link "$iface"
  fi
  apply_static_address "$iface"
  ensure_static_routes "$iface"
  apply_hostname
  write_resolv_conf || true
  if [[ "${PVE_THIN_CLIENT_NETWORK_MODE:-dhcp}" == "dhcp" ]]; then
    dhcp_ipv4="$(wait_for_ipv4_address "$iface" 2>/dev/null || true)"
    if [[ -z "$dhcp_ipv4" ]]; then
      beagle_log_event "network.ipv4-timeout" "iface=${iface} mode=dhcp"
      if ! have_networkmanager; then
        ip link set "$iface" down >/dev/null 2>&1 || true
        sleep 1
        ip link set "$iface" up >/dev/null 2>&1 || true
        restart_networkd
        refresh_networkd_link "$iface"
        dhcp_ipv4="$(wait_for_ipv4_address "$iface" 2>/dev/null || true)"
      fi
    fi
    if [[ -z "$dhcp_ipv4" ]]; then
      beagle_log_event "network.dhcp-client-fallback" "iface=${iface} mode=dhcp"
      acquire_dhcp_ipv4_fallback "$iface" || true
      dhcp_ipv4="$(wait_for_ipv4_address "$iface" 2>/dev/null || true)"
    fi
    if [[ -z "$dhcp_ipv4" ]]; then
      write_runtime_debug_report "network-ipv4-failed" "$iface" || true
      return 1
    fi
  fi
  wait_for_default_route "$iface" || {
    write_runtime_debug_report "network-route-failed" "$iface" || true
    return 1
  }
  wait_for_dns_targets || {
    write_runtime_debug_report "network-dns-failed" "$iface" || true
    return 1
  }
  write_runtime_debug_report "network-applied" "$iface" || true
}

main "$@"
