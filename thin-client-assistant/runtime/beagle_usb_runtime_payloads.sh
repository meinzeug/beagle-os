#!/usr/bin/env bash

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
