#!/usr/bin/env bash
set -euo pipefail

PUBLIC_IP="${BEAGLE_PUBLIC_IP:-}"
HOST_SSH="${BEAGLE_HOST_SSH:-srv1.beagle-os.com}"
VM_IP="${BEAGLE_STREAM_VM_IP:-}"
WG_IFACE="${BEAGLE_WG_IFACE:-wg-beagle}"
THINCLIENT_SSH="${BEAGLE_THINCLIENT_SSH:-}"
STREAM_TCP_PORTS="${BEAGLE_STREAM_TCP_PORTS:-49995 50000 50001 50021}"
STREAM_UDP_PORTS="${BEAGLE_STREAM_UDP_PORTS:-50009 50010 50011 50012 50013 50014 50015}"

usage() {
  cat <<'USAGE'
Usage: check-beaglestream-production-baseline.sh --public-ip IP --vm-ip IP [--host SSH] [--thinclient SSH]

Validates the production BeagleStream baseline:
- public stream TCP ports are closed from the caller's network
- srv1 has no legacy public BeagleStream DNAT table
- srv1 has the public stream drop guard before DNAT
- VM stream TCP ports remain reachable internally from the host
- WireGuard interface is present on the host
- optional thinclient SSH check confirms client process/socket target

Environment overrides:
  BEAGLE_PUBLIC_IP, BEAGLE_HOST_SSH, BEAGLE_STREAM_VM_IP, BEAGLE_WG_IFACE, BEAGLE_THINCLIENT_SSH
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --public-ip) PUBLIC_IP="${2:-}"; shift 2 ;;
    --vm-ip) VM_IP="${2:-}"; shift 2 ;;
    --host) HOST_SSH="${2:-}"; shift 2 ;;
    --thinclient) THINCLIENT_SSH="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$PUBLIC_IP" ]] || { echo "missing --public-ip" >&2; exit 2; }
[[ -n "$VM_IP" ]] || { echo "missing --vm-ip" >&2; exit 2; }

failures=0

record_ok() {
  printf 'OK %s\n' "$*"
}

record_fail() {
  printf 'FAIL %s\n' "$*" >&2
  failures=$((failures + 1))
}

for port in $STREAM_TCP_PORTS; do
  if timeout 3 bash -lc "</dev/tcp/${PUBLIC_IP}/${port}" >/dev/null 2>&1; then
    record_fail "public tcp ${PUBLIC_IP}:${port} is open"
  else
    record_ok "public tcp ${PUBLIC_IP}:${port} closed"
  fi
done

host_script=$(cat <<'HOSTSCRIPT'
set -euo pipefail
vm_ip="$1"
wg_iface="$2"
shift 2
tcp_ports="$*"

echo ---legacy-public-dnat---
if sudo nft list table inet beagle_stream >/dev/null 2>&1; then
  echo legacy_public_dnat=present
else
  echo legacy_public_dnat=absent
fi

echo ---public-guard---
sudo nft list table inet beagle_stream_public_guard 2>/dev/null | grep -E 'hook prerouting priority dstnat - 10|tcp dport \{ 49995, 50000, 50001, 50021 \} drop|udp dport \{ 50009, 50010, 50011, 50012, 50013, 50014, 50015 \} drop' || true

echo ---wireguard---
ip -brief addr show "$wg_iface" 2>/dev/null || true

echo ---internal-vm-ports---
for port in $tcp_ports; do
  if timeout 2 bash -lc "</dev/tcp/${vm_ip}/${port}" >/dev/null 2>&1; then
    echo "internal:${port}:open"
  else
    echo "internal:${port}:closed"
  fi
done
HOSTSCRIPT
)

host_output="$(ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no "$HOST_SSH" bash -s -- "$VM_IP" "$WG_IFACE" $STREAM_TCP_PORTS <<<"$host_script")"
printf '%s\n' "$host_output"

grep -q 'legacy_public_dnat=absent' <<<"$host_output" || record_fail "legacy public BeagleStream DNAT table is present"
grep -q 'hook prerouting priority dstnat - 10' <<<"$host_output" || record_fail "public guard hook is missing"
grep -q 'tcp dport { 49995, 50000, 50001, 50021 } drop' <<<"$host_output" || record_fail "public TCP guard is missing"
grep -q 'udp dport { 50009, 50010, 50011, 50012, 50013, 50014, 50015 } drop' <<<"$host_output" || record_fail "public UDP guard is missing"
grep -q "^${WG_IFACE}[[:space:]]" <<<"$host_output" || record_fail "host WireGuard interface ${WG_IFACE} is missing"

for port in $STREAM_TCP_PORTS; do
  grep -q "internal:${port}:open" <<<"$host_output" || record_fail "internal VM tcp ${VM_IP}:${port} is not reachable from host"
done

if [[ -n "$THINCLIENT_SSH" ]]; then
  thinclient_output="$(ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no "$THINCLIENT_SSH" 'ps -eo pid,ni,args | grep -E "[b]eagle-stream stream" || true; ip -brief addr show wg-beagle 2>/dev/null || true; ss -tunp 2>/dev/null | grep -E "192\.168\.|10\.88\.|:50000|:49995|:50001|:50021" || true')"
  printf '%s\n' "---thinclient---" "$thinclient_output"
  grep -q 'beagle-stream stream' <<<"$thinclient_output" || record_fail "thinclient BeagleStream process not found"
  grep -q '^wg-beagle[[:space:]]' <<<"$thinclient_output" || record_fail "thinclient wg-beagle interface not found"
fi

if [[ "$failures" -gt 0 ]]; then
  echo "beaglestream_production_baseline=FAIL failures=${failures}" >&2
  exit 1
fi

echo "beaglestream_production_baseline=PASS"