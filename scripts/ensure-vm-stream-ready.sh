#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib/provider_shell.sh"
PROVIDER_MODULE_PATH="${BEAGLE_PROVIDER_MODULE_PATH:-$SCRIPT_DIR/lib/beagle_provider.py}"
PROVIDER_HELPER_AVAILABLE_CACHE="${PROVIDER_HELPER_AVAILABLE_CACHE:-}"

# Ensure provider imports can resolve top-level repo modules (e.g. core/*) on live hosts.
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
VMID="${VMID:-}"
NODE="${NODE:-}"
CONFIG_DIR="${PVE_DCV_CONFIG_DIR:-/etc/beagle}"
MANAGER_DATA_DIR="${BEAGLE_MANAGER_DATA_DIR:-/var/lib/beagle/beagle-manager}"
STATE_DIR="${BEAGLE_INSTALLER_PREP_DIR:-$MANAGER_DATA_DIR/installer-prep}"
STATE_FILE="${BEAGLE_INSTALLER_PREP_STATE_FILE:-}"
PUBLIC_STREAM_HOST_RAW="${BEAGLE_PUBLIC_STREAM_HOST:-${PVE_DCV_PROXY_SERVER_NAME:-$(hostname -f 2>/dev/null || hostname)}}"
STREAMS_FILE="${BEAGLE_PUBLIC_STREAMS_FILE:-$MANAGER_DATA_DIR/public-streams.json}"
VM_SECRETS_DIR="${BEAGLE_VM_SECRETS_DIR:-$MANAGER_DATA_DIR/vm-secrets}"
BEAGLE_STREAM_SERVER_DEFAULT_USER="${BEAGLE_STREAM_SERVER_DEFAULT_USER:-}"
BEAGLE_STREAM_SERVER_DEFAULT_PASSWORD="${BEAGLE_STREAM_SERVER_DEFAULT_PASSWORD:-}"
BEAGLE_STREAM_SERVER_DEFAULT_PIN="${BEAGLE_STREAM_SERVER_DEFAULT_PIN:-}"
BEAGLE_STREAM_SERVER_DEFAULT_GUEST_USER="${BEAGLE_STREAM_SERVER_DEFAULT_GUEST_USER:-beagle}"
HOST_TLS_CERT_FILE="${BEAGLE_HOST_TLS_CERT_FILE:-/etc/beagle/manager-ssl.pem}"

resolve_public_stream_host() {
  python3 - "$1" <<'PY'
import ipaddress
import socket
import sys

host = str(sys.argv[1] or "").strip()
if not host:
    print("")
    raise SystemExit(0)
try:
    ipaddress.ip_address(host)
except ValueError:
    pass
else:
    print(host)
    raise SystemExit(0)

try:
    infos = socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
except socket.gaierror:
    print(host)
    raise SystemExit(0)

for item in infos:
    ip = str(item[4][0]).strip()
    if ip:
        print(ip)
        raise SystemExit(0)
print(host)
PY
}

PUBLIC_STREAM_HOST="$(resolve_public_stream_host "$PUBLIC_STREAM_HOST_RAW")"

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

meta_get() {
  local key="$1"
  python3 - "$PROVIDER_MODULE_PATH" "$NODE" "$VMID" "$key" <<'PY'
import sys
from pathlib import Path
from urllib.parse import unquote

provider_module_path = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(provider_module_path.parent))

from beagle_provider import vm_config

node = sys.argv[2]
vmid = int(sys.argv[3])
key = sys.argv[4].strip().lower()
config = vm_config(node, vmid)
text = unquote(str(config.get("description", "") or ""))
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

beagle_stream_server_guest_status_json() {
  local command
  command='binary=0; service=0; process=0; command -v beagle-stream-server >/dev/null 2>&1 && binary=1; (systemctl is-active beagle-stream-server >/dev/null 2>&1 || systemctl is-active beagle-stream-server.service >/dev/null 2>&1) && service=1; pgrep -x beagle-stream-server >/dev/null 2>&1 && process=1; printf "{\"binary\":%s,\"service\":%s,\"process\":%s}\n" "$binary" "$service" "$process"'
  beagle_provider_guest_exec_sync_bash "$VMID" "$command"
}

