#!/usr/bin/env bash

generate_config_dir_from_preset() {
  local preset_file="${1:-}"
  local state_dir="${2:-${PRESET_STATE_DIR:-$PRESET_STATE_DIR_DEFAULT}}"
  local installer_dir installer_script runtime_user runtime_helper

  [[ -f "$preset_file" ]] || return 1

  installer_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../installer" && pwd)"
  installer_script="$installer_dir/write-config.sh"
  runtime_helper="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/generate_config_from_preset.py"
  [[ -x "$installer_script" ]] || return 1
  [[ -f "$runtime_helper" ]] || return 1

  runtime_user="${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}"
  python3 "$runtime_helper" \
    --preset-file "$preset_file" \
    --state-dir "$state_dir" \
    --installer-script "$installer_script" \
    --runtime-user "$runtime_user"

  printf '%s\n' "$state_dir"
}

source_runtime_env_file() {
  local path="${1:-}"
  local label="${2:-config}"

  [[ -n "$path" ]] || return 1
  if [[ -r "$path" ]]; then
    # shellcheck disable=SC1090
    source "$path"
    return 0
  fi
  if [[ -e "$path" ]]; then
    echo "Skipping unreadable ${label} file: $path" >&2
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
  LOCAL_AUTH_FILE="$dir/local-auth.env"

  if [[ ! -r "$CONFIG_FILE" ]]; then
    echo "Thin-client config is not readable: $CONFIG_FILE" >&2
    return 1
  fi

  source_runtime_env_file "$CONFIG_FILE" "config"
  source_runtime_env_file "$NETWORK_FILE" "network" || true
  source_runtime_env_file "$CREDENTIALS_FILE" "credentials" || true

  apply_runtime_mode_overrides
}
