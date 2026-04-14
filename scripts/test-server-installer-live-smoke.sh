#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ISO_PATH="${BEAGLE_SERVER_INSTALLER_ISO:-$ROOT_DIR/dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso}"
VM_NAME="${BEAGLE_LIVE_SMOKE_VM_NAME:-beagle-live-smoke}"
DISK_PATH="${BEAGLE_LIVE_SMOKE_DISK_PATH:-/var/lib/libvirt/images/${VM_NAME}.qcow2}"
DISK_SIZE_GB="${BEAGLE_LIVE_SMOKE_DISK_GB:-20}"
MEMORY_MB="${BEAGLE_LIVE_SMOKE_MEMORY_MB:-2048}"
VCPUS="${BEAGLE_LIVE_SMOKE_VCPUS:-2}"
NETWORK_NAME="${BEAGLE_LIVE_SMOKE_NETWORK:-default}"
ISO_STAGING_PATH="${BEAGLE_LIVE_SMOKE_ISO_STAGING:-/tmp/${VM_NAME}.iso}"
WAIT_VM_SECONDS="${BEAGLE_LIVE_SMOKE_WAIT_VM_SECONDS:-45}"
WAIT_DHCP_SECONDS="${BEAGLE_LIVE_SMOKE_WAIT_DHCP_SECONDS:-120}"
WAIT_HEALTH_SECONDS="${BEAGLE_LIVE_SMOKE_WAIT_HEALTH_SECONDS:-240}"
REQUIRE_HEALTH="${BEAGLE_LIVE_SMOKE_REQUIRE_HEALTH:-0}"
KEEP_VM="${BEAGLE_LIVE_SMOKE_KEEP_VM:-0}"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[ERROR] Missing required command: $cmd" >&2
    exit 1
  fi
}

ensure_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi
  exec sudo \
    BEAGLE_SERVER_INSTALLER_ISO="$ISO_PATH" \
    BEAGLE_LIVE_SMOKE_VM_NAME="$VM_NAME" \
    BEAGLE_LIVE_SMOKE_DISK_PATH="$DISK_PATH" \
    BEAGLE_LIVE_SMOKE_DISK_GB="$DISK_SIZE_GB" \
    BEAGLE_LIVE_SMOKE_MEMORY_MB="$MEMORY_MB" \
    BEAGLE_LIVE_SMOKE_VCPUS="$VCPUS" \
    BEAGLE_LIVE_SMOKE_NETWORK="$NETWORK_NAME" \
    BEAGLE_LIVE_SMOKE_ISO_STAGING="$ISO_STAGING_PATH" \
    BEAGLE_LIVE_SMOKE_WAIT_VM_SECONDS="$WAIT_VM_SECONDS" \
    BEAGLE_LIVE_SMOKE_WAIT_DHCP_SECONDS="$WAIT_DHCP_SECONDS" \
    BEAGLE_LIVE_SMOKE_WAIT_HEALTH_SECONDS="$WAIT_HEALTH_SECONDS" \
    BEAGLE_LIVE_SMOKE_REQUIRE_HEALTH="$REQUIRE_HEALTH" \
    BEAGLE_LIVE_SMOKE_KEEP_VM="$KEEP_VM" \
    "$0"
}