beagle_stream_server_guest_desktop_smoke_json() {
  local guest_user="$1"
  local command
  command="$(cat <<'EOF'
guest_user="__GUEST_USER__"
xauth="/home/${guest_user}/.Xauthority"
xset_ok=0
light_locker_running=0
xfce_power_running=0

if command -v xset >/dev/null 2>&1; then
  if DISPLAY=:0 XAUTHORITY="$xauth" xset q >/dev/null 2>&1; then
    xset_ok=1
  fi
fi

pgrep -x light-locker >/dev/null 2>&1 && light_locker_running=1
pgrep -x xfce4-power-manager >/dev/null 2>&1 && xfce_power_running=1

printf '{"xset_ok":%s,"light_locker_running":%s,"xfce4_power_manager_running":%s}\n' "$xset_ok" "$light_locker_running" "$xfce_power_running"
EOF
)"
  command="${command//__GUEST_USER__/$guest_user}"
  beagle_provider_guest_exec_sync_bash "$VMID" "$command"
}

repair_beagle_stream_server_guest_runtime() {
  local command
  command='if command -v /usr/local/bin/beagle-stream-server-healthcheck >/dev/null 2>&1; then /usr/local/bin/beagle-stream-server-healthcheck --repair-only >/dev/null 2>&1 || true; else systemctl daemon-reload >/dev/null 2>&1 || true; systemctl enable --now beagle-stream-server.service >/dev/null 2>&1 || true; systemctl restart beagle-stream-server.service >/dev/null 2>&1 || true; fi; binary=0; service=0; process=0; command -v beagle-stream-server >/dev/null 2>&1 && binary=1; (systemctl is-active beagle-stream-server >/dev/null 2>&1 || systemctl is-active beagle-stream-server.service >/dev/null 2>&1) && service=1; pgrep -x beagle-stream-server >/dev/null 2>&1 && process=1; printf "{\"binary\":%s,\"service\":%s,\"process\":%s}\n" "$binary" "$service" "$process"'
  beagle_provider_guest_exec_sync_bash "$VMID" "$command"
}

guest_ipv4() {
  beagle_provider_guest_ipv4 "$VMID"
}

vm_secret_get() {
  local field="$1"
  python3 - "$VM_SECRETS_DIR" "$NODE" "$VMID" "$field" <<'PY'
import json
import sys
from pathlib import Path

secrets_dir, node, vmid, field = sys.argv[1:5]
path = Path(secrets_dir) / f"{node}-{vmid}.json"
if not path.is_file():
    raise SystemExit(0)
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)
value = payload.get(field)
if value is None:
    raise SystemExit(0)
print(str(value))
PY
}

latest_ubuntu_state_credential() {
  local field="$1"
  python3 - "$MANAGER_DATA_DIR/ubuntu-beagle-install" "$VMID" "$field" <<'PY'
import json
import sys
from pathlib import Path

tokens_dir = Path(sys.argv[1])
vmid = int(sys.argv[2])
field = str(sys.argv[3]).strip()
if not tokens_dir.is_dir():
    raise SystemExit(0)

latest_created_at = ""
latest_value = ""
for path in sorted(tokens_dir.glob("*.json")):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(payload, dict):
        continue
    if int(payload.get("vmid", 0) or 0) != vmid:
        continue
    value = str(payload.get(field, "") or "").strip()
    if not value:
        continue
    created_at = str(payload.get("created_at", "") or "")
    if created_at >= latest_created_at:
        latest_created_at = created_at
        latest_value = value

if latest_value:
    print(latest_value)
PY
}

