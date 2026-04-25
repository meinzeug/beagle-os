#!/usr/bin/env bash
# enrollment_wireguard.sh — WireGuard Zero-Trust Enrollment for Beagle Thin Client
# GoEnterprise Plan 02, Schritt 0
#
# Generates a WireGuard keypair, registers the public key with the Beagle Control
# Plane, and writes /etc/wireguard/wg-beagle.conf so the thin client joins the
# secure mesh immediately after enrollment.
#
# Requirements: wireguard-tools, curl, jq
# Called by: runtime_endpoint_enrollment.sh (after QR-code or manual enrollment)
#
# Environment:
#   BEAGLE_CONTROL_PLANE   — Base URL of the Control Plane  (default: read from /etc/beagle/enrollment.conf)
#   BEAGLE_ENROLLMENT_TOKEN — One-time enrollment token       (default: read from /etc/beagle/enrollment.conf)
#   BEAGLE_DEVICE_ID        — Stable device ID               (default: read from /etc/beagle/enrollment.conf)
#   WG_IFACE                — WireGuard interface name        (default: wg-beagle)
#   WG_CONF                 — Destination config path         (default: /etc/wireguard/wg-beagle.conf)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
ENROLLMENT_CONF="${ENROLLMENT_CONF:-/etc/beagle/enrollment.conf}"
WG_IFACE="${WG_IFACE:-wg-beagle}"
WG_CONF="${WG_CONF:-/etc/wireguard/${WG_IFACE}.conf}"
WG_KEYS_DIR="${WG_KEYS_DIR:-/etc/beagle/wireguard}"
TIMEOUT="${TIMEOUT:-15}"

# ---------------------------------------------------------------------------
# Read enrollment config if environment not provided
# ---------------------------------------------------------------------------
if [[ -f "${ENROLLMENT_CONF}" ]]; then
    BEAGLE_CONTROL_PLANE="${BEAGLE_CONTROL_PLANE:-$(grep -E '^control_plane=' "${ENROLLMENT_CONF}" | cut -d= -f2- | tr -d '[:space:]')}"
    BEAGLE_ENROLLMENT_TOKEN="${BEAGLE_ENROLLMENT_TOKEN:-$(grep -E '^enrollment_token=' "${ENROLLMENT_CONF}" | cut -d= -f2- | tr -d '[:space:]')}"
    BEAGLE_DEVICE_ID="${BEAGLE_DEVICE_ID:-$(grep -E '^device_id=' "${ENROLLMENT_CONF}" | cut -d= -f2- | tr -d '[:space:]')}"
fi

if [[ -z "${BEAGLE_CONTROL_PLANE:-}" ]]; then
    echo "[wg-enroll] ERROR: BEAGLE_CONTROL_PLANE is not set and not found in ${ENROLLMENT_CONF}" >&2
    exit 1
fi
if [[ -z "${BEAGLE_DEVICE_ID:-}" ]]; then
    echo "[wg-enroll] ERROR: BEAGLE_DEVICE_ID is not set" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Check dependencies
# ---------------------------------------------------------------------------
for cmd in wg wg-quick curl jq; do
    if ! command -v "${cmd}" &>/dev/null; then
        echo "[wg-enroll] ERROR: Required command not found: ${cmd}" >&2
        exit 1
    fi
done

# ---------------------------------------------------------------------------
# Generate keypair (only if private key does not already exist)
# ---------------------------------------------------------------------------
mkdir -p "${WG_KEYS_DIR}"
chmod 700 "${WG_KEYS_DIR}"

PRIVKEY_FILE="${WG_KEYS_DIR}/private.key"
PUBKEY_FILE="${WG_KEYS_DIR}/public.key"

if [[ -f "${PRIVKEY_FILE}" ]]; then
    echo "[wg-enroll] Existing WireGuard keypair found — reusing."
    PRIVATE_KEY="$(cat "${PRIVKEY_FILE}")"
    PUBLIC_KEY="$(cat "${PUBKEY_FILE}")"
else
    echo "[wg-enroll] Generating WireGuard keypair..."
    PRIVATE_KEY="$(wg genkey)"
    PUBLIC_KEY="$(echo "${PRIVATE_KEY}" | wg pubkey)"
    # Write with restricted permissions — private key NEVER leaves the device
    (umask 077; echo "${PRIVATE_KEY}" > "${PRIVKEY_FILE}")
    echo "${PUBLIC_KEY}" > "${PUBKEY_FILE}"
    chmod 600 "${PRIVKEY_FILE}"
    chmod 644 "${PUBKEY_FILE}"
    echo "[wg-enroll] Keypair written to ${WG_KEYS_DIR}/"
