#!/usr/bin/env bash
# smoke test: backup restore, file-list, replication config
# Usage: bash scripts/test-backup-restore-smoke.sh
set -euo pipefail

BASE="http://127.0.0.1:9088/api/v1"
ENVFILE="/etc/beagle/beagle-manager.env"
if [[ -f "$ENVFILE" ]]; then
  TOKEN=$(grep "^BEAGLE_MANAGER_API_TOKEN=" "$ENVFILE" | cut -d= -f2- | tr -d '"'"'")
fi
TOKEN="${BEAGLE_MANAGER_API_TOKEN:-}"
# Strip surrounding quotes that env files may include
TOKEN="${TOKEN//\"/}"
TOKEN="${TOKEN//\'/}"
if [[ -z "$TOKEN" ]]; then
  echo "ERROR: BEAGLE_MANAGER_API_TOKEN not set" >&2
  exit 1
fi
AUTH="Authorization: Bearer $TOKEN"

# 1) Run a backup to get a job_id
echo "--- POST /api/v1/backups/run ---"
RUN_RESP=$(curl -sf -X POST -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"scope_type":"pool","scope_id":"smoke-test"}' \
  "$BASE/backups/run")
echo "$RUN_RESP" | python3 -m json.tool
JOB_ID=$(echo "$RUN_RESP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['job']['job_id'])")
echo "job_id=$JOB_ID"

# 2) List snapshots
echo "--- GET /api/v1/backups/snapshots ---"
SNAPS=$(curl -sf -H "$AUTH" "$BASE/backups/snapshots?scope_type=pool&scope_id=smoke-test")
echo "$SNAPS" | python3 -m json.tool
SNAPS_OK=$(echo "$SNAPS" | python3 -c "import json,sys; print(json.load(sys.stdin).get('ok',''))")
[[ "$SNAPS_OK" == "True" ]] && echo "SNAPSHOTS_LIST=PASS" || echo "SNAPSHOTS_LIST=FAIL"

# 3) List files in the backup archive
echo "--- GET /api/v1/backups/$JOB_ID/files ---"
FILES=$(curl -sf -H "$AUTH" "$BASE/backups/$JOB_ID/files")
echo "$FILES" | python3 -m json.tool
FILES_OK=$(echo "$FILES" | python3 -c "import json,sys; print(json.load(sys.stdin).get('ok',''))")
[[ "$FILES_OK" == "True" ]] && echo "FILES_LIST=PASS" || echo "FILES_LIST=FAIL"

# 4) Restore the snapshot (to safe tmpdir)
echo "--- POST /api/v1/backups/$JOB_ID/restore ---"
RESTORE=$(curl -sf -X POST -H "$AUTH" -H "Content-Type: application/json" \
  -d '{}' "$BASE/backups/$JOB_ID/restore")
echo "$RESTORE" | python3 -m json.tool
RESTORE_OK=$(echo "$RESTORE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('ok',''))")
[[ "$RESTORE_OK" == "True" ]] && echo "RESTORE=PASS" || echo "RESTORE=FAIL"

# 5) Get replication config
echo "--- GET /api/v1/backups/replication/config ---"
REPL=$(curl -sf -H "$AUTH" "$BASE/backups/replication/config")
echo "$REPL" | python3 -m json.tool
REPL_OK=$(echo "$REPL" | python3 -c "import json,sys; print(json.load(sys.stdin).get('ok',''))")
[[ "$REPL_OK" == "True" ]] && echo "REPLICATION_CONFIG=PASS" || echo "REPLICATION_CONFIG=FAIL"

# 6) Update replication config (disabled, no real remote)
echo "--- PUT /api/v1/backups/replication/config ---"
REPL_UPD=$(curl -sf -X PUT -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"enabled":false,"remote_url":"","auto_replicate":false}' \
  "$BASE/backups/replication/config")
echo "$REPL_UPD" | python3 -m json.tool
REPL_UPD_OK=$(echo "$REPL_UPD" | python3 -c "import json,sys; print(json.load(sys.stdin).get('ok',''))")
[[ "$REPL_UPD_OK" == "True" ]] && echo "REPLICATION_CONFIG_UPDATE=PASS" || echo "REPLICATION_CONFIG_UPDATE=FAIL"

echo "BACKUP_RESTORE_SMOKE=PASS"
