#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROVIDER_MODULE_PATH="${BEAGLE_PROVIDER_MODULE_PATH:-$ROOT_DIR/scripts/lib/beagle_provider.py}"
CONFIG_DIR="${PVE_DCV_CONFIG_DIR:-/etc/beagle}"
MANAGER_ENV_FILE="${BEAGLE_MANAGER_ENV_FILE:-$CONFIG_DIR/beagle-manager.env}"
PUBLIC_STREAM_HOST_RAW="${BEAGLE_PUBLIC_STREAM_HOST:-${PVE_DCV_PROXY_SERVER_NAME:-$(hostname -f 2>/dev/null || hostname)}}"
PUBLIC_STREAM_BASE_PORT="${BEAGLE_PUBLIC_STREAM_BASE_PORT:-50000}"
PUBLIC_STREAM_PORT_STEP="${BEAGLE_PUBLIC_STREAM_PORT_STEP:-32}"
PUBLIC_STREAM_PORT_COUNT="${BEAGLE_PUBLIC_STREAM_PORT_COUNT:-256}"
NFT_TABLE_NAME="${BEAGLE_PUBLIC_STREAM_NFT_TABLE:-beagle_stream}"
LAN_IFACE="${BEAGLE_PUBLIC_STREAM_LAN_IF:-vmbr1}"
STREAMS_FILE="${BEAGLE_PUBLIC_STREAMS_FILE:-/var/lib/beagle/beagle-manager/public-streams.json}"
NFT_STATE_FILE="${BEAGLE_PUBLIC_STREAM_NFT_STATE_FILE:-$CONFIG_DIR/beagle-streams.nft}"

if [[ -f "$MANAGER_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$MANAGER_ENV_FILE"
fi

resolve_public_stream_host() {
  python3 - "$1" <<'PY'
import ipaddress
import socket
import sys

host = str(sys.argv[1] or "").strip()
if not host:
    print("")
    raise SystemExit(0)
try:
    ipaddress.ip_address(host)
except ValueError:
    pass
else:
    print(host)
    raise SystemExit(0)

try:
    infos = socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
except socket.gaierror:
    print(host)
    raise SystemExit(0)

for item in infos:
    ip = str(item[4][0]).strip()
    if ip:
        print(ip)
        raise SystemExit(0)
print(host)
PY
}

PUBLIC_STREAM_HOST="$(resolve_public_stream_host "$PUBLIC_STREAM_HOST_RAW")"

ensure_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi
  if command -v sudo >/dev/null 2>&1; then
    exec sudo \
      PVE_DCV_CONFIG_DIR="$CONFIG_DIR" \
      BEAGLE_MANAGER_ENV_FILE="$MANAGER_ENV_FILE" \
      BEAGLE_PUBLIC_STREAM_HOST="$PUBLIC_STREAM_HOST" \
      BEAGLE_PUBLIC_STREAM_BASE_PORT="$PUBLIC_STREAM_BASE_PORT" \
      BEAGLE_PUBLIC_STREAM_PORT_STEP="$PUBLIC_STREAM_PORT_STEP" \
      BEAGLE_PUBLIC_STREAM_PORT_COUNT="$PUBLIC_STREAM_PORT_COUNT" \
      BEAGLE_PUBLIC_STREAM_NFT_TABLE="$NFT_TABLE_NAME" \
      BEAGLE_PUBLIC_STREAM_LAN_IF="$LAN_IFACE" \
      BEAGLE_PUBLIC_STREAMS_FILE="$STREAMS_FILE" \
      BEAGLE_PUBLIC_STREAM_NFT_STATE_FILE="$NFT_STATE_FILE" \
      "$0" "$@"
  fi
  echo "This command must run as root." >&2
  exit 1
}

resolve_public_ips_json() {
  python3 - "$PUBLIC_STREAM_HOST" <<'PY'
import json
import socket
import sys

host = sys.argv[1]
ips = []
seen = set()
for item in socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM):
    ip = item[4][0]
    if ip in seen:
        continue
    seen.add(ip)
    ips.append(ip)
print(json.dumps(ips))
PY
}

ensure_root "$@"
install -d -m 0755 "$(dirname "$STREAMS_FILE")" "$CONFIG_DIR"

inventory_file="$(mktemp)"
public_ips_file="$(mktemp)"
nft_tmp="$(mktemp)"
cleanup() {
  rm -f "$inventory_file" "$public_ips_file" "$nft_tmp"
}
trap cleanup EXIT

python3 - "$PROVIDER_MODULE_PATH" "$STREAMS_FILE" "$PUBLIC_STREAM_HOST" "$PUBLIC_STREAM_BASE_PORT" "$PUBLIC_STREAM_PORT_STEP" "$PUBLIC_STREAM_PORT_COUNT" >"$inventory_file" <<'PY'
import json
import sys
from pathlib import Path
from urllib.parse import unquote

provider_module_path = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(provider_module_path.parent))

from beagle_provider import guest_interfaces, list_vms, vm_config

streams_path = Path(sys.argv[2])
public_host = sys.argv[3]
base_port = int(sys.argv[4])
port_step = int(sys.argv[5])
port_count = int(sys.argv[6])


def parse_description_meta(description):
    meta = {}
    text = str(description or "").replace("\\r\\n", "\n").replace("\\n", "\n")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key and key not in meta:
            meta[key] = value
    return meta


def first_guest_ipv4(vmid):
    for iface in guest_interfaces(vmid):
        for address in iface.get("ip-addresses", []):
            ip = str(address.get("ip-address", ""))
            if address.get("ip-address-type") != "ipv4":
                continue
            if not ip or ip.startswith("127.") or ip.startswith("169.254."):
                continue
            return ip
    return ""


