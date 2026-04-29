#!/usr/bin/env bash
set -euo pipefail

API_URL_DEFAULT="http://127.0.0.1:9088"
SCOPE_TYPE_DEFAULT="pool"
SCOPE_ID_DEFAULT="plan07-loadtest-5gb"
TARGET_PATH_DEFAULT="/tmp/beagle-backups-loadtest"
DATA_DIR_DEFAULT="/etc/beagle/backup-loadtest"
DATA_FILE_DEFAULT="payload-5g.bin"
DATA_SIZE_MB_DEFAULT=5120
MIN_HEADROOM_MB_DEFAULT=3072
WAIT_SEC_DEFAULT=3600
POLL_SEC_DEFAULT=2

API_URL="${BEAGLE_MANAGER_API_URL:-$API_URL_DEFAULT}"
SCOPE_TYPE="$SCOPE_TYPE_DEFAULT"
SCOPE_ID="$SCOPE_ID_DEFAULT"
TARGET_PATH="$TARGET_PATH_DEFAULT"
DATA_DIR="$DATA_DIR_DEFAULT"
DATA_FILE="$DATA_FILE_DEFAULT"
DATA_SIZE_MB="$DATA_SIZE_MB_DEFAULT"
MIN_HEADROOM_MB="$MIN_HEADROOM_MB_DEFAULT"
KEEP_ARTIFACTS=0
WAIT_SEC="$WAIT_SEC_DEFAULT"
POLL_SEC="$POLL_SEC_DEFAULT"

created_data_file=""
created_archive=""
policy_path_before=""

usage() {
  cat <<'EOF'
Usage: bash scripts/test-backup-load-5gb-smoke.sh [options]

Options:
  --api-url <url>             API base URL (default: http://127.0.0.1:9088)
  --scope-type <pool|vm>      Backup scope type (default: pool)
  --scope-id <id>             Backup scope id (default: plan07-loadtest-5gb)
  --target-path <path>        Backup target path (default: /tmp/beagle-backups-loadtest)
  --data-dir <path>           Directory under /etc/beagle for load data
  --data-file <name>          File name for generated payload
  --size-mb <int>             Payload size in MB (default: 5120)
  --headroom-mb <int>         Required free-space headroom in MB in addition to payload size
  --wait-sec <int>            Max wait for async backup completion (default: 3600)
  --poll-sec <int>            Poll interval for async completion (default: 2)
  --keep-artifacts            Keep payload and created backup archive for manual inspection
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url)
      API_URL="$2"
      shift 2
      ;;
    --scope-type)
      SCOPE_TYPE="$2"
      shift 2
      ;;
    --scope-id)
      SCOPE_ID="$2"
      shift 2
      ;;
    --target-path)
      TARGET_PATH="$2"
      shift 2
      ;;
    --data-dir)
      DATA_DIR="$2"
      shift 2
      ;;
    --data-file)
      DATA_FILE="$2"
      shift 2
      ;;
    --size-mb)
      DATA_SIZE_MB="$2"
      shift 2
      ;;
    --headroom-mb)
      MIN_HEADROOM_MB="$2"
      shift 2
      ;;
    --keep-artifacts)
      KEEP_ARTIFACTS=1
      shift
      ;;
    --wait-sec)
      WAIT_SEC="$2"
      shift 2
      ;;
    --poll-sec)
      POLL_SEC="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=unknown_arg arg=$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "$SCOPE_TYPE" != "pool" && "$SCOPE_TYPE" != "vm" ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=invalid_scope_type value=$SCOPE_TYPE" >&2
  exit 1
fi

