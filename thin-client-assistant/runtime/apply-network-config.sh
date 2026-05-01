#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_BOOTSTRAP_SERVICES_SH="${RUNTIME_BOOTSTRAP_SERVICES_SH:-$SCRIPT_DIR/runtime_bootstrap_services.sh}"
RUNTIME_PREPARE_FLOW_SH="${RUNTIME_PREPARE_FLOW_SH:-$SCRIPT_DIR/runtime_prepare_flow.sh}"
RUNTIME_NETWORK_BACKEND_SH="${RUNTIME_NETWORK_BACKEND_SH:-$SCRIPT_DIR/runtime_network_backend.sh}"
RUNTIME_NETWORK_RUNTIME_SH="${RUNTIME_NETWORK_RUNTIME_SH:-$SCRIPT_DIR/runtime_network_runtime.sh}"
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

load_runtime_config_with_retry

main() {
  local iface

  iface="$(pick_interface)" || exit 0
  if have_networkmanager; then
    write_nmconnection "$iface"
    restart_networkmanager
  else
    if [[ "${PVE_THIN_CLIENT_NETWORK_TYPE:-ethernet}" == "wifi" ]]; then
      write_wifi_wpa_supplicant_config
      start_wifi_wpa_supplicant "$iface" || beagle_log_event "network.wifi-error" "wpa_supplicant failed for $iface"
    fi
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
