#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_SYSTEMD_UNITS_SH="${RUNTIME_SYSTEMD_UNITS_SH:-$SCRIPT_DIR/runtime_systemd_units.sh}"
# shellcheck disable=SC1090
source "$RUNTIME_SYSTEMD_UNITS_SH"

runtime_boot_mode_bin() {
  printf '%s\n' "${BEAGLE_BOOT_MODE_BIN:-/usr/local/bin/pve-thin-client-boot-mode}"
}

runtime_getty_tty1_override_dir() {
  printf '%s\n' "${PVE_THIN_CLIENT_GETTY_TTY1_OVERRIDE_DIR:-/etc/systemd/system/getty@tty1.service.d}"
}

runtime_getty_default_override_dir() {
  printf '%s\n' "${PVE_THIN_CLIENT_GETTY_DEFAULT_OVERRIDE_DIR:-/etc/systemd/system/getty@.service.d}"
}

ensure_getty_overrides() {
  local tty1_dir default_dir systemctl_bin

  tty1_dir="$(runtime_getty_tty1_override_dir)"
  default_dir="$(runtime_getty_default_override_dir)"
  systemctl_bin="$(runtime_systemctl_bin)"

  mkdir -p "$tty1_dir" "$default_dir"
  chmod 0755 "$tty1_dir" "$default_dir" >/dev/null 2>&1 || true

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
