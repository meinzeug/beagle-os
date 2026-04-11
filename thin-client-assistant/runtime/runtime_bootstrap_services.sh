#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_SYSTEMD_BOOTSTRAP_SH="${RUNTIME_SYSTEMD_BOOTSTRAP_SH:-$SCRIPT_DIR/runtime_systemd_bootstrap.sh}"
RUNTIME_SSH_HOST_KEYS_SH="${RUNTIME_SSH_HOST_KEYS_SH:-$SCRIPT_DIR/runtime_ssh_host_keys.sh}"
# shellcheck disable=SC1090
source "$RUNTIME_SYSTEMD_BOOTSTRAP_SH"
# shellcheck disable=SC1090
source "$RUNTIME_SSH_HOST_KEYS_SH"

runtime_sshd_bin() {
  printf '%s\n' "${BEAGLE_SSHD_BIN:-sshd}"
}

runtime_sshd_service_name() {
  printf '%s\n' "${PVE_THIN_CLIENT_SSH_SERVICE_NAME:-ssh.service}"
}

runtime_sshd_config_path() {
  printf '%s\n' "${PVE_THIN_CLIENT_SSHD_CONFIG:-/etc/ssh/sshd_config}"
}

managed_ssh_begin_marker() {
  printf '%s\n' "# --- pve-thin-client managed ssh begin ---"
}

managed_ssh_end_marker() {
  printf '%s\n' "# --- pve-thin-client managed ssh end ---"
}

strip_managed_ssh_block() {
  local src_file="$1"
  local begin_marker="${2:-$(managed_ssh_begin_marker)}"
  local end_marker="${3:-$(managed_ssh_end_marker)}"

  awk -v begin="$begin_marker" -v end="$end_marker" '
    $0 == begin {skip = 1; next}
    $0 == end {skip = 0; next}
    !skip {print}
  ' "$src_file"
}

runtime_restart_service_if_valid() {
  local sshd_config="${1:-$(runtime_sshd_config_path)}"
  local systemctl_bin sshd_bin service_name

  systemctl_bin="$(runtime_systemctl_bin)"
  sshd_bin="$(runtime_sshd_bin)"
  service_name="$(runtime_sshd_service_name)"

  if command -v "$sshd_bin" >/dev/null 2>&1 && "$sshd_bin" -t -f "$sshd_config" >/dev/null 2>&1; then
    "$systemctl_bin" reset-failed "$service_name" >/dev/null 2>&1 || true
    "$systemctl_bin" restart "$service_name" >/dev/null 2>&1 || true
  fi
}

runtime_start_service_if_valid() {
  local sshd_config="${1:-$(runtime_sshd_config_path)}"
  local systemctl_bin sshd_bin service_name

  systemctl_bin="$(runtime_systemctl_bin)"
  sshd_bin="$(runtime_sshd_bin)"
  service_name="$(runtime_sshd_service_name)"

  if command -v "$sshd_bin" >/dev/null 2>&1 && "$sshd_bin" -t -f "$sshd_config" >/dev/null 2>&1; then
    "$systemctl_bin" reset-failed "$service_name" >/dev/null 2>&1 || true
    "$systemctl_bin" start "$service_name" >/dev/null 2>&1 || true
  fi
}

apply_runtime_ssh_config() {
  local sshd_config begin_marker end_marker temp_file

  sshd_config="$(runtime_sshd_config_path)"
  begin_marker="$(managed_ssh_begin_marker)"
  end_marker="$(managed_ssh_end_marker)"

  [[ -f "$sshd_config" ]] || return 0

  temp_file="$(mktemp)"
  strip_managed_ssh_block "$sshd_config" "$begin_marker" "$end_marker" >"$temp_file" || cp -f "$sshd_config" "$temp_file"

  {
    cat "$temp_file"
    printf '\n%s\n' "$begin_marker"
    printf 'PasswordAuthentication yes\n'
    printf 'KbdInteractiveAuthentication yes\n'
    printf 'PermitEmptyPasswords no\n'
    printf 'PermitRootLogin no\n'
    printf '%s\n' "$end_marker"
  } >"$sshd_config"

  rm -f "$temp_file"
  chmod 0600 "$sshd_config" >/dev/null 2>&1 || true

  runtime_restart_service_if_valid "$sshd_config"
}

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
