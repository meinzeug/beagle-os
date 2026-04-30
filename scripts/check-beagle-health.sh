#!/usr/bin/env bash
# scripts/check-beagle-health.sh
#
# Beagle OS health check: nginx/TLS, disk usage, control plane.
# Usage: bash check-beagle-health.sh [--alert-threshold <pct>]
# Exit 0 = all OK, Exit 1 = one or more checks failed.
#
# Designed to be run via cron or as a standalone monitoring call.
# Results are written as JSON to stdout for integration with alerting tools.

set -euo pipefail

ALERT_THRESHOLD=80
HOST="srv1.beagle-os.com"
CONTROL_PLANE_URL="http://localhost:9088/healthz"
DISK_PATHS=("/var/lib/beagle" "/var/lib/libvirt/images" "/")

while [[ $# -gt 0 ]]; do
  case "$1" in
    --alert-threshold) ALERT_THRESHOLD="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

PASS=0
FAIL=0
declare -a RESULTS=()

# --------------------------------------------------------------------------
# Helper
# --------------------------------------------------------------------------
check_pass() {
  local name="$1" detail="$2"
  RESULTS+=("{\"check\":\"${name}\",\"status\":\"PASS\",\"detail\":\"${detail}\"}")
  PASS=$((PASS+1))
}

check_fail() {
  local name="$1" detail="$2"
  RESULTS+=("{\"check\":\"${name}\",\"status\":\"FAIL\",\"detail\":\"${detail}\"}")
  FAIL=$((FAIL+1))
  echo "  [FAIL] ${name}: ${detail}" >&2
}

# --------------------------------------------------------------------------
# 1. nginx systemd status
# --------------------------------------------------------------------------
if systemctl is-active --quiet nginx 2>/dev/null; then
  check_pass "nginx_active" "nginx is active"
else
  check_fail "nginx_active" "nginx is NOT active"
fi

# --------------------------------------------------------------------------
# 2. TLS certificate expiry (warn at <14 days, fail at expired)
# --------------------------------------------------------------------------
if command -v openssl >/dev/null 2>&1; then
  CERT_EXPIRY=$(echo "" \
    | openssl s_client -connect "${HOST}:443" -servername "${HOST}" 2>/dev/null \
    | openssl x509 -noout -enddate 2>/dev/null \
    | sed 's/notAfter=//' || echo "")

  if [[ -z "$CERT_EXPIRY" ]]; then
    check_fail "tls_cert_expiry" "could not retrieve TLS certificate from ${HOST}:443"
  else
    # Compute days until expiry
    EXPIRY_EPOCH=$(date -d "$CERT_EXPIRY" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$CERT_EXPIRY" +%s 2>/dev/null || echo 0)
    NOW_EPOCH=$(date +%s)
    DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))

    if [[ $DAYS_LEFT -lt 0 ]]; then
      check_fail "tls_cert_expiry" "TLS certificate EXPIRED ${DAYS_LEFT#-} days ago (${CERT_EXPIRY})"
    elif [[ $DAYS_LEFT -lt 14 ]]; then
      check_fail "tls_cert_expiry" "TLS certificate expires in ${DAYS_LEFT} days — renew soon (${CERT_EXPIRY})"
    else
      check_pass "tls_cert_expiry" "TLS cert valid for ${DAYS_LEFT} days (expires ${CERT_EXPIRY})"
    fi
  fi
else
  check_fail "tls_cert_expiry" "openssl not available — cannot check TLS"
fi

# --------------------------------------------------------------------------
# 3. Disk usage
# --------------------------------------------------------------------------
for MOUNT in "${DISK_PATHS[@]}"; do
  if [[ ! -d "$MOUNT" ]]; then
    continue
  fi
  USAGE_PCT=$(df --output=pcent "$MOUNT" 2>/dev/null | tail -1 | tr -d '% ' || echo "0")
  if [[ $USAGE_PCT -ge $ALERT_THRESHOLD ]]; then
    check_fail "disk_${MOUNT//\//_}" "disk at ${MOUNT} is ${USAGE_PCT}% full (threshold: ${ALERT_THRESHOLD}%)"
  else
    check_pass "disk_${MOUNT//\//_}" "${MOUNT} is ${USAGE_PCT}% full"
  fi
done

# --------------------------------------------------------------------------
# 4. Control plane health endpoint
# --------------------------------------------------------------------------
if command -v curl >/dev/null 2>&1; then
  CP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" "${CONTROL_PLANE_URL}" 2>/dev/null || echo "000")
  CP_BODY=$(curl -sk "${CONTROL_PLANE_URL}" 2>/dev/null || echo "{}")
  if [[ "$CP_STATUS" == "200" ]]; then
    check_pass "control_plane_health" "control plane health endpoint returned 200"
  else
    check_fail "control_plane_health" "control plane health endpoint returned ${CP_STATUS}: ${CP_BODY}"
  fi
else
  check_fail "control_plane_health" "curl not available — cannot check control plane health"
fi

# --------------------------------------------------------------------------
# Output JSON summary
# --------------------------------------------------------------------------
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
OVERALL="PASS"
[[ $FAIL -gt 0 ]] && OVERALL="FAIL"

RESULTS_JSON=$(printf '%s\n' "${RESULTS[@]}" | paste -sd ',' -)
printf '{"timestamp":"%s","overall":"%s","pass":%d,"fail":%d,"checks":[%s]}\n' \
  "$TIMESTAMP" "$OVERALL" "$PASS" "$FAIL" "$RESULTS_JSON"

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0
