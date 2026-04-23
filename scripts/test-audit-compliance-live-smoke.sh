#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BEAGLE_CONTROL_PLANE_BASE_URL:-http://127.0.0.1:9088}"
ENV_FILE="${BEAGLE_MANAGER_ENV_FILE:-/etc/beagle/beagle-manager.env}"
MINIO_DIR="$(mktemp -d)"
TMP_DIR="$(mktemp -d)"
MINIO_PID=""
ORIG_ENV_BAK=""

cleanup() {
  set +e
  if [[ -n "$MINIO_PID" ]]; then
    kill "$MINIO_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$ORIG_ENV_BAK" && -f "$ORIG_ENV_BAK" ]]; then
    cp "$ORIG_ENV_BAK" "$ENV_FILE"
    systemctl restart beagle-control-plane >/dev/null 2>&1 || true
  fi
  rm -rf "$MINIO_DIR" "$TMP_DIR"
}
trap cleanup EXIT

require_cmd() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "[FAIL] required command not found: $name" >&2
    exit 1
  fi
}

require_cmd curl
require_cmd python3
require_cmd systemctl

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[FAIL] missing env file: $ENV_FILE" >&2
  exit 1
fi

TOKEN_RAW="$(sed -n 's/^BEAGLE_MANAGER_API_TOKEN=//p' "$ENV_FILE" | head -n1)"
if [[ -z "$TOKEN_RAW" ]]; then
  TOKEN_RAW="$(sed -n 's/^BEAGLE_API_TOKEN=//p' "$ENV_FILE" | head -n1)"
fi
if [[ -z "$TOKEN_RAW" ]]; then
  TOKEN_RAW="$(sed -n 's/^BEAGLE_MANAGER_TOKEN=//p' "$ENV_FILE" | head -n1)"
fi
if [[ -z "$TOKEN_RAW" ]]; then
  echo "[FAIL] no API token found in $ENV_FILE" >&2
  exit 1
fi

TOKEN="$(printf '%s' "$TOKEN_RAW" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//" | tr -d '\r\n[:space:]')"
AUTH=(-H "Authorization: Bearer $TOKEN")

HTTP_CODE="$(curl -sS -o "$TMP_DIR/auth-check.json" -w '%{http_code}' "$BASE_URL/api/v1/pools" "${AUTH[@]}")"
if [[ "$HTTP_CODE" != "200" ]]; then
  echo "[FAIL] token auth check failed (HTTP $HTTP_CODE)" >&2
  cat "$TMP_DIR/auth-check.json" >&2 || true
  exit 1
fi
echo "[PASS] token auth check (HTTP 200)"

START_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

call_power_action() {
  local action="$1"
  local out="$TMP_DIR/vm-${action}.json"
  local code=""
  code="$(curl -sS -o "$out" -w '%{http_code}' -X POST "$BASE_URL/api/v1/virtualization/vms/999999/power" "${AUTH[@]}" -H 'Content-Type: application/json' --data "{\"action\":\"$action\"}")"
  if [[ "$code" == "401" ]]; then
    echo "[FAIL] vm.$action request unauthorized" >&2
    cat "$out" >&2 || true
    exit 1
  fi
  echo "[PASS] vm.$action request accepted for audit generation (HTTP $code)"
}

call_power_action start
call_power_action stop
call_power_action reboot

python3 - <<'PY' "$BASE_URL" "$TOKEN" "$START_TS" "$TMP_DIR"
import json
import sys
import urllib.parse
import urllib.request

base, token, start_ts, tmp_dir = sys.argv[1:]
required = ["id", "timestamp", "tenant_id", "user_id", "action", "resource_type", "resource_id", "result", "source_ip", "user_agent"]
actions = ["vm.start", "vm.stop", "vm.reboot"]

