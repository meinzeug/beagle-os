#!/usr/bin/env bash

beagle_curl_tls_args() {
  local url="${1:-}"
  local pinned_pubkey="${2:-}"
  local ca_cert="${3:-}"
  local -a args=()

  if [[ "$url" == https://* ]]; then
    if [[ -n "$ca_cert" && -r "$ca_cert" ]]; then
      args+=(--cacert "$ca_cert")
      if [[ -n "$pinned_pubkey" ]]; then
        args+=(--pinnedpubkey "$pinned_pubkey")
      fi
    elif [[ -n "$pinned_pubkey" ]]; then
      args+=(-k --pinnedpubkey "$pinned_pubkey")
    fi
  fi

  printf '%s\n' "${args[@]}"
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
  output="${output//\{moonlight_local_host\}/${PVE_THIN_CLIENT_MOONLIGHT_LOCAL_HOST:-}}"
  output="${output//\{moonlight_port\}/${PVE_THIN_CLIENT_MOONLIGHT_PORT:-}}"
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
