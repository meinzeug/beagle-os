#!/usr/bin/env bash
set -euo pipefail

VMID="${VMID:-}"
NODE="${NODE:-}"
CONFIG_DIR="${PVE_DCV_CONFIG_DIR:-/etc/beagle}"
MANAGER_DATA_DIR="${BEAGLE_MANAGER_DATA_DIR:-/var/lib/beagle/beagle-manager}"
STATE_DIR="${BEAGLE_INSTALLER_PREP_DIR:-$MANAGER_DATA_DIR/installer-prep}"
STATE_FILE="${BEAGLE_INSTALLER_PREP_STATE_FILE:-}"
PUBLIC_STREAM_HOST="${BEAGLE_PUBLIC_STREAM_HOST:-${PVE_DCV_PROXY_SERVER_NAME:-$(hostname -f 2>/dev/null || hostname)}}"
STREAMS_FILE="${BEAGLE_PUBLIC_STREAMS_FILE:-$MANAGER_DATA_DIR/public-streams.json}"
SUNSHINE_DEFAULT_USER="${BEAGLE_SUNSHINE_DEFAULT_USER:-sunshine}"
SUNSHINE_DEFAULT_PASSWORD="${BEAGLE_SUNSHINE_DEFAULT_PASSWORD:-beagleos}"
SUNSHINE_DEFAULT_GUEST_USER="${BEAGLE_SUNSHINE_DEFAULT_GUEST_USER:-dennis}"

usage() {
  echo "Usage: $0 --vmid VMID --node NODE" >&2
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --vmid) VMID="$2"; shift 2 ;;
      --node) NODE="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
    esac
  done
}

state_init() {
  install -d -m 0755 "$STATE_DIR"
  if [[ -z "$STATE_FILE" ]]; then
    STATE_FILE="$STATE_DIR/${NODE}-${VMID}.json"
  fi
}

write_state() {
  local status="$1"
  local phase="$2"
  local progress="$3"
  local message="$4"
  local extra_json="${5:-{}}"
  python3 - "$STATE_FILE" "$VMID" "$NODE" "$status" "$phase" "$progress" "$message" "$extra_json" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
vmid = int(sys.argv[2])
node = sys.argv[3]
status = sys.argv[4]
phase = sys.argv[5]
progress = int(sys.argv[6])
message = sys.argv[7]
existing = {}
if path.exists():
    try:
        existing = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        existing = {}
try:
    extra = json.loads(sys.argv[8]) if sys.argv[8] else {}
except Exception:
    extra = {}
now = datetime.now(timezone.utc).isoformat()
payload = {
    **existing,
    **(extra if isinstance(extra, dict) else {}),
    'vmid': vmid,
    'node': node,
    'status': status,
    'phase': phase,
    'progress': progress,
    'message': message,
    'updated_at': now,
}
if 'requested_at' not in payload:
    payload['requested_at'] = now
if status == 'running' and 'started_at' not in payload:
    payload['started_at'] = now
if status in {'ready', 'error'}:
    payload['completed_at'] = now
path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
PY
}

qm_config_description() {
  qm config "$VMID" | sed -n 's/^description: //p' | head -n1
}

meta_get() {
  local key="$1"
  python3 - "$key" <<'PY'
import sys, urllib.parse, subprocess
key = sys.argv[1].strip().lower()
raw = subprocess.check_output(['qm','config',sys.argv[2]], text=True)
encoded = ''
for line in raw.splitlines():
    if line.startswith('description: '):
        encoded = line.split(': ',1)[1]
        break
text = urllib.parse.unquote(encoded) if encoded else ''
for raw_line in text.splitlines():
    line = raw_line.strip()
    if ':' not in line:
        continue
    left, right = line.split(':',1)
    if left.strip().lower() == key:
        print(right.strip())
        raise SystemExit(0)
raise SystemExit(0)
PY
}

