#!/usr/bin/env bash

runtime_ssh_keygen_bin() {
  printf '%s\n' "${BEAGLE_SSH_KEYGEN_BIN:-ssh-keygen}"
}

runtime_ssh_dir() {
  printf '%s\n' "${PVE_THIN_CLIENT_SSH_DIR:-/etc/ssh}"
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
