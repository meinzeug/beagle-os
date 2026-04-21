#!/usr/bin/env bash
set -euo pipefail

API_BASE="${BEAGLE_OWASP_API_BASE:-https://127.0.0.1/beagle-api/api/v1}"
CURL_OPTS=(--silent --show-error --insecure --output /dev/null --write-out '%{http_code}' --max-time 10)

pass=0
fail=0

check_code() {
  local name="$1"
  local expected="$2"
  shift 2
  local code
  code="$(curl "${CURL_OPTS[@]}" "$@")"
  if [[ "$code" == "$expected" ]]; then
    echo "[PASS] $name -> $code"
    pass=$((pass + 1))
  else
    echo "[FAIL] $name -> expected $expected got $code"
    fail=$((fail + 1))
  fi
}

check_code "A01 access control unauth mutation" 401 -X POST "$API_BASE/provisioning/vms"
check_code "A01 admin settings unauth" 401 -X POST "$API_BASE/settings/general"
check_code "A07 auth endpoint me unauth" 401 "$API_BASE/auth/me"
check_code "A03 malformed login payload rejected" 400 -X POST -H 'Content-Type: application/json' -d '{"username":123}' "$API_BASE/auth/login"
check_code "A05 unknown route rejected" 401 "$API_BASE/not-found-route"
check_code "A08 logout endpoint consistent" 200 -X POST "$API_BASE/auth/logout"

if [[ "$fail" -ne 0 ]]; then
  echo "[FAIL] OWASP smoke checks failed: pass=$pass fail=$fail"
  exit 1
fi

echo "[PASS] OWASP smoke checks passed: pass=$pass fail=$fail"
