#!/usr/bin/env bash
set -euo pipefail

PUBLIC_IP="${BEAGLE_PUBLIC_IP:-}"
HOST_SSH="${BEAGLE_HOST_SSH:-srv1.beagle-os.com}"
VM_IP="${BEAGLE_STREAM_VM_IP:-}"
WG_IFACE="${BEAGLE_WG_IFACE:-wg-beagle}"
THINCLIENT_SSH="${BEAGLE_THINCLIENT_SSH:-}"
VMID="${BEAGLE_STREAM_VMID:-100}"
SKIP_GUEST_CONFIG_CHECK="${BEAGLE_SKIP_GUEST_CONFIG_CHECK:-0}"
REQUIRE_WG_HANDSHAKE="${BEAGLE_REQUIRE_WG_HANDSHAKE:-0}"
WG_REQUIRED_ALLOWED_IP="${BEAGLE_WG_REQUIRED_ALLOWED_IP:-10.88.1.1/32}"
STREAM_TCP_PORTS="${BEAGLE_STREAM_TCP_PORTS:-49995 50000 50001 50021}"
STREAM_UDP_PORTS="${BEAGLE_STREAM_UDP_PORTS:-50009 50010 50011 50012 50013 50014 50015}"

usage() {
  cat <<'USAGE'
Usage: check-beaglestream-production-baseline.sh --public-ip IP --vm-ip IP [--host SSH] [--vmid ID] [--thinclient SSH] [--require-wg-handshake] [--wg-peer-allowed-ip CIDR] [--skip-guest-config-check]

Validates the production BeagleStream baseline:
- public stream TCP ports are closed from the caller's network
- srv1 has no legacy public BeagleStream DNAT table
- srv1 has the public stream drop guard before DNAT
- VM stream TCP ports remain reachable internally from the host
- VM BeagleStream/Sunshine guest config matches the frozen production baseline
- WireGuard interface is present on the host
- optional WireGuard peer handshake check confirms the thinclient VPN is connected
- optional thinclient SSH check confirms client process/socket target

Environment overrides:
  BEAGLE_PUBLIC_IP, BEAGLE_HOST_SSH, BEAGLE_STREAM_VM_IP, BEAGLE_STREAM_VMID,
  BEAGLE_WG_IFACE, BEAGLE_WG_REQUIRED_ALLOWED_IP, BEAGLE_REQUIRE_WG_HANDSHAKE,
  BEAGLE_THINCLIENT_SSH, BEAGLE_SKIP_GUEST_CONFIG_CHECK
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --public-ip) PUBLIC_IP="${2:-}"; shift 2 ;;
    --vm-ip) VM_IP="${2:-}"; shift 2 ;;
    --host) HOST_SSH="${2:-}"; shift 2 ;;
    --vmid) VMID="${2:-}"; shift 2 ;;
    --thinclient) THINCLIENT_SSH="${2:-}"; shift 2 ;;
    --require-wg-handshake) REQUIRE_WG_HANDSHAKE=1; shift ;;
    --wg-peer-allowed-ip) WG_REQUIRED_ALLOWED_IP="${2:-}"; shift 2 ;;
    --skip-guest-config-check) SKIP_GUEST_CONFIG_CHECK=1; shift ;;
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
vmid="$3"
skip_guest_config_check="$4"
wg_required_allowed_ip="$5"
shift 5
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
sudo wg show "$wg_iface" dump 2>/dev/null | awk -v allowed="$wg_required_allowed_ip" '
  NR > 1 && $4 == allowed {
    print "wg_peer_allowed_ips=" $4
    print "wg_peer_endpoint=" $3
    print "wg_peer_latest_handshake=" $5
    print "wg_peer_transfer_rx=" $6
    print "wg_peer_transfer_tx=" $7
  }
  NR > 1 && $5 == allowed {
    print "wg_peer_allowed_ips=" $5
    print "wg_peer_endpoint=" $4
    print "wg_peer_latest_handshake=" $6
    print "wg_peer_transfer_rx=" $7
    print "wg_peer_transfer_tx=" $8
  }
' || true

echo ---internal-vm-ports---
for port in $tcp_ports; do
  if timeout 2 bash -lc "</dev/tcp/${vm_ip}/${port}" >/dev/null 2>&1; then
    echo "internal:${port}:open"
  else
    echo "internal:${port}:closed"
  fi
done

if [[ "$skip_guest_config_check" != "1" ]]; then
  echo ---guest-stream-config---
  cd /opt/beagle
  PYTHONPATH=beagle-host/services:beagle-host/bin:beagle-host/providers python3 - "$vmid" <<'HOSTPY'
from service_registry import guest_exec_text
import sys

