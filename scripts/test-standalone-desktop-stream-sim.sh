#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d /tmp/beagle-standalone-e2e.XXXXXX)"
chmod 0755 "${TMP_DIR}"
PORT="${BEAGLE_TEST_PORT:-19088}"
API_BASE="http://127.0.0.1:${PORT}/api/v1"
CONTROL_PLANE_LOG="${TMP_DIR}/control-plane.log"
LISTENER_LOG="${TMP_DIR}/moonlight-listener.log"
PROVIDER_DIR="${TMP_DIR}/provider"
DATA_DIR="${TMP_DIR}/data"
FAKE_ISO_DIR="${TMP_DIR}/fake-iso"
FAKE_ISO_PATH="${TMP_DIR}/fake-ubuntu.iso"
CP_PID=""
LISTENER_PID=""

cleanup() {
  if [[ -n "${LISTENER_PID}" ]]; then
    kill "${LISTENER_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${CP_PID}" ]]; then
    kill "${CP_PID}" >/dev/null 2>&1 || true
    wait "${CP_PID}" >/dev/null 2>&1 || true
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] Missing required command: $1" >&2
    exit 1
  fi
}

json_get() {
  local expression="$1"
  python3 -c "import json,sys; data=json.load(sys.stdin); value=${expression}; print(value if value is not None else '')"
}

http_get() {
  local path="$1"
  local response_file
  local http_code
  response_file="$(mktemp "${TMP_DIR}/http-get.XXXXXX")"
  http_code="$(curl -sS -o "${response_file}" -w '%{http_code}' "${API_BASE}${path}")"
  if [[ "${http_code}" != 2* ]]; then
    echo "[ERROR] GET ${path} failed with HTTP ${http_code}" >&2
    sed -n '1,200p' "${response_file}" >&2 || true
    rm -f "${response_file}"
    return 1
  fi
  cat "${response_file}"
  rm -f "${response_file}"
}

http_post_json() {
  local path="$1"
  local payload="$2"
  local response_file
  local http_code
  response_file="$(mktemp "${TMP_DIR}/http-post.XXXXXX")"
  http_code="$(curl -sS -o "${response_file}" -w '%{http_code}' -H 'Content-Type: application/json' -X POST "${API_BASE}${path}" -d "${payload}")"
  if [[ "${http_code}" != 2* ]]; then
    echo "[ERROR] POST ${path} failed with HTTP ${http_code}" >&2
    sed -n '1,240p' "${response_file}" >&2 || true
    rm -f "${response_file}"
    return 1
  fi
  cat "${response_file}"
  rm -f "${response_file}"
}

require_cmd python3
require_cmd curl
require_cmd xorriso

mkdir -p "${FAKE_ISO_DIR}/casper" "${PROVIDER_DIR}" "${DATA_DIR}"
printf 'fake-kernel' > "${FAKE_ISO_DIR}/casper/vmlinuz"
printf 'fake-initrd' > "${FAKE_ISO_DIR}/casper/initrd"

xorriso -as mkisofs -volid UBUNTU_FAKE -joliet -rock -output "${FAKE_ISO_PATH}" \
  -graft-points \
  /casper/vmlinuz="${FAKE_ISO_DIR}/casper/vmlinuz" \
  /casper/initrd="${FAKE_ISO_DIR}/casper/initrd" >/dev/null 2>&1

env \
  BEAGLE_HOST_PROVIDER=beagle \
  BEAGLE_MANAGER_LISTEN_HOST=127.0.0.1 \
  BEAGLE_MANAGER_LISTEN_PORT="${PORT}" \
  BEAGLE_MANAGER_ALLOW_LOCALHOST_NOAUTH=1 \
  BEAGLE_MANAGER_DATA_DIR="${DATA_DIR}" \
  BEAGLE_BEAGLE_PROVIDER_STATE_DIR="${PROVIDER_DIR}" \
  PVE_DCV_PROXY_SERVER_NAME=127.0.0.1 \
  BEAGLE_UBUNTU_ISO_URL="file://${FAKE_ISO_PATH}" \
  BEAGLE_UBUNTU_LOCAL_ISO_DIR="${TMP_DIR}/iso-cache" \
  python3 "${REPO_ROOT}/beagle-host/bin/beagle-control-plane.py" >"${CONTROL_PLANE_LOG}" 2>&1 &
CP_PID="$!"

for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

if ! curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then
  echo "[ERROR] Control plane failed to start" >&2
  sed -n '1,200p' "${CONTROL_PLANE_LOG}" >&2 || true
  exit 1
fi

