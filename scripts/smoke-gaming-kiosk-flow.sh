#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BEAGLE_SMOKE_BASE_URL:-https://127.0.0.1/beagle-api}"
TOKEN="${BEAGLE_SMOKE_API_TOKEN:-${BEAGLE_MANAGER_API_TOKEN:-}}"
STATE_FILE="${BEAGLE_SMOKE_POOL_STATE_FILE:-/var/lib/beagle/beagle-manager/desktop-pools.json}"
SUDO_BIN="${BEAGLE_SMOKE_SUDO:-sudo}"
CURL_TLS_ARGS=()

if [[ "${BEAGLE_SMOKE_INSECURE:-1}" == "1" ]]; then
  CURL_TLS_ARGS+=(--insecure)
fi

if [[ -z "${TOKEN}" ]]; then
  echo "BEAGLE_SMOKE_API_TOKEN or BEAGLE_MANAGER_API_TOKEN is required" >&2
  exit 2
fi

TMP_ROOT="$(mktemp -d)"
BACKUP_FILE="${TMP_ROOT}/desktop-pools.json.bak"
HAD_STATE=0
STATE_OWNER="${BEAGLE_SMOKE_STATE_OWNER:-beagle-manager}"
STATE_GROUP="${BEAGLE_SMOKE_STATE_GROUP:-beagle-manager}"
STATE_MODE="0644"

capture_state_metadata() {
  if ${SUDO_BIN} test -f "${STATE_FILE}"; then
    STATE_MODE="$(${SUDO_BIN} stat -c '%a' "${STATE_FILE}")"
  fi
}

apply_state_metadata() {
  if ${SUDO_BIN} test -f "${STATE_FILE}"; then
    ${SUDO_BIN} chown "${STATE_OWNER}:${STATE_GROUP}" "${STATE_FILE}"
    ${SUDO_BIN} chmod "${STATE_MODE}" "${STATE_FILE}"
  fi
  ${SUDO_BIN} rm -f "${STATE_FILE}.lock"
}

cleanup() {
  if [[ "${HAD_STATE}" == "1" ]]; then
    ${SUDO_BIN} install -m "${STATE_MODE}" "${BACKUP_FILE}" "${STATE_FILE}"
    apply_state_metadata
  else
    ${SUDO_BIN} rm -f "${STATE_FILE}"
    ${SUDO_BIN} rm -f "${STATE_FILE}.lock"
  fi
  rm -rf "${TMP_ROOT}"
}
trap cleanup EXIT

capture_state_metadata
if ${SUDO_BIN} test -f "${STATE_FILE}"; then
  ${SUDO_BIN} cp "${STATE_FILE}" "${BACKUP_FILE}"
  HAD_STATE=1
fi

STATE_FILE="${STATE_FILE}" ${SUDO_BIN} -E python3 - <<'PY'
import os
import sys
from pathlib import Path

repo_root = Path.cwd()
services_dir = repo_root / "beagle-host" / "services"
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
if str(services_dir) not in sys.path:
    sys.path.insert(0, str(services_dir))

from core.virtualization.desktop_pool import DesktopPoolMode, DesktopPoolSpec, DesktopPoolType
from pool_manager import PoolManagerService

state_file = Path(os.environ["STATE_FILE"])
svc = PoolManagerService(
    state_file=state_file,
    utcnow=lambda: "2026-04-27T12:00:00Z",
)

gaming_pool = "gaming-smoke-flow"
kiosk_pool = "kiosk-smoke-flow"

for pool_id in (gaming_pool, kiosk_pool):
    if svc.get_pool(pool_id):
        svc.delete_pool(pool_id)

svc.create_pool(
    DesktopPoolSpec(
        pool_id=gaming_pool,
        template_id="tpl-gaming-smoke",
        mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
        min_pool_size=1,
        max_pool_size=1,
        warm_pool_size=1,
        cpu_cores=8,
        memory_mib=16384,
        storage_pool="local",
        pool_type=DesktopPoolType.GAMING,
        gpu_class="passthrough-nvidia-geforce-gtx-1080",
    )
)
gaming_vm = svc.register_vm(gaming_pool, 9901)
if str(gaming_vm.get("state") or "") == "free":
    svc.allocate_desktop(gaming_pool, "gaming-smoke-user")
