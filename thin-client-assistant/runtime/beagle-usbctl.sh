#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_runtime_config >/dev/null 2>&1 || true

STATE_ROOT="${BEAGLE_USB_STATE_DIR:-/var/lib/beagle-os/usb}"
STATE_FILE="$STATE_ROOT/state.env"
USB_ENABLED="${PVE_THIN_CLIENT_BEAGLE_USB_ENABLED:-1}"
USB_HOST="${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_HOST:-}"
USB_USER="${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_USER:-thinovernet}"
USB_PORT="${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PORT:-}"
USB_ATTACH_HOST="${PVE_THIN_CLIENT_BEAGLE_USB_ATTACH_HOST:-10.10.10.1}"
USB_KEY_FILE="${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PRIVATE_KEY_FILE:-/etc/pve-thin-client/usb-tunnel.key}"
USB_KNOWN_HOSTS_FILE="${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_KNOWN_HOSTS_FILE:-/etc/pve-thin-client/usb-tunnel-known_hosts}"

install -d -m 0755 "$STATE_ROOT"

state_bound_busids() {
  if [[ -r "$STATE_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$STATE_FILE"
  fi
  printf '%s\n' "${BEAGLE_USB_BOUND_BUSIDS:-}"
}

write_state() {
  local busids="$1"
  cat >"$STATE_FILE" <<STATE
BEAGLE_USB_BOUND_BUSIDS=${busids@Q}
STATE
  chmod 0644 "$STATE_FILE"
}

bound_contains() {
  local needle="$1"
  local item
  for item in $(state_bound_busids); do
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
}

bound_add() {
  local needle="$1"
  local item out=""
  if bound_contains "$needle"; then
    write_state "$(state_bound_busids)"
    return 0
  fi
  for item in $(state_bound_busids); do
    out+="$item "
  done
  out+="$needle"
  write_state "$out"
}

bound_remove() {
  local needle="$1"
  local item out=""
  for item in $(state_bound_busids); do
    [[ "$item" == "$needle" ]] && continue
    out+="$item "
  done
  write_state "$out"
}

require_enabled() {
  [[ "$USB_ENABLED" == "1" ]] || {
    echo "usb disabled" >&2
    exit 0
  }
}

have_usbipd() {
  pgrep -x usbipd >/dev/null 2>&1
}

restart_usbipd() {
  pkill -x usbipd >/dev/null 2>&1 || true
  sleep 1
  usbipd -D >/dev/null 2>&1 || true
  sleep 1
}

have_exportable_devices() {
  local output
  output="$(usbip list -r 127.0.0.1 2>/dev/null || true)"
  grep -q "^ - 127\\.0\\.0\\.1" <<<"$output"
}

ensure_usbipd() {
  require_enabled
  modprobe usbip-host >/dev/null 2>&1 || true
  if ! have_usbipd; then
    restart_usbipd
  fi
}

sync_bound_devices() {
  local item
  ensure_usbipd
  for item in $(state_bound_busids); do
    [[ -n "$item" ]] || continue
    usbip unbind -b "$item" >/dev/null 2>&1 || true
    usbip bind -b "$item" >/dev/null 2>&1 || true
  done
  sleep 1
  restart_usbipd
  if [[ -n "$(state_bound_busids)" ]] && ! have_exportable_devices; then
    for item in $(state_bound_busids); do
      [[ -n "$item" ]] || continue
      usbip unbind -b "$item" >/dev/null 2>&1 || true
      sleep 1
      usbip bind -b "$item" >/dev/null 2>&1 || true
    done
    sleep 1
    restart_usbipd
  fi
}

is_tunnel_running() {
  [[ -n "$USB_PORT" ]] || return 1
  pgrep -af "${USB_ATTACH_HOST}:${USB_PORT}:127.0.0.1:3240" | grep -q "${USB_USER}@${USB_HOST}" 2>/dev/null
}

list_local_usb_json() {
  python3 - "$STATE_FILE" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

state_path = Path(sys.argv[1])
bound = []
if state_path.exists():
    for raw_line in state_path.read_text(encoding='utf-8', errors='ignore').splitlines():
        if raw_line.startswith('BEAGLE_USB_BOUND_BUSIDS='):
            value = raw_line.split('=', 1)[1].strip().strip('"').strip("'")
            bound = [item.strip() for item in value.split() if item.strip()]
            break

try:
    output = subprocess.run(['usbip', 'list', '-l'], capture_output=True, text=True, check=False).stdout
except FileNotFoundError:
    print(json.dumps({'devices': [], 'device_count': 0, 'bound_count': len(bound)}))
    raise SystemExit(0)

devices = []
current = None
for raw_line in output.splitlines():
    line = raw_line.rstrip()
    normalized = line.lstrip()
    if not line.strip():
        continue
    if normalized.startswith('- busid '):
        if current:
            devices.append(current)
        prefix, _, rest = normalized.partition('(')
        busid = prefix.split()[-1]
        current = {
            'busid': busid,
            'description': rest.rstrip(')') if rest else '',
            'bound': busid in bound,
        }
        continue
    if current is not None and raw_line.startswith('    '):
        current.setdefault('interfaces', []).append(line.strip())
if current:
    devices.append(current)
print(json.dumps({'devices': devices, 'device_count': len(devices), 'bound_count': sum(1 for item in devices if item.get('bound'))}))
PY
}

cmd_list_json() {
  local tunnel_state="down"
  local payload="{}"
  is_tunnel_running && tunnel_state="up"
  ensure_usbipd >/dev/null 2>&1 || true
  payload="$(list_local_usb_json)"
  python3 - "$USB_HOST" "$USB_PORT" "$USB_ATTACH_HOST" "$tunnel_state" "$payload" <<'PY'
import json
import sys
host, port, attach_host, tunnel_state, payload_text = sys.argv[1:6]
base = {'enabled': True, 'tunnel_host': host, 'tunnel_port': port, 'attach_host': attach_host, 'tunnel_state': tunnel_state}
try:
    payload = json.loads(payload_text)
except Exception:
    payload = {'devices': [], 'device_count': 0, 'bound_count': 0}
base.update(payload)
print(json.dumps(base))
PY
}

cmd_bind() {
  local busid="$1"
  require_enabled
  ensure_usbipd
  usbip unbind -b "$busid" >/dev/null 2>&1 || true
  usbip bind -b "$busid" >/dev/null 2>&1 || true
  bound_add "$busid"
  restart_usbipd
  systemctl restart --no-block beagle-usb-tunnel.service >/dev/null 2>&1 || true
  cmd_list_json
}

cmd_unbind() {
  local busid="$1"
  require_enabled
  usbip unbind -b "$busid" >/dev/null 2>&1 || true
  bound_remove "$busid"
  restart_usbipd
  cmd_list_json
}

cmd_status_json() {
  local tunnel_state="down"
  is_tunnel_running && tunnel_state="up"
  python3 - "$USB_HOST" "$USB_PORT" "$USB_ATTACH_HOST" "$tunnel_state" "$USB_ENABLED" <<'PY'
import json
import sys
print(json.dumps({
  'enabled': sys.argv[5] == '1',
  'tunnel_host': sys.argv[1],
  'tunnel_port': sys.argv[2],
  'attach_host': sys.argv[3],
  'tunnel_state': sys.argv[4],
}))
PY
}

cmd_daemon() {
  require_enabled
  [[ -n "$USB_HOST" && -n "$USB_PORT" && -n "$USB_USER" ]] || exit 0
  [[ -r "$USB_KEY_FILE" && -r "$USB_KNOWN_HOSTS_FILE" ]] || exit 0
  sync_bound_devices
  exec ssh -N \
    -o BatchMode=yes \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=20 \
    -o ServerAliveCountMax=3 \
    -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="$USB_KNOWN_HOSTS_FILE" \
    -i "$USB_KEY_FILE" \
    -R "${USB_ATTACH_HOST}:${USB_PORT}:127.0.0.1:3240" \
    "${USB_USER}@${USB_HOST}"
}

case "${1:-}" in
  daemon)
    cmd_daemon
    ;;
  list-json)
    cmd_list_json
    ;;
  status-json)
    cmd_status_json
    ;;
  bind)
    [[ -n "${2:-}" ]] || { echo 'missing busid' >&2; exit 1; }
    cmd_bind "$2"
    ;;
  unbind)
    [[ -n "${2:-}" ]] || { echo 'missing busid' >&2; exit 1; }
    cmd_unbind "$2"
    ;;
  *)
    echo "usage: $0 {daemon|list-json|status-json|bind BUSID|unbind BUSID}" >&2
    exit 1
    ;;
esac
