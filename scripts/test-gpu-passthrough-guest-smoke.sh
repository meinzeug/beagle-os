#!/usr/bin/env bash
set -euo pipefail

SUDO_BIN="${BEAGLE_SMOKE_SUDO:-sudo}"
DOMAIN_NAME="${BEAGLE_GPU_SMOKE_DOMAIN:-beagle-gpu-smoke}"
GPU_PCI="${BEAGLE_GPU_PCI:-0000:01:00.0}"
AUDIO_PCI="${BEAGLE_GPU_AUDIO_PCI:-0000:01:00.1}"
KERNEL_PATH="${BEAGLE_GPU_SMOKE_KERNEL:-/var/lib/libvirt/images/test-vmlinuz}"
INITRD_PATH="${BEAGLE_GPU_SMOKE_INITRD:-/var/lib/libvirt/images/tiny-initrd.cpio.gz}"
WORK_DIR="${BEAGLE_GPU_SMOKE_WORKDIR:-/tmp}"
TIMEOUT_SECONDS="${BEAGLE_GPU_SMOKE_TIMEOUT_SECONDS:-45}"

XML_PATH="${WORK_DIR%/}/${DOMAIN_NAME}.xml"
INITRD_BUILD_DIR="${WORK_DIR%/}/${DOMAIN_NAME}.initrd.d"
INITRD_IMAGE_PATH="${WORK_DIR%/}/${DOMAIN_NAME}.initrd.img"
LOG_PATH="${WORK_DIR%/}/${DOMAIN_NAME}.log"

cleanup() {
  ${SUDO_BIN} virsh destroy "${DOMAIN_NAME}" >/dev/null 2>&1 || true
  ${SUDO_BIN} rm -rf "${XML_PATH}" "${LOG_PATH}" "${INITRD_BUILD_DIR}" "${INITRD_IMAGE_PATH}"
}
trap cleanup EXIT

require_file() {
  local path="$1"
  if ! ${SUDO_BIN} test -f "${path}"; then
    echo "missing required file: ${path}" >&2
    exit 2
  fi
}

pci_xml_address() {
  local pci="$1"
  local domain="${pci%%:*}"
  local rest="${pci#*:}"
  local bus="${rest%%:*}"
  local slot_func="${rest#*:}"
  local slot="${slot_func%%.*}"
  local func="${slot_func#*.}"
  cat <<EOF
      <address domain='0x${domain}' bus='0x${bus}' slot='0x${slot}' function='0x${func}'/>
EOF
}

require_file "${KERNEL_PATH}"
require_file "${INITRD_PATH}"

${SUDO_BIN} rm -rf "${INITRD_BUILD_DIR}" "${INITRD_IMAGE_PATH}"
${SUDO_BIN} mkdir -p "${INITRD_BUILD_DIR}"
${SUDO_BIN} bash -lc "cd '${INITRD_BUILD_DIR}' && gzip -dc '${INITRD_PATH}' | cpio -idmu >/dev/null 2>&1"
${SUDO_BIN} mkdir -p \
  "${INITRD_BUILD_DIR}/bin" \
  "${INITRD_BUILD_DIR}/lib64" \
  "${INITRD_BUILD_DIR}/lib/x86_64-linux-gnu"
