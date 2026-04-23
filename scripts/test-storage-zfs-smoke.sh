#!/usr/bin/env bash
set -euo pipefail

VM_ID="${BEAGLE_STORAGE_ZFS_SMOKE_VMID:-993}"
VM_NAME="beagle-zfs-smoke-${VM_ID}"
POOL_NAME="${BEAGLE_STORAGE_ZFS_POOL:-beaglezfstest}"
VOL_NAME="vm-${VM_ID}-disk0"
CLONE_NAME="${VOL_NAME}-clone"
SNAP_NAME="preclone"
TMP_DIR="$(mktemp -d)"
POOL_FILE="${TMP_DIR}/${POOL_NAME}.img"
XML_PATH="${TMP_DIR}/${VM_NAME}.xml"
LOOP_DEV=""

cleanup() {
  set +e
  virsh --connect qemu:///system destroy "$VM_NAME" >/dev/null 2>&1 || true
  virsh --connect qemu:///system undefine "$VM_NAME" --snapshots-metadata >/dev/null 2>&1 || true
  zfs destroy -r "${POOL_NAME}/${CLONE_NAME}" >/dev/null 2>&1 || true
  zfs destroy -r "${POOL_NAME}/${VOL_NAME}@${SNAP_NAME}" >/dev/null 2>&1 || true
  zfs destroy -r "${POOL_NAME}/${VOL_NAME}" >/dev/null 2>&1 || true
  zpool destroy "$POOL_NAME" >/dev/null 2>&1 || true
  if [[ -n "$LOOP_DEV" ]]; then
    losetup -d "$LOOP_DEV" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

require_cmd() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "[FAIL] required command not found: $name" >&2
    exit 1
  fi
}

require_cmd virsh
require_cmd zpool
require_cmd zfs
require_cmd losetup
require_cmd truncate

virsh --connect qemu:///system list --all >/dev/null

if virsh --connect qemu:///system dominfo "$VM_NAME" >/dev/null 2>&1; then
  virsh --connect qemu:///system destroy "$VM_NAME" >/dev/null 2>&1 || true
  virsh --connect qemu:///system undefine "$VM_NAME" --snapshots-metadata >/dev/null 2>&1 || true
fi
if zpool list "$POOL_NAME" >/dev/null 2>&1; then
  zpool destroy "$POOL_NAME" >/dev/null 2>&1 || true
fi

truncate -s 6G "$POOL_FILE"
LOOP_DEV="$(losetup --find --show "$POOL_FILE")"
zpool create "$POOL_NAME" "$LOOP_DEV" >/dev/null
zfs create -V 2G "${POOL_NAME}/${VOL_NAME}" >/dev/null

for _ in $(seq 1 20); do
  if [[ -b "/dev/zvol/${POOL_NAME}/${VOL_NAME}" ]]; then
    break
  fi
  sleep 1
done

if [[ ! -b "/dev/zvol/${POOL_NAME}/${VOL_NAME}" ]]; then
  echo "[FAIL] zvol block device missing: /dev/zvol/${POOL_NAME}/${VOL_NAME}" >&2
  exit 1
fi

cat > "$XML_PATH" <<EOF
<domain type='kvm'>
  <name>${VM_NAME}</name>
  <memory unit='MiB'>512</memory>
  <vcpu>1</vcpu>
  <os>
    <type arch='x86_64' machine='pc-q35-7.2'>hvm</type>
    <boot dev='hd'/>
  </os>
  <features>
    <acpi/>
    <apic/>
  </features>
  <cpu mode='host-passthrough'/>
  <devices>
    <disk type='block' device='disk'>
      <driver name='qemu' type='raw'/>
      <source dev='/dev/zvol/${POOL_NAME}/${VOL_NAME}'/>
      <target dev='vda' bus='virtio'/>
    </disk>
    <graphics type='vnc' autoport='yes' listen='127.0.0.1'/>
    <console type='pty'/>
    <serial type='pty'/>
  </devices>
</domain>
EOF

virsh --connect qemu:///system define "$XML_PATH" >/dev/null
virsh --connect qemu:///system start "$VM_NAME" >/dev/null
STATE="$(virsh --connect qemu:///system domstate "$VM_NAME" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
if [[ "$STATE" != "running" ]]; then
  echo "[FAIL] ZFS backend VM did not start (state=$STATE)" >&2
  exit 1
fi
echo "[PASS] zfs backend VM created and started"

virsh --connect qemu:///system destroy "$VM_NAME" >/dev/null
zfs snapshot "${POOL_NAME}/${VOL_NAME}@${SNAP_NAME}"
zfs clone "${POOL_NAME}/${VOL_NAME}@${SNAP_NAME}" "${POOL_NAME}/${CLONE_NAME}"

if ! zfs list "${POOL_NAME}/${VOL_NAME}@${SNAP_NAME}" >/dev/null 2>&1; then
  echo "[FAIL] zfs snapshot missing" >&2
  exit 1
fi
if ! zfs list "${POOL_NAME}/${CLONE_NAME}" >/dev/null 2>&1; then
  echo "[FAIL] zfs clone missing" >&2
  exit 1
fi

echo "[PASS] zfs snapshot and clone created"
echo "STORAGE_ZFS_SMOKE=PASS"