def should_publish(meta, guest_ip):
    if str(meta.get("beagle-public-stream", "1")).strip().lower() in {"0", "false", "no", "off"}:
        return False
    if meta.get("beagle-public-moonlight-port"):
        return True
    if meta.get("sunshine-user") or meta.get("sunshine-password") or meta.get("sunshine-api-url"):
        return True
    if meta.get("moonlight-host") or meta.get("sunshine-host") or meta.get("sunshine-ip"):
        return True
    if guest_ip and str(meta.get("beagle-role", "")).strip().lower() == "desktop":
        return True
    return False


def load_streams():
    try:
        payload = json.loads(streams_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    data = {}
    for key, value in payload.items():
        try:
            data[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return data


def save_streams(data):
    streams_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


resources = list_vms()
if not resources:
    print("[]")
    raise SystemExit(0)

streams = load_streams()
used = {int(value) for value in streams.values()}
upper_bound = base_port + (port_step * port_count)
items = []
active_keys = set()

for vm in sorted(resources, key=lambda item: int(item.get("vmid", 0))):
    if vm.get("type") != "qemu" or vm.get("vmid") is None or not vm.get("node"):
        continue
    vmid = int(vm["vmid"])
    node = str(vm["node"])
    config = vm_config(node, vmid) or {}
    meta = parse_description_meta(config.get("description", ""))
    guest_ip = first_guest_ipv4(vmid)
    if not should_publish(meta, guest_ip):
        continue
    if not guest_ip:
        continue
    key = f"{node}:{vmid}"
    active_keys.add(key)
    explicit_port = str(meta.get("beagle-public-moonlight-port", "")).strip()
    if explicit_port.isdigit():
        mapped_base = int(explicit_port)
        if streams.get(key) != mapped_base:
            streams[key] = mapped_base
        used.add(mapped_base)
    else:
        mapped_base = streams.get(key)
        if mapped_base is None:
            for candidate in range(base_port, upper_bound, port_step):
                if candidate in used:
                    continue
                mapped_base = candidate
                streams[key] = candidate
                used.add(candidate)
                break
    if mapped_base is None:
        continue
    items.append({
        "vmid": vmid,
        "node": node,
        "name": str(config.get("name") or vm.get("name") or f"vm-{vmid}"),
        "guest_ip": guest_ip,
        "public_host": str(meta.get("beagle-public-stream-host", "")).strip() or public_host,
        "base_port": int(mapped_base),
        "sunshine_api_url": str(meta.get("beagle-public-sunshine-api-url", "")).strip() or f"https://{public_host}:{int(mapped_base) + 1}",
    })

stale_keys = [key for key in streams if key not in active_keys]
for key in stale_keys:
    streams.pop(key, None)

save_streams(streams)
print(json.dumps(items, indent=2))
PY

resolve_public_ips_json >"$public_ips_file"

python3 - "$inventory_file" "$public_ips_file" "$NFT_TABLE_NAME" "$LAN_IFACE" >"$nft_tmp" <<'PY'
import json
import sys

inventory = json.load(open(sys.argv[1], encoding="utf-8"))
public_ips = json.load(open(sys.argv[2], encoding="utf-8"))
table_name = sys.argv[3]
lan_iface = sys.argv[4]

print(f"table inet {table_name} {{")
print("  chain prerouting {")
print("    type nat hook prerouting priority dstnat; policy accept;")
if public_ips:
    daddr_expr = "{ " + ", ".join(public_ips) + " }" if len(public_ips) > 1 else public_ips[0]
    for item in inventory:
        guest_ip = item["guest_ip"]
        base = int(item["base_port"])
        tcp_ports = {
            base - 5: base - 5,
            base: base,
            base + 1: base + 1,
            base + 21: base + 21,
        }
        udp_ports = {
            base + 9: base + 9,
            base + 10: base + 10,
            base + 11: base + 11,
            base + 13: base + 13,
        }
        for public_port, guest_port in tcp_ports.items():
            print(f"    ip daddr {daddr_expr} tcp dport {public_port} dnat to {guest_ip}:{guest_port}")
        for public_port, guest_port in udp_ports.items():
            print(f"    ip daddr {daddr_expr} udp dport {public_port} dnat to {guest_ip}:{guest_port}")
print("  }")
print("  chain forward {")
print("    type filter hook forward priority filter; policy accept;")
for item in inventory:
    guest_ip = item["guest_ip"]
    base = int(item["base_port"])
    print(f"    oifname \"{lan_iface}\" ip daddr {guest_ip} tcp dport {{ {base - 5}, {base}, {base + 1}, {base + 21} }} accept")
    print(f"    oifname \"{lan_iface}\" ip daddr {guest_ip} udp dport {{ {base + 9}, {base + 10}, {base + 11}, {base + 13} }} accept")
print("  }")
print("}")
PY

sysctl -w net.ipv4.ip_forward=1 >/dev/null
nft delete table inet "$NFT_TABLE_NAME" >/dev/null 2>&1 || true
nft -f "$nft_tmp"
install -D -m 0644 "$nft_tmp" "$NFT_STATE_FILE"

echo "Reconciled Beagle public streams for host $PUBLIC_STREAM_HOST"
python3 - "$inventory_file" <<'PY'
import json
import sys
items = json.load(open(sys.argv[1], encoding='utf-8'))
for item in items:
    print(f"VM {item['vmid']} -> {item['public_host']}:{item['base_port']} ({item['guest_ip']})")
if not items:
    print("No public stream targets found.")
PY