${SUDO_BIN} cp /usr/bin/busybox "${INITRD_BUILD_DIR}/bin/busybox"
${SUDO_BIN} ln -sf busybox "${INITRD_BUILD_DIR}/bin/sh"
${SUDO_BIN} cp -L /lib64/ld-linux-x86-64.so.2 "${INITRD_BUILD_DIR}/lib64/ld-linux-x86-64.so.2"
${SUDO_BIN} cp -L /lib/x86_64-linux-gnu/libc.so.6 "${INITRD_BUILD_DIR}/lib/x86_64-linux-gnu/libc.so.6"
${SUDO_BIN} cp -L /lib/x86_64-linux-gnu/libresolv.so.2 "${INITRD_BUILD_DIR}/lib/x86_64-linux-gnu/libresolv.so.2"
${SUDO_BIN} bash -lc "cat > '${INITRD_BUILD_DIR}/init' <<'EOF'
#!/bin/sh
/bin/busybox mount -t proc none /proc
/bin/busybox mount -t sysfs none /sys
found_gpu=0
found_audio=0
for dev in /sys/bus/pci/devices/*; do
  [ -d \"\$dev\" ] || continue
  slot=\$(/bin/busybox basename \"\$dev\")
  vendor=\$(/bin/busybox cat \"\$dev/vendor\" 2>/dev/null || true)
  device=\$(/bin/busybox cat \"\$dev/device\" 2>/dev/null || true)
  class=\$(/bin/busybox cat \"\$dev/class\" 2>/dev/null || true)
  /bin/busybox echo \"PCI_SLOT=\$slot VENDOR=\$vendor DEVICE=\$device CLASS=\$class\"
  if [ \"\$vendor\" = \"0x10de\" ] && [ \"\$device\" = \"0x1b80\" ]; then
    found_gpu=1
    /bin/busybox echo 'BEAGLE_GPU_GUEST_NVIDIA_GTX1080=1'
  fi
  if [ \"\$vendor\" = \"0x10de\" ] && [ \"\$device\" = \"0x10f0\" ]; then
    found_audio=1
    /bin/busybox echo 'BEAGLE_GPU_GUEST_NVIDIA_AUDIO=1'
  fi
done
if [ \"\$found_gpu\" != \"1\" ]; then
  /bin/busybox echo 'BEAGLE_GPU_GUEST_NVIDIA_GTX1080=0'
fi
if [ \"\$found_audio\" != \"1\" ]; then
  /bin/busybox echo 'BEAGLE_GPU_GUEST_NVIDIA_AUDIO=0'
fi
/bin/busybox sleep 2
EOF"
${SUDO_BIN} chmod 0755 "${INITRD_BUILD_DIR}/init"
${SUDO_BIN} bash -lc "cd '${INITRD_BUILD_DIR}' && find . -print | cpio -o -H newc 2>/dev/null | gzip -c > '${INITRD_IMAGE_PATH}'"

${SUDO_BIN} bash -lc "cat > '${XML_PATH}' <<'EOF'
<domain type='kvm'>
  <name>${DOMAIN_NAME}</name>
  <memory unit='MiB'>1024</memory>
  <vcpu>1</vcpu>
  <os>
    <type arch='x86_64' machine='pc'>hvm</type>
    <kernel>${KERNEL_PATH}</kernel>
    <initrd>${INITRD_IMAGE_PATH}</initrd>
    <cmdline>console=tty0 console=ttyS0,115200n8</cmdline>
  </os>
  <features>
    <acpi/>
    <apic/>
  </features>
  <cpu mode='host-passthrough'/>
  <clock offset='utc'/>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>destroy</on_reboot>
  <on_crash>destroy</on_crash>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>
    <serial type='file'>
      <source path='${LOG_PATH}'/>
      <target port='0'/>
    </serial>
    <console type='file'>
      <source path='${LOG_PATH}'/>
      <target type='serial' port='0'/>
    </console>
    <memballoon model='none'/>
    <rng model='virtio'>
      <backend model='random'>/dev/urandom</backend>
    </rng>
    <hostdev mode='subsystem' type='pci' managed='yes'>
      <source>
$(pci_xml_address "${GPU_PCI}")
      </source>
    </hostdev>
    <hostdev mode='subsystem' type='pci' managed='yes'>
      <source>
$(pci_xml_address "${AUDIO_PCI}")
      </source>
    </hostdev>
  </devices>
</domain>
EOF"

${SUDO_BIN} virsh create "${XML_PATH}" >/dev/null

deadline=$(( $(date +%s) + TIMEOUT_SECONDS ))
while (( $(date +%s) < deadline )); do
  if ${SUDO_BIN} test -f "${LOG_PATH}"; then
    if ${SUDO_BIN} grep -q "BEAGLE_GPU_GUEST_NVIDIA_GTX1080=1" "${LOG_PATH}" \
      && ${SUDO_BIN} grep -q "BEAGLE_GPU_GUEST_NVIDIA_AUDIO=1" "${LOG_PATH}"; then
      echo "OK guest detected NVIDIA GTX 1080 and audio function"
      ${SUDO_BIN} grep -E "PCI_SLOT=|BEAGLE_GPU_GUEST_" "${LOG_PATH}" || true
      exit 0
    fi
  fi
  sleep 1
done

echo "GPU passthrough guest smoke timed out after ${TIMEOUT_SECONDS}s" >&2
if ${SUDO_BIN} test -f "${LOG_PATH}"; then
  ${SUDO_BIN} tail -n 80 "${LOG_PATH}" >&2 || true
fi
exit 1
