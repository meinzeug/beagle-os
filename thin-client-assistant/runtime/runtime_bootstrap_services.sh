#!/usr/bin/env bash

runtime_systemctl_bin() {
  printf '%s\n' "${BEAGLE_SYSTEMCTL_BIN:-systemctl}"
}

runtime_sshd_bin() {
  printf '%s\n' "${BEAGLE_SSHD_BIN:-sshd}"
}

runtime_ssh_keygen_bin() {
  printf '%s\n' "${BEAGLE_SSH_KEYGEN_BIN:-ssh-keygen}"
}

runtime_boot_mode_bin() {
  printf '%s\n' "${BEAGLE_BOOT_MODE_BIN:-/usr/local/bin/pve-thin-client-boot-mode}"
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

runtime_getty_tty1_override_dir() {
  printf '%s\n' "${PVE_THIN_CLIENT_GETTY_TTY1_OVERRIDE_DIR:-/etc/systemd/system/getty@tty1.service.d}"
}

runtime_getty_default_override_dir() {
  printf '%s\n' "${PVE_THIN_CLIENT_GETTY_DEFAULT_OVERRIDE_DIR:-/etc/systemd/system/getty@.service.d}"
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

ensure_usb_tunnel_service() {
  local systemctl_bin
  systemctl_bin="$(runtime_systemctl_bin)"

  if ! beagle_unit_file_present "beagle-usb-tunnel.service"; then
    return 0
  fi
  "$systemctl_bin" enable beagle-usb-tunnel.service >/dev/null 2>&1 || true
  if [[ "${PVE_THIN_CLIENT_BEAGLE_USB_ENABLED:-0}" == "1" ]]; then
    "$systemctl_bin" restart --no-block beagle-usb-tunnel.service >/dev/null 2>&1 || true
  else
    "$systemctl_bin" stop --no-block beagle-usb-tunnel.service >/dev/null 2>&1 || true
  fi
}

ensure_beagle_management_units() {
  local systemctl_bin unit
  systemctl_bin="$(runtime_systemctl_bin)"

  for unit in \
    beagle-endpoint-report.timer \
    beagle-endpoint-dispatch.timer \
    beagle-runtime-heartbeat.timer \
    beagle-update-scan.timer
  do
    if beagle_unit_file_present "$unit"; then
      "$systemctl_bin" enable "$unit" >/dev/null 2>&1 || true
      "$systemctl_bin" restart --no-block "$unit" >/dev/null 2>&1 || true
    fi
  done

  for unit in beagle-endpoint-report.service beagle-endpoint-dispatch.service; do
    if beagle_unit_file_present "$unit"; then
      "$systemctl_bin" start --no-block "$unit" >/dev/null 2>&1 || true
    fi
  done

  if beagle_unit_file_present "beagle-update-boot-scan.service"; then
    "$systemctl_bin" enable beagle-update-boot-scan.service >/dev/null 2>&1 || true
    "$systemctl_bin" start --no-block beagle-update-boot-scan.service >/dev/null 2>&1 || true
  fi
}

ensure_getty_overrides() {
  local tty1_dir default_dir systemctl_bin

  tty1_dir="$(runtime_getty_tty1_override_dir)"
  default_dir="$(runtime_getty_default_override_dir)"
  systemctl_bin="$(runtime_systemctl_bin)"

  install -d -m 0755 "$tty1_dir" "$default_dir"

  cat >"$default_dir/zz-beagle-default.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty -o '-p -- \u' --noclear - $TERM
EOF

  cat >"$tty1_dir/zz-beagle-autologin.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=-/usr/local/bin/pve-thin-client-tty-login %I $TERM
EOF

  rm -f "$tty1_dir/autologin.conf" >/dev/null 2>&1 || true
  "$systemctl_bin" daemon-reload >/dev/null 2>&1 || true
}

normalize_boot_services() {
  local boot_mode systemctl_bin boot_mode_bin

  systemctl_bin="$(runtime_systemctl_bin)"
  boot_mode_bin="$(runtime_boot_mode_bin)"
  boot_mode="$("$boot_mode_bin" 2>/dev/null || printf 'runtime')"

  case "$boot_mode" in
    runtime)
      "$systemctl_bin" list-unit-files pve-thin-client-prepare.service >/dev/null 2>&1 && \
        "$systemctl_bin" enable pve-thin-client-prepare.service >/dev/null 2>&1 || true
      "$systemctl_bin" list-unit-files pve-thin-client-runtime.service >/dev/null 2>&1 && \
        "$systemctl_bin" enable pve-thin-client-runtime.service >/dev/null 2>&1 || true
      "$systemctl_bin" list-unit-files pve-thin-client-installer-menu.service >/dev/null 2>&1 && \
        "$systemctl_bin" disable pve-thin-client-installer-menu.service >/dev/null 2>&1 || true
      "$systemctl_bin" disable getty@tty1.service >/dev/null 2>&1 || true
      ;;
    installer)
      "$systemctl_bin" list-unit-files pve-thin-client-prepare.service >/dev/null 2>&1 && \
        "$systemctl_bin" enable pve-thin-client-prepare.service >/dev/null 2>&1 || true
      "$systemctl_bin" list-unit-files pve-thin-client-installer-menu.service >/dev/null 2>&1 && \
        "$systemctl_bin" enable pve-thin-client-installer-menu.service >/dev/null 2>&1 || true
      "$systemctl_bin" list-unit-files pve-thin-client-runtime.service >/dev/null 2>&1 && \
        "$systemctl_bin" disable pve-thin-client-runtime.service >/dev/null 2>&1 || true
      "$systemctl_bin" disable getty@tty1.service >/dev/null 2>&1 || true
      ;;
    *)
      "$systemctl_bin" enable getty@tty1.service >/dev/null 2>&1 || true
      ;;
  esac
}
