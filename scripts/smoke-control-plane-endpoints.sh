#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BEAGLE_SMOKE_BASE_URL:-https://127.0.0.1/beagle-api}"
TOKEN="${BEAGLE_SMOKE_API_TOKEN:-${BEAGLE_MANAGER_API_TOKEN:-${PVE_DCV_API_TOKEN:-}}}"
CURL_TLS_ARGS=()

if [[ "${BEAGLE_SMOKE_INSECURE:-1}" == "1" ]]; then
  CURL_TLS_ARGS+=(--insecure)
fi

if [[ -z "$TOKEN" ]]; then
  echo "BEAGLE_SMOKE_API_TOKEN or BEAGLE_MANAGER_API_TOKEN is required" >&2
  exit 2
fi

request_json() {
  local path="$1"
  local payload
  payload="$(curl -fsS "${CURL_TLS_ARGS[@]}" \
    -H "X-Beagle-Api-Token: ${TOKEN}" \
    "${BASE_URL%/}${path}")"
  python3 -c '
import json
import sys

path = sys.argv[1]
payload = json.loads(sys.argv[2])
if payload.get("ok") is False:
    raise SystemExit(f"{path}: ok=false payload={payload!r}")
print(f"OK {path}")
' "$path" "$payload"
}

request_text() {
  local url="$1"
  curl -fsS "${CURL_TLS_ARGS[@]}" "$url" | head -n 1 | grep -Eq "$2"
  echo "OK $url"
}

request_json "/api/v1/health"
request_json "/api/v1/vms"
request_json "/api/v1/cluster/status"
request_json "/api/v1/virtualization/overview"
request_json "/api/v1/jobs"
request_text "${BEAGLE_SMOKE_METRICS_URL:-https://127.0.0.1/metrics}" '^# HELP '
