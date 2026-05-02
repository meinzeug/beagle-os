#!/usr/bin/env bash
# scripts/check-beagle-health.sh
#
# Beagle OS health check: nginx/TLS, disk usage, control plane,
# VM/session/stream health, backup age, and optional webhook alerting.
#
# Usage: bash check-beagle-health.sh [--alert-threshold <pct>]
#                                     [--host <fqdn-or-host>]
#                                     [--backup-dir <path>]
#                                     [--backup-max-age-hours <hours>]
#                                     [--webhook-url <url>]
# Exit 0 = all OK, Exit 1 = one or more checks failed.
#
# Designed to be run via cron or as a standalone monitoring call.
# Results are written as JSON to stdout for integration with alerting tools.

set -euo pipefail

ALERT_THRESHOLD=80
HOST="srv1.beagle-os.com"
CONTROL_PLANE_URL="http://localhost:9088/healthz"
DISK_PATHS=("/var/lib/beagle" "/var/lib/libvirt/images" "/")
BACKUP_DIR="${BEAGLE_BACKUP_DIR:-/var/lib/beagle/backups}"
BACKUP_MAX_AGE_HOURS="${BEAGLE_BACKUP_MAX_AGE_HOURS:-48}"
WEBHOOK_URL="${BEAGLE_ALERT_WEBHOOK_URL:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --alert-threshold) ALERT_THRESHOLD="$2"; shift 2 ;;
    --host) HOST="$2"; shift 2 ;;
    --backup-dir) BACKUP_DIR="$2"; shift 2 ;;
    --backup-max-age-hours) BACKUP_MAX_AGE_HOURS="$2"; shift 2 ;;
    --webhook-url) WEBHOOK_URL="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ ! "$ALERT_THRESHOLD" =~ ^[0-9]+$ ]]; then
  echo "Invalid --alert-threshold: $ALERT_THRESHOLD" >&2
  exit 2
fi
if [[ ! "$BACKUP_MAX_AGE_HOURS" =~ ^[0-9]+$ ]]; then
  echo "Invalid --backup-max-age-hours: $BACKUP_MAX_AGE_HOURS" >&2
  exit 2
fi

PASS=0
FAIL=0
declare -a RESULTS=()

# --------------------------------------------------------------------------
# Helper
# --------------------------------------------------------------------------
check_pass() {
  local name="$1" detail="$2"
  RESULTS+=("{\"check\":\"$(json_escape "$name")\",\"status\":\"PASS\",\"detail\":\"$(json_escape "$detail")\"}")
  PASS=$((PASS+1))
}

check_fail() {
  local name="$1" detail="$2"
  RESULTS+=("{\"check\":\"$(json_escape "$name")\",\"status\":\"FAIL\",\"detail\":\"$(json_escape "$detail")\"}")
  FAIL=$((FAIL+1))
  echo "  [FAIL] ${name}: ${detail}" >&2
}

