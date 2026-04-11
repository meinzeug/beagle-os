#!/usr/bin/env bash

load_runtime_config_with_retry() {
  local attempts interval attempt
  attempts="${PVE_THIN_CLIENT_CONFIG_RETRY_ATTEMPTS:-30}"
  interval="${PVE_THIN_CLIENT_CONFIG_RETRY_INTERVAL:-1}"

  for attempt in $(seq 1 "$attempts"); do
    if load_runtime_config >/dev/null 2>&1; then
      return 0
    fi
    sleep "$interval"
  done

  load_runtime_config
}

detect_runtime_boot_mode() {
  local boot_mode_bin
  boot_mode_bin="$(runtime_boot_mode_bin)"
  "$boot_mode_bin" 2>/dev/null || printf 'runtime'
}

plymouth_status() {
  local message="$1"
  local plymouth_bin="${BEAGLE_PLYMOUTH_BIN:-plymouth}"

  command -v "$plymouth_bin" >/dev/null 2>&1 || return 0
  "$plymouth_bin" --ping >/dev/null 2>&1 || return 0
  "$plymouth_bin" display-message --text="$message" >/dev/null 2>&1 || true
}

ensure_kiosk_runtime() {
  local kiosk_install_bin="${BEAGLE_KIOSK_INSTALL_BIN:-/usr/local/sbin/beagle-kiosk-install}"
  local boot_mode="${1:-${BOOT_MODE:-}}"

  [[ "$boot_mode" == "runtime" ]] || return 0
  [[ "${PVE_THIN_CLIENT_MODE:-MOONLIGHT}" == "KIOSK" ]] || return 0
  command -v "$kiosk_install_bin" >/dev/null 2>&1 || return 0

  plymouth_status "Preparing Beagle OS Gaming..."
  if ! "$kiosk_install_bin" --ensure >/dev/null 2>&1; then
    beagle_log_event "prepare-runtime.kiosk-error" "kiosk installation/update failed"
    return 1
  fi

  beagle_log_event "prepare-runtime.kiosk-ready" "beagle-kiosk ensured"
}

run_optional_runtime_hook() {
  local hook_path="${1:-}"
  local status_message="${2:-}"

  [[ -n "$hook_path" ]] || return 0
  [[ -x "$hook_path" ]] || return 0

  if [[ -n "$status_message" ]]; then
    plymouth_status "$status_message"
  fi
  "$hook_path" >/dev/null 2>&1 || true
}
