#!/usr/bin/env bash
# protocol_selector.sh — BeagleStream / RDP Protocol Fallback Selector
# GoEnterprise Plan 01, Schritt 6
#
# Selects the best streaming protocol in order of preference:
#   1. BeagleStream (Beagle Stream Client/Beagle Stream Server fork) via WireGuard tunnel (UDP 47998)
#   2. BeagleStream direct (if policy allows and WireGuard unavailable)
#   3. xRDP via WireGuard tunnel (TCP 3389)
#   4. Error with diagnostic info
#
# Outputs to stdout: selected protocol info for use by the caller.
# Exits 0 on success, non-zero on failure (no protocol available).
#
# Environment:
#   BEAGLE_HOST       — Target VM host (IP or DNS name inside WireGuard mesh)
#   BEAGLE_PORT       — BeagleStream port  (default: 47998)
#   RDP_PORT          — RDP fallback port  (default: 3389)
#   WG_IFACE          — WireGuard interface name (default: wg-beagle)
#   PROBE_TIMEOUT_S   — Timeout per probe in seconds (default: 2)
#   NETWORK_MODE      — vpn_required | vpn_preferred | direct_allowed  (default: vpn_preferred)
#   BEAGLE_STREAM_CLIENT_BIN     — Path to beagle-stream-client binary (default: beagle-stream-client)
#   XFREERDP_BIN      — Path to xfreerdp binary (default: xfreerdp)

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
BEAGLE_PORT="${BEAGLE_PORT:-47998}"
RDP_PORT="${RDP_PORT:-3389}"
WG_IFACE="${WG_IFACE:-wg-beagle}"
PROBE_TIMEOUT_S="${PROBE_TIMEOUT_S:-2}"
NETWORK_MODE="${NETWORK_MODE:-vpn_preferred}"
BEAGLE_STREAM_CLIENT_BIN="${BEAGLE_STREAM_CLIENT_BIN:-beagle-stream-client}"
XFREERDP_BIN="${XFREERDP_BIN:-xfreerdp}"

# ---------------------------------------------------------------------------
# Validate required parameters
# ---------------------------------------------------------------------------
if [[ -z "${BEAGLE_HOST:-}" ]]; then
    echo "[proto-select] ERROR: BEAGLE_HOST is not set" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Helper: check if WireGuard interface is up and has a peer
# ---------------------------------------------------------------------------
wireguard_active() {
    if ! ip link show "${WG_IFACE}" &>/dev/null; then
        return 1
    fi
    # Interface exists — check it has a handshake (peer is reachable)
    local latest_handshake
    latest_handshake="$(wg show "${WG_IFACE}" latest-handshakes 2>/dev/null | awk '{print $2}' | sort -n | tail -1 || echo 0)"
    local now
    now="$(date +%s)"
    # Consider WireGuard active if last handshake was within 3 minutes
    if (( (now - latest_handshake) < 180 )); then
        return 0
    fi
    return 1
}

# ---------------------------------------------------------------------------
# Helper: probe TCP/UDP port reachability
# ---------------------------------------------------------------------------
probe_tcp() {
    local host="$1" port="$2"
    timeout "${PROBE_TIMEOUT_S}" bash -c "echo >/dev/tcp/${host}/${port}" 2>/dev/null
}

probe_udp() {
    local host="$1" port="$2"
    # UDP probing with nc; not 100% reliable but a best-effort check
    timeout "${PROBE_TIMEOUT_S}" nc -u -z -w "${PROBE_TIMEOUT_S}" "${host}" "${port}" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Protocol selection logic
# ---------------------------------------------------------------------------
WG_ACTIVE=false
if wireguard_active; then
    WG_ACTIVE=true
    echo "[proto-select] WireGuard interface ${WG_IFACE} is active (recent handshake)."
else
    echo "[proto-select] WireGuard interface ${WG_IFACE} is not active or no recent handshake."
fi

# -- Check policy constraint --
if [[ "${NETWORK_MODE}" == "vpn_required" && "${WG_ACTIVE}" == "false" ]]; then
    echo "[proto-select] ERROR: network_mode=vpn_required but WireGuard is not active." >&2
    echo "[proto-select] DIAGNOSIS: Check ${WG_IFACE} interface: 'wg show ${WG_IFACE}'" >&2
    echo "[proto-select] DIAGNOSIS: Re-run enrollment_wireguard.sh to rejoin the mesh." >&2
    exit 10
fi

# -- Attempt 1: BeagleStream through WireGuard --
if [[ "${WG_ACTIVE}" == "true" ]]; then
    echo "[proto-select] Probing BeagleStream (UDP ${BEAGLE_HOST}:${BEAGLE_PORT}) via WireGuard..."
    if probe_udp "${BEAGLE_HOST}" "${BEAGLE_PORT}"; then
        echo "[proto-select] SUCCESS: BeagleStream via WireGuard"
        echo "PROTOCOL=beaglestream"
        echo "VPN=wireguard"
        echo "HOST=${BEAGLE_HOST}"
        echo "PORT=${BEAGLE_PORT}"
        exit 0
    else
        echo "[proto-select] BeagleStream UDP probe failed (timeout or port unreachable)."
    fi
fi

# -- Attempt 2: BeagleStream direct (only if policy allows) --
if [[ "${NETWORK_MODE}" == "direct_allowed" ]]; then
    echo "[proto-select] Probing BeagleStream direct (UDP ${BEAGLE_HOST}:${BEAGLE_PORT})..."
    if probe_udp "${BEAGLE_HOST}" "${BEAGLE_PORT}"; then
        echo "[proto-select] SUCCESS: BeagleStream direct (no VPN — allowed by policy)"
        echo "PROTOCOL=beaglestream"
        echo "VPN=none"
        echo "HOST=${BEAGLE_HOST}"
        echo "PORT=${BEAGLE_PORT}"
        exit 0
    else
        echo "[proto-select] BeagleStream direct probe failed."
    fi
fi

# -- Attempt 3: xRDP through WireGuard --
if [[ "${WG_ACTIVE}" == "true" ]]; then
    echo "[proto-select] Probing xRDP fallback (TCP ${BEAGLE_HOST}:${RDP_PORT}) via WireGuard..."
    if probe_tcp "${BEAGLE_HOST}" "${RDP_PORT}"; then
        echo "[proto-select] SUCCESS: xRDP via WireGuard (BeagleStream UDP was blocked)"
        echo "PROTOCOL=xrdp"
        echo "VPN=wireguard"
        echo "HOST=${BEAGLE_HOST}"
        echo "PORT=${RDP_PORT}"
        exit 0
    else
        echo "[proto-select] xRDP TCP probe failed."
    fi
fi

# -- No protocol available --
echo "[proto-select] ERROR: No streaming protocol available." >&2
echo "" >&2
echo "DIAGNOSIS:" >&2
echo "  BEAGLE_HOST:   ${BEAGLE_HOST}" >&2
echo "  NETWORK_MODE:  ${NETWORK_MODE}" >&2
echo "  WG_ACTIVE:     ${WG_ACTIVE}" >&2
echo "" >&2
echo "Troubleshooting steps:" >&2
echo "  1. Check WireGuard mesh:   wg show ${WG_IFACE}" >&2
echo "  2. Ping target via mesh:   ping -c1 ${BEAGLE_HOST}" >&2
echo "  3. Re-enroll if needed:    enrollment_wireguard.sh" >&2
echo "  4. Check VM firewall:      UDP ${BEAGLE_PORT} and TCP ${RDP_PORT} must be open on target" >&2
echo "  5. Check Control Plane:    stream policy may block direct connections" >&2
exit 11