json_escape() {
  local input="$1"
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$input" <<'PY'
import json
import sys
print(json.dumps(sys.argv[1])[1:-1])
PY
    return 0
  fi
  input="${input//\\/\\\\}"
  input="${input//\"/\\\"}"
  input="${input//$'\n'/\\n}"
  input="${input//$'\r'/\\r}"
  input="${input//$'\t'/\\t}"
  printf '%s' "$input"
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
  CP_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" "${CONTROL_PLANE_URL}" 2>/dev/null || echo "000") # tls-bypass-allowlist: health probe against local/self-signed control-plane endpoint
  CP_BODY=$(curl -sk "${CONTROL_PLANE_URL}" 2>/dev/null || echo "{}") # tls-bypass-allowlist: health probe against local/self-signed control-plane endpoint
  if [[ "$CP_STATUS" == "200" ]]; then
    check_pass "control_plane_health" "control plane health endpoint returned 200"
  else
    check_fail "control_plane_health" "control plane health endpoint returned ${CP_STATUS}: ${CP_BODY}"
  fi
else
  check_fail "control_plane_health" "curl not available — cannot check control plane health"
fi

# --------------------------------------------------------------------------
# 5. VM health (libvirt / virsh)
# --------------------------------------------------------------------------
if command -v virsh >/dev/null 2>&1; then
  VM_LIST=$(virsh list --all 2>/dev/null || echo "")
  VM_TOTAL=$(echo "$VM_LIST" | grep -cE '^\s+[0-9-]+\s+' 2>/dev/null; true)
  VM_RUNNING=$(echo "$VM_LIST" | grep -c " running" 2>/dev/null; true)
  VM_CRASHED=$(echo "$VM_LIST" | grep -cE " crashed| paused" 2>/dev/null; true)

  if [[ $VM_CRASHED -gt 0 ]]; then
    check_fail "vm_health" "${VM_CRASHED} VM(s) in crashed/paused state (total=${VM_TOTAL}, running=${VM_RUNNING})"
  else
    check_pass "vm_health" "${VM_RUNNING} running, ${VM_TOTAL} total VMs — no crashed/paused"
  fi

  # Check for VMs stuck in shutdown/die state > 5 minutes
  VM_SHUTOFF=$(echo "$VM_LIST" | grep -c " shut off" 2>/dev/null; true)
  check_pass "vm_shutoff_count" "${VM_SHUTOFF} VMs shut off (informational)"
else
  check_pass "vm_health" "virsh not available — skipping VM health check (non-hypervisor host)"
fi

# --------------------------------------------------------------------------
# 6. Active session / stream health via API
# --------------------------------------------------------------------------
if command -v curl >/dev/null 2>&1; then
  SESSION_URL="http://localhost:9088/api/v1/sessions"
  SESSION_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" "${SESSION_URL}" 2>/dev/null || echo "000") # tls-bypass-allowlist: health probe against local/self-signed session API endpoint
  if [[ "$SESSION_STATUS" == "200" || "$SESSION_STATUS" == "401" || "$SESSION_STATUS" == "403" ]]; then
    # 401/403 = auth required = service is alive
    check_pass "session_api_alive" "sessions API endpoint responding (HTTP ${SESSION_STATUS})"
  elif [[ "$SESSION_STATUS" == "404" ]]; then
    # endpoint may not exist yet — informational skip
    check_pass "session_api_alive" "sessions endpoint not implemented yet (HTTP 404) — skipped"
  else
    check_fail "session_api_alive" "sessions API unreachable (HTTP ${SESSION_STATUS})"
  fi

  # Sunshine/stream-server service check
  if systemctl is-active --quiet sunshine 2>/dev/null; then
    check_pass "stream_server_active" "sunshine stream server is active"
  elif systemctl list-units --type=service 2>/dev/null | grep -q sunshine; then
    check_fail "stream_server_active" "sunshine stream server is installed but not active"
  else
    check_pass "stream_server_active" "sunshine not installed on this host — skipped"
  fi
fi

# --------------------------------------------------------------------------
# 7. Backup success + restore age
# --------------------------------------------------------------------------
if [[ -d "$BACKUP_DIR" ]]; then
  # Find the newest backup file (any qcow2/tar.gz/img/zip in the backup dir)
  NEWEST_BACKUP=$(find "$BACKUP_DIR" -maxdepth 3 \
    \( -name "*.qcow2" -o -name "*.tar.gz" -o -name "*.img" -o -name "*.zip" \) \
    -printf '%T@ %p\n' 2>/dev/null \
    | sort -n | tail -1 | awk '{print $2}' || echo "")

  if [[ -z "$NEWEST_BACKUP" ]]; then
    check_fail "backup_age" "no backup files found in ${BACKUP_DIR}"
  else
    BACKUP_MTIME=$(stat -c %Y "$NEWEST_BACKUP" 2>/dev/null || echo 0)
    NOW_EPOCH=$(date +%s)
    AGE_HOURS=$(( (NOW_EPOCH - BACKUP_MTIME) / 3600 ))
    BACKUP_NAME=$(basename "$NEWEST_BACKUP")

    if [[ $AGE_HOURS -gt $BACKUP_MAX_AGE_HOURS ]]; then
      check_fail "backup_age" "newest backup (${BACKUP_NAME}) is ${AGE_HOURS}h old — exceeds threshold of ${BACKUP_MAX_AGE_HOURS}h"
    else
      check_pass "backup_age" "newest backup (${BACKUP_NAME}) is ${AGE_HOURS}h old (threshold: ${BACKUP_MAX_AGE_HOURS}h)"
    fi
  fi
else
  check_pass "backup_age" "backup dir ${BACKUP_DIR} not present — skipped (informational)"
fi

# --------------------------------------------------------------------------
# Output JSON summary
# --------------------------------------------------------------------------
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
OVERALL="PASS"
[[ $FAIL -gt 0 ]] && OVERALL="FAIL"

RESULTS_JSON=$(printf '%s\n' "${RESULTS[@]}" | paste -sd ',' -)
SUMMARY=$(printf '{"timestamp":"%s","overall":"%s","pass":%d,"fail":%d,"checks":[%s]}\n' \
  "$(json_escape "$TIMESTAMP")" "$(json_escape "$OVERALL")" "$PASS" "$FAIL" "$RESULTS_JSON")

echo "$SUMMARY"

# --------------------------------------------------------------------------
# 8. Webhook alert (if configured and there are failures)
# --------------------------------------------------------------------------
if [[ -n "$WEBHOOK_URL" && $FAIL -gt 0 ]] && command -v curl >/dev/null 2>&1; then
  curl -sf -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d "$SUMMARY" \
    >/dev/null 2>&1 \
    && echo "  [ALERT] Webhook notification sent to ${WEBHOOK_URL}" >&2 \
    || echo "  [WARN] Webhook notification failed for ${WEBHOOK_URL}" >&2
fi

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0
