#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_SYSTEMD_BOOTSTRAP_SH="${RUNTIME_SYSTEMD_BOOTSTRAP_SH:-$SCRIPT_DIR/runtime_systemd_bootstrap.sh}"
RUNTIME_SSH_HOST_KEYS_SH="${RUNTIME_SSH_HOST_KEYS_SH:-$SCRIPT_DIR/runtime_ssh_host_keys.sh}"
RUNTIME_SSH_SERVICE_CONFIG_SH="${RUNTIME_SSH_SERVICE_CONFIG_SH:-$SCRIPT_DIR/runtime_ssh_service_config.sh}"
# shellcheck disable=SC1090
source "$RUNTIME_SYSTEMD_BOOTSTRAP_SH"
# shellcheck disable=SC1090
source "$RUNTIME_SSH_HOST_KEYS_SH"
# shellcheck disable=SC1090
source "$RUNTIME_SSH_SERVICE_CONFIG_SH"

ensure_runtime_ssh_host_keys() {
  local live_state_dir="${1:-}"
  local persistent_key_dir=""

  if [[ -z "$live_state_dir" ]]; then
    live_state_dir="$(find_live_state_dir || true)"
  fi
  if [[ -n "$live_state_dir" ]]; then
    remount_live_state_writable "$live_state_dir" || true
    persistent_key_dir="$(runtime_persistent_ssh_key_dir "$live_state_dir" || true)"
    install -d -m 0700 "$persistent_key_dir"
  fi

  copy_persistent_ssh_keys_to_runtime "$persistent_key_dir"
  remove_empty_runtime_ssh_keys
  generate_runtime_ssh_host_keys_if_missing
  persist_runtime_ssh_host_keys "$persistent_key_dir"
  runtime_start_service_if_valid "$(runtime_sshd_config_path)"
}