verify_public_api() {
  local api_url="$1"
  local beagle_stream_server_user="$2"
  local beagle_stream_server_password="$3"
  local pinned_pubkey="${4:-}"
  local -a curl_args=(curl -fsS --connect-timeout 4 --max-time 10 --user "${beagle_stream_server_user}:${beagle_stream_server_password}")

  if [[ "$api_url" == https://* ]]; then
    if [[ -n "$pinned_pubkey" ]]; then
      # tls-bypass-allowlist: beagle-stream-server API uses self-signed cert; pubkey-pinning provides the security guarantee
      curl_args+=(--insecure --pinnedpubkey "$pinned_pubkey") # tls-bypass-allowlist: beagle-stream-server API uses self-signed cert; pubkey pinning is enforced
    elif [[ -n "${BEAGLE_PUBLIC_TLS_PINNED_PUBKEY:-}" ]]; then
      curl_args+=(--pinnedpubkey "${BEAGLE_PUBLIC_TLS_PINNED_PUBKEY}")
    elif [[ -f "$HOST_TLS_CERT_FILE" ]]; then
      curl_args+=(--cacert "$HOST_TLS_CERT_FILE")
    else
      return 1
    fi
  fi

  "${curl_args[@]}" "${api_url%/}/api/apps" >/dev/null
}

verify_public_api_insecure_local() {
  local api_url="$1"
  local beagle_stream_server_user="$2"
  local beagle_stream_server_password="$3"

  if [[ "$api_url" != https://192.168.* && "$api_url" != https://10.* && "$api_url" != https://172.16.* && "$api_url" != https://172.17.* && "$api_url" != https://172.18.* && "$api_url" != https://172.19.* && "$api_url" != https://172.2*.* && "$api_url" != https://172.30.* && "$api_url" != https://172.31.* ]]; then
    return 1
  fi

  # tls-bypass-allowlist: this fallback is limited to direct private guest addresses used for host-local readiness probes
  curl -fsS --connect-timeout 4 --max-time 10 --insecure --user "${beagle_stream_server_user}:${beagle_stream_server_password}" "${api_url%/}/api/apps" >/dev/null # tls-bypass-allowlist: host-local readiness probe against self-signed Beagle Stream Server TLS
}

run_public_stream_reconcile() {
  if command -v systemctl >/dev/null 2>&1 && systemctl cat beagle-public-streams.service >/dev/null 2>&1; then
    systemctl start beagle-public-streams.service
    return 0
  fi
  /opt/beagle/scripts/reconcile-public-streams.sh
}

main() {
  local stream_port beagle_stream_server_user beagle_stream_server_password beagle_stream_server_pin beagle_stream_server_pinned_pubkey guest_user guest_password beagle_stream_server_status_raw beagle_stream_server_status_json desktop_smoke_raw desktop_smoke_json public_api_url direct_api_url guest_ip installer_guest_ip extra_json verify_extra_json

  parse_args "$@"
  [[ -n "$VMID" && -n "$NODE" ]] || { usage; exit 1; }
  state_init

  stream_port="$(meta_get beagle-public-beagle-stream-client-port)"
  if [[ -z "$stream_port" ]]; then
    stream_port="$(allocate_stream_port)"
  fi
  beagle_stream_server_user="$(vm_secret_get beagle_stream_server_username)"
  beagle_stream_server_password="$(vm_secret_get beagle_stream_server_password)"
  beagle_stream_server_pin="$(vm_secret_get beagle_stream_server_pin)"
  beagle_stream_server_pinned_pubkey="$(vm_secret_get beagle_stream_server_pinned_pubkey)"
  if [[ -z "$beagle_stream_server_user" ]]; then
    beagle_stream_server_user="$(meta_get beagle-stream-server-user)"
  fi
  if [[ -z "$beagle_stream_server_password" ]]; then
    beagle_stream_server_password="$(meta_get beagle-stream-server-password)"
  fi
  if [[ -z "$beagle_stream_server_pin" ]]; then
    beagle_stream_server_pin="$(meta_get beagle-stream-server-pin)"
  fi
  if [[ -z "$beagle_stream_server_user" ]]; then
    beagle_stream_server_user="$(latest_ubuntu_state_credential beagle_stream_server_username)"
  fi
  if [[ -z "$beagle_stream_server_password" ]]; then
    beagle_stream_server_password="$(latest_ubuntu_state_credential beagle_stream_server_password)"
  fi
  if [[ -z "$beagle_stream_server_pin" ]]; then
    beagle_stream_server_pin="$(latest_ubuntu_state_credential beagle_stream_server_pin)"
  fi
  guest_user="$(meta_get beagle-stream-server-guest-user)"
  guest_password="$(vm_secret_get guest_password)"
  if [[ -z "$guest_password" ]]; then
    guest_password="$(vm_secret_get password)"
  fi
  if [[ -z "$guest_password" ]]; then
    guest_password="$(latest_ubuntu_state_credential guest_password)"
  fi
  [[ -n "$beagle_stream_server_user" ]] || beagle_stream_server_user="$BEAGLE_STREAM_SERVER_DEFAULT_USER"
  [[ -n "$beagle_stream_server_password" ]] || beagle_stream_server_password="$BEAGLE_STREAM_SERVER_DEFAULT_PASSWORD"
  [[ -n "$beagle_stream_server_pin" ]] || beagle_stream_server_pin="$BEAGLE_STREAM_SERVER_DEFAULT_PIN"
  [[ -n "$beagle_stream_server_user" ]] || beagle_stream_server_user="beagle-stream-server-vm${VMID}"
  [[ -n "$beagle_stream_server_password" ]] || beagle_stream_server_password="beagle-vm${VMID}-beagle-stream-server"
  [[ -n "$beagle_stream_server_pin" ]] || beagle_stream_server_pin="$(printf '%04d' $(( VMID % 10000 )))"
  [[ -n "$guest_user" ]] || guest_user="$BEAGLE_STREAM_SERVER_DEFAULT_GUEST_USER"
  installer_guest_ip="$(meta_get beagle-stream-server-ip)"
  if [[ -z "$installer_guest_ip" ]]; then
    installer_guest_ip="$(guest_ipv4 2>/dev/null || true)"
  fi
  public_api_url="https://${PUBLIC_STREAM_HOST}:$((stream_port + 1))"
  extra_json="$(python3 - "$VMID" "$PUBLIC_STREAM_HOST" "$stream_port" "$public_api_url" "$installer_guest_ip" "$guest_password" <<'PY'
import json
import sys

vmid, stream_host, beagle_stream_client_port, beagle_stream_server_api_url, installer_guest_ip, guest_password = sys.argv[1:7]
print(json.dumps({
    "installer_url": f"/beagle-api/api/v1/vms/{vmid}/installer.sh",
    "stream_host": stream_host,
    "beagle_stream_client_port": beagle_stream_client_port,
    "beagle_stream_server_api_url": beagle_stream_server_api_url,
    "installer_guest_ip": installer_guest_ip,
    "installer_guest_password_available": bool(guest_password),
}))
PY
)"
  write_state running inspect 5 "Pruefe Beagle Stream Server in VM ${VMID}." "$extra_json"

  beagle_stream_server_status_raw="$(beagle_stream_server_guest_status_json)"
  beagle_stream_server_status_json="$(python3 - "$beagle_stream_server_status_raw" <<'PY'
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
  verify_extra_json="$(python3 - "$extra_json" "$beagle_stream_server_status_json" <<'PY'
import json
import sys

base = json.loads(sys.argv[1])
status = json.loads(sys.argv[2])
base["beagle_stream_server_status"] = {
    "binary": bool(status.get("binary")),
    "service": bool(status.get("service")),
    "process": bool(status.get("process")),
}
print(json.dumps(base))
PY
)"

  if python3 - "$beagle_stream_server_status_json" <<'PY'
import json, sys
payload=json.loads(sys.argv[1])
raise SystemExit(0 if payload.get('binary') and not payload.get('service') else 1)
PY
  then
  write_state running repair 20 "Beagle Stream Server ist installiert, aber der Dienst ist inaktiv. Reparatur wird versucht." "$verify_extra_json"
  beagle_stream_server_status_raw="$(repair_beagle_stream_server_guest_runtime)"
  beagle_stream_server_status_json="$(python3 - "$beagle_stream_server_status_raw" <<'PY'
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
  verify_extra_json="$(python3 - "$extra_json" "$beagle_stream_server_status_json" <<'PY'
import json
import sys

base = json.loads(sys.argv[1])
status = json.loads(sys.argv[2])
base["beagle_stream_server_status"] = {
  "binary": bool(status.get("binary")),
  "service": bool(status.get("service")),
  "process": bool(status.get("process")),
}
print(json.dumps(base))
PY
)"
  fi

  if python3 - "$beagle_stream_server_status_json" <<'PY'
import json, sys
payload=json.loads(sys.argv[1])
raise SystemExit(0 if payload.get('binary') and payload.get('service') else 1)
PY
  then
    write_state running verify 65 "Beagle Stream Server ist bereits installiert. Pruefe Beagle Stream Server API." "$verify_extra_json"
  else
    write_state running install 25 "Beagle Stream Server fehlt oder ist nicht aktiv. Installation wird gestartet." "$verify_extra_json"
    local -a configure_args=(
      --beagle-host localhost
      --vmid "$VMID"
      --guest-user "$guest_user"
      --beagle-stream-server-user "$beagle_stream_server_user"
      --beagle-stream-server-password "$beagle_stream_server_password"
      --beagle-stream-server-pin "$beagle_stream_server_pin"
      --beagle-stream-server-port "$stream_port"
      --public-stream-host "$PUBLIC_STREAM_HOST"
      --no-reboot
    )
    if [[ -n "$installer_guest_ip" ]]; then
      configure_args+=(--guest-ip "$installer_guest_ip")
    fi
    if [[ -n "$guest_password" ]]; then
      configure_args+=(--guest-password "$guest_password")
    fi
    /opt/beagle/scripts/configure-beagle-stream-server-guest.sh "${configure_args[@]}"
    beagle_stream_server_status_raw="$(beagle_stream_server_guest_status_json)"
    beagle_stream_server_status_json="$(python3 - "$beagle_stream_server_status_raw" <<'PY'
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
    verify_extra_json="$(python3 - "$extra_json" "$beagle_stream_server_status_json" <<'PY'
import json
import sys

base = json.loads(sys.argv[1])
status = json.loads(sys.argv[2])
base["beagle_stream_server_status"] = {
    "binary": bool(status.get("binary")),
    "service": bool(status.get("service")),
    "process": bool(status.get("process")),
}
print(json.dumps(base))
PY
)"
  fi

  write_state running expose 75 "Aktiviere oeffentliche Stream-Ports auf dem Beagle-Host." "$verify_extra_json"
  run_public_stream_reconcile >/dev/null

  guest_ip="$(meta_get beagle-stream-server-ip)"
  if [[ -z "$guest_ip" ]]; then
    guest_ip="$(guest_ipv4 2>/dev/null || true)"
  fi
  if [[ -n "$guest_ip" ]]; then
    direct_api_url="https://${guest_ip}:$((stream_port + 1))"
    write_state running verify 90 "Pruefe Beagle Stream Server API direkt in der VM." "$verify_extra_json"
    if verify_public_api "$direct_api_url" "$beagle_stream_server_user" "$beagle_stream_server_password" "$beagle_stream_server_pinned_pubkey" || verify_public_api_insecure_local "$direct_api_url" "$beagle_stream_server_user" "$beagle_stream_server_password"; then
      verify_extra_json="$(python3 - "$verify_extra_json" <<'PY'
import json, sys
base = json.loads(sys.argv[1])
base["ready"] = True
base["installer_target_status"] = "ready"
print(json.dumps(base))
PY
)"
      write_state running verify 95 "Beagle Stream Server ist bereit. Pruefe Desktop-Streaming-Guards in der VM." "$verify_extra_json"
      desktop_smoke_raw="$(beagle_stream_server_guest_desktop_smoke_json "$guest_user")"
      desktop_smoke_json="$(python3 - "$desktop_smoke_raw" <<'PY'
