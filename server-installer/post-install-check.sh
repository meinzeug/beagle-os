#!/usr/bin/env bash
# post-install-check.sh — Post-installation smoke test for Beagle OS server
#
# GoEnterprise Plan 08, Schritt 5
#
# Verifies:
#   1. Core systemd services are running
#   2. libvirt / KVM is accessible
#   3. Network connectivity
#   4. Beagle Host API responds
#
# Optional: reports result to control plane if BEAGLE_CONTROL_PLANE is set.
#
# Exit codes:
#   0 — all checks passed
#   1 — one or more checks failed

set -uo pipefail

# ── Config ─────────────────────────────────────────────────────────────────────
BEAGLE_API_HOST="${BEAGLE_API_HOST:-127.0.0.1}"
BEAGLE_API_PORT="${BEAGLE_API_PORT:-9088}"
BEAGLE_API_TIMEOUT="${BEAGLE_API_TIMEOUT:-10}"
BEAGLE_API_URL="${BEAGLE_API_URL:-http://${BEAGLE_API_HOST}:${BEAGLE_API_PORT}/healthz}"
BEAGLE_CONTROL_PLANE="${BEAGLE_CONTROL_PLANE:-}"
BEAGLE_DEVICE_ID="${BEAGLE_DEVICE_ID:-$(hostname -f 2>/dev/null || hostname)}"
BEAGLE_REPORT_TOKEN="${BEAGLE_REPORT_TOKEN:-}"

REQUIRED_SERVICES=(
    "libvirtd"
    "beagle-control-plane"
)
OPTIONAL_SERVICES=(
    "systemd-resolved"
    "networkd-dispatcher"
)
DNS_CHECK_HOST="dns.google"
VIRSH_TIMEOUT=10
BEAGLE_KVM_DEVICE="${BEAGLE_KVM_DEVICE:-/dev/kvm}"

# ── Helpers ────────────────────────────────────────────────────────────────────
PASS=0
FAIL=0
RESULTS=()

pass()  { echo "[PASS] $*"; RESULTS+=("{\"check\":\"$1\",\"status\":\"pass\"}"); ((PASS++)) || true; }
fail()  { echo "[FAIL] $*" >&2; RESULTS+=("{\"check\":\"$1\",\"status\":\"fail\",\"detail\":\"$2\"}"); ((FAIL++)) || true; }
warn()  { echo "[WARN] $*" >&2; RESULTS+=("{\"check\":\"$1\",\"status\":\"warn\",\"detail\":\"$2\"}"); }

check_required_service() {
    local svc="$1"
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        pass "service:$svc"
    else
        fail "service:$svc" "$svc is not active"
    fi
}

check_optional_service() {
    local svc="$1"
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        pass "service:$svc"
    else
        warn "service:$svc" "$svc is not active"
    fi
}

# ── 1. Systemd services ────────────────────────────────────────────────────────
echo "=== Beagle OS Post-Install Check ==="
echo ""
echo "--- 1. systemd services ---"
for svc in "${REQUIRED_SERVICES[@]}"; do
    check_required_service "$svc"
done
for svc in "${OPTIONAL_SERVICES[@]}"; do
    check_optional_service "$svc"
done

# ── 2. libvirt / KVM ──────────────────────────────────────────────────────────
echo ""
echo "--- 2. libvirt / KVM ---"
if command -v virsh >/dev/null 2>&1; then
    if timeout "${VIRSH_TIMEOUT}" virsh list --all >/dev/null 2>&1; then
        pass "libvirt:virsh"
    else
        fail "libvirt:virsh" "virsh list failed"
    fi

    if [ -r "$BEAGLE_KVM_DEVICE" ]; then
        pass "kvm:device"
    else
        fail "kvm:device" "$BEAGLE_KVM_DEVICE not readable"
    fi
else
    fail "libvirt:virsh" "virsh not found"
fi

# ── 3. Network ────────────────────────────────────────────────────────────────
echo ""
echo "--- 3. Network connectivity ---"
if ping -c 2 -W 3 "$DNS_CHECK_HOST" >/dev/null 2>&1; then
    pass "network:ping:$DNS_CHECK_HOST"
else
    fail "network:ping:$DNS_CHECK_HOST" "ping to $DNS_CHECK_HOST failed"
fi

# ── 4. Beagle Host API ────────────────────────────────────────────────────────
echo ""
echo "--- 4. Beagle Host API ---"
if command -v curl >/dev/null 2>&1; then
    http_code=$(curl --silent --write-out "%{http_code}" --output /dev/null \
        --max-time "$BEAGLE_API_TIMEOUT" "$BEAGLE_API_URL" 2>/dev/null || echo "000")
    if [ "$http_code" = "200" ]; then
        pass "beagle-host-api:health"
    else
        fail "beagle-host-api:health" "HTTP $http_code from $BEAGLE_API_URL"
    fi
else
    fail "beagle-host-api:health" "curl not found"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="
overall_status="pass"
if [ "$FAIL" -gt 0 ]; then
    overall_status="fail"
fi

# ── Report to control plane (optional) ───────────────────────────────────────
if [ -n "$BEAGLE_CONTROL_PLANE" ] && [ -n "$BEAGLE_REPORT_TOKEN" ] && command -v curl >/dev/null 2>&1; then
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    # Build JSON array from RESULTS
    results_json=$(printf '%s,' "${RESULTS[@]}")
    results_json="[${results_json%,}]"

    payload=$(python3 - "$BEAGLE_DEVICE_ID" "$timestamp" "$overall_status" "$results_json" <<'PY'
import json
import sys

device_id = sys.argv[1]
timestamp = sys.argv[2]
status = sys.argv[3]
checks_raw = sys.argv[4]
try:
    checks = json.loads(checks_raw)
    if not isinstance(checks, list):
        checks = []
except json.JSONDecodeError:
    checks = []
print(json.dumps({
    "device_id": device_id,
    "timestamp": timestamp,
    "status": status,
    "checks": checks,
}))
PY
)

    curl --silent --show-error \
        --request POST \
        --header "Content-Type: application/json" \
        --header "Authorization: Bearer ${BEAGLE_REPORT_TOKEN}" \
        --data "$payload" \
        --max-time 15 \
        "${BEAGLE_CONTROL_PLANE}/api/v1/nodes/install-check" >/dev/null 2>&1 || \
        echo "[WARN] Failed to report to control plane" >&2
fi

[ "$FAIL" -eq 0 ]
