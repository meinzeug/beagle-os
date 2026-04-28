#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_SH="${COMMON_SH:-$SCRIPT_DIR/common.sh}"
RUNTIME_ENDPOINT_ENROLLMENT_SH="${RUNTIME_ENDPOINT_ENROLLMENT_SH:-$SCRIPT_DIR/runtime_endpoint_enrollment.sh}"

if [[ -r "$COMMON_SH" ]]; then
  # shellcheck disable=SC1090
  source "$COMMON_SH"
fi
if [[ -r "$RUNTIME_ENDPOINT_ENROLLMENT_SH" ]]; then
  # shellcheck disable=SC1090
  source "$RUNTIME_ENDPOINT_ENROLLMENT_SH"
fi

runtime_manager_sync_url() {
  local manager_url="${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}"
  [[ -n "$manager_url" ]] || return 1
  printf '%s/api/v1/endpoints/device/sync\n' "${manager_url%/}"
}

runtime_manager_confirm_wiped_url() {
  local manager_url="${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}"
  [[ -n "$manager_url" ]] || return 1
  printf '%s/api/v1/endpoints/device/confirm-wiped\n' "${manager_url%/}"
}

runtime_device_id() {
  local configured="${PVE_THIN_CLIENT_BEAGLE_DEVICE_ID:-}"
  if [[ -n "$configured" ]]; then
    printf '%s\n' "$configured"
    return 0
  fi
  runtime_endpoint_id
}

runtime_os_version() {
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    printf '%s\n' "${PRETTY_NAME:-${VERSION_ID:-unknown}}"
    return 0
  fi
  printf '%s\n' "unknown"
}

runtime_cpu_model() {
  awk -F: '/model name/ {gsub(/^[ \t]+/, "", $2); print $2; exit}' /proc/cpuinfo 2>/dev/null || true
}

runtime_ram_gb() {
  awk '/MemTotal:/ {printf "%d\n", ($2 + 1024*1024 - 1) / (1024*1024); exit}' /proc/meminfo 2>/dev/null || printf '0\n'
}

runtime_gpu_model() {
  if command -v lspci >/dev/null 2>&1; then
    lspci 2>/dev/null | awk -F': ' '/VGA compatible controller|3D controller|Display controller/ {print $2; exit}' || true
    return 0
  fi
  printf '%s\n' ""
}

runtime_network_interfaces_json() {
  if command -v ip >/dev/null 2>&1; then
    ip -o link show 2>/dev/null | awk -F': ' '{print $2}' | cut -d@ -f1 | grep -v '^lo$' | python3 -c 'import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))'
    return 0
  fi
  printf '[]\n'
}

runtime_wireguard_active() {
  local iface="${1:-wg-beagle}"
  ip link show "$iface" >/dev/null 2>&1
}

runtime_wireguard_ip() {
  local iface="${1:-wg-beagle}"
  ip -o -4 addr show dev "$iface" 2>/dev/null | awk '{print $4; exit}' || true
}

runtime_wipe_report_file_path() {
  local state_dir
  state_dir="$(beagle_state_dir)"
  printf '%s/device-wipe-report.json\n' "$state_dir"
}

runtime_wipe_report_json() {
  local wipe_report_file
  wipe_report_file="${1:-$(runtime_wipe_report_file_path)}"
  if [[ -r "$wipe_report_file" ]]; then
    python3 - "$wipe_report_file" <<'PY'
import json, sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
if not isinstance(payload, dict):
    payload = {}
print(json.dumps(payload))
PY
    return 0
  fi
  printf '{}\n'
}

runtime_device_sync_payload() {
  local device_id="${1:-}"
  local hostname_value="${2:-}"
  local wg_iface="${3:-wg-beagle}"
  local wg_active="${4:-0}"
  local wg_ip="${5:-}"
  local wipe_report_json interfaces_json cpu_model cpu_cores ram_gb gpu_model os_version

  wipe_report_json="$(runtime_wipe_report_json)"
  interfaces_json="$(runtime_network_interfaces_json)"
  cpu_model="$(runtime_cpu_model)"
  cpu_cores="$(nproc 2>/dev/null || printf '0')"
  ram_gb="$(runtime_ram_gb)"
  gpu_model="$(runtime_gpu_model)"
  os_version="$(runtime_os_version)"

  python3 - "$device_id" "$hostname_value" "$os_version" "$cpu_model" "$cpu_cores" "$ram_gb" "$gpu_model" "$interfaces_json" "$wg_iface" "$wg_active" "$wg_ip" "$wipe_report_json" <<'PY'
import json, sys

payload = {
    "device_id": sys.argv[1],
    "hostname": sys.argv[2],
    "os_version": sys.argv[3],
    "hardware": {
        "cpu_model": sys.argv[4],
        "cpu_cores": int(sys.argv[5] or "0"),
        "ram_gb": int(sys.argv[6] or "0"),
        "gpu_model": sys.argv[7],
        "network_interfaces": json.loads(sys.argv[8] or "[]"),
        "disk_gb": 0,
    },
    "vpn": {
        "interface": sys.argv[9],
        "active": sys.argv[10] == "1",
        "assigned_ip": sys.argv[11],
    },
    "metrics": {
        "streaming_active": False,
    },
    "reports": {
        "wipe": json.loads(sys.argv[12] or "{}"),
    },
}
print(json.dumps(payload))
PY
}