cleanup() {
  if [[ "$KEEP_VM" == "1" ]]; then
    return 0
  fi
  virsh --connect qemu:///system destroy "$VM_NAME" >/dev/null 2>&1 || true
  virsh --connect qemu:///system undefine "$VM_NAME" --remove-all-storage >/dev/null 2>&1 || true
  rm -f "$ISO_STAGING_PATH" >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_for_vm_running() {
  local deadline state
  deadline=$((SECONDS + WAIT_VM_SECONDS))
  while (( SECONDS < deadline )); do
    state="$(virsh --connect qemu:///system domstate "$VM_NAME" 2>/dev/null | tr -d '\r' || true)"
    if [[ "$state" == "running" ]]; then
      return 0
    fi
    sleep 2
  done
  return 1
}

vm_mac_address() {
  virsh --connect qemu:///system domiflist "$VM_NAME" \
    | awk '/network/ {print $5; exit}'
}

wait_for_vm_ip() {
  local mac deadline ip
  mac="$1"
  deadline=$((SECONDS + WAIT_DHCP_SECONDS))
  while (( SECONDS < deadline )); do
    ip="$(virsh --connect qemu:///system net-dhcp-leases "$NETWORK_NAME" \
      | awk -v m="$mac" 'tolower($0) ~ tolower(m) {split($5,a,"/"); print a[1]; exit}')"
    if [[ -n "$ip" ]]; then
      printf '%s\n' "$ip"
      return 0
    fi
    sleep 3
  done
  return 1
}

wait_for_health() {
  local ip deadline payload
  ip="$1"
  deadline=$((SECONDS + WAIT_HEALTH_SECONDS))
  while (( SECONDS < deadline )); do
    payload="$(curl -k -sS --max-time 5 "https://${ip}/beagle-api/api/v1/health" || true)"
    if [[ "$payload" == *'"ok": true'* ]]; then
      return 0
    fi
    sleep 5
  done
  return 1
}

require_cmd virsh
require_cmd virt-install
require_cmd curl
require_cmd awk
require_cmd cp

if [[ ! -f "$ISO_PATH" ]]; then
  echo "[ERROR] ISO not found: $ISO_PATH" >&2
  exit 1
fi

ensure_root

echo "[INFO] Staging ISO: $ISO_PATH -> $ISO_STAGING_PATH"
cp "$ISO_PATH" "$ISO_STAGING_PATH"
chmod 0644 "$ISO_STAGING_PATH"

virsh --connect qemu:///system destroy "$VM_NAME" >/dev/null 2>&1 || true
virsh --connect qemu:///system undefine "$VM_NAME" --remove-all-storage >/dev/null 2>&1 || true
rm -f "$DISK_PATH" >/dev/null 2>&1 || true

echo "[INFO] Creating VM: $VM_NAME"
virt-install \
  --connect qemu:///system \
  --name "$VM_NAME" \
  --memory "$MEMORY_MB" \
  --vcpus "$VCPUS" \
  --cdrom "$ISO_STAGING_PATH" \
  --disk "path=$DISK_PATH,size=$DISK_SIZE_GB,format=qcow2" \
  --network "network=$NETWORK_NAME" \
  --nographics \
  --boot cdrom \
  --osinfo detect=on,require=off \
  --noautoconsole >/dev/null

if ! wait_for_vm_running; then
  echo "[ERROR] VM did not reach running state within ${WAIT_VM_SECONDS}s" >&2
  exit 1
fi

MAC="$(vm_mac_address)"
if [[ -z "$MAC" ]]; then
  echo "[ERROR] Could not determine VM MAC address" >&2
  exit 1
fi

echo "[INFO] VM running, MAC=$MAC"

IP="$(wait_for_vm_ip "$MAC" || true)"
if [[ -z "$IP" ]]; then
  echo "[ERROR] No DHCP lease observed within ${WAIT_DHCP_SECONDS}s" >&2
  exit 1
fi

echo "[INFO] DHCP lease acquired: $IP"

if [[ "$REQUIRE_HEALTH" == "1" ]]; then
  echo "[INFO] Waiting for API health readiness"
  if ! wait_for_health "$IP"; then
    echo "[ERROR] API health endpoint did not become ready within ${WAIT_HEALTH_SECONDS}s" >&2
    exit 1
  fi
  echo "[INFO] API health is ready"
fi

echo "[OK] Live-server smoke test passed"
echo "[OK] VM=$VM_NAME IP=$IP REQUIRE_HEALTH=$REQUIRE_HEALTH KEEP_VM=$KEEP_VM"