import json
import sys

raw = sys.argv[1].strip()
if not raw:
    print('{"xset_ok":0,"light_locker_running":0,"xfce4_power_manager_running":0}')
    raise SystemExit(0)
try:
    payload = json.loads(raw)
except Exception:
    payload = {"xset_ok": 0, "light_locker_running": 0, "xfce4_power_manager_running": 0}
if isinstance(payload, dict):
  out = payload.get('out-data') or payload.get('stdout') or payload.get('output') or ''
else:
  out = ''
try:
    if out:
        inner = json.loads(out.strip().splitlines()[-1])
    else:
        inner = {"xset_ok": 0, "light_locker_running": 0, "xfce4_power_manager_running": 0}
except Exception:
    inner = {"xset_ok": 0, "light_locker_running": 0, "xfce4_power_manager_running": 0}
print(json.dumps(inner))
PY
)"
      verify_extra_json="$(python3 - "$verify_extra_json" "$desktop_smoke_json" <<'PY'
import json
import sys

base = json.loads(sys.argv[1])
desktop = json.loads(sys.argv[2])
base["desktop_smoke"] = {
    "xset_ok": bool(desktop.get("xset_ok")),
    "light_locker_running": bool(desktop.get("light_locker_running")),
    "xfce4_power_manager_running": bool(desktop.get("xfce4_power_manager_running")),
}
print(json.dumps(base))
PY
)"

      if ! python3 - "$desktop_smoke_json" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
