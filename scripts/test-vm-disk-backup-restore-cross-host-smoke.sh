#!/usr/bin/env bash
set -euo pipefail

# test-vm-disk-backup-restore-cross-host-smoke.sh
# Reproducible smoke for BEA-26:
# - Trigger VM-scope backup on source host
# - Validate archive hash on source + destination host
# - Restore archive to destination filesystem
# - Compare source VM disk hash vs restored disk hash
# - Optional boot-check hook on destination host
#
# Requirements:
# - SSH access to source and destination host
# - Beagle control-plane reachable on source host via 127.0.0.1:9088
# - BEAGLE_MANAGER_API_TOKEN present on source host in /etc/beagle/beagle-manager.env
#
# Notes:
# - This script intentionally does not mutate existing production VMs.
# - Optional --boot-check-cmd can run any destination-side command, e.g.
#   virsh start <restored-test-domain>.

SRC_HOST=""
DST_HOST=""
VMID=""
API_URL="http://127.0.0.1:9088"
DST_RESTORE_DIR="/var/restores/beagle-cross-host"
DST_ARCHIVE_DIR="/var/backups/beagle-cross-host"
SSH_OPTS="-o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"
BOOT_CHECK_CMD=""
TIMEOUT_SEC=900
POLL_SEC=3

usage() {
  cat <<'EOF'
Usage:
  bash scripts/test-vm-disk-backup-restore-cross-host-smoke.sh \
    --src-host srv1.beagle-os.com \
    --dst-host srv2.beagle-os.com \
    --vmid 100 \
    [--api-url http://127.0.0.1:9088] \
    [--dst-restore-dir /var/restores/beagle-cross-host] \
    [--dst-archive-dir /var/backups/beagle-cross-host] \
    [--boot-check-cmd 'virsh start beagle-restore-smoke-100 && sleep 15 && virsh destroy beagle-restore-smoke-100']

Outputs:
  BACKUP_RESTORE_CROSS_HOST_SMOKE=PASS ... on success
  BACKUP_RESTORE_CROSS_HOST_SMOKE=FAIL reason=... on failure
EOF
}

fail() {
  local reason="$1"
  echo "BACKUP_RESTORE_CROSS_HOST_SMOKE=FAIL reason=${reason}"
  exit 1
}

require_cmd() {
  local c="$1"
  command -v "$c" >/dev/null 2>&1 || fail "missing_command_${c}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --src-host) SRC_HOST="$2"; shift 2 ;;
    --dst-host) DST_HOST="$2"; shift 2 ;;
    --vmid) VMID="$2"; shift 2 ;;
    --api-url) API_URL="$2"; shift 2 ;;
    --dst-restore-dir) DST_RESTORE_DIR="$2"; shift 2 ;;
    --dst-archive-dir) DST_ARCHIVE_DIR="$2"; shift 2 ;;
    --boot-check-cmd) BOOT_CHECK_CMD="$2"; shift 2 ;;
    --timeout-sec) TIMEOUT_SEC="$2"; shift 2 ;;
    --poll-sec) POLL_SEC="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown_arg_${1}" ;;
  esac
done

[[ -n "$SRC_HOST" ]] || fail "missing_src_host"
[[ -n "$DST_HOST" ]] || fail "missing_dst_host"
[[ -n "$VMID" ]] || fail "missing_vmid"
[[ "$VMID" =~ ^[0-9]+$ ]] || fail "invalid_vmid"
[[ "$TIMEOUT_SEC" =~ ^[0-9]+$ ]] || fail "invalid_timeout"
[[ "$POLL_SEC" =~ ^[0-9]+$ ]] || fail "invalid_poll_sec"

require_cmd ssh
require_cmd scp
require_cmd python3
require_cmd sha256sum

remote_src() {
  ssh $SSH_OPTS "$SRC_HOST" "$@"
}

remote_dst() {
  ssh $SSH_OPTS "$DST_HOST" "$@"
}

echo "=== Cross Host VM-Disk Backup/Restore Smoke ==="
echo "src_host=$SRC_HOST dst_host=$DST_HOST vmid=$VMID"

echo "--- [1/9] Resolve source VM disk path via libvirt"
SRC_DISK_PATH="$(remote_src "virsh --connect qemu:///system domblklist beagle-${VMID} --details | awk '\$1==\"file\" && \$2==\"disk\" {print \$4; exit}'")"
[[ -n "$SRC_DISK_PATH" ]] || fail "source_disk_not_found"
echo "source_disk_path=$SRC_DISK_PATH"

