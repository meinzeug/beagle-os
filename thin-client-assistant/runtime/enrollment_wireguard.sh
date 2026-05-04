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
for trace_guard_candidate in \
  "$SCRIPT_DIR/../../scripts/lib/trace-guard.sh" \
  "/usr/local/lib/scripts/lib/trace-guard.sh" \
  "/usr/local/lib/pve-thin-client/scripts/lib/trace-guard.sh"
do
  if [[ -r "$trace_guard_candidate" ]]; then
    # shellcheck disable=SC1090
    source "$trace_guard_candidate"
    break
  fi
done
if declare -F beagle_trace_guard_disable_xtrace_if_sensitive >/dev/null 2>&1; then
  beagle_trace_guard_disable_xtrace_if_sensitive
fi
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh" 2>/dev/null || true
PERSIST_WIREGUARD_CONFIG_PY="${PERSIST_WIREGUARD_CONFIG_PY:-$SCRIPT_DIR/persist_wireguard_runtime_config.py}"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
ENROLLMENT_CONF="${ENROLLMENT_CONF:-/etc/beagle/enrollment.conf}"
WG_IFACE="${WG_IFACE:-wg-beagle}"
WG_CONF="${WG_CONF:-/etc/wireguard/${WG_IFACE}.conf}"
WG_KEYS_DIR="${WG_KEYS_DIR:-/etc/beagle/wireguard}"
WG_RESOLV_CONF="${WG_RESOLV_CONF:-/etc/resolv.conf}"
WG_MTU="${PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_MTU:-${WG_MTU:-1280}}"
TIMEOUT="${TIMEOUT:-15}"

# ---------------------------------------------------------------------------
# Read enrollment config if environment not provided
# ---------------------------------------------------------------------------
if [[ -f "${ENROLLMENT_CONF}" ]]; then
    BEAGLE_CONTROL_PLANE="${BEAGLE_CONTROL_PLANE:-$(grep -E '^control_plane=' "${ENROLLMENT_CONF}" | cut -d= -f2- | tr -d '[:space:]')}"
    BEAGLE_ENROLLMENT_TOKEN="${BEAGLE_ENROLLMENT_TOKEN:-$(grep -E '^enrollment_token=' "${ENROLLMENT_CONF}" | cut -d= -f2- | tr -d '[:space:]')}"
    BEAGLE_DEVICE_ID="${BEAGLE_DEVICE_ID:-$(grep -E '^device_id=' "${ENROLLMENT_CONF}" | cut -d= -f2- | tr -d '[:space:]')}"
fi
BEAGLE_CONTROL_PLANE="${BEAGLE_CONTROL_PLANE:-${BEAGLE_MANAGER_URL:-}}"

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
for cmd in wg ip curl jq; do
    if ! command -v "${cmd}" &>/dev/null; then
        echo "[wg-enroll] ERROR: Required command not found: ${cmd}" >&2
        exit 1
    fi
done

endpoint_host() {
    local endpoint="${SERVER_ENDPOINT:-}"

    endpoint="${endpoint#[}"
    endpoint="${endpoint%]}"
    if [[ "$endpoint" == *:* ]]; then
        printf '%s\n' "${endpoint%:*}"
        return 0
    fi
    printf '%s\n' "$endpoint"
}

default_route_state() {
    ip -4 route show default 2>/dev/null | head -n1
}

