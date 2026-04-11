#!/usr/bin/env bash

usb_state_root() {
  printf '%s\n' "${BEAGLE_USB_STATE_DIR:-/var/lib/beagle-os/usb}"
}

usb_state_file() {
  local state_root
  state_root="$(usb_state_root)"
  printf '%s\n' "$state_root/state.env"
}

usb_enabled() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_ENABLED:-1}"
}

usb_host() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_HOST:-}"
}

usb_user() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_USER:-beagle}"
}

usb_port() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PORT:-}"
}

usb_attach_host() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_ATTACH_HOST:-10.10.10.1}"
}

usb_key_file() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PRIVATE_KEY_FILE:-/etc/pve-thin-client/usb-tunnel.key}"
}

usb_known_hosts_file() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_KNOWN_HOSTS_FILE:-/etc/pve-thin-client/usb-tunnel-known_hosts}"
}

usbip_bin() {
  printf '%s\n' "${BEAGLE_USBIP_BIN:-usbip}"
}

pgrep_bin() {
  printf '%s\n' "${BEAGLE_PGREP_BIN:-pgrep}"
}

ensure_usb_state_root() {
  install -d -m 0755 "$(usb_state_root)"
}

state_bound_busids() {
  local state_file

  state_file="$(usb_state_file)"
  if [[ -r "$state_file" ]]; then
    # shellcheck disable=SC1090
    source "$state_file"
  fi
  printf '%s\n' "${BEAGLE_USB_BOUND_BUSIDS:-}"
}

write_state() {
  local busids="$1"
  local state_file

  ensure_usb_state_root
  state_file="$(usb_state_file)"
  cat >"$state_file" <<STATE
BEAGLE_USB_BOUND_BUSIDS=${busids@Q}
STATE
  chmod 0644 "$state_file"
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
  write_state "${out%" "}"
}

bound_remove() {
  local needle="$1"
  local item out=""
  for item in $(state_bound_busids); do
    [[ "$item" == "$needle" ]] && continue
    out+="$item "
  done
  write_state "${out%" "}"
}

require_enabled() {
  [[ "$(usb_enabled)" == "1" ]] || {
    echo "usb disabled" >&2
    exit 0
  }
}

is_tunnel_running() {
  local port attach_host user host pgrep_cmd

  port="$(usb_port)"
  [[ -n "$port" ]] || return 1
  attach_host="$(usb_attach_host)"
  user="$(usb_user)"
  host="$(usb_host)"
  pgrep_cmd="$(pgrep_bin)"
  "$pgrep_cmd" -af "${attach_host}:${port}:127.0.0.1:3240" | grep -q "${user}@${host}" 2>/dev/null
}

list_local_usb_json() {
  local state_file usbip_cmd
  state_file="$(usb_state_file)"
  usbip_cmd="$(usbip_bin)"

  python3 - "$state_file" "$usbip_cmd" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

state_path = Path(sys.argv[1])
usbip_bin = sys.argv[2]
bound = []
if state_path.exists():
    for raw_line in state_path.read_text(encoding='utf-8', errors='ignore').splitlines():
        if raw_line.startswith('BEAGLE_USB_BOUND_BUSIDS='):
            value = raw_line.split('=', 1)[1].strip().strip('"').strip("'")
            bound = [item.strip() for item in value.split() if item.strip()]
            break

try:
    output = subprocess.run([usbip_bin, 'list', '-l'], capture_output=True, text=True, check=False).stdout
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

render_usb_list_json() {
  local tunnel_state="$1"
  local payload="${2-}"

  if [[ -z "$payload" ]]; then
    payload='{}'
  fi

  python3 - "$(usb_host)" "$(usb_port)" "$(usb_attach_host)" "$tunnel_state" "$payload" <<'PY'
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

render_usb_status_json() {
  local tunnel_state="$1"

  python3 - "$(usb_host)" "$(usb_port)" "$(usb_attach_host)" "$tunnel_state" "$(usb_enabled)" <<'PY'
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