vmid = int(sys.argv[1])
script = r'''
set -euo pipefail
conf=/home/dennis/.config/beagle-stream-server/sunshine.conf
if [[ ! -f "$conf" ]]; then
  conf=/home/dennis/.config/beagle-stream-server/beagle-stream-server.conf
fi
grep -E '^(encoder|sw_preset|sw_tune|capture|minimum_fps_target|max_bitrate|hevc_mode|av1_mode|port)\s*=' "$conf" || true
systemctl is-active beagle-stream-server.service 2>/dev/null | sed 's/^/service=/' || true
ps -eo ni,args | grep -E '[s]unshine|[b]eagle-stream-server' | head -n 1 | sed -E 's/^ *([^ ]+).*/nice=\1/' || true
'''
exit_code, stdout, stderr = guest_exec_text(vmid, script)
print(stdout, end="")
if stderr:
    print(stderr, end="", file=sys.stderr)
raise SystemExit(exit_code)
HOSTPY
fi
HOSTSCRIPT
)

host_output="$(ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no "$HOST_SSH" bash -s -- "$VM_IP" "$WG_IFACE" "$VMID" "$SKIP_GUEST_CONFIG_CHECK" "$WG_REQUIRED_ALLOWED_IP" $STREAM_TCP_PORTS <<<"$host_script")"
printf '%s\n' "$host_output"

grep -q 'legacy_public_dnat=absent' <<<"$host_output" || record_fail "legacy public BeagleStream DNAT table is present"
grep -q 'hook prerouting priority dstnat - 10' <<<"$host_output" || record_fail "public guard hook is missing"
grep -q 'tcp dport { 49995, 50000, 50001, 50021 } drop' <<<"$host_output" || record_fail "public TCP guard is missing"
grep -q 'udp dport { 50009, 50010, 50011, 50012, 50013, 50014, 50015 } drop' <<<"$host_output" || record_fail "public UDP guard is missing"
grep -q "^${WG_IFACE}[[:space:]]" <<<"$host_output" || record_fail "host WireGuard interface ${WG_IFACE} is missing"

if [[ "$REQUIRE_WG_HANDSHAKE" == "1" ]]; then
  wg_latest_handshake="$(awk -F= '/^wg_peer_latest_handshake=/{print $2; exit}' <<<"$host_output")"
  wg_endpoint="$(awk -F= '/^wg_peer_endpoint=/{print $2; exit}' <<<"$host_output")"
  grep -q "^wg_peer_allowed_ips=${WG_REQUIRED_ALLOWED_IP}$" <<<"$host_output" || record_fail "WireGuard peer ${WG_REQUIRED_ALLOWED_IP} is missing"
  if [[ ! "$wg_latest_handshake" =~ ^[0-9]+$ || "$wg_latest_handshake" -le 0 ]]; then
    record_fail "WireGuard peer ${WG_REQUIRED_ALLOWED_IP} has no latest handshake"
  fi
  if [[ -z "$wg_endpoint" || "$wg_endpoint" == "(none)" ]]; then
    record_fail "WireGuard peer ${WG_REQUIRED_ALLOWED_IP} has no endpoint"
  fi
fi

for port in $STREAM_TCP_PORTS; do
  grep -q "internal:${port}:open" <<<"$host_output" || record_fail "internal VM tcp ${VM_IP}:${port} is not reachable from host"
done

if [[ "$SKIP_GUEST_CONFIG_CHECK" != "1" ]]; then
  grep -q '^encoder = software$' <<<"$host_output" || record_fail "guest stream encoder is not software"
  grep -q '^sw_preset = ultrafast$' <<<"$host_output" || record_fail "guest stream sw_preset is not ultrafast"
  grep -q '^sw_tune = zerolatency$' <<<"$host_output" || record_fail "guest stream sw_tune is not zerolatency"
  grep -q '^capture = kms$' <<<"$host_output" || record_fail "guest stream capture is not kms"
  grep -q '^hevc_mode = 0$' <<<"$host_output" || record_fail "guest stream hevc_mode is not disabled"
  grep -q '^av1_mode = 0$' <<<"$host_output" || record_fail "guest stream av1_mode is not disabled"
  grep -q '^minimum_fps_target = 60$' <<<"$host_output" || record_fail "guest stream minimum_fps_target is not 60"
  grep -q '^max_bitrate = 35000$' <<<"$host_output" || record_fail "guest stream max_bitrate is not 35000"
  grep -q '^service=active$' <<<"$host_output" || record_fail "guest stream service is not active"
  grep -q '^nice=-10$' <<<"$host_output" || record_fail "guest stream process nice is not -10"
fi

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