CATALOG_JSON="$(http_get '/provisioning/catalog')"
NODE_NAME="$(printf '%s' "${CATALOG_JSON}" | json_get "data.get('catalog',{}).get('defaults',{}).get('node','')")"
BRIDGE_NAME="$(printf '%s' "${CATALOG_JSON}" | json_get "data.get('catalog',{}).get('defaults',{}).get('bridge','')")"
BRIDGE_CANDIDATE="$(printf '%s' "${CATALOG_JSON}" | json_get "(data.get('catalog',{}).get('bridges') or [''])[0]")"
DESKTOP_DEFAULT="$(printf '%s' "${CATALOG_JSON}" | json_get "data.get('catalog',{}).get('defaults',{}).get('desktop','')")"
DISK_STORAGE="$(printf '%s' "${CATALOG_JSON}" | json_get "data.get('catalog',{}).get('defaults',{}).get('disk_storage','')")"
ISO_STORAGE="$(printf '%s' "${CATALOG_JSON}" | json_get "data.get('catalog',{}).get('defaults',{}).get('iso_storage','')")"

if [[ -n "${BRIDGE_CANDIDATE}" && "${BRIDGE_NAME}" != "${BRIDGE_CANDIDATE}" ]]; then
  BRIDGE_NAME="${BRIDGE_CANDIDATE}"
fi

if virsh --connect qemu:///system net-info default >/dev/null 2>&1; then
  BRIDGE_NAME="default"
fi

if [[ -z "${NODE_NAME}" || -z "${BRIDGE_NAME}" ]]; then
  echo "[ERROR] Provisioning catalog missing required defaults" >&2
  exit 1
fi

if ! printf '%s' "${CATALOG_JSON}" | python3 -c "import json,sys; data=json.load(sys.stdin); ids={item.get('id') for item in data.get('catalog',{}).get('desktop_profiles',[])}; sys.exit(0 if 'xfce' in ids else 1)"; then
  echo "[ERROR] XFCE desktop profile not available in provisioning catalog" >&2
  exit 1
fi

CREATE_PAYLOAD="$(python3 - <<PY
import json
print(json.dumps({
  "node": "${NODE_NAME}",
  "name": "beagle-desktop-e2e",
  "desktop": "xfce",
  "memory": 4096,
  "cores": 2,
  "disk_gb": 40,
  "bridge": "${BRIDGE_NAME}",
  "disk_storage": "${DISK_STORAGE}",
  "iso_storage": "${ISO_STORAGE}",
  "guest_user": "beagle",
  "guest_password": "BeagleTest123!",
  "extra_packages": ["htop"],
  "start": True
}))
PY
)"

CREATE_JSON="$(http_post_json '/provisioning/vms' "${CREATE_PAYLOAD}")"
DESKTOP_VMID="$(printf '%s' "${CREATE_JSON}" | json_get "data.get('provisioned_vm',{}).get('vmid','')")"
DESKTOP_LABEL="$(printf '%s' "${CREATE_JSON}" | json_get "data.get('provisioned_vm',{}).get('desktop_label','')")"

if [[ -z "${DESKTOP_VMID}" ]]; then
  echo "[ERROR] Failed to create desktop VM via provisioning API" >&2
  printf '%s\n' "${CREATE_JSON}" >&2
  exit 1
fi

PROVISION_STATE="$(http_get "/provisioning/vms/${DESKTOP_VMID}")"
PROFILE_JSON="$(http_get "/vms/${DESKTOP_VMID}")"
STREAM_HOST="$(printf '%s' "${PROFILE_JSON}" | json_get "data.get('profile',{}).get('stream_host','')")"
MOONLIGHT_PORT="$(printf '%s' "${PROFILE_JSON}" | json_get "data.get('profile',{}).get('moonlight_port','')")"
SUNSHINE_API_URL="$(printf '%s' "${PROFILE_JSON}" | json_get "data.get('profile',{}).get('sunshine_api_url','')")"

if [[ "${DESKTOP_LABEL}" != "XFCE" ]]; then
  echo "[ERROR] Desktop VM not provisioned with XFCE (label=${DESKTOP_LABEL})" >&2
  exit 1
fi

if [[ -z "${SUNSHINE_API_URL}" ]]; then
  echo "[ERROR] Desktop profile missing sunshine_api_url" >&2
  exit 1
fi

if ! printf '%s' "${PROVISION_STATE}" | python3 -c "import json,sys; s=json.load(sys.stdin).get('provisioning',{}); msg=str(s.get('message','')).lower(); sys.exit(0 if ('sunshine' in msg and 'xfce' in msg) else 1)"; then
  echo "[ERROR] Provisioning state message does not confirm XFCE+Sunshine provisioning" >&2
  printf '%s\n' "${PROVISION_STATE}" >&2
  exit 1
