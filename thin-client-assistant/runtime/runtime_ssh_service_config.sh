#!/usr/bin/env bash

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
    if "$systemctl_bin" is-active "$service_name" >/dev/null 2>&1; then
      return 0
    fi
    "$systemctl_bin" reset-failed "$service_name" >/dev/null 2>&1 || true
    "$systemctl_bin" start "$service_name" >/dev/null 2>&1 || true
  fi
}

apply_runtime_ssh_config() {
  local sshd_config begin_marker end_marker temp_file block_file changed=0

  sshd_config="$(runtime_sshd_config_path)"
  begin_marker="$(managed_ssh_begin_marker)"
  end_marker="$(managed_ssh_end_marker)"

  [[ -f "$sshd_config" ]] || return 0

  temp_file="$(mktemp)"
  block_file="$(mktemp)"
  strip_managed_ssh_block "$sshd_config" "$begin_marker" "$end_marker" >"$temp_file" || cp -f "$sshd_config" "$temp_file"
  cat >"$block_file" <<EOF
$begin_marker
PasswordAuthentication yes
KbdInteractiveAuthentication yes
PermitEmptyPasswords no
PermitRootLogin yes
$end_marker
EOF

  {
    cat "$temp_file"
    printf '\n'
    cat "$block_file"
  } >"${sshd_config}.tmp"

  if ! cmp -s "${sshd_config}.tmp" "$sshd_config"; then
    mv -f "${sshd_config}.tmp" "$sshd_config"
    changed=1
  else
    rm -f "${sshd_config}.tmp"
  fi

  rm -f "$temp_file" "$block_file"
  chmod 0600 "$sshd_config" >/dev/null 2>&1 || true

  if [[ "$changed" -eq 1 ]]; then
    runtime_restart_service_if_valid "$sshd_config"
  fi
}
