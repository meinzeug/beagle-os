#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_SYSTEMD_BOOTSTRAP_SH="${RUNTIME_SYSTEMD_BOOTSTRAP_SH:-$SCRIPT_DIR/runtime_systemd_bootstrap.sh}"
# shellcheck disable=SC1090
source "$RUNTIME_SYSTEMD_BOOTSTRAP_SH"

runtime_sshd_bin() {
  printf '%s\n' "${BEAGLE_SSHD_BIN:-sshd}"
}

runtime_ssh_keygen_bin() {
  printf '%s\n' "${BEAGLE_SSH_KEYGEN_BIN:-ssh-keygen}"
}

runtime_sshd_service_name() {
  printf '%s\n' "${PVE_THIN_CLIENT_SSH_SERVICE_NAME:-ssh.service}"
}

runtime_sshd_config_path() {
  printf '%s\n' "${PVE_THIN_CLIENT_SSHD_CONFIG:-/etc/ssh/sshd_config}"
}

runtime_ssh_dir() {
  printf '%s\n' "${PVE_THIN_CLIENT_SSH_DIR:-/etc/ssh}"
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

runtime_persistent_ssh_key_dir() {
  local live_state_dir="${1:-}"
  if [[ -z "$live_state_dir" ]]; then
    live_state_dir="$(find_live_state_dir || true)"
  fi
  [[ -n "$live_state_dir" ]] || return 1
  printf '%s\n' "$live_state_dir/ssh-hostkeys"
}

copy_persistent_ssh_keys_to_runtime() {
  local persistent_key_dir="${1:-}"
  local ssh_dir key_path base_name

  [[ -n "$persistent_key_dir" ]] || return 0
  ssh_dir="$(runtime_ssh_dir)"

  for key_path in "$persistent_key_dir"/ssh_host_*_key; do
    [[ -s "$key_path" ]] || continue
    base_name="$(basename "$key_path")"
    install -m 0600 "$key_path" "$ssh_dir/$base_name"
    if [[ -s "$key_path.pub" ]]; then
      install -m 0644 "$key_path.pub" "$ssh_dir/$base_name.pub"
    fi
  done
}

remove_empty_runtime_ssh_keys() {
  local ssh_dir key_path
  ssh_dir="$(runtime_ssh_dir)"

  for key_path in "$ssh_dir"/ssh_host_*_key "$ssh_dir"/ssh_host_*_key.pub; do
    [[ -e "$key_path" ]] || continue
    [[ -s "$key_path" ]] && continue
    rm -f "$key_path"
  done
}

runtime_ssh_host_keys_present() {
  local ssh_dir key_path
  ssh_dir="$(runtime_ssh_dir)"

  for key_path in "$ssh_dir"/ssh_host_*_key; do
    [[ -s "$key_path" ]] || continue
    return 0
  done

  return 1
}

generate_runtime_ssh_host_keys_if_missing() {
  local ssh_keygen_bin
  ssh_keygen_bin="$(runtime_ssh_keygen_bin)"
  runtime_ssh_host_keys_present && return 0
  "$ssh_keygen_bin" -A >/dev/null 2>&1 || true
}

persist_runtime_ssh_host_keys() {
  local persistent_key_dir="${1:-}"
  local ssh_dir key_path base_name

  [[ -n "$persistent_key_dir" ]] || return 0
  ssh_dir="$(runtime_ssh_dir)"

  for key_path in "$ssh_dir"/ssh_host_*_key; do
    [[ -s "$key_path" ]] || continue
    base_name="$(basename "$key_path")"
    install -m 0600 "$key_path" "$persistent_key_dir/$base_name"
    if [[ -s "$key_path.pub" ]]; then
      install -m 0644 "$key_path.pub" "$persistent_key_dir/$base_name.pub"
    fi
  done
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
