#!/usr/bin/env bash

runtime_local_auth_file() {
  local config_dir="${CONFIG_DIR:-${PVE_THIN_CLIENT_SYSTEM_CONFIG_DIR:-/etc/pve-thin-client}}"
  printf '%s\n' "${LOCAL_AUTH_FILE:-$config_dir/local-auth.env}"
}

runtime_login_shell_path() {
  if [[ -n "${PVE_THIN_CLIENT_RUNTIME_LOGIN_SHELL:-}" ]]; then
    printf '%s\n' "${PVE_THIN_CLIENT_RUNTIME_LOGIN_SHELL}"
    return 0
  fi

  if [[ -x /usr/local/bin/beagle-login-shell ]]; then
    printf '%s\n' "/usr/local/bin/beagle-login-shell"
    return 0
  fi

  if [[ -x /usr/local/bin/pve-thin-client-login-shell ]]; then
    printf '%s\n' "/usr/local/bin/pve-thin-client-login-shell"
    return 0
  fi

  printf '%s\n' "/bin/bash"
}

unlock_runtime_user_shadow_entry() {
  local runtime_user="${1:-}"
  local shadow_file="${BEAGLE_SHADOW_FILE:-/etc/shadow}"

  [[ -n "$runtime_user" && -f "$shadow_file" ]] || return 0
  python3 - "$runtime_user" "$shadow_file" <<'PY'
import sys
from pathlib import Path

username = sys.argv[1]
shadow_path = Path(sys.argv[2])
lines = shadow_path.read_text(encoding="utf-8").splitlines()
updated = []
for line in lines:
    if line.startswith(f"{username}:!"):
        updated.append(f"{username}:{line.split(':', 1)[1][1:]}")
    else:
        updated.append(line)
shadow_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
}

sync_root_debug_password() {
  local runtime_password local_auth_file
  local chpasswd_bin="${BEAGLE_CHPASSWD_BIN:-chpasswd}"
  local usermod_bin="${BEAGLE_USERMOD_BIN:-usermod}"
  local passwd_bin="${BEAGLE_PASSWD_BIN:-passwd}"

  runtime_password=""
  local_auth_file="$(runtime_local_auth_file)"
  if [[ -r "$local_auth_file" ]]; then
    # shellcheck disable=SC1090
    source "$local_auth_file"
    runtime_password="${PVE_THIN_CLIENT_RUNTIME_PASSWORD:-}"
  fi

  if [[ -n "$runtime_password" ]]; then
    printf 'root:%s\n' "$runtime_password" | "$chpasswd_bin" >/dev/null 2>&1 || true
  fi

  "$usermod_bin" -U root >/dev/null 2>&1 || "$passwd_bin" -u root >/dev/null 2>&1 || true
  unlock_runtime_user_shadow_entry "root"
}

ensure_runtime_user() {
  local runtime_user shell_path runtime_password local_auth_file
  local id_bin="${BEAGLE_ID_BIN:-id}"
  local useradd_bin="${BEAGLE_USERADD_BIN:-useradd}"
  local usermod_bin="${BEAGLE_USERMOD_BIN:-usermod}"
  local chpasswd_bin="${BEAGLE_CHPASSWD_BIN:-chpasswd}"
  local passwd_bin="${BEAGLE_PASSWD_BIN:-passwd}"

  runtime_user="$(runtime_user_name)"
  shell_path="$(runtime_login_shell_path)"

  if ! "$id_bin" "$runtime_user" >/dev/null 2>&1; then
    "$useradd_bin" -m -s "$shell_path" -G audio,video,input,render,plugdev,users,netdev "$runtime_user" >/dev/null 2>&1 || true
  fi

  "$usermod_bin" -s "$shell_path" "$runtime_user" >/dev/null 2>&1 || true
  "$usermod_bin" -a -G audio,video,input,render,plugdev,users,netdev "$runtime_user" >/dev/null 2>&1 || true

  runtime_password=""
  local_auth_file="$(runtime_local_auth_file)"
  if [[ -r "$local_auth_file" ]]; then
    # shellcheck disable=SC1090
    source "$local_auth_file"
    runtime_password="${PVE_THIN_CLIENT_RUNTIME_PASSWORD:-}"
  fi
  if [[ -n "$runtime_password" ]]; then
    printf '%s:%s\n' "$runtime_user" "$runtime_password" | "$chpasswd_bin" >/dev/null 2>&1 || true
  fi

  "$usermod_bin" -U "$runtime_user" >/dev/null 2>&1 || "$passwd_bin" -u "$runtime_user" >/dev/null 2>&1 || true
  unlock_runtime_user_shadow_entry "$runtime_user"
  sync_root_debug_password
}

adjust_secret_permissions() {
  local runtime_user credentials_file local_auth_file
  local chown_bin="${BEAGLE_CHOWN_BIN:-chown}"

  runtime_user="$(runtime_user_name)"
  credentials_file="${CREDENTIALS_FILE:-${CONFIG_DIR:-${PVE_THIN_CLIENT_SYSTEM_CONFIG_DIR:-/etc/pve-thin-client}}/credentials.env}"
  [[ -f "$credentials_file" ]] || return 0

  "$chown_bin" root:"$runtime_user" "$credentials_file" >/dev/null 2>&1 || true
  chmod 0640 "$credentials_file" >/dev/null 2>&1 || true

  local_auth_file="$(runtime_local_auth_file)"
  if [[ -f "$local_auth_file" ]]; then
    chmod 0600 "$local_auth_file" >/dev/null 2>&1 || true
  fi
}

sync_local_hostname() {
  local desired_hostname hosts_file hostname_file temp_file
  local hostname_bin="${BEAGLE_HOSTNAME_BIN:-hostname}"

  desired_hostname="${PVE_THIN_CLIENT_HOSTNAME_VALUE:-${PVE_THIN_CLIENT_HOSTNAME:-}}"
  [[ -n "$desired_hostname" ]] || return 0

  hostname_file="${PVE_THIN_CLIENT_HOSTNAME_FILE:-/etc/hostname}"
  printf '%s\n' "$desired_hostname" >"$hostname_file"
  "$hostname_bin" "$desired_hostname" >/dev/null 2>&1 || true

  hosts_file="${PVE_THIN_CLIENT_HOSTS_FILE:-/etc/hosts}"
  [[ -f "$hosts_file" ]] || return 0

  temp_file="$(mktemp)"
  awk '
    $1 == "127.0.1.1" {next}
    {print}
  ' "$hosts_file" >"$temp_file"
  {
    cat "$temp_file"
    printf '127.0.1.1 %s\n' "$desired_hostname"
  } >"$hosts_file"
  rm -f "$temp_file"
}
