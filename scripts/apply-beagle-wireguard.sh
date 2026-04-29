#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${BEAGLE_CONFIG_DIR:-/etc/beagle}"
MANAGER_ENV_FILE="${BEAGLE_MANAGER_ENV_FILE:-$CONFIG_DIR/beagle-manager.env}"
HOST_ENV_FILE="${BEAGLE_HOST_ENV_FILE:-$CONFIG_DIR/host.env}"
WG_STATE_DIR="${BEAGLE_WIREGUARD_STATE_DIR:-$CONFIG_DIR/wireguard}"
WG_IFACE="${BEAGLE_WIREGUARD_INTERFACE:-wg-beagle}"
WG_PORT="${BEAGLE_WIREGUARD_PORT:-51820}"
WG_SUBNET="${BEAGLE_WIREGUARD_SUBNET:-10.88.0.0/16}"
WG_ADDRESS="${BEAGLE_WIREGUARD_ADDRESS:-10.88.0.1/16}"
WG_CONF="${BEAGLE_WIREGUARD_CONF:-/etc/wireguard/${WG_IFACE}.conf}"
WG_NFT_FILE="${BEAGLE_WIREGUARD_NFT_FILE:-$CONFIG_DIR/beagle-wireguard.nft}"
WG_NFT_TABLE="${BEAGLE_WIREGUARD_NFT_TABLE:-beagle_wireguard_nat}"
WG_CLIENT_DNS="${BEAGLE_WIREGUARD_CLIENT_DNS:-1.1.1.1}"
WG_ALLOWED_IPS="${BEAGLE_WIREGUARD_ALLOWED_IPS:-0.0.0.0/0}"
WG_MESH_STATE_FILE="${BEAGLE_WIREGUARD_MESH_STATE_FILE:-/var/lib/beagle/beagle-manager/wireguard-mesh/mesh-state.json}"
WG_UPLINK_IFACE="${BEAGLE_WIREGUARD_UPLINK_IFACE:-}"
WG_PUBLIC_HOST="${BEAGLE_WIREGUARD_PUBLIC_HOST:-}"
ACTION="${1:---enable}"

source_env_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    # shellcheck disable=SC1090
    set -a; source "$file"; set +a
  fi
}

write_env_key() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp
  tmp="$(mktemp)"
  if [[ -f "$file" ]]; then
    grep -Ev "^${key}=" "$file" >"$tmp" || true
  fi
  printf '%s=%q\n' "$key" "$value" >>"$tmp"
  install -D -m 0600 "$tmp" "$file"
  rm -f "$tmp"
}

detect_uplink_iface() {
  if [[ -n "$WG_UPLINK_IFACE" ]]; then
    printf '%s\n' "$WG_UPLINK_IFACE"
    return 0
  fi
  ip route show default 2>/dev/null | awk '/default/ {print $5; exit}'
}

detect_public_host() {
  if [[ -n "$WG_PUBLIC_HOST" ]]; then
    printf '%s\n' "$WG_PUBLIC_HOST"
    return 0
  fi
  if [[ -n "${BEAGLE_PUBLIC_STREAM_HOST:-}" ]]; then
    printf '%s\n' "${BEAGLE_PUBLIC_STREAM_HOST}"
    return 0
  fi
  hostname -f 2>/dev/null || hostname
}

ensure_keys() {
  local private_key_file public_key_file
  private_key_file="$WG_STATE_DIR/server_private.key"
  public_key_file="$WG_STATE_DIR/server_public.key"
  install -d -m 0700 "$WG_STATE_DIR"
  if [[ ! -s "$private_key_file" ]]; then
    umask 077
    wg genkey >"$private_key_file"
  fi
  if [[ ! -s "$public_key_file" ]]; then
    wg pubkey <"$private_key_file" >"$public_key_file"
  fi
  chmod 0600 "$private_key_file" "$public_key_file"
}

append_mesh_peers() {
  python3 - "$WG_MESH_STATE_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(0)

state = json.loads(path.read_text(encoding="utf-8"))
peers = state.get("peers") or {}
for device_id in sorted(peers):
    peer = peers.get(device_id) or {}
    public_key = str(peer.get("public_key") or "").strip()
    assigned_ip = str(peer.get("assigned_ip") or "").strip()
    if not public_key or not assigned_ip:
        continue
    print()
    print("[Peer]")
    print(f"# device_id = {device_id}")
    print(f"PublicKey = {public_key}")
    preshared_key = str(peer.get("preshared_key") or "").strip()
    if preshared_key:
        print(f"PresharedKey = {preshared_key}")
    print(f"AllowedIPs = {assigned_ip}/32")
    endpoint = str(peer.get("endpoint") or "").strip()
    if endpoint:
        print(f"Endpoint = {endpoint}")
PY
}

