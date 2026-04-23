#!/usr/bin/env bash
set -euo pipefail

API_URL_DEFAULT="http://127.0.0.1:9088"
SCOPE_TYPE_DEFAULT="pool"
SCOPE_ID_DEFAULT="default"
TARGET_PATH_DEFAULT="/tmp/beagle-backups"

API_URL="${BEAGLE_MANAGER_API_URL:-$API_URL_DEFAULT}"
SCOPE_TYPE="${1:-$SCOPE_TYPE_DEFAULT}"
SCOPE_ID="${2:-$SCOPE_ID_DEFAULT}"
TARGET_PATH="${3:-$TARGET_PATH_DEFAULT}"

if [[ -z "${BEAGLE_MANAGER_API_TOKEN:-}" && -f /etc/beagle/beagle-manager.env ]]; then
  # shellcheck disable=SC1091
  source /etc/beagle/beagle-manager.env
fi

RAW_TOKEN="${BEAGLE_MANAGER_API_TOKEN:-${API_TOKEN:-}}"
TOKEN="${RAW_TOKEN%\"}"
TOKEN="${TOKEN#\"}"

if [[ -z "$TOKEN" ]]; then
  echo "BACKUP_SCOPE_SMOKE=FAIL reason=missing_api_token"
  exit 1
fi

put_policy_payload=$(cat <<JSON
{"enabled":true,"schedule":"daily","retention_days":3,"target_path":"$TARGET_PATH"}
JSON
)

post_run_payload=$(cat <<JSON
{"scope_type":"$SCOPE_TYPE","scope_id":"$SCOPE_ID"}
JSON
)

call_json() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  if [[ -n "$data" ]]; then
    curl -sS -w "\nHTTP:%{http_code}" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -X "$method" "$API_URL$path" \
      -d "$data"
  else
    curl -sS -w "\nHTTP:%{http_code}" \
      -H "Authorization: Bearer $TOKEN" \
      "$API_URL$path"
  fi
}

status_of() {
  sed -n 's/^HTTP://p' <<<"$1" | tail -n1
}

body_of() {
  sed '$d' <<<"$1"
}

ok_true() {
  grep -q '"ok"[[:space:]]*:[[:space:]]*true' <<<"$1"
}

PUT_RESP="$(call_json PUT "/api/v1/backups/policies/pools/$SCOPE_ID" "$put_policy_payload")"
GET_RESP="$(call_json GET "/api/v1/backups/policies/pools/$SCOPE_ID")"
POST_RESP="$(call_json POST "/api/v1/backups/run" "$post_run_payload")"
JOBS_RESP="$(call_json GET "/api/v1/backups/jobs?scope_type=$SCOPE_TYPE&scope_id=$SCOPE_ID")"

PUT_STATUS="$(status_of "$PUT_RESP")"
GET_STATUS="$(status_of "$GET_RESP")"
POST_STATUS="$(status_of "$POST_RESP")"
JOBS_STATUS="$(status_of "$JOBS_RESP")"

PUT_BODY="$(body_of "$PUT_RESP")"
GET_BODY="$(body_of "$GET_RESP")"
POST_BODY="$(body_of "$POST_RESP")"
JOBS_BODY="$(body_of "$JOBS_RESP")"

echo "PUT status=$PUT_STATUS body=$PUT_BODY"
echo "GET status=$GET_STATUS body=$GET_BODY"
echo "POST status=$POST_STATUS body=$POST_BODY"
echo "JOBS status=$JOBS_STATUS body=$JOBS_BODY"

if [[ "$PUT_STATUS" != "200" ]] || ! ok_true "$PUT_BODY"; then
  echo "BACKUP_SCOPE_SMOKE=FAIL reason=policy_put_failed"
  exit 1
fi
if [[ "$GET_STATUS" != "200" ]] || ! ok_true "$GET_BODY"; then
  echo "BACKUP_SCOPE_SMOKE=FAIL reason=policy_get_failed"
  exit 1
fi
if [[ "$POST_STATUS" != "200" ]] || ! ok_true "$POST_BODY"; then
  echo "BACKUP_SCOPE_SMOKE=FAIL reason=run_failed"
  exit 1
fi
if [[ "$JOBS_STATUS" != "200" ]] || ! ok_true "$JOBS_BODY" || ! grep -q '"job_id"' <<<"$JOBS_BODY"; then
  echo "BACKUP_SCOPE_SMOKE=FAIL reason=jobs_failed"
  exit 1
fi

echo "BACKUP_SCOPE_SMOKE=PASS"
