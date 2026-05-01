#!/usr/bin/env bash
# Validate that VM streaming readiness persists across a full VM reboot
# without any manual firewall/route intervention on the host.
#
# Usage:
#   scripts/test-stream-persistence-reboot-smoke.sh --vmid 100 --node beagle-0
#
# Optional env:
#   BEAGLE_SMOKE_API_BASE          default: http://127.0.0.1:9088
#   BEAGLE_SMOKE_API_TOKEN         overrides token lookup from /etc/beagle/beagle-manager.env
#   BEAGLE_SMOKE_WAIT_RUNNING_SEC  default: 360
#   BEAGLE_SMOKE_WAIT_STREAM_SEC   default: 240
#   BEAGLE_SMOKE_POLL_SEC          default: 5
#   BEAGLE_MANAGER_ENV_FILE        default: /etc/beagle/beagle-manager.env

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
source "$SCRIPT_DIR/lib/provider_shell.sh"

VMID="${VMID:-}"
NODE="${NODE:-}"
API_BASE="${BEAGLE_SMOKE_API_BASE:-http://127.0.0.1:9088}"
API_TOKEN="${BEAGLE_SMOKE_API_TOKEN:-}"
WAIT_RUNNING_SEC="${BEAGLE_SMOKE_WAIT_RUNNING_SEC:-360}"
WAIT_STREAM_SEC="${BEAGLE_SMOKE_WAIT_STREAM_SEC:-240}"
POLL_SEC="${BEAGLE_SMOKE_POLL_SEC:-5}"
MANAGER_ENV_FILE="${BEAGLE_MANAGER_ENV_FILE:-/etc/beagle/beagle-manager.env}"

usage() {
  echo "Usage: $0 --vmid VMID --node NODE" >&2
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --vmid)
        VMID="$2"
        shift 2
        ;;
      --node)
        NODE="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "Unknown argument: $1" >&2
        usage
        exit 1
        ;;
    esac
  done

  if [[ -z "$VMID" || -z "$NODE" ]]; then
    usage
    exit 1
  fi
}

trim_quotes() {
  sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//" | tr -d '\r\n[:space:]'
}

load_api_token() {
  if [[ -n "$API_TOKEN" ]]; then
    return 0
  fi
  if [[ ! -f "$MANAGER_ENV_FILE" ]]; then
    echo "[ERROR] API token file missing: $MANAGER_ENV_FILE" >&2
    exit 1
  fi

  local token_raw=""
  token_raw="$(sed -n 's/^BEAGLE_MANAGER_API_TOKEN=//p' "$MANAGER_ENV_FILE" | head -n1)"
  if [[ -z "$token_raw" ]]; then
    token_raw="$(sed -n 's/^BEAGLE_API_TOKEN=//p' "$MANAGER_ENV_FILE" | head -n1)"
  fi
  if [[ -z "$token_raw" ]]; then
    token_raw="$(sed -n 's/^BEAGLE_MANAGER_TOKEN=//p' "$MANAGER_ENV_FILE" | head -n1)"
  fi

  API_TOKEN="$(printf '%s' "$token_raw" | trim_quotes)"
  if [[ -z "$API_TOKEN" ]]; then
    echo "[ERROR] Could not resolve API token from $MANAGER_ENV_FILE" >&2
    exit 1
  fi
}

api_get() {
  local path="$1"
  curl -fsS -H "Authorization: Bearer $API_TOKEN" "${API_BASE%/}${path}"
}

json_get() {
  local json_payload="$1"
  local expr="$2"
  python3 - "$json_payload" "$expr" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
expr = sys.argv[2]
cur = payload
for part in expr.split('.'):
    if isinstance(cur, dict):
        cur = cur.get(part)
    else:
        cur = None
        break
if cur is None:
    print("")
elif isinstance(cur, (dict, list)):
    print(json.dumps(cur))
else:
    print(str(cur))
PY
}

check_sunshine_api() {
  local sunshine_api_url="$1"
  local wait_sec="$2"
  local fallback_url="${3:-}"
  local deadline=$((SECONDS + wait_sec))
  local code="000"
  local url_in_use="$sunshine_api_url"

  while (( SECONDS < deadline )); do
    code="$(curl -sk --max-time 6 -o /dev/null -w '%{http_code}' "${url_in_use%/}/api/apps" 2>/dev/null || echo '000')" # tls-bypass-allowlist: persistence smoke probes local Sunshine API over self-signed TLS
    if [[ "$code" == "200" || "$code" == "401" ]]; then
      echo "[OK]  Sunshine API reachable after check (HTTP $code, url=${url_in_use%/}/api/apps)"
      return 0
    fi
    if [[ -n "$fallback_url" && "$url_in_use" != "$fallback_url" ]]; then
      url_in_use="$fallback_url"
    fi
    sleep "$POLL_SEC"
  done

  echo "[ERROR] Sunshine API did not recover (tried ${sunshine_api_url%/}/api/apps${fallback_url:+ and ${fallback_url%/}/api/apps}) within ${wait_sec}s (last HTTP $code)" >&2
  return 1
}