fi

THINCLIENT_VMID=9200
python3 - <<PY
import json
from pathlib import Path
provider_dir = Path("${PROVIDER_DIR}")
vms_path = provider_dir / "vms.json"
vm_configs_path = provider_dir / "vm-configs" / "${NODE_NAME}" / f"${THINCLIENT_VMID}.json"
if vms_path.exists():
    vms = json.loads(vms_path.read_text(encoding='utf-8'))
else:
    vms = []
vms = [item for item in vms if int(item.get('vmid', 0) or 0) != ${THINCLIENT_VMID}]
vms.append({
    "vmid": ${THINCLIENT_VMID},
    "node": "${NODE_NAME}",
    "name": "thinclient-sim-vm",
    "status": "running",
    "tags": "beagle;endpoint"
})
vms_path.write_text(json.dumps(sorted(vms, key=lambda x: int(x.get('vmid', 0))), indent=2) + "\n", encoding='utf-8')
vm_configs_path.parent.mkdir(parents=True, exist_ok=True)
vm_configs_path.write_text(json.dumps({
    "vmid": ${THINCLIENT_VMID},
    "name": "thinclient-sim-vm",
    "description": "beagle-role: endpoint\\nbeagle-thinclient-sim: true\\n",
    "net0": "virtio,bridge=${BRIDGE_NAME}"
}, indent=2) + "\n", encoding='utf-8')
PY

if [[ -z "${STREAM_HOST}" || -z "${MOONLIGHT_PORT}" ]]; then
  echo "[ERROR] Desktop profile missing stream target data" >&2
  printf '%s\n' "${PROFILE_JSON}" >&2
  exit 1
fi

python3 - <<PY >"${LISTENER_LOG}" 2>&1 &
import socket
import time
host = "127.0.0.1"
port = int("${MOONLIGHT_PORT}")
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((host, port))
server.listen(1)
server.settimeout(6)
end = time.time() + 6
while time.time() < end:
    try:
        conn, _ = server.accept()
    except socket.timeout:
        continue
    conn.sendall(b"MOONLIGHT_SIM_OK")
    conn.close()
    break
server.close()
PY
LISTENER_PID="$!"

python3 - <<PY
import socket
import sys
host = "${STREAM_HOST}"
port = int("${MOONLIGHT_PORT}")
sock = socket.create_connection((host, port), timeout=3)
sock.recv(64)
sock.close()
print("THINCLIENT_STREAM_SIM_OK")
PY

SUNSHINE_ACCESS="$(http_post_json "/vms/${DESKTOP_VMID}/sunshine-access" '{}')"
if ! printf '%s' "${SUNSHINE_ACCESS}" | python3 -c "import json,sys; data=json.load(sys.stdin); url=data.get('sunshine_access',{}).get('url',''); sys.exit(0 if url else 1)"; then
  echo "[ERROR] sunshine-access endpoint did not return access URL" >&2
  printf '%s\n' "${SUNSHINE_ACCESS}" >&2
  exit 1
fi

INVENTORY_JSON="$(http_get '/vms')"
if ! printf '%s' "${INVENTORY_JSON}" | python3 -c "import json,sys; vmids={int(item.get('profile',{}).get('vmid',0) or item.get('vmid',0) or 0) for item in json.load(sys.stdin).get('vms',[])}; sys.exit(0 if ${DESKTOP_VMID} in vmids else 1)"; then
  echo "[ERROR] API inventory does not include the provisioned desktop VM" >&2
  exit 1
fi

if ! python3 - <<PY
import json
from pathlib import Path
vms_path = Path("${PROVIDER_DIR}") / "vms.json"
payload = json.loads(vms_path.read_text(encoding='utf-8')) if vms_path.exists() else []
vmids = {int(item.get('vmid', 0) or 0) for item in payload if isinstance(item, dict)}
raise SystemExit(0 if ${DESKTOP_VMID} in vmids and ${THINCLIENT_VMID} in vmids else 1)
PY
then
  echo "[ERROR] Provider state does not include desktop VM and thinclient simulation VM" >&2
  exit 1
fi

echo "PASS: Standalone provisioning E2E simulation successful"
echo "  Desktop VMID: ${DESKTOP_VMID} (Ubuntu XFCE + Sunshine provisioning path)"
echo "  Thinclient VMID: ${THINCLIENT_VMID} (stream simulation connected to ${STREAM_HOST}:${MOONLIGHT_PORT})"
echo "  Sunshine API URL: ${SUNSHINE_API_URL}"