echo "--- [2/9] Source disk hash"
SRC_DISK_SHA256="$(remote_src "sha256sum '$SRC_DISK_PATH' | awk '{print \$1}'")"
[[ "$SRC_DISK_SHA256" =~ ^[0-9a-f]{64}$ ]] || fail "source_disk_sha_invalid"
echo "source_disk_sha256=$SRC_DISK_SHA256"

echo "--- [3/9] Trigger vm-scope backup on source host"
RUN_JSON="$(remote_src "bash -lc '
set -euo pipefail
if [[ -z \"\${BEAGLE_MANAGER_API_TOKEN:-}\" && -f /etc/beagle/beagle-manager.env ]]; then
  # shellcheck disable=SC1091
  source /etc/beagle/beagle-manager.env
fi
RAW_TOKEN=\"\${BEAGLE_MANAGER_API_TOKEN:-\${API_TOKEN:-}}\"
TOKEN=\"\${RAW_TOKEN%\\\"}\"; TOKEN=\"\${TOKEN#\\\"}\"; TOKEN=\"\${TOKEN%\\'}\"; TOKEN=\"\${TOKEN#\\'}\"
[[ -n \"\$TOKEN\" ]] || { echo \"missing_api_token\"; exit 10; }
curl -sS -X POST \
  -H \"Authorization: Bearer \$TOKEN\" \
  -H \"Content-Type: application/json\" \
  -d \"{\\\"scope_type\\\":\\\"vm\\\",\\\"scope_id\\\":\\\"${VMID}\\\"}\" \
  \"${API_URL}/api/v1/backups/run\"
'")" || fail "backup_run_request_failed"

echo "backup_run_response=$RUN_JSON"

JOB_ID="$(python3 - <<'PY' "$RUN_JSON"
import json,sys
raw=sys.argv[1]
try:
    d=json.loads(raw)
except Exception:
    print("")
    raise SystemExit(0)
job=(d.get("job") or {}).get("job_id")
if not job:
    job=d.get("job_id") or ""
print(job)
PY
)"
[[ -n "$JOB_ID" ]] || fail "backup_job_id_missing"
echo "backup_job_id=$JOB_ID"

echo "--- [4/9] Poll backup jobs for completed snapshot"
START_TS="$(date +%s)"
JOB_JSON=""
while true; do
  NOW_TS="$(date +%s)"
  if (( NOW_TS - START_TS > TIMEOUT_SEC )); then
    fail "backup_poll_timeout"
  fi

  JOB_JSON="$(remote_src "bash -lc '
set -euo pipefail
if [[ -z \"\${BEAGLE_MANAGER_API_TOKEN:-}\" && -f /etc/beagle/beagle-manager.env ]]; then
  # shellcheck disable=SC1091
  source /etc/beagle/beagle-manager.env
fi
RAW_TOKEN=\"\${BEAGLE_MANAGER_API_TOKEN:-\${API_TOKEN:-}}\"
TOKEN=\"\${RAW_TOKEN%\\\"}\"; TOKEN=\"\${TOKEN#\\\"}\"; TOKEN=\"\${TOKEN%\\'}\"; TOKEN=\"\${TOKEN#\\'}\"
curl -sS -H \"Authorization: Bearer \$TOKEN\" \"${API_URL}/api/v1/backups/jobs?scope_type=vm&scope_id=${VMID}\"
'")" || fail "backup_jobs_request_failed"

  STATUS="$(python3 - <<'PY' "$JOB_JSON" "$JOB_ID"
import json,sys
raw=sys.argv[1]
job_id=sys.argv[2]
try:
    d=json.loads(raw)
except Exception:
    print("")
    raise SystemExit(0)
jobs=d.get("jobs") or []
for j in jobs:
    if str(j.get("job_id") or "")==job_id:
        print(str(j.get("status") or ""))
        raise SystemExit(0)
print("")
PY
)"
  if [[ "$STATUS" == "success" ]]; then
    break
  fi
  if [[ "$STATUS" == "error" ]]; then
    fail "backup_job_failed"
  fi
  sleep "$POLL_SEC"
done

ARCHIVE_PATH="$(python3 - <<'PY' "$JOB_JSON" "$JOB_ID"
import json,sys
d=json.loads(sys.argv[1]); jid=sys.argv[2]
for j in d.get("jobs") or []:
    if str(j.get("job_id") or "")==jid:
        print(str(j.get("archive") or ""))
        break
PY
)"
ARCHIVE_SHA256_EXPECTED="$(python3 - <<'PY' "$JOB_JSON" "$JOB_ID"
import json,sys
d=json.loads(sys.argv[1]); jid=sys.argv[2]
for j in d.get("jobs") or []:
    if str(j.get("job_id") or "")==jid:
        print(str(j.get("archive_sha256") or ""))
        break
PY
)"
[[ -n "$ARCHIVE_PATH" ]] || fail "backup_archive_path_missing"
[[ "$ARCHIVE_SHA256_EXPECTED" =~ ^[0-9a-f]{64}$ ]] || fail "backup_archive_sha_missing"
echo "backup_archive_path=$ARCHIVE_PATH"
echo "backup_archive_sha256_expected=$ARCHIVE_SHA256_EXPECTED"

echo "--- [5/9] Verify source archive hash"
ARCHIVE_SHA256_SRC="$(remote_src "sha256sum '$ARCHIVE_PATH' | awk '{print \$1}'")"
[[ "$ARCHIVE_SHA256_SRC" == "$ARCHIVE_SHA256_EXPECTED" ]] || fail "source_archive_sha_mismatch"

echo "--- [6/9] Copy archive to destination host"
remote_dst "mkdir -p '$DST_ARCHIVE_DIR' '$DST_RESTORE_DIR'" || fail "dst_prepare_dirs_failed"
ARCHIVE_BASENAME="$(basename "$ARCHIVE_PATH")"
scp $SSH_OPTS "${SRC_HOST}:${ARCHIVE_PATH}" "${DST_HOST}:${DST_ARCHIVE_DIR}/${ARCHIVE_BASENAME}" >/dev/null 2>&1 || fail "archive_copy_failed"

echo "--- [7/9] Verify destination archive hash"
ARCHIVE_SHA256_DST="$(remote_dst "sha256sum '${DST_ARCHIVE_DIR}/${ARCHIVE_BASENAME}' | awk '{print \$1}'")"
[[ "$ARCHIVE_SHA256_DST" == "$ARCHIVE_SHA256_EXPECTED" ]] || fail "destination_archive_sha_mismatch"

echo "--- [8/9] Extract archive on destination and compare restored disk hash"
RESTORE_TARGET="${DST_RESTORE_DIR}/${JOB_ID}"
remote_dst "rm -rf '$RESTORE_TARGET' && mkdir -p '$RESTORE_TARGET'" || fail "dst_restore_dir_prepare_failed"
remote_dst "tar -xzf '${DST_ARCHIVE_DIR}/${ARCHIVE_BASENAME}' -C '$RESTORE_TARGET'" || fail "dst_extract_failed"

SRC_DISK_BASENAME="$(basename "$SRC_DISK_PATH")"
RESTORED_DISK_PATH="$(remote_dst "find '$RESTORE_TARGET' -type f -name '$SRC_DISK_BASENAME' | head -n1")"
[[ -n "$RESTORED_DISK_PATH" ]] || fail "restored_disk_not_found"

RESTORED_DISK_SHA256="$(remote_dst "sha256sum '$RESTORED_DISK_PATH' | awk '{print \$1}'")"
[[ "$RESTORED_DISK_SHA256" == "$SRC_DISK_SHA256" ]] || fail "restored_disk_sha_mismatch"

echo "--- [9/9] Optional destination boot-check hook"
if [[ -n "$BOOT_CHECK_CMD" ]]; then
  remote_dst "bash -lc '$BOOT_CHECK_CMD'" || fail "destination_boot_check_failed"
  BOOT_CHECK_STATUS="executed"
else
  BOOT_CHECK_STATUS="skipped"
fi

echo "BACKUP_RESTORE_CROSS_HOST_SMOKE=PASS vmid=${VMID} job_id=${JOB_ID} source_disk=${SRC_DISK_PATH} restored_disk=${RESTORED_DISK_PATH} source_disk_sha256=${SRC_DISK_SHA256} archive_sha256=${ARCHIVE_SHA256_EXPECTED} boot_check=${BOOT_CHECK_STATUS}"