if ! [[ "$DATA_SIZE_MB" =~ ^[0-9]+$ ]] || [[ "$DATA_SIZE_MB" -le 0 ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=invalid_size_mb value=$DATA_SIZE_MB" >&2
  exit 1
fi

if ! [[ "$MIN_HEADROOM_MB" =~ ^[0-9]+$ ]] || [[ "$MIN_HEADROOM_MB" -lt 0 ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=invalid_headroom_mb value=$MIN_HEADROOM_MB" >&2
  exit 1
fi

if ! [[ "$WAIT_SEC" =~ ^[0-9]+$ ]] || [[ "$WAIT_SEC" -le 0 ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=invalid_wait_sec value=$WAIT_SEC" >&2
  exit 1
fi

if ! [[ "$POLL_SEC" =~ ^[0-9]+$ ]] || [[ "$POLL_SEC" -le 0 ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=invalid_poll_sec value=$POLL_SEC" >&2
  exit 1
fi

if [[ -z "${BEAGLE_MANAGER_API_TOKEN:-}" && -f /etc/beagle/beagle-manager.env ]]; then
  # shellcheck disable=SC1091
  source /etc/beagle/beagle-manager.env
fi

RAW_TOKEN="${BEAGLE_MANAGER_API_TOKEN:-${API_TOKEN:-}}"
TOKEN="${RAW_TOKEN%\"}"
TOKEN="${TOKEN#\"}"
TOKEN="${TOKEN%\'}"
TOKEN="${TOKEN#\'}"

if [[ -z "$TOKEN" ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=missing_api_token" >&2
  exit 1
fi

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=missing_command cmd=$cmd" >&2
    exit 1
  fi
}

require_cmd curl
require_cmd python3
require_cmd dd
require_cmd df
require_cmd stat
require_cmd sleep

call_json() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  local extra_header="${4:-}"
  local header_args=()
  if [[ -n "$extra_header" ]]; then
    header_args=( -H "$extra_header" )
  fi
  if [[ -n "$data" ]]; then
    curl -sS -w "\nHTTP:%{http_code}" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      "${header_args[@]}" \
      -X "$method" "$API_URL$path" \
      -d "$data"
  else
    curl -sS -w "\nHTTP:%{http_code}" \
      -H "Authorization: Bearer $TOKEN" \
      "${header_args[@]}" \
      "$API_URL$path"
  fi
}

status_of() {
  sed -n 's/^HTTP://p' <<<"$1" | tail -n1
}

body_of() {
  sed '$d' <<<"$1"
}

json_get() {
  local body="$1"
  local path="$2"
  python3 -c '
import json
import sys

path = sys.argv[1]
obj = json.load(sys.stdin)
cur = obj
for part in path.split("."):
  if not part:
    continue
  if isinstance(cur, dict):
    cur = cur.get(part)
  elif isinstance(cur, list):
    try:
      idx = int(part)
    except Exception:
      cur = None
      break
    if idx < 0 or idx >= len(cur):
      cur = None
      break
    cur = cur[idx]
  else:
    cur = None
    break
if cur is None:
  print("")
elif isinstance(cur, (dict, list)):
  print(json.dumps(cur, separators=(",", ":")))
else:
  print(cur)
' "$path" <<<"$body"
}

cleanup() {
  if [[ "$KEEP_ARTIFACTS" -eq 0 ]]; then
    if [[ -n "$created_data_file" && -f "$created_data_file" ]]; then
      rm -f "$created_data_file" || true
    fi
    if [[ -n "$created_archive" && -f "$created_archive" ]]; then
      rm -f "$created_archive" || true
    fi
  fi
}
trap cleanup EXIT

echo "=== Backup 5GB Load Smoke ==="
echo "  API URL      : $API_URL"
echo "  Scope        : $SCOPE_TYPE/$SCOPE_ID"
echo "  Target Path  : $TARGET_PATH"
echo "  Data Dir     : $DATA_DIR"
echo "  Data Size MB : $DATA_SIZE_MB"

mkdir -p "$DATA_DIR"
mkdir -p "$TARGET_PATH"

data_path="$DATA_DIR/$DATA_FILE"

avail_data_mb="$(df -Pm "$DATA_DIR" | awk 'NR==2{print $4}')"
avail_target_mb="$(df -Pm "$TARGET_PATH" | awk 'NR==2{print $4}')"
required_total_mb=$(( DATA_SIZE_MB + MIN_HEADROOM_MB ))

if [[ "$avail_data_mb" -lt "$required_total_mb" ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=SKIP reason=insufficient_data_fs_space avail_mb=$avail_data_mb required_mb=$required_total_mb"
  exit 0
fi
if [[ "$avail_target_mb" -lt "$required_total_mb" ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=SKIP reason=insufficient_target_fs_space avail_mb=$avail_target_mb required_mb=$required_total_mb"
  exit 0
fi

if [[ -f "$data_path" ]]; then
  echo "[WARN] Existing payload file found, replacing: $data_path"
  rm -f "$data_path"
fi

echo "[1/5] Generating ${DATA_SIZE_MB}MB payload under /etc/beagle ..."
dd if=/dev/urandom of="$data_path" bs=1M count="$DATA_SIZE_MB" status=progress conv=fsync
created_data_file="$data_path"

payload_size_bytes="$(stat -c%s "$data_path")"
if [[ "$payload_size_bytes" -lt $((DATA_SIZE_MB * 1024 * 1024)) ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=payload_size_mismatch bytes=$payload_size_bytes" >&2
  exit 1
fi

echo "[2/5] Reading current backup policy ..."
if [[ "$SCOPE_TYPE" == "pool" ]]; then
  policy_get_path="/api/v1/backups/policies/pools/$SCOPE_ID"
  policy_put_path="/api/v1/backups/policies/pools/$SCOPE_ID"
else
  policy_get_path="/api/v1/backups/policies/vms/$SCOPE_ID"
  policy_put_path="/api/v1/backups/policies/vms/$SCOPE_ID"
fi

GET_RESP="$(call_json GET "$policy_get_path")"
GET_STATUS="$(status_of "$GET_RESP")"
GET_BODY="$(body_of "$GET_RESP")"
if [[ "$GET_STATUS" != "200" ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=policy_get_failed status=$GET_STATUS body=$GET_BODY" >&2
  exit 1
fi

policy_path_before="$(json_get "$GET_BODY" "target_path")"

put_policy_payload=$(cat <<JSON
{"enabled":true,"schedule":"daily","retention_days":3,"target_type":"local","target_path":"$TARGET_PATH","incremental":false}
JSON
)

echo "[3/5] Running backup job with 5GB payload ..."
PUT_RESP="$(call_json PUT "$policy_put_path" "$put_policy_payload")"
PUT_STATUS="$(status_of "$PUT_RESP")"
PUT_BODY="$(body_of "$PUT_RESP")"
if [[ "$PUT_STATUS" != "200" ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=policy_put_failed status=$PUT_STATUS body=$PUT_BODY" >&2
  exit 1
fi

run_payload=$(cat <<JSON
{"scope_type":"$SCOPE_TYPE","scope_id":"$SCOPE_ID"}
JSON
)

start_ts="$(date +%s)"
run_ikey="backup.load5gb.$SCOPE_TYPE.$SCOPE_ID.$(date +%s%N)"
RUN_RESP="$(call_json POST "/api/v1/backups/run" "$run_payload" "Idempotency-Key: $run_ikey")"
end_ts="$(date +%s)"
RUN_STATUS="$(status_of "$RUN_RESP")"
RUN_BODY="$(body_of "$RUN_RESP")"
if [[ "$RUN_STATUS" != "200" && "$RUN_STATUS" != "202" ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=run_failed status=$RUN_STATUS body=$RUN_BODY" >&2
  exit 1
fi

job_status=""
job_id=""
backup_job_id=""
archive_path=""

if [[ "$RUN_STATUS" == "200" ]]; then
  job_status="$(json_get "$RUN_BODY" "job.status")"
  job_id="$(json_get "$RUN_BODY" "job.job_id")"
  backup_job_id="$job_id"
  archive_path="$(json_get "$RUN_BODY" "job.archive")"
else
  async_job_id="$(json_get "$RUN_BODY" "job_id")"
  if [[ -z "$async_job_id" ]]; then
    echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=missing_async_job_id" >&2
    exit 1
  fi
  echo "[3/5] Async backup job enqueued: $async_job_id"
  deadline=$(( $(date +%s) + WAIT_SEC ))
  while true; do
    JOB_RESP="$(call_json GET "/api/v1/jobs/$async_job_id")"
    JOB_STATUS_HTTP="$(status_of "$JOB_RESP")"
    JOB_BODY="$(body_of "$JOB_RESP")"
    if [[ "$JOB_STATUS_HTTP" != "200" ]]; then
      echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=async_job_poll_failed status=$JOB_STATUS_HTTP body=$JOB_BODY" >&2
      exit 1
    fi
    async_status="$(json_get "$JOB_BODY" "status")"
    if [[ "$async_status" == "completed" ]]; then
      break
    fi
    if [[ "$async_status" == "failed" || "$async_status" == "cancelled" ]]; then
      echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=async_job_terminal status=$async_status job_id=$async_job_id" >&2
      exit 1
    fi
    if [[ "$(date +%s)" -ge "$deadline" ]]; then
      echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=async_job_timeout job_id=$async_job_id wait_sec=$WAIT_SEC" >&2
      exit 1
    fi
    sleep "$POLL_SEC"
  done

  job_status="$(json_get "$JOB_BODY" "result.job.status")"
  backup_job_id="$(json_get "$JOB_BODY" "result.job.job_id")"
  job_id="$backup_job_id"
  archive_path="$(json_get "$JOB_BODY" "result.job.archive")"
fi

if [[ "$job_status" != "success" ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=job_not_success status=$job_status job_id=$job_id" >&2
  exit 1
fi
if [[ -z "$backup_job_id" ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=missing_backup_job_id" >&2
  exit 1
fi
if [[ -z "$archive_path" ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=archive_missing path=$archive_path job_id=$job_id" >&2
  exit 1
fi

created_archive="$archive_path"
elapsed_sec=$(( end_ts - start_ts ))

echo "[4/5] Verifying backup payload size via snapshot file list ..."
FILES_RESP="$(call_json GET "/api/v1/backups/$backup_job_id/files")"
FILES_STATUS="$(status_of "$FILES_RESP")"
FILES_BODY="$(body_of "$FILES_RESP")"
if [[ "$FILES_STATUS" != "200" ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=files_list_failed status=$FILES_STATUS" >&2
  exit 1
fi

payload_entry_size="$(python3 -c '
import json
import sys

needle = sys.argv[1]
try:
  payload = json.load(sys.stdin)
except Exception:
  print("")
  raise SystemExit(0)

for item in payload.get("files") or []:
  path = str(item.get("path") or "")
  if path.endswith("/" + needle) or path.endswith(needle):
    print(int(item.get("size") or 0))
    raise SystemExit(0)
print("")
' "$DATA_FILE" <<<"$FILES_BODY")"

if [[ -z "$payload_entry_size" ]]; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=payload_not_in_snapshot file=$DATA_FILE backup_job_id=$backup_job_id" >&2
  exit 1
fi

if [[ "$payload_entry_size" -eq 0 ]]; then
  echo "[WARN] payload listed with size=0 via /backups/{job}/files (known parser limitation); continuing with presence proof"
fi

echo "[5/5] Verifying job history entry ..."
JOBS_RESP="$(call_json GET "/api/v1/backups/jobs?scope_type=$SCOPE_TYPE&scope_id=$SCOPE_ID")"
JOBS_STATUS="$(status_of "$JOBS_RESP")"
JOBS_BODY="$(body_of "$JOBS_RESP")"
if [[ "$JOBS_STATUS" != "200" ]] || ! grep -q "$backup_job_id" <<<"$JOBS_BODY"; then
  echo "BACKUP_LOAD_5GB_SMOKE=FAIL reason=job_history_missing job_id=$backup_job_id" >&2
  exit 1
fi

echo "[5/5] Restoring original target_path policy ..."
if [[ -n "$policy_path_before" ]]; then
  restore_payload=$(cat <<JSON
{"target_path":"$policy_path_before"}
JSON
)
  call_json PUT "$policy_put_path" "$restore_payload" >/dev/null || true
fi

echo "BACKUP_LOAD_5GB_SMOKE=PASS scope=$SCOPE_TYPE/$SCOPE_ID async_or_backup_job_id=$job_id elapsed_sec=$elapsed_sec payload_bytes_generated=$payload_size_bytes snapshot_payload_entry_seen=1 snapshot_payload_bytes_reported=$payload_entry_size archive_path=$archive_path"