write_wireguard_conf() {
  local private_key
  private_key="$(cat "$WG_STATE_DIR/server_private.key")"
  install -d -m 0700 "$(dirname "$WG_CONF")"
  umask 077
  cat >"$WG_CONF" <<EOF
[Interface]
Address = ${WG_ADDRESS}
ListenPort = ${WG_PORT}
PrivateKey = ${private_key}
SaveConfig = false
EOF
  append_mesh_peers >>"$WG_CONF"
  chmod 0600 "$WG_CONF"
}

write_sysctl_conf() {
  install -d -m 0755 /etc/sysctl.d
  cat >/etc/sysctl.d/99-beagle-wireguard.conf <<'EOF'
net.ipv4.ip_forward=1
EOF
  sysctl -q -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
}

write_nat_rules() {
  local uplink
  uplink="$(detect_uplink_iface)"
  [[ -n "$uplink" ]] || {
    echo "unable to detect WireGuard uplink interface" >&2
    return 1
  }
  install -d -m 0755 "$CONFIG_DIR"
  cat >"$WG_NFT_FILE" <<EOF
table ip ${WG_NFT_TABLE} {
  chain postrouting {
    type nat hook postrouting priority srcnat; policy accept;
    ip saddr ${WG_SUBNET} oifname "${uplink}" masquerade
  }
}
EOF
  chmod 0644 "$WG_NFT_FILE"
}

apply_nat_rules() {
  nft delete table ip "$WG_NFT_TABLE" >/dev/null 2>&1 || true
  nft -f "$WG_NFT_FILE"
}

enable_wireguard() {
  local public_host public_key endpoint
  ensure_keys
  write_wireguard_conf
  write_sysctl_conf
  write_nat_rules
  apply_nat_rules
  systemctl enable "wg-quick@${WG_IFACE}" >/dev/null 2>&1 || true
  systemctl restart "wg-quick@${WG_IFACE}" >/dev/null 2>&1 || {
    wg-quick down "$WG_IFACE" >/dev/null 2>&1 || true
    wg-quick up "$WG_IFACE"
  }
  public_host="$(detect_public_host)"
  public_key="$(cat "$WG_STATE_DIR/server_public.key")"
  endpoint="${public_host}:${WG_PORT}"
  write_env_key "$MANAGER_ENV_FILE" "BEAGLE_WIREGUARD_ENABLED" "1"
  write_env_key "$MANAGER_ENV_FILE" "BEAGLE_WIREGUARD_INTERFACE" "$WG_IFACE"
  write_env_key "$MANAGER_ENV_FILE" "BEAGLE_WIREGUARD_PORT" "$WG_PORT"
  write_env_key "$MANAGER_ENV_FILE" "BEAGLE_WIREGUARD_SUBNET" "$WG_SUBNET"
  write_env_key "$MANAGER_ENV_FILE" "BEAGLE_WIREGUARD_CLIENT_DNS" "$WG_CLIENT_DNS"
  write_env_key "$MANAGER_ENV_FILE" "BEAGLE_WIREGUARD_ALLOWED_IPS" "$WG_ALLOWED_IPS"
  write_env_key "$MANAGER_ENV_FILE" "BEAGLE_WIREGUARD_SERVER_PUBLIC_KEY" "$public_key"
  write_env_key "$MANAGER_ENV_FILE" "BEAGLE_WIREGUARD_SERVER_ENDPOINT" "$endpoint"
}

disable_wireguard() {
  systemctl stop "wg-quick@${WG_IFACE}" >/dev/null 2>&1 || true
  nft delete table ip "$WG_NFT_TABLE" >/dev/null 2>&1 || true
  write_env_key "$MANAGER_ENV_FILE" "BEAGLE_WIREGUARD_ENABLED" "0"
}

status_wireguard() {
  if ip link show "$WG_IFACE" >/dev/null 2>&1; then
    echo "active"
  else
    echo "inactive"
  fi
}

source_env_file "$HOST_ENV_FILE"
source_env_file "$MANAGER_ENV_FILE"

case "$ACTION" in
  --enable|enable)
    enable_wireguard
    ;;
  --disable|disable)
    disable_wireguard
    ;;
  --status|status)
    status_wireguard
    ;;
  *)
    echo "Usage: $0 [--enable|--disable|--status]" >&2
    exit 2
    ;;
esac