else:
    # Current live hosts may legitimately block real gaming allocation:
    # - srv1 has no usable GPU inventory
    # - srv2 exposes the GTX 1080 as not allocatable for productive pool use
    # For the metrics/API smoke we promote the temporary slot to an active lease
    # after the scheduler-side registration decision has been exercised.
    state = svc._load()
    state["vms"]["9901"]["state"] = "in_use"
    state["vms"]["9901"]["user_id"] = "gaming-smoke-user"
    state["vms"]["9901"]["assigned_at"] = "2026-04-27T12:00:00Z"
    svc._save(state)
svc.update_stream_health(
    pool_id=gaming_pool,
    vmid=9901,
    stream_health={
        "fps": 121,
        "rtt_ms": 7,
        "dropped_frames": 0,
        "encoder_load": 57,
        "gpu_util_pct": 92,
        "gpu_temp_c": 73,
        "window_title": "Steam - Hades",
        "updated_at": "2026-04-27T12:00:00Z",
    },
)

svc.create_pool(
    DesktopPoolSpec(
        pool_id=kiosk_pool,
        template_id="tpl-kiosk-smoke",
        mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
        min_pool_size=1,
        max_pool_size=1,
        warm_pool_size=1,
        cpu_cores=4,
        memory_mib=8192,
        storage_pool="local",
        pool_type=DesktopPoolType.KIOSK,
        session_time_limit_minutes=45,
        session_extension_options_minutes=(30, 60),
    )
)
svc.register_vm(kiosk_pool, 9902)
svc.allocate_desktop(kiosk_pool, "kiosk-smoke-user")
svc.update_stream_health(
    pool_id=kiosk_pool,
    vmid=9902,
    stream_health={
        "fps": 117,
        "rtt_ms": 9,
        "dropped_frames": 12,
        "encoder_load": 95,
        "gpu_util_pct": 88,
        "gpu_temp_c": 71,
        "window_title": "Steam - Hades",
        "updated_at": "2026-04-27T12:00:00Z",
    },
)
PY

apply_state_metadata

gaming_payload="$(curl -fsS "${CURL_TLS_ARGS[@]}" -H "X-Beagle-Api-Token: ${TOKEN}" "${BASE_URL%/}/api/v1/gaming/metrics")"
kiosk_payload="$(curl -fsS "${CURL_TLS_ARGS[@]}" -H "X-Beagle-Api-Token: ${TOKEN}" "${BASE_URL%/}/api/v1/pools/kiosk/sessions")"
extend_payload="$(curl -fsS "${CURL_TLS_ARGS[@]}" -H "X-Beagle-Api-Token: ${TOKEN}" -H "Content-Type: application/json" -X POST -d '{"minutes":30}' "${BASE_URL%/}/api/v1/pools/kiosk/sessions/9902/extend")"

python3 - "$gaming_payload" "$kiosk_payload" "$extend_payload" <<'PY'
import json
import sys

gaming = json.loads(sys.argv[1])
kiosk = json.loads(sys.argv[2])
extend = json.loads(sys.argv[3])

assert gaming.get("ok") is True, gaming
assert kiosk.get("ok") is True, kiosk
assert extend.get("ok") is True, extend

overview = gaming.get("overview") or {}
assert int(overview.get("active_sessions") or 0) >= 1, gaming

active_sessions = gaming.get("active_sessions") or []
gaming_item = next((item for item in active_sessions if item.get("pool_id") == "gaming-smoke-flow"), None)
assert gaming_item, active_sessions
latest = gaming_item.get("latest_sample") or {}
assert float(latest.get("fps") or 0) == 121.0, latest
assert float(latest.get("rtt_ms") or 0) == 7.0, latest
assert float(latest.get("gpu_temp_c") or 0) == 73.0, latest

sessions = kiosk.get("sessions") or []
kiosk_item = next((item for item in sessions if item.get("pool_id") == "kiosk-smoke-flow"), None)
assert kiosk_item, sessions
assert kiosk_item.get("session_extension_options_minutes") == [30, 60], kiosk_item
stream = kiosk_item.get("stream_health") or {}
assert int(stream.get("encoder_load") or 0) == 95, stream
assert int(stream.get("dropped_frames") or 0) == 12, stream

assert int(extend.get("vmid") or 0) == 9902, extend
assert float(extend.get("time_remaining_seconds") or 0) > 0, extend

print("OK /api/v1/gaming/metrics active gaming session visible")
print("OK /api/v1/pools/kiosk/sessions kiosk session visible with configured extension options")
print("OK POST /api/v1/pools/kiosk/sessions/9902/extend accepted configured 30 minute level")
PY