ok = bool(payload.get("xset_ok")) and not bool(payload.get("light_locker_running")) and not bool(payload.get("xfce4_power_manager_running"))
raise SystemExit(0 if ok else 1)
PY
      then
        verify_extra_json="$(python3 - "$verify_extra_json" <<'PY'
import json
import sys

base = json.loads(sys.argv[1])
base["desktop_smoke_ok"] = False
base["desktop_smoke_warning"] = "xset q oder Locker/Power-Manager-Pruefung fehlgeschlagen"
print(json.dumps(base))
PY
)"
        if verify_public_api "$public_api_url" "$beagle_stream_server_user" "$beagle_stream_server_password" "$beagle_stream_server_pinned_pubkey"; then
          write_state ready complete 100 "Beagle Stream Server ist bereit, aber Desktop-Streaming-Guards melden Warnungen (xset q oder Locker/Power-Manager)." "$verify_extra_json"
        else
          write_state ready complete 100 "Beagle Stream Server ist bereit (direkter API-Check), aber Desktop-Streaming-Guards melden Warnungen (xset q oder Locker/Power-Manager)." "$verify_extra_json"
        fi
        exit 0
      fi

      verify_extra_json="$(python3 - "$verify_extra_json" <<'PY'
import json
import sys

base = json.loads(sys.argv[1])
base["desktop_smoke_ok"] = True
print(json.dumps(base))
PY
)"

      if verify_public_api "$public_api_url" "$beagle_stream_server_user" "$beagle_stream_server_password" "$beagle_stream_server_pinned_pubkey"; then
        write_state ready complete 100 "Beagle Stream Server ist bereit. Oeffentlicher API-Check und Desktop-Streaming-Guards waren erfolgreich." "$verify_extra_json"
      else
        write_state ready complete 100 "Beagle Stream Server ist bereit. Direkter API-Check und Desktop-Streaming-Guards in der VM waren erfolgreich; oeffentlicher Self-Check wurde auf dem Host uebersprungen." "$verify_extra_json"
      fi
      exit 0
    fi
  fi

  write_state error verify 100 "Beagle Stream Server API ist nach der Vorbereitung noch nicht erreichbar." "$verify_extra_json"
  exit 1
}

main "$@"