apply_runtime_sync_response() {
  local response_file="${1:-}"
  [[ -r "$response_file" ]] || return 1

  local state_dir lock_file wipe_file policy_file
  state_dir="$(beagle_state_dir)"
  mkdir -p "$state_dir" >/dev/null 2>&1 || true
  lock_file="$state_dir/device.locked"
  wipe_file="$state_dir/device.wipe-pending"
  policy_file="$state_dir/device-policy.json"

  python3 - "$response_file" "$lock_file" "$wipe_file" "$policy_file" <<'PY'
import json, sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
commands = payload.get("commands") if isinstance(payload, dict) else {}
policy = payload.get("policy") if isinstance(payload, dict) else {}

lock_file = Path(sys.argv[2])
wipe_file = Path(sys.argv[3])
policy_file = Path(sys.argv[4])

if commands.get("lock_screen"):
    lock_file.write_text("locked\n", encoding="utf-8")
else:
    lock_file.unlink(missing_ok=True)

if commands.get("wipe_pending"):
    wipe_file.write_text("wipe_pending\n", encoding="utf-8")
else:
    wipe_file.unlink(missing_ok=True)

policy_file.write_text(json.dumps(policy, indent=2), encoding="utf-8")
PY
}

sync_device_runtime_state() {
  local sync_url manager_token manager_pin manager_ca_cert device_id hostname_value wg_iface wg_active=0 wg_ip="" response_file payload_file http_status curl_bin
  local -a curl_args tls_args

  sync_url="$(runtime_manager_sync_url)" || return 0
  manager_token="${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}"
  [[ -n "$manager_token" ]] || return 0
  manager_pin="${PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  manager_ca_cert="${PVE_THIN_CLIENT_BEAGLE_MANAGER_CA_CERT:-}"
  device_id="$(runtime_device_id)"
  hostname_value="$(runtime_endpoint_hostname)"
  wg_iface="${WG_IFACE:-wg-beagle}"
  if runtime_wireguard_active "$wg_iface"; then
    wg_active=1
    wg_ip="$(runtime_wireguard_ip "$wg_iface")"
  fi

  response_file="$(mktemp)"
  payload_file="$(mktemp)"
  curl_bin="$(runtime_curl_bin)"
  runtime_device_sync_payload "$device_id" "$hostname_value" "$wg_iface" "$wg_active" "$wg_ip" >"$payload_file"

  curl_args=("$curl_bin" -fsS --connect-timeout 8 --max-time 25 --output "$response_file" --write-out '%{http_code}' \
    -H "Authorization: Bearer ${manager_token}" \
    -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "$sync_url" "$manager_pin" "$manager_ca_cert")
  curl_args+=("${tls_args[@]}")
  http_status="$("${curl_args[@]}" --data-binary "@${payload_file}" "$sync_url" || true)"

  if [[ "$http_status" == "200" ]]; then
    apply_runtime_sync_response "$response_file" || true
    beagle_log_event "device.sync.ok" "device_id=${device_id} wg_active=${wg_active} status=200"
    rm -f "$payload_file" "$response_file"
    return 0
  fi

  beagle_log_event "device.sync.error" "device_id=${device_id} status=${http_status:-unknown}"
  rm -f "$payload_file" "$response_file"
  return 1
}

confirm_device_wiped_runtime() {
  local confirm_url manager_token manager_pin manager_ca_cert device_id response_file http_status curl_bin
  local -a curl_args tls_args

  confirm_url="$(runtime_manager_confirm_wiped_url)" || return 0
  manager_token="${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}"
  [[ -n "$manager_token" ]] || return 0
  device_id="${1:-$(runtime_device_id)}"
  [[ -n "$device_id" ]] || return 1
  manager_pin="${PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  manager_ca_cert="${PVE_THIN_CLIENT_BEAGLE_MANAGER_CA_CERT:-}"
  response_file="$(mktemp)"
  curl_bin="$(runtime_curl_bin)"

  curl_args=("$curl_bin" -fsS --connect-timeout 8 --max-time 20 --output "$response_file" --write-out '%{http_code}' \
    -H "Authorization: Bearer ${manager_token}" \
    -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "$confirm_url" "$manager_pin" "$manager_ca_cert")
  curl_args+=("${tls_args[@]}")
  http_status="$("${curl_args[@]}" --data '{}' "$confirm_url" || true)"

  if [[ "$http_status" == "200" ]]; then
    beagle_log_event "device.wipe.confirmed" "device_id=${device_id} status=200"
    rm -f "$response_file"
    return 0
  fi

  beagle_log_event "device.wipe.confirm-error" "device_id=${device_id} status=${http_status:-unknown}"
  rm -f "$response_file"
  return 1
}