def fetch_json(path):
    req = urllib.request.Request(base + path, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

for action in actions:
    q = urllib.parse.urlencode({"start": start_ts, "action": action})
    report = fetch_json(f"/api/v1/audit/report?{q}")
    if not report.get("ok"):
        raise SystemExit(f"[FAIL] audit report for {action} is not ok")
    if report.get("count", 0) < 1:
        raise SystemExit(f"[FAIL] no audit events found for {action}")
    event = report["events"][0]
    missing = [k for k in required if k not in event]
    if missing:
        raise SystemExit(f"[FAIL] missing schema keys for {action}: {missing}")
    if event.get("action") != action:
        raise SystemExit(f"[FAIL] wrong action in filtered report for {action}: {event.get('action')}")
    print(f"[PASS] schema check for {action} (count={report.get('count')})")

viewer_q = urllib.parse.urlencode({"start": start_ts, "action": "vm.stop", "user": "legacy-api-token"})
viewer_report = fetch_json(f"/api/v1/audit/report?{viewer_q}")
if not viewer_report.get("ok"):
    raise SystemExit("[FAIL] filtered viewer report not ok")
for e in viewer_report.get("events", []):
    if e.get("action") != "vm.stop":
        raise SystemExit("[FAIL] action filter leaked non vm.stop event")
    if e.get("user_id") != "legacy-api-token":
        raise SystemExit("[FAIL] user filter leaked non legacy-api-token event")
print(f"[PASS] audit viewer filter semantics (count={viewer_report.get('count', 0)})")

all_q = urllib.parse.urlencode({"start": start_ts, "resource_type": "vm"})
all_json = fetch_json(f"/api/v1/audit/report?{all_q}")
if not all_json.get("ok"):
    raise SystemExit("[FAIL] full vm report not ok")
with open(f"{tmp_dir}/json-count.txt", "w", encoding="utf-8") as fh:
    fh.write(str(int(all_json.get("count", 0))))
PY

CSV_CODE="$(curl -sS -o "$TMP_DIR/audit.csv" -w '%{http_code}' "$BASE_URL/api/v1/audit/report?start=$START_TS&resource_type=vm" "${AUTH[@]}" -H 'Accept: text/csv')"
if [[ "$CSV_CODE" != "200" ]]; then
  echo "[FAIL] csv report request failed (HTTP $CSV_CODE)" >&2
  exit 1
fi

python3 - <<'PY' "$TMP_DIR/audit.csv" "$TMP_DIR/json-count.txt"
import csv
import sys

csv_path, count_path = sys.argv[1:]
expected = int(open(count_path, "r", encoding="utf-8").read().strip() or "0")
with open(csv_path, "r", encoding="utf-8-sig", newline="") as fh:
    rows = list(csv.reader(fh))
if not rows:
    raise SystemExit("[FAIL] csv report empty")
header = rows[0]
if not header or header[0] != "timestamp":
    raise SystemExit("[FAIL] csv header invalid")
actual = max(0, len(rows) - 1)
if actual != expected:
    raise SystemExit(f"[FAIL] csv/json count mismatch: csv={actual} json={expected}")
print(f"[PASS] compliance csv completeness (rows={actual})")
PY

ORIG_ENV_BAK="$TMP_DIR/beagle-manager.env.bak"
cp "$ENV_FILE" "$ORIG_ENV_BAK"

MINIO_BIN="$MINIO_DIR/minio"
MC_BIN="$MINIO_DIR/mc"
curl -fsSL -o "$MINIO_BIN" "https://dl.min.io/server/minio/release/linux-amd64/minio"
curl -fsSL -o "$MC_BIN" "https://dl.min.io/client/mc/release/linux-amd64/mc"
chmod +x "$MINIO_BIN" "$MC_BIN"

MINIO_ROOT_USER="beagleminio"
MINIO_ROOT_PASSWORD="beagleminio123"
MINIO_DATA="$MINIO_DIR/data"
mkdir -p "$MINIO_DATA"
MINIO_ENDPOINT="http://127.0.0.1:19000"
MINIO_CONSOLE_ADDR=":19001" MINIO_ROOT_USER="$MINIO_ROOT_USER" MINIO_ROOT_PASSWORD="$MINIO_ROOT_PASSWORD" "$MINIO_BIN" server "$MINIO_DATA" --address ":19000" >"$TMP_DIR/minio.log" 2>&1 &
MINIO_PID="$!"

for _ in $(seq 1 30); do
  if curl -fsS "$MINIO_ENDPOINT/minio/health/live" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! curl -fsS "$MINIO_ENDPOINT/minio/health/live" >/dev/null 2>&1; then
  echo "[FAIL] minio did not become healthy" >&2
  tail -n 50 "$TMP_DIR/minio.log" >&2 || true
  exit 1
fi
echo "[PASS] minio started"

"$MC_BIN" alias set beagleminio "$MINIO_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
"$MC_BIN" mb --ignore-existing beagleminio/beagle-audit >/dev/null

set_env_kv() {
  local key="$1"
  local val="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s#^${key}=.*#${key}=${val}#" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
  fi
}

set_env_kv "BEAGLE_AUDIT_EXPORT_S3_ENABLED" "1"
set_env_kv "BEAGLE_AUDIT_EXPORT_S3_ENDPOINT" "$MINIO_ENDPOINT"
set_env_kv "BEAGLE_AUDIT_EXPORT_S3_BUCKET" "beagle-audit"
set_env_kv "BEAGLE_AUDIT_EXPORT_S3_REGION" "us-east-1"
set_env_kv "BEAGLE_AUDIT_EXPORT_S3_ACCESS_KEY" "$MINIO_ROOT_USER"
set_env_kv "BEAGLE_AUDIT_EXPORT_S3_SECRET_KEY" "$MINIO_ROOT_PASSWORD"
set_env_kv "BEAGLE_AUDIT_EXPORT_S3_PREFIX" "audit"

systemctl restart beagle-control-plane
systemctl is-active --quiet beagle-control-plane || {
  echo "[FAIL] beagle-control-plane not active after enabling S3 export" >&2
  exit 1
}

for _ in $(seq 1 30); do
  if curl -fsS "$BASE_URL/api/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! curl -fsS "$BASE_URL/api/v1/health" >/dev/null 2>&1; then
  echo "[FAIL] beagle-control-plane did not become healthy after restart" >&2
  exit 1
fi

LOGIN_CODE="$(curl -sS -o "$TMP_DIR/login-fail.json" -w '%{http_code}' -X POST "$BASE_URL/api/v1/auth/login" -H 'Content-Type: application/json' --data '{"username":"audit-smoke-invalid","password":"invalid-password"}' || true)"
if [[ "$LOGIN_CODE" != "401" ]]; then
  echo "[FAIL] expected failed login 401, got $LOGIN_CODE" >&2
  cat "$TMP_DIR/login-fail.json" >&2 || true
  exit 1
fi

FOUND_OBJECT=""
for _ in $(seq 1 30); do
  if "$MC_BIN" ls --recursive beagleminio/beagle-audit/audit >/dev/null 2>&1; then
    FOUND_OBJECT="$("$MC_BIN" ls --recursive beagleminio/beagle-audit/audit | head -n1 | awk '{print $NF}')"
    if [[ -n "$FOUND_OBJECT" ]]; then
      break
    fi
  fi
  sleep 1
done

if [[ -z "$FOUND_OBJECT" ]]; then
  echo "[FAIL] no audit object found in MinIO bucket" >&2
  "$MC_BIN" ls --recursive beagleminio/beagle-audit || true
  exit 1
fi

echo "[PASS] s3 export delivered object to MinIO: $FOUND_OBJECT"
echo "AUDIT_COMPLIANCE_SMOKE=PASS"