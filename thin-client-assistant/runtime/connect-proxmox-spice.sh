#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_runtime_config

if [[ "${PVE_THIN_CLIENT_CONNECTION_METHOD:-direct}" != "proxmox-ticket" ]]; then
  echo "SPICE Proxmox connector requires PVE_THIN_CLIENT_CONNECTION_METHOD=proxmox-ticket" >&2
  exit 1
fi

if [[ -z "${PVE_THIN_CLIENT_PROXMOX_HOST:-}" || -z "${PVE_THIN_CLIENT_PROXMOX_NODE:-}" || -z "${PVE_THIN_CLIENT_PROXMOX_VMID:-}" ]]; then
  echo "Missing Proxmox host, node or VMID." >&2
  exit 1
fi

if [[ -z "${PVE_THIN_CLIENT_CONNECTION_USERNAME:-}" || -z "${PVE_THIN_CLIENT_CONNECTION_PASSWORD:-}" ]]; then
  echo "Missing Proxmox username or password." >&2
  exit 1
fi

API_SCHEME="${PVE_THIN_CLIENT_PROXMOX_SCHEME:-https}"
API_PORT="${PVE_THIN_CLIENT_PROXMOX_PORT:-8006}"
VERIFY_TLS="${PVE_THIN_CLIENT_PROXMOX_VERIFY_TLS:-0}"
REMOTE_VIEWER_BIN="${PVE_THIN_CLIENT_REMOTE_VIEWER_BIN:-remote-viewer}"
API_BASE="${API_SCHEME}://${PVE_THIN_CLIENT_PROXMOX_HOST}:${API_PORT}/api2/json"
USERNAME="${PVE_THIN_CLIENT_CONNECTION_USERNAME}@${PVE_THIN_CLIENT_PROXMOX_REALM:-pam}"

CURL_OPTS=(--silent --show-error --fail)
if [[ "$VERIFY_TLS" != "1" ]]; then
  CURL_OPTS+=(-k)
fi

LOGIN_RESPONSE="$(
  curl "${CURL_OPTS[@]}" \
    --data-urlencode "username=${USERNAME}" \
    --data-urlencode "password=${PVE_THIN_CLIENT_CONNECTION_PASSWORD}" \
    "${API_BASE}/access/ticket"
)"

read_ticket_field() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
field = sys.argv[2]
print(payload["data"].get(field, ""))
PY
}

TICKET="$(read_ticket_field "$LOGIN_RESPONSE" "ticket")"
CSRF_TOKEN="$(read_ticket_field "$LOGIN_RESPONSE" "CSRFPreventionToken")"

if [[ -z "$TICKET" || -z "$CSRF_TOKEN" ]]; then
  echo "Unable to obtain Proxmox access ticket." >&2
  exit 1
fi

SPICE_RESPONSE="$(
  curl "${CURL_OPTS[@]}" \
    --cookie "PVEAuthCookie=${TICKET}" \
    --header "CSRFPreventionToken: ${CSRF_TOKEN}" \
    --data-urlencode "proxy=${PVE_THIN_CLIENT_PROXMOX_HOST}" \
    "${API_BASE}/nodes/${PVE_THIN_CLIENT_PROXMOX_NODE}/qemu/${PVE_THIN_CLIENT_PROXMOX_VMID}/spiceproxy"
)"

VV_FILE="$(mktemp --suffix=.vv)"
python3 - "$SPICE_RESPONSE" "$VV_FILE" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(sys.argv[1])
target = Path(sys.argv[2])
lines = ["[virt-viewer]"]
for key, value in payload["data"].items():
    lines.append(f"{key}={value}")
target.write_text("\n".join(lines) + "\n")
PY

exec "$REMOTE_VIEWER_BIN" "$VV_FILE"
