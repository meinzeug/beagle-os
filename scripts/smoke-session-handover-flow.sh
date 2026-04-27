#!/usr/bin/env bash
set -euo pipefail

VMID="${1:-100}"
TARGET_NODE="${2:-srv2}"
MANAGER_URL="${BEAGLE_MANAGER_URL:-http://127.0.0.1:9088}"
TOKEN_VALUE="smoke-session-handover-token-${VMID}"
SESSION_ID="smoke-session-${VMID}"
STATE_DIR="${BEAGLE_MANAGER_DATA_DIR:-/var/lib/beagle/beagle-manager}"
TOKEN_FILE="${STATE_DIR}/endpoint-tokens/$(printf '%s' "${TOKEN_VALUE}" | sha256sum | awk '{print $1}').json"
SESSION_FILE="${STATE_DIR}/session-manager/sessions.json"
START_RESPONSE="$(mktemp)"
END_RESPONSE="$(mktemp)"

cleanup() {
  runuser -u beagle-manager -- python3 - <<'PY' "$TOKEN_VALUE" "$SESSION_ID" "$SESSION_FILE"
import json
import sys
from pathlib import Path

sys.path[:0] = ['/opt/beagle/beagle-host/bin', '/opt/beagle/beagle-host', '/opt/beagle/beagle-host/services', '/opt/beagle/beagle-host/providers', '/opt/beagle']
import service_registry as s

token = sys.argv[1]
session_id = sys.argv[2]
session_file = Path(sys.argv[3])
s.endpoint_token_path(token).unlink(missing_ok=True)
if session_file.exists():
    payload = json.loads(session_file.read_text(encoding='utf-8'))
    sessions = payload.get('sessions') if isinstance(payload, dict) else {}
    if isinstance(sessions, dict):
        sessions.pop(session_id, None)
        session_file.write_text(json.dumps(payload), encoding='utf-8')
PY
  rm -f "$START_RESPONSE" "$END_RESPONSE"
}
trap cleanup EXIT

runuser -u beagle-manager -- python3 - <<'PY' "$VMID" "$TOKEN_VALUE" "$SESSION_ID"
import sys
sys.path[:0] = ['/opt/beagle/beagle-host/bin', '/opt/beagle/beagle-host', '/opt/beagle/beagle-host/services', '/opt/beagle/beagle-host/providers', '/opt/beagle']
import service_registry as s

vmid = int(sys.argv[1])
token = sys.argv[2]
session_id = sys.argv[3]
vm = s.find_vm(vmid)
if vm is None:
    raise SystemExit(f"vm {vmid} not found")
s.store_endpoint_token(token, {"vmid": vmid, "node": str(vm.node), "hostname": f"smoke-endpoint-{vmid}"})
s.session_manager_service().register_session(
    session_id=session_id,
    pool_id="smoke-pool",
    vm_id=vmid,
    user_id="smoke-user",
    node_id=str(vm.node),
)
PY

start_ts="$(python3 - <<'PY'
import time
print(time.monotonic())
PY
)"

curl -fsS -H "Authorization: Bearer ${TOKEN_VALUE}" \
  "${MANAGER_URL%/}/api/v1/session/current?vmid=${VMID}" >"$START_RESPONSE"

runuser -u beagle-manager -- python3 - <<'PY' "$SESSION_ID" "$TARGET_NODE"
import sys
sys.path[:0] = ['/opt/beagle/beagle-host/bin', '/opt/beagle/beagle-host', '/opt/beagle/beagle-host/services', '/opt/beagle/beagle-host/providers', '/opt/beagle']
import service_registry as s

session_id = sys.argv[1]
target_node = sys.argv[2]
transfer = s.session_manager_service().transfer_session(session_id, target_node)
if transfer.status != "completed":
    raise SystemExit(f"handover failed: {transfer.error}")
PY

curl -fsS -H "Authorization: Bearer ${TOKEN_VALUE}" \
  "${MANAGER_URL%/}/api/v1/session/current?vmid=${VMID}" >"$END_RESPONSE"

end_ts="$(python3 - <<'PY'
import time
print(time.monotonic())
PY
)"

python3 - <<'PY' "$START_RESPONSE" "$END_RESPONSE" "$TARGET_NODE" "$start_ts" "$end_ts"
import json
import sys

start_payload = json.load(open(sys.argv[1], encoding="utf-8"))
end_payload = json.load(open(sys.argv[2], encoding="utf-8"))
target_node = sys.argv[3]
start_ts = float(sys.argv[4])
end_ts = float(sys.argv[5])
elapsed = end_ts - start_ts

assert start_payload.get("ok") is True, start_payload
assert end_payload.get("ok") is True, end_payload
assert end_payload.get("current_node") == target_node, end_payload
assert elapsed < 5.0, f"handover broker path too slow: {elapsed:.2f}s"

print(f"SESSION_HANDOVER_SMOKE=PASS elapsed={elapsed:.2f}s target_node={target_node} stream_host={end_payload.get('stream_host','')}")
PY