# override helper with vmid arg bound
meta_get() {
  local key="$1"
  python3 - "$VMID" "$key" <<'PY'
import sys, urllib.parse, subprocess
vmid = sys.argv[1]
key = sys.argv[2].strip().lower()
raw = subprocess.check_output(['qm','config',vmid], text=True)
encoded = ''
for line in raw.splitlines():
    if line.startswith('description: '):
        encoded = line.split(': ',1)[1]
        break
text = urllib.parse.unquote(encoded) if encoded else ''
for raw_line in text.splitlines():
    line = raw_line.strip()
    if ':' not in line:
        continue
    left, right = line.split(':',1)
    if left.strip().lower() == key:
        print(right.strip())
        break
PY
}

allocate_stream_port() {
  python3 - "$STREAMS_FILE" "$NODE" "$VMID" <<'PY'
import json, os, sys
from pathlib import Path

path = Path(sys.argv[1])
node = sys.argv[2]
vmid = int(sys.argv[3])
base = int(os.environ.get('BEAGLE_PUBLIC_STREAM_BASE_PORT', '50000'))
step = int(os.environ.get('BEAGLE_PUBLIC_STREAM_PORT_STEP', '32'))
count = int(os.environ.get('BEAGLE_PUBLIC_STREAM_PORT_COUNT', '256'))
key = f"{node}:{vmid}"
try:
    payload = json.loads(path.read_text(encoding='utf-8'))
except Exception:
    payload = {}
if not isinstance(payload, dict):
    payload = {}
clean = {}
for k, v in payload.items():
    try:
        clean[str(k)] = int(v)
    except Exception:
        pass
if key in clean:
    print(clean[key])
    raise SystemExit(0)
used = {int(v) for v in clean.values()}
for candidate in range(base, base + step * count, step):
    if candidate in used:
        continue
    clean[key] = candidate
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, indent=2) + '\n', encoding='utf-8')
    print(candidate)
    raise SystemExit(0)
raise SystemExit(1)
PY
}

sunshine_guest_status_json() {
  qm guest exec "$VMID" -- bash -lc 'binary=0; service=0; process=0; command -v sunshine >/dev/null 2>&1 && binary=1; systemctl is-active sunshine >/dev/null 2>&1 && service=1; pgrep -x sunshine >/dev/null 2>&1 && process=1; printf "{\"binary\":%s,\"service\":%s,\"process\":%s}\n" "$binary" "$service" "$process"'
}

guest_ipv4() {
  python3 - "$VMID" <<'PY'
import json
import subprocess
import sys

vmid = sys.argv[1]
try:
    raw = subprocess.check_output(["qm", "guest", "cmd", vmid, "network-get-interfaces"], text=True)
    payload = json.loads(raw)
except Exception:
    raise SystemExit(1)

for iface in payload if isinstance(payload, list) else []:
    for address in iface.get("ip-addresses", []):
        ip = str(address.get("ip-address", ""))
        if address.get("ip-address-type") != "ipv4":
            continue
        if not ip or ip.startswith("127.") or ip.startswith("169.254."):
            continue
        print(ip)
        raise SystemExit(0)
raise SystemExit(1)
PY
}

verify_public_api() {
  local api_url="$1"
  local sunshine_user="$2"
  local sunshine_password="$3"
  curl -kfsS --connect-timeout 4 --max-time 10 --user "${sunshine_user}:${sunshine_password}" "${api_url%/}/api/apps" >/dev/null
}

