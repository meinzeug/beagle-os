#!/usr/bin/env bash

runtime_debug_dir() {
  printf '%s\n' "${PVE_THIN_CLIENT_DEBUG_DIR:-/var/lib/pve-thin-client/debug}"
}

runtime_debug_live_dir() {
  local live_state_dir=""

  live_state_dir="$(find_live_state_dir 2>/dev/null || true)"
  [[ -n "$live_state_dir" ]] || return 1
  printf '%s\n' "$live_state_dir/debug"
}

runtime_debug_redact_env_file() {
  local source_file="$1"
  local target_file="$2"

  [[ -f "$source_file" ]] || return 0
  python3 - "$source_file" "$target_file" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
secret_key = re.compile(r"(PASSWORD|PASS|TOKEN|PRIVATE_KEY|PRESHARED|PIN|PSK|CERT_B64|SECRET)", re.I)

lines = []
for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
    if "=" in line and secret_key.search(line.split("=", 1)[0]):
        key = line.split("=", 1)[0]
        lines.append(f"{key}=<redacted>")
    else:
        lines.append(line)
target.write_text("\n".join(lines) + "\n", encoding="utf-8")
target.chmod(0o600)
PY
}

runtime_debug_collect_command() {
  local title="$1"
  shift

  printf '\n## %s\n' "$title"
  "$@" 2>&1 || true
}

runtime_debug_collect_systemd_unit() {
  local unit="$1"

  command -v systemctl >/dev/null 2>&1 || return 0
  printf '%s: ' "$unit"
  systemctl is-active "$unit" 2>/dev/null || true
}

write_runtime_debug_report() {
  local stage="${1:-runtime}"
  local iface="${2:-}"
  local debug_dir report_path latest_path config_dir live_debug_dir live_latest
  local stamp safe_stage file base

  stamp="$(date -u +%Y%m%dT%H%M%SZ 2>/dev/null || date +%s)"
  safe_stage="$(printf '%s' "$stage" | tr -c 'A-Za-z0-9_.-' '-')"
  debug_dir="$(runtime_debug_dir)"
  report_path="$debug_dir/${stamp}-${safe_stage}.log"
  latest_path="$debug_dir/latest.log"

  install -d -m 0755 "$debug_dir" >/dev/null 2>&1 || return 0
  {
    printf 'Beagle OS thin-client runtime debug report\n'
    printf 'stage=%s\n' "$stage"
    printf 'timestamp_utc=%s\n' "$stamp"
    printf 'hostname=%s\n' "$(hostname 2>/dev/null || true)"
    printf 'interface=%s\n' "${iface:-auto}"
    printf 'boot_id=%s\n' "$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)"
    printf 'kernel_cmdline=%s\n' "$(cat /proc/cmdline 2>/dev/null || true)"

    runtime_debug_collect_command "network links" ip -brief link
    runtime_debug_collect_command "network addresses" ip -brief addr
    runtime_debug_collect_command "routes" ip route
    runtime_debug_collect_command "neighbors" ip neigh

    printf '\n## interface addresses and assignment type\n'
    for file in /sys/class/net/*/address; do
      [[ -f "$file" ]] || continue
      base="$(basename "$(dirname "$file")")"
      printf '%s address=%s addr_assign_type=%s\n' \
        "$base" \
        "$(cat "$file" 2>/dev/null || true)" \
        "$(cat "/sys/class/net/$base/addr_assign_type" 2>/dev/null || true)"
    done

    printf '\n## service state\n'
    runtime_debug_collect_systemd_unit ssh.service
    runtime_debug_collect_systemd_unit NetworkManager.service
    runtime_debug_collect_systemd_unit systemd-networkd.service
    runtime_debug_collect_systemd_unit pve-thin-client-network-menu.service
    runtime_debug_collect_systemd_unit beagle-thin-client-prepare.service
    runtime_debug_collect_systemd_unit pve-thin-client-runtime.service

    if command -v ss >/dev/null 2>&1; then
      runtime_debug_collect_command "listening tcp sockets" ss -ltn
    fi

    if command -v journalctl >/dev/null 2>&1; then
      runtime_debug_collect_command "runtime unit journals" journalctl \
        -u pve-thin-client-network-menu.service \
        -u beagle-thin-client-prepare.service \
        -u pve-thin-client-runtime.service \
        -u ssh.service \
        -n 220 --no-pager
    fi
  } >"$report_path" 2>/dev/null || true
  chmod 0644 "$report_path" >/dev/null 2>&1 || true
  cp "$report_path" "$latest_path" >/dev/null 2>&1 || true

  if command -v runtime_system_config_dir >/dev/null 2>&1; then
    config_dir="${CONFIG_DIR:-$(runtime_system_config_dir 2>/dev/null || printf '/etc/pve-thin-client')}"
  else
    config_dir="${CONFIG_DIR:-/etc/pve-thin-client}"
  fi
  if [[ -d "$config_dir" ]]; then
    install -d -m 0700 "$debug_dir/config-redacted" >/dev/null 2>&1 || true
    for file in "$config_dir"/*.env "$config_dir"/*.conf "$config_dir"/*.json; do
      [[ -f "$file" ]] || continue
      runtime_debug_redact_env_file "$file" "$debug_dir/config-redacted/$(basename "$file")" || true
    done
  fi

  live_debug_dir="$(runtime_debug_live_dir 2>/dev/null || true)"
  [[ -n "$live_debug_dir" ]] || return 0
  if command -v remount_live_state_writable >/dev/null 2>&1; then
    remount_live_state_writable "$(dirname "$live_debug_dir")" >/dev/null 2>&1 || true
  fi
  install -d -m 0755 "$live_debug_dir" >/dev/null 2>&1 || return 0
  install -m 0644 "$report_path" "$live_debug_dir/$(basename "$report_path")" >/dev/null 2>&1 || true
  live_latest="$live_debug_dir/latest.log"
  install -m 0644 "$report_path" "$live_latest" >/dev/null 2>&1 || true
  if [[ -d "$debug_dir/config-redacted" ]]; then
    install -d -m 0700 "$live_debug_dir/config-redacted" >/dev/null 2>&1 || true
    for file in "$debug_dir/config-redacted"/*; do
      [[ -f "$file" ]] || continue
      install -m 0600 "$file" "$live_debug_dir/config-redacted/$(basename "$file")" >/dev/null 2>&1 || true
    done
  fi
}
