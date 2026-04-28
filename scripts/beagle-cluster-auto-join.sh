#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${PVE_DCV_CONFIG_DIR:-/etc/beagle}"
HOST_ENV_FILE="${CONFIG_DIR}/host.env"
CONTROL_ENV_FILE="${CONFIG_DIR}/beagle-manager.env"
JOIN_ENV_FILE="${BEAGLE_CLUSTER_JOIN_ENV_FILE:-${CONFIG_DIR}/cluster-join.env}"
STATUS_FILE="${BEAGLE_CLUSTER_JOIN_STATUS_FILE:-/var/lib/beagle/beagle-manager/cluster-auto-join-status.json}"
BEAGLECTL_BIN="${BEAGLECTL_BIN:-/opt/beagle/scripts/beaglectl.py}"

log() {
  printf '[beagle-cluster-auto-join] %s\n' "$*" >&2
}

json_status() {
  local status="$1"
  local detail="$2"
  local attempted_target="$3"
  local joined="${4:-false}"
  python3 - "$STATUS_FILE" "$status" "$detail" "$attempted_target" "$joined" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
payload = {
    "status": sys.argv[2],
    "detail": sys.argv[3],
    "target": sys.argv[4],
    "joined": str(sys.argv[5]).lower() == "true",
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

normalize_truthy() {
  printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]'
}

persist_join_disabled() {
  python3 - "$JOIN_ENV_FILE" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(0)
lines = []
seen = False
for raw in path.read_text(encoding="utf-8").splitlines():
    if raw.startswith("BEAGLE_CLUSTER_JOIN_REQUESTED="):
        lines.append('BEAGLE_CLUSTER_JOIN_REQUESTED="no"')
        seen = True
    else:
        lines.append(raw)
if not seen:
    lines.append('BEAGLE_CLUSTER_JOIN_REQUESTED="no"')
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

wait_for_local_api() {
  local token="${1:-}"
  local api_url="${2:-http://127.0.0.1:9088/api/v1/health}"
  local attempt=""
  for attempt in $(seq 1 45); do
    if curl -fsS --max-time 5 -H "Authorization: Bearer ${token}" "$api_url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

if [[ -f "$HOST_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$HOST_ENV_FILE"
fi
if [[ -f "$CONTROL_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONTROL_ENV_FILE"
fi
if [[ -f "$JOIN_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$JOIN_ENV_FILE"
fi

JOIN_REQUESTED="$(normalize_truthy "${BEAGLE_CLUSTER_JOIN_REQUESTED:-no}")"
JOIN_TARGET="${BEAGLE_CLUSTER_JOIN_TARGET:-}"
LOCAL_TOKEN="${BEAGLE_MANAGER_API_TOKEN:-}"
LOCAL_SERVER="${BEAGLE_CLUSTER_JOIN_LOCAL_SERVER:-http://127.0.0.1:9088}"
LOCAL_API_URL="${BEAGLE_CLUSTER_JOIN_LOCAL_API_URL:-${LOCAL_SERVER%/}/api/v1}"
NODE_NAME="${BEAGLE_CLUSTER_NODE_NAME:-$(hostname -s 2>/dev/null || hostname)}"
ADVERTISE_HOST="${BEAGLE_CLUSTER_JOIN_ADVERTISE_HOST:-$(hostname -f 2>/dev/null || hostname)}"

if [[ "$JOIN_REQUESTED" != "1" && "$JOIN_REQUESTED" != "true" && "$JOIN_REQUESTED" != "yes" && "$JOIN_REQUESTED" != "on" ]]; then
  log "cluster auto-join not requested"
  json_status "skipped" "cluster auto-join not requested" "$JOIN_TARGET" false
  exit 0
fi

if [[ -z "$JOIN_TARGET" ]]; then
  log "cluster auto-join requested but no target configured"
  json_status "failed" "cluster auto-join requested but no target configured" "$JOIN_TARGET" false
  exit 1
fi

if [[ -z "$LOCAL_TOKEN" ]]; then
  log "missing local BEAGLE_MANAGER_API_TOKEN"
  json_status "failed" "missing local BEAGLE_MANAGER_API_TOKEN" "$JOIN_TARGET" false
  exit 1
fi

if [[ ! -x "$BEAGLECTL_BIN" ]]; then
  log "beaglectl not found at $BEAGLECTL_BIN"
  json_status "failed" "beaglectl not found at $BEAGLECTL_BIN" "$JOIN_TARGET" false
  exit 1
fi

if ! wait_for_local_api "$LOCAL_TOKEN" "${LOCAL_SERVER%/}/api/v1/health"; then
  log "local control plane did not become ready"
  json_status "failed" "local control plane did not become ready" "$JOIN_TARGET" false
  exit 1
fi

if [[ "$JOIN_TARGET" == http://* || "$JOIN_TARGET" == https://* ]]; then
  log "cluster auto-join target is a leader URL without a join token"
  json_status "failed" "cluster auto-join target is a leader URL without a join token" "$JOIN_TARGET" false
  exit 1
fi

log "attempting cluster join for node $NODE_NAME"
if "$BEAGLECTL_BIN" \
  --server "$LOCAL_SERVER" \
  --token "$LOCAL_TOKEN" \
  cluster join \
  --join-token "$JOIN_TARGET" \
  --node-name "$NODE_NAME" \
  --api-url "$LOCAL_API_URL" \
  --advertise-host "$ADVERTISE_HOST"; then
  persist_join_disabled
  json_status "joined" "cluster join completed" "$JOIN_TARGET" true
  log "cluster join completed"
  exit 0
fi

json_status "failed" "cluster join command failed" "$JOIN_TARGET" false
log "cluster join command failed"
exit 1