resolve_endpoint_ip() {
    local host="$1"
    if [[ "$host" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        printf '%s\n' "$host"
        return 0
    fi
    getent ahostsv4 "$host" 2>/dev/null | awk 'NR==1 { print $1 }' || true
}

apply_dns_settings() {
    local raw_dns="$1"
    local -a dns_servers=()
    local dns_value

    raw_dns="${raw_dns//,/ }"
    for dns_value in $raw_dns; do
        [[ -n "$dns_value" ]] || continue
        dns_servers+=("$dns_value")
    done
    [[ ${#dns_servers[@]} -gt 0 ]] || return 0

    if command -v resolvectl >/dev/null 2>&1; then
        if command -v timeout >/dev/null 2>&1 &&
           timeout 5 resolvectl dns "$WG_IFACE" "${dns_servers[@]}" &&
           timeout 5 resolvectl domain "$WG_IFACE" "~."; then
            return 0
        fi
    fi

    if command -v resolvconf >/dev/null 2>&1; then
        if command -v timeout >/dev/null 2>&1 &&
           {
               local server
               for server in "${dns_servers[@]}"; do
                   printf 'nameserver %s\n' "$server"
               done
           } | timeout 5 resolvconf -a "$WG_IFACE" -m 0 -x; then
            return 0
        fi
    fi

    {
        local server
        for server in "${dns_servers[@]}"; do
            printf 'nameserver %s\n' "$server"
        done
    } >"$WG_RESOLV_CONF"
}

apply_wireguard_routes() {
  local raw_allowed_ips="$1"
  local route_line endpoint_ip endpoint_value default_gateway default_dev
  local -a allowed_ip_entries=()
  local cidr

  ip route delete 0.0.0.0/1 dev "$WG_IFACE" 2>/dev/null || true
  ip route delete 128.0.0.0/1 dev "$WG_IFACE" 2>/dev/null || true
  ip -6 route delete ::/1 dev "$WG_IFACE" 2>/dev/null || true
  ip -6 route delete 8000::/1 dev "$WG_IFACE" 2>/dev/null || true

  raw_allowed_ips="${raw_allowed_ips//,/ }"
    for cidr in $raw_allowed_ips; do
        [[ -n "$cidr" ]] || continue
        allowed_ip_entries+=("$cidr")
    done
    [[ ${#allowed_ip_entries[@]} -gt 0 ]] || return 0

    route_line="$(default_route_state)"
    default_gateway="$(awk '{for (idx=1; idx<=NF; idx++) if ($idx == "via") { print $(idx+1); exit }}' <<<"$route_line")"
    default_dev="$(awk '{for (idx=1; idx<=NF; idx++) if ($idx == "dev") { print $(idx+1); exit }}' <<<"$route_line")"
    endpoint_value="$(endpoint_host)"
    endpoint_ip="$(resolve_endpoint_ip "$endpoint_value")"

    if [[ -n "$endpoint_ip" && -n "$default_dev" ]]; then
        if [[ -n "$default_gateway" ]]; then
            ip route replace "${endpoint_ip}/32" via "$default_gateway" dev "$default_dev"
        else
            ip route replace "${endpoint_ip}/32" dev "$default_dev"
        fi
    fi

    for cidr in "${allowed_ip_entries[@]}"; do
        case "$cidr" in
            0.0.0.0/0)
                ip route replace 0.0.0.0/1 dev "$WG_IFACE"
                ip route replace 128.0.0.0/1 dev "$WG_IFACE"
                ;;
            ::/0)
                ip -6 route replace ::/1 dev "$WG_IFACE"
                ip -6 route replace 8000::/1 dev "$WG_IFACE"
                ;;
            *:*)
                ip -6 route replace "$cidr" dev "$WG_IFACE"
                ;;
            *)
                ip route replace "$cidr" dev "$WG_IFACE"
                ;;
        esac
    done
}

apply_wireguard_peer_config() {
    local runtime_conf
    runtime_conf="$(mktemp)"
    trap 'rm -f "$runtime_conf"' RETURN

    {
        echo "[Interface]"
        echo "PrivateKey = ${PRIVATE_KEY}"
        echo ""
        echo "[Peer]"
        echo "PublicKey = ${SERVER_PUBKEY}"
        if [[ -n "${PRESHARED_KEY}" ]]; then
            echo "PresharedKey = ${PRESHARED_KEY}"
        fi
        echo "Endpoint = ${SERVER_ENDPOINT}"
        echo "AllowedIPs = ${ALLOWED_IPS}"
        echo "PersistentKeepalive = 25"
    } >"$runtime_conf"

    wg setconf "${WG_IFACE}" "$runtime_conf"
}

persist_runtime_wireguard_config() {
    local config_dir config_file credentials_file keepalive
    [[ -f "${PERSIST_WIREGUARD_CONFIG_PY}" ]] || return 0

    config_dir="${CONFIG_DIR:-${PVE_THIN_CLIENT_SYSTEM_CONFIG_DIR:-/etc/pve-thin-client}}"
    config_file="${CONFIG_FILE:-${config_dir}/thinclient.conf}"
    credentials_file="${CREDENTIALS_FILE:-${config_dir}/credentials.env}"
    keepalive="${PVE_THIN_CLIENT_BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE:-25}"

    python3 "${PERSIST_WIREGUARD_CONFIG_PY}" \
        "${config_file}" \
        "${credentials_file}" \
        "${CLIENT_IP}" \
        "${DNS}" \
        "${SERVER_PUBKEY}" \
        "${SERVER_ENDPOINT}" \
        "${ALLOWED_IPS}" \
        "${PRIVATE_KEY}" \
        "${PRESHARED_KEY}" \
        "${keepalive}"
}

# ---------------------------------------------------------------------------
# Generate keypair (only if private key does not already exist)
# ---------------------------------------------------------------------------
mkdir -p "${WG_KEYS_DIR}"
chmod 700 "${WG_KEYS_DIR}" 2>/dev/null || true

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
    chmod 600 "${PRIVKEY_FILE}" 2>/dev/null || true
    chmod 644 "${PUBKEY_FILE}" 2>/dev/null || true
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

curl_args=(
    curl
    --silent
    --show-error
    --max-time "${TIMEOUT}"
    --connect-timeout 5
    --output /tmp/wg-register-response.json
    --write-out "%{http_code}"
    --header "Content-Type: application/json"
)
if [[ -n "${BEAGLE_MANAGER_TOKEN:-}" ]]; then
    curl_args+=(--header "Authorization: Bearer ${BEAGLE_MANAGER_TOKEN}")
fi
HTTP_CODE="$("${curl_args[@]}" \
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
ALLOWED_IPS="$(echo "${RESPONSE}" | jq -r 'if (.allowed_ips | type) == "array" then (.allowed_ips | join(", ")) else (.allowed_ips // "10.88.0.0/16, 192.168.123.0/24") end')"
CLIENT_IP="$(echo "${RESPONSE}" | jq -r '.client_ip // empty')"
DNS="$(echo "${RESPONSE}" | jq -r 'if (.dns | type) == "array" then (.dns | join(", ")) else (.dns // "10.88.0.1") end')"
PRESHARED_KEY="$(echo "${RESPONSE}" | jq -r '.preshared_key // empty')"

if [[ -z "${SERVER_PUBKEY}" || -z "${SERVER_ENDPOINT}" || -z "${CLIENT_IP}" ]]; then
    echo "[wg-enroll] ERROR: Incomplete peer config in Control Plane response" >&2
    echo "${RESPONSE}" >&2
    exit 3
fi

persist_runtime_wireguard_config

# ---------------------------------------------------------------------------
# Write /etc/wireguard/wg-beagle.conf
# ---------------------------------------------------------------------------
echo "[wg-enroll] Writing WireGuard config to ${WG_CONF}..."

mkdir -p "$(dirname "${WG_CONF}")"

{
    echo "[Interface]"
    echo "Address = ${CLIENT_IP}"
    echo "PrivateKey = ${PRIVATE_KEY}"
    echo "MTU = ${WG_MTU}"
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
# Bring up the WireGuard interface without wg-quick so live images do not
# depend on additional DNS helpers or policy-routing side effects.
# ---------------------------------------------------------------------------
echo "[wg-enroll] Starting WireGuard interface ${WG_IFACE}..."

if ip link show "${WG_IFACE}" &>/dev/null; then
    ip link delete "${WG_IFACE}" 2>/dev/null || true
fi

ip link add "${WG_IFACE}" type wireguard
apply_wireguard_peer_config
ip address add "${CLIENT_IP}" dev "${WG_IFACE}"
ip link set mtu "${WG_MTU}" up dev "${WG_IFACE}"
apply_dns_settings "${DNS}"
apply_wireguard_routes "${ALLOWED_IPS}"

echo "[wg-enroll] WireGuard interface ${WG_IFACE} is up. Client IP: ${CLIENT_IP}"
echo "[wg-enroll] Mesh enrollment complete. All subsequent streams will run through the secure tunnel."