main() {
  local stream_port sunshine_user sunshine_password sunshine_pin guest_user sunshine_status_raw sunshine_status_json public_api_url direct_api_url guest_ip extra_json

  parse_args "$@"
  [[ -n "$VMID" && -n "$NODE" ]] || { usage; exit 1; }
  state_init

  stream_port="$(meta_get beagle-public-moonlight-port)"
  if [[ -z "$stream_port" ]]; then
    stream_port="$(allocate_stream_port)"
  fi
  sunshine_user="$(meta_get sunshine-user)"
  sunshine_password="$(meta_get sunshine-password)"
  sunshine_pin="$(meta_get sunshine-pin)"
  guest_user="$(meta_get sunshine-guest-user)"
  [[ -n "$sunshine_user" ]] || sunshine_user="$SUNSHINE_DEFAULT_USER"
  [[ -n "$sunshine_password" ]] || sunshine_password="$SUNSHINE_DEFAULT_PASSWORD"
  [[ -n "$sunshine_pin" ]] || sunshine_pin="$(printf '%04d' $(( VMID % 10000 )))"
  [[ -n "$guest_user" ]] || guest_user="$SUNSHINE_DEFAULT_GUEST_USER"
  public_api_url="https://${PUBLIC_STREAM_HOST}:$((stream_port + 1))"
  extra_json="$(python3 - "$VMID" "$PUBLIC_STREAM_HOST" "$stream_port" "$public_api_url" <<'PY'
import json
import sys

vmid, stream_host, moonlight_port, sunshine_api_url = sys.argv[1:5]
print(json.dumps({
    "installer_url": f"/beagle-api/api/v1/public/vms/{vmid}/installer.sh",
    "stream_host": stream_host,
    "moonlight_port": moonlight_port,
    "sunshine_api_url": sunshine_api_url,
}))
PY
)"
  write_state running inspect 5 "Pruefe Sunshine in VM ${VMID}." "$extra_json"

  sunshine_status_raw="$(sunshine_guest_status_json)"
  sunshine_status_json="$(python3 - "$sunshine_status_raw" <<'PY'
import json, sys
raw=sys.argv[1].strip()
if not raw:
    print('{"binary":0,"service":0,"process":0}')
    raise SystemExit(0)
try:
    payload=json.loads(raw)
except Exception:
    payload={"binary":0,"service":0,"process":0}
out=payload.get('out-data','') if isinstance(payload,dict) else ''
try:
    if out:
        inner=json.loads(out.strip().splitlines()[-1])
    else:
        inner={"binary":0,"service":0,"process":0}
except Exception:
    inner={"binary":0,"service":0,"process":0}
print(json.dumps(inner))
PY
)"

  if python3 - "$sunshine_status_json" <<'PY'
import json, sys
payload=json.loads(sys.argv[1])
raise SystemExit(0 if payload.get('binary') and payload.get('service') else 1)
PY
  then
    write_state running verify 65 "Sunshine ist bereits installiert. Pruefe oeffentlichen Zugriff." "$extra_json"
  else
    write_state running install 25 "Sunshine fehlt oder ist nicht aktiv. Installation wird gestartet." "$extra_json"
    /opt/beagle/scripts/configure-sunshine-guest.sh \
      --proxmox-host localhost \
      --vmid "$VMID" \
      --guest-user "$guest_user" \
      --sunshine-user "$sunshine_user" \
      --sunshine-password "$sunshine_password" \
      --sunshine-pin "$sunshine_pin" \
      --sunshine-port "$stream_port" \
      --public-stream-host "$PUBLIC_STREAM_HOST" \
      --no-reboot
  fi

  write_state running expose 75 "Aktiviere oeffentliche Stream-Ports auf dem Proxmox-Host." "$extra_json"
  /opt/beagle/scripts/reconcile-public-streams.sh >/dev/null

  write_state running verify 90 "Pruefe Sunshine API ueber ${PUBLIC_STREAM_HOST}." "$extra_json"
  if ! verify_public_api "$public_api_url" "$sunshine_user" "$sunshine_password"; then
    guest_ip="$(meta_get sunshine-ip)"
    if [[ -z "$guest_ip" ]]; then
      guest_ip="$(guest_ipv4 2>/dev/null || true)"
    fi
    if [[ -n "$guest_ip" ]]; then
      direct_api_url="https://${guest_ip}:$((stream_port + 1))"
      if verify_public_api "$direct_api_url" "$sunshine_user" "$sunshine_password"; then
        write_state ready complete 100 "Sunshine ist bereit. Direkter API-Check in der VM war erfolgreich; oeffentlicher Self-Check wurde auf dem Host uebersprungen." "$extra_json"
        exit 0
      fi
    fi
    write_state error verify 100 "Sunshine API ist nach der Vorbereitung noch nicht erreichbar." "$extra_json"
    exit 1
  fi

  write_state ready complete 100 "Sunshine ist bereit. Der Beagle-USB-Installer kann heruntergeladen werden." "$extra_json"
}

main "$@"
