#!/usr/bin/env bash

runtime_system_config_dir() {
  printf '%s\n' "${PVE_THIN_CLIENT_SYSTEM_CONFIG_DIR:-/etc/pve-thin-client}"
}

runtime_config_sync_files() {
  printf '%s\n' \
    thinclient.conf \
    network.env \
    credentials.env \
    local-auth.env \
    install-manifest.json
}

runtime_set_config_dir_paths() {
  local config_dir="${1:-}"

  [[ -n "$config_dir" ]] || return 1

  CONFIG_DIR="$config_dir"
  CONFIG_FILE="$config_dir/thinclient.conf"
  NETWORK_ENV_FILE="$config_dir/network.env"
  CREDENTIALS_FILE="$config_dir/credentials.env"
  LOCAL_AUTH_FILE="$config_dir/local-auth.env"
}

runtime_relax_config_permissions() {
  local target_dir="${1:-}"
  local file=""

  [[ -n "$target_dir" ]] || return 1
  for file in thinclient.conf network.env install-manifest.json; do
    [[ -f "$target_dir/$file" ]] || continue
    if [[ "$file" == "network.env" ]] && grep -q '^PVE_THIN_CLIENT_WIFI_PSK=' "$target_dir/$file" 2>/dev/null; then
      chmod 0600 "$target_dir/$file" >/dev/null 2>&1 || true
    else
      chmod 0644 "$target_dir/$file" >/dev/null 2>&1 || true
    fi
  done
}

sync_runtime_config_to_system() {
  local source_dir="${1:-${CONFIG_DIR:-}}"
  local target_dir="${2:-$(runtime_system_config_dir)}"
  local file=""
  local copied=0

  [[ -n "$source_dir" ]] || return 0
  [[ "$source_dir" != "$target_dir" ]] || return 0
  [[ -d "$source_dir" ]] || return 0

  install -d -m 0755 "$target_dir"
  while IFS= read -r file; do
    if [[ -f "$source_dir/$file" ]]; then
      install -m 0600 "$source_dir/$file" "$target_dir/$file"
      copied=1
    fi
  done < <(runtime_config_sync_files)

  if [[ "$copied" == "1" ]]; then
    runtime_set_config_dir_paths "$target_dir"
  fi
  runtime_relax_config_permissions "$target_dir"
}

remount_live_state_writable() {
  local state_dir="${1:-}"
  local mount_target mount_opts

  [[ -n "$state_dir" ]] || return 1
  mount_target="$(findmnt -nro TARGET --target "$state_dir" 2>/dev/null | head -n1)"
  [[ -n "$mount_target" ]] || return 1
  mount_opts="$(findmnt -nro OPTIONS --target "$state_dir" 2>/dev/null || true)"
  if grep -qw rw <<<"$mount_opts" && ! grep -qw ro <<<"$mount_opts"; then
    return 0
  fi
  mount -o remount,rw "$mount_target" >/dev/null 2>&1
}

persist_runtime_config_to_live_state() {
  local source_dir="${1:-${CONFIG_DIR:-$(runtime_system_config_dir)}}"
  local live_state_dir="${2:-}"
  local file=""
  local copied=0

  [[ -d "$source_dir" ]] || return 0
  if [[ -z "$live_state_dir" ]]; then
    live_state_dir="$(find_live_state_dir || true)"
  fi
  [[ -n "$live_state_dir" ]] || return 0
  [[ "$live_state_dir" != "$source_dir" ]] || return 0
  remount_live_state_writable "$live_state_dir" || return 0

  install -d -m 0755 "$live_state_dir"
  while IFS= read -r file; do
    if [[ -f "$source_dir/$file" ]]; then
      install -m 0600 "$source_dir/$file" "$live_state_dir/$file"
      copied=1
    fi
  done < <(runtime_config_sync_files)

  if [[ "$copied" == "1" ]]; then
    runtime_relax_config_permissions "$live_state_dir"
  fi
}