wait_for_vm_running() {
  local vmid="$1"
  local deadline=$((SECONDS + WAIT_RUNNING_SEC))
  local status=""

  while (( SECONDS < deadline )); do
    local payload
    if payload="$(api_get "/api/v1/vms/${vmid}" 2>/dev/null)"; then
      status="$(json_get "$payload" "profile.status")"
      if [[ "$status" == "running" ]]; then
        echo "[OK]  VM ${vmid} reported as running"
        return 0
      fi
    fi
    sleep "$POLL_SEC"
  done

  echo "[ERROR] VM ${vmid} did not return to running within ${WAIT_RUNNING_SEC}s (last status=$status)" >&2
  return 1
}

main() {
  parse_args "$@"
  load_api_token

  echo "=== Stream Persistence Reboot Smoke ==="
  echo "  VMID       : $VMID"
  echo "  Node       : $NODE"
  echo "  API Base   : $API_BASE"
  echo "  Wait VM up : ${WAIT_RUNNING_SEC}s"
  echo "  Wait API   : ${WAIT_STREAM_SEC}s"
  echo ""

  echo "[1] Loading VM stream profile ..."
  local vm_payload sunshine_api_url sunshine_api_url_fallback stream_host moonlight_port moonlight_local_host egress_mode egress_type
  vm_payload="$(api_get "/api/v1/vms/${VMID}")"
  if [[ "$(json_get "$vm_payload" "profile.status")" != "running" ]]; then
    echo "[ERROR] VM ${VMID} is not running before reboot" >&2
    exit 1
  fi
  sunshine_api_url="$(json_get "$vm_payload" "profile.sunshine_api_url")"
  stream_host="$(json_get "$vm_payload" "profile.stream_host")"
  moonlight_port="$(json_get "$vm_payload" "profile.moonlight_port")"
  moonlight_local_host="$(json_get "$vm_payload" "profile.moonlight_local_host")"
  egress_mode="$(json_get "$vm_payload" "profile.egress_mode")"
  egress_type="$(json_get "$vm_payload" "profile.egress_type")"

  if [[ -z "$sunshine_api_url" ]]; then
    echo "[ERROR] profile.sunshine_api_url missing for VM ${VMID}" >&2
    exit 1
  fi
  if [[ -n "$moonlight_local_host" ]]; then
    local sunshine_port
    sunshine_port="$(python3 - "$sunshine_api_url" <<'PY'
from urllib.parse import urlparse
import sys
u = urlparse(sys.argv[1])
print(str(u.port or 50001))
PY
)"
    sunshine_api_url_fallback="https://${moonlight_local_host}:${sunshine_port}"
  fi

  echo "[OK]  profile egress_mode=$egress_mode egress_type=$egress_type"

  echo "[2] Validating Sunshine API before reboot ..."
  check_sunshine_api "$sunshine_api_url" 30 "$sunshine_api_url_fallback"

  echo "[3] Rebooting VM ${VMID} ..."
  beagle_provider_reboot_vm "$VMID"

  echo "[4] Waiting for VM running state ..."
  wait_for_vm_running "$VMID"

  echo "[5] Waiting for stream API recovery after reboot ..."
  check_sunshine_api "$sunshine_api_url" "$WAIT_STREAM_SEC" "$sunshine_api_url_fallback"

  echo "[6] Verifying stream profile stability after reboot ..."
  vm_payload="$(api_get "/api/v1/vms/${VMID}")"
  if [[ "$(json_get "$vm_payload" "profile.status")" != "running" ]]; then
    echo "[ERROR] VM ${VMID} is not running after reboot" >&2
    exit 1
  fi
  if [[ "$(json_get "$vm_payload" "profile.sunshine_api_url")" != "$sunshine_api_url" ]]; then
    echo "[ERROR] sunshine_api_url changed unexpectedly across reboot" >&2
    exit 1
  fi
  if [[ "$(json_get "$vm_payload" "profile.egress_mode")" != "$egress_mode" ]]; then
    echo "[ERROR] egress_mode changed unexpectedly across reboot" >&2
    exit 1
  fi
  if [[ "$(json_get "$vm_payload" "profile.egress_type")" != "$egress_type" ]]; then
    echo "[ERROR] egress_type changed unexpectedly across reboot" >&2
    exit 1
  fi
  echo "[OK]  stream profile unchanged after reboot"

  echo ""
  echo "STREAM_REBOOT_PERSISTENCE_SMOKE=PASS"
  echo "  vmid=$VMID node=$NODE"
  echo "  stream_host=$stream_host moonlight_port=$moonlight_port"
  echo "  sunshine_api_url=$sunshine_api_url"
}

main "$@"
