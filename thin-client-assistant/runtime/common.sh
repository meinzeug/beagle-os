#!/usr/bin/env bash
set -euo pipefail

DEFAULT_CONFIG_DIR="/etc/pve-thin-client"
LIVE_STATE_DIR="/run/live/medium/pve-thin-client/state"

find_config_dir() {
  if [[ -f "${CONFIG_DIR:-$DEFAULT_CONFIG_DIR}/thinclient.conf" ]]; then
    printf '%s\n' "${CONFIG_DIR:-$DEFAULT_CONFIG_DIR}"
    return 0
  fi

  if [[ -f "$LIVE_STATE_DIR/thinclient.conf" ]]; then
    printf '%s\n' "$LIVE_STATE_DIR"
    return 0
  fi

  return 1
}

load_runtime_config() {
  local dir
  dir="$(find_config_dir)" || {
    echo "Unable to locate thin-client config." >&2
    return 1
  }

  CONFIG_DIR="$dir"
  CONFIG_FILE="$dir/thinclient.conf"
  NETWORK_FILE="$dir/network.env"
  CREDENTIALS_FILE="$dir/credentials.env"

  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
  if [[ -f "$NETWORK_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$NETWORK_FILE"
  fi
  if [[ -f "$CREDENTIALS_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CREDENTIALS_FILE"
  fi
}

render_template() {
  local template="$1"
  local output="$template"

  output="${output//\{mode\}/${PVE_THIN_CLIENT_MODE:-}}"
  output="${output//\{username\}/${PVE_THIN_CLIENT_CONNECTION_USERNAME:-}}"
  output="${output//\{password\}/${PVE_THIN_CLIENT_CONNECTION_PASSWORD:-}}"
  output="${output//\{token\}/${PVE_THIN_CLIENT_CONNECTION_TOKEN:-}}"
  output="${output//\{host\}/${PVE_THIN_CLIENT_PROXMOX_HOST:-}}"
  output="${output//\{node\}/${PVE_THIN_CLIENT_PROXMOX_NODE:-}}"
  output="${output//\{vmid\}/${PVE_THIN_CLIENT_PROXMOX_VMID:-}}"
  output="${output//\{moonlight_host\}/${PVE_THIN_CLIENT_MOONLIGHT_HOST:-}}"
  output="${output//\{sunshine_api_url\}/${PVE_THIN_CLIENT_SUNSHINE_API_URL:-}}"

  printf '%s\n' "$output"
}

split_browser_flags() {
  local flags="${PVE_THIN_CLIENT_BROWSER_FLAGS:-}"
  if [[ -z "$flags" ]]; then
    return 0
  fi

  # shellcheck disable=SC2206
  BROWSER_FLAG_ARRAY=($flags)
}
