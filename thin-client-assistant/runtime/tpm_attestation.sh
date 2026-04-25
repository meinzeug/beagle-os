#!/usr/bin/env bash
# tpm_attestation.sh — TPM PCR attestation for Beagle OS thin clients
#
# GoEnterprise Plan 02, Schritt 2
#
# Reads PCR values from TPM 2.0, builds an attestation report, and sends it
# to the Beagle Control Plane for validation.
#
# Required env vars:
#   BEAGLE_CONTROL_PLANE  — base URL, e.g. https://ctrl.beagle-os.com
#   BEAGLE_DEVICE_ID      — device identifier
#   BEAGLE_ATTEST_TOKEN   — pre-shared bearer token for the attestation endpoint
#
# Exit codes:
#   0 — attestation accepted
#   1 — attestation rejected or error

set -euo pipefail

BEAGLE_CONTROL_PLANE="${BEAGLE_CONTROL_PLANE:?BEAGLE_CONTROL_PLANE must be set}"
BEAGLE_DEVICE_ID="${BEAGLE_DEVICE_ID:?BEAGLE_DEVICE_ID must be set}"
BEAGLE_ATTEST_TOKEN="${BEAGLE_ATTEST_TOKEN:?BEAGLE_ATTEST_TOKEN must be set}"

ATTEST_ENDPOINT="${BEAGLE_CONTROL_PLANE}/api/v1/attestation/validate"
PCR_BANKS="sha256"
# PCRs 0-7: firmware/BIOS/boot loader; PCR 14: shim; PCR 15: custom
PCR_INDICES="0,1,2,3,4,5,6,7,14,15"

log() { echo "[tpm_attestation] $*" >&2; }
die() { log "ERROR: $*"; exit 1; }

# ── Check dependencies ─────────────────────────────────────────────────────────
for cmd in tpm2_pcrread curl jq; do
    command -v "$cmd" >/dev/null 2>&1 || die "$cmd not found in PATH"
done

# ── Read PCR values ────────────────────────────────────────────────────────────
log "Reading TPM PCR values (banks: ${PCR_BANKS}, indices: ${PCR_INDICES})"

pcr_json=$(tpm2_pcrread "${PCR_BANKS}:${PCR_INDICES}" --output=yaml 2>/dev/null | \
    python3 -c "
import sys, json, yaml
data = yaml.safe_load(sys.stdin.read())
# tpm2_pcrread yaml: {sha256: {0: '0x...', 1: '0x...', ...}}
bank = list(data.values())[0] if data else {}
pcrs = {str(k): v for k, v in bank.items()}
print(json.dumps(pcrs))
" 2>/dev/null) || die "Failed to parse PCR output from tpm2_pcrread"

if [ -z "$pcr_json" ] || [ "$pcr_json" = "null" ] || [ "$pcr_json" = "{}" ]; then
    die "No PCR values returned by tpm2_pcrread"
fi

log "PCR read successful"

# ── Build attestation report ───────────────────────────────────────────────────
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
hostname=$(hostname -f 2>/dev/null || hostname)

report=$(jq -nc \
    --arg device_id "$BEAGLE_DEVICE_ID" \
    --arg hostname  "$hostname" \
    --arg timestamp "$timestamp" \
    --arg pcr_bank  "$PCR_BANKS" \
    --argjson pcrs  "$pcr_json" \
    '{
        device_id:  $device_id,
        hostname:   $hostname,
        timestamp:  $timestamp,
        pcr_bank:   $pcr_bank,
        pcr_values: $pcrs
    }')

# ── Send to control plane ─────────────────────────────────────────────────────
log "Sending attestation report to ${ATTEST_ENDPOINT}"

http_code=$(curl \
    --silent \
    --show-error \
    --write-out "%{http_code}" \
    --output /tmp/beagle-attest-response.json \
    --request POST \
    --header "Content-Type: application/json" \
    --header "Authorization: Bearer ${BEAGLE_ATTEST_TOKEN}" \
    --data "$report" \
    --max-time 30 \
    "${ATTEST_ENDPOINT}")

# ── Evaluate response ─────────────────────────────────────────────────────────
if [ "$http_code" -eq 200 ]; then
    status=$(jq -r '.status // "unknown"' /tmp/beagle-attest-response.json 2>/dev/null)
    if [ "$status" = "accepted" ]; then
        log "Attestation accepted by control plane"
        exit 0
    else
        log "Attestation REJECTED by control plane (status=${status})"
        jq '.' /tmp/beagle-attest-response.json >&2 2>/dev/null || true
        exit 1
    fi
elif [ "$http_code" -eq 403 ]; then
    log "Attestation REJECTED: HTTP 403 (invalid token or unknown device)"
    exit 1
else
    log "Unexpected HTTP status from control plane: ${http_code}"
    cat /tmp/beagle-attest-response.json >&2 2>/dev/null || true
    exit 1
fi