fi

# ---------------------------------------------------------------------------
# Register public key with the Control Plane
# ---------------------------------------------------------------------------
echo "[wg-enroll] Registering public key with Control Plane at ${BEAGLE_CONTROL_PLANE}..."

REGISTER_PAYLOAD="$(jq -n \
    --arg device_id "${BEAGLE_DEVICE_ID}" \
    --arg public_key "${PUBLIC_KEY}" \
    --arg token "${BEAGLE_ENROLLMENT_TOKEN:-}" \
    '{device_id: $device_id, public_key: $public_key, token: $token}')"

HTTP_CODE="$(curl \
    --silent \
    --show-error \
    --max-time "${TIMEOUT}" \
    --connect-timeout 5 \
    --output /tmp/wg-register-response.json \
    --write-out "%{http_code}" \
    --header "Content-Type: application/json" \
    --data "${REGISTER_PAYLOAD}" \
    "${BEAGLE_CONTROL_PLANE}/api/v1/vpn/register" || true)"

if [[ "${HTTP_CODE}" != "200" ]]; then
    echo "[wg-enroll] ERROR: Control Plane returned HTTP ${HTTP_CODE}" >&2
    cat /tmp/wg-register-response.json >&2 || true
    exit 2
fi

# ---------------------------------------------------------------------------
# Parse peer config from response
# ---------------------------------------------------------------------------
RESPONSE="$(cat /tmp/wg-register-response.json)"

SERVER_PUBKEY="$(echo "${RESPONSE}" | jq -r '.server_public_key // empty')"
SERVER_ENDPOINT="$(echo "${RESPONSE}" | jq -r '.server_endpoint // empty')"
ALLOWED_IPS="$(echo "${RESPONSE}" | jq -r '.allowed_ips // "10.88.0.0/16"')"
CLIENT_IP="$(echo "${RESPONSE}" | jq -r '.client_ip // empty')"
DNS="$(echo "${RESPONSE}" | jq -r '.dns // "10.88.0.1"')"
PRESHARED_KEY="$(echo "${RESPONSE}" | jq -r '.preshared_key // empty')"

if [[ -z "${SERVER_PUBKEY}" || -z "${SERVER_ENDPOINT}" || -z "${CLIENT_IP}" ]]; then
    echo "[wg-enroll] ERROR: Incomplete peer config in Control Plane response" >&2
    echo "${RESPONSE}" >&2
    exit 3
fi

# ---------------------------------------------------------------------------
# Write /etc/wireguard/wg-beagle.conf
# ---------------------------------------------------------------------------
echo "[wg-enroll] Writing WireGuard config to ${WG_CONF}..."

mkdir -p "$(dirname "${WG_CONF}")"

{
    echo "[Interface]"
    echo "Address = ${CLIENT_IP}"
    echo "PrivateKey = ${PRIVATE_KEY}"
    echo "DNS = ${DNS}"
    echo ""
    echo "[Peer]"
    echo "PublicKey = ${SERVER_PUBKEY}"
    if [[ -n "${PRESHARED_KEY}" ]]; then
        echo "PresharedKey = ${PRESHARED_KEY}"
    fi
    echo "Endpoint = ${SERVER_ENDPOINT}"
    echo "AllowedIPs = ${ALLOWED_IPS}"
    echo "PersistentKeepalive = 25"
} | (umask 077; cat > "${WG_CONF}")

chmod 600 "${WG_CONF}"

# ---------------------------------------------------------------------------
# Bring up the WireGuard interface
# ---------------------------------------------------------------------------
echo "[wg-enroll] Starting WireGuard interface ${WG_IFACE}..."

# Down first if already running (e.g. re-enrollment)
if ip link show "${WG_IFACE}" &>/dev/null; then
    wg-quick down "${WG_IFACE}" 2>/dev/null || true
fi

wg-quick up "${WG_IFACE}"

echo "[wg-enroll] WireGuard interface ${WG_IFACE} is up. Client IP: ${CLIENT_IP}"
echo "[wg-enroll] Mesh enrollment complete. All subsequent streams will run through the secure tunnel."
