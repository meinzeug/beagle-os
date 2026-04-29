#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BEAGLE_CONTROL_PLANE_BASE_URL:-http://127.0.0.1:9088}"
ENV_FILE="${BEAGLE_MANAGER_ENV_FILE:-/etc/beagle/beagle-manager.env}"

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

AUTH=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TLS_GET_CODE="$(curl -sS -o "$TMP_DIR/tls-get.json" -w '%{http_code}' "$BASE_URL/api/v1/settings/security/tls" "${AUTH[@]}")"
if [[ "$TLS_GET_CODE" != "200" ]]; then
  echo "[FAIL] GET /api/v1/settings/security/tls returned HTTP $TLS_GET_CODE" >&2
  cat "$TMP_DIR/tls-get.json" >&2 || true
  exit 1
fi

python3 - <<'PY' "$TMP_DIR/tls-get.json"
import json
import sys
payload = json.loads(open(sys.argv[1], encoding='utf-8').read())
if not payload.get('ok'):
    raise SystemExit('[FAIL] tls status payload has ok=false')
if 'tls' not in payload:
    raise SystemExit('[FAIL] tls status payload missing tls object')
print('[PASS] tls status endpoint schema ok')
PY

TLS_POST_CODE="$(curl -sS -o "$TMP_DIR/tls-post.json" -w '%{http_code}' -X POST "$BASE_URL/api/v1/settings/security/tls/letsencrypt" "${AUTH[@]}" --data '{"domain":"invalid_domain","email":"ops@beagle-os.com"}')"
if [[ "$TLS_POST_CODE" != "400" ]]; then
  echo "[FAIL] POST /api/v1/settings/security/tls/letsencrypt expected HTTP 400, got $TLS_POST_CODE" >&2
  cat "$TMP_DIR/tls-post.json" >&2 || true
  exit 1
fi

python3 - <<'PY' "$TMP_DIR/tls-post.json"
import json
import sys
payload = json.loads(open(sys.argv[1], encoding='utf-8').read())
if payload.get('ok') is not False:
    raise SystemExit('[FAIL] letsencrypt validation response expected ok=false')
if payload.get('error') != 'invalid domain format':
    raise SystemExit(f"[FAIL] unexpected letsencrypt validation error: {payload.get('error')!r}")
print('[PASS] letsencrypt validation guardrail ok')
PY

echo "SECURITY_TLS_API_SMOKE=PASS"