#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BEAGLE_CONTROL_PLANE_BASE_URL:-http://127.0.0.1:9088}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

PASS_COUNT=0

request() {
  local name="$1"
  local method="$2"
  local path="$3"
  local expected_status="$4"
  local body="${5:-}"
  local out_file="$TMP_DIR/$(echo "$name" | tr ' /' '__').json"
  local status=""

  if [[ -n "$body" ]]; then
    status="$(curl -sS -o "$out_file" -w "%{http_code}" -X "$method" -H "Content-Type: application/json" --data "$body" "$BASE_URL$path")"
  else
    status="$(curl -sS -o "$out_file" -w "%{http_code}" -X "$method" "$BASE_URL$path")"
  fi

  if [[ "$status" != "$expected_status" ]]; then
    echo "[FAIL] $name: expected $expected_status, got $status" >&2
    echo "Response:" >&2
    cat "$out_file" >&2 || true
    exit 1
  fi

  if ! grep -q '"ok"' "$out_file"; then
    echo "[FAIL] $name: response missing 'ok' field" >&2
    cat "$out_file" >&2 || true
    exit 1
  fi

  echo "[PASS] $name ($status)"
  PASS_COUNT=$((PASS_COUNT + 1))
}

request "healthz" "GET" "/healthz" "200"
request "api health" "GET" "/api/v1/health" "200"
request "onboarding status" "GET" "/api/v1/auth/onboarding/status" "200"
request "auth me unauth" "GET" "/api/v1/auth/me" "401"
request "inventory unauth" "GET" "/api/v1/vms" "401"
request "settings general unauth" "GET" "/api/v1/settings/general" "401"
request "login missing payload" "POST" "/api/v1/auth/login" "400" "{}"
request "refresh missing token" "POST" "/api/v1/auth/refresh" "400" "{}"
request "logout unauth noop" "POST" "/api/v1/auth/logout" "200" "{}"
request "create user unauth" "POST" "/api/v1/auth/users" "401" "{\"username\":\"x\",\"password\":\"secret123\"}"
request "provisioning unauth" "POST" "/api/v1/provisioning/vms" "401" "{}"
request "legacy vms post unauth" "POST" "/api/v1/vms" "401" "{}"
request "not found" "GET" "/api/v1/does-not-exist" "401"

echo "Smoke checks passed: $PASS_COUNT"
