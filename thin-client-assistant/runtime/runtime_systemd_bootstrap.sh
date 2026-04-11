#!/usr/bin/env bash

runtime_systemctl_bin() {
  printf '%s\n' "${BEAGLE_SYSTEMCTL_BIN:-systemctl}"
}

runtime_boot_mode_bin() {
  printf '%s\n' "${BEAGLE_BOOT_MODE_BIN:-/usr/local/bin/pve-thin-client-boot-mode}"
}

runtime_getty_tty1_override_dir() {
  printf '%s\n' "${PVE_THIN_CLIENT_GETTY_TTY1_OVERRIDE_DIR:-/etc/systemd/system/getty@tty1.service.d}"
}

runtime_getty_default_override_dir() {
  printf '%s\n' "${PVE_THIN_CLIENT_GETTY_DEFAULT_OVERRIDE_DIR:-/etc/systemd/system/getty@.service.d}"
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
  local boot_mode systemctl_bin boot_mode_cmd

  systemctl_bin="$(runtime_systemctl_bin)"
  boot_mode_cmd="$(runtime_boot_mode_bin)"
  boot_mode="$("$boot_mode_cmd" 2>/dev/null || printf 'runtime')"

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
