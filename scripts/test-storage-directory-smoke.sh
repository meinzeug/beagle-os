#!/usr/bin/env bash
set -euo pipefail

DISK_DIR="${BEAGLE_STORAGE_DIRECTORY_PATH:-/var/lib/libvirt/images}"
VM_ID="${BEAGLE_STORAGE_SMOKE_VMID:-992}"
VM_NAME="beagle-storage-smoke-${VM_ID}"
SNAP_NAME="pre-restore-$(date +%s)"
TMP_DIR="$(mktemp -d)"
DISK_PATH="${DISK_DIR}/${VM_NAME}.qcow2"
XML_PATH="${TMP_DIR}/${VM_NAME}.xml"

cleanup() {
  set +e
  virsh --connect qemu:///system destroy "$VM_NAME" >/dev/null 2>&1 || true
  virsh --connect qemu:///system undefine "$VM_NAME" --snapshots-metadata >/dev/null 2>&1 || true
  rm -f "$DISK_PATH"
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
require_cmd qemu-img

virsh --connect qemu:///system list --all >/dev/null

if virsh --connect qemu:///system dominfo "$VM_NAME" >/dev/null 2>&1; then
  echo "[INFO] pre-existing domain found, removing: $VM_NAME"
  virsh --connect qemu:///system destroy "$VM_NAME" >/dev/null 2>&1 || true
  virsh --connect qemu:///system undefine "$VM_NAME" --snapshots-metadata >/dev/null 2>&1 || true
fi

mkdir -p "$DISK_DIR"
qemu-img create -f qcow2 "$DISK_PATH" 4G >/dev/null

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
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='${DISK_PATH}'/>
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
  echo "[FAIL] VM did not start (state=$STATE)" >&2
  exit 1
fi
echo "[PASS] directory backend VM created and started"

virsh --connect qemu:///system destroy "$VM_NAME" >/dev/null
qemu-img snapshot -c "$SNAP_NAME" "$DISK_PATH" >/dev/null

if ! qemu-img snapshot -l "$DISK_PATH" | awk '{print $2}' | grep -Fx "$SNAP_NAME" >/dev/null; then
  echo "[FAIL] snapshot was not created: $SNAP_NAME" >&2
  exit 1
fi
echo "[PASS] snapshot created"

qemu-img snapshot -a "$SNAP_NAME" "$DISK_PATH" >/dev/null
virsh --connect qemu:///system start "$VM_NAME" >/dev/null
STATE_AFTER="$(virsh --connect qemu:///system domstate "$VM_NAME" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
if [[ "$STATE_AFTER" != "running" ]]; then
  echo "[FAIL] snapshot restore did not keep VM running (state=$STATE_AFTER)" >&2
  exit 1
fi

echo "[PASS] snapshot restored"
echo "STORAGE_DIRECTORY_SMOKE=PASS"