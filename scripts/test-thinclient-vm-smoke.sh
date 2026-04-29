#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/disk_guardrails.sh"

VM_NAME="${BEAGLE_THINCLIENT_VM_NAME:-beagle-thinclient}"
CREATE_IF_MISSING="${BEAGLE_THINCLIENT_CREATE_IF_MISSING:-0}"
ISO_PATH="${BEAGLE_THINCLIENT_ISO:-}"
DISK_PATH="${BEAGLE_THINCLIENT_DISK_PATH:-/var/lib/libvirt/images/${VM_NAME}.qcow2}"
DISK_SIZE_GB="${BEAGLE_THINCLIENT_DISK_GB:-12}"
MEMORY_MB="${BEAGLE_THINCLIENT_MEMORY_MB:-4096}"
VCPUS="${BEAGLE_THINCLIENT_VCPUS:-4}"
NETWORK_NAME="${BEAGLE_THINCLIENT_NETWORK:-default}"
GRAPHICS_MODE="${BEAGLE_THINCLIENT_GRAPHICS:-spice,listen=127.0.0.1}"
WAIT_VM_SECONDS="${BEAGLE_THINCLIENT_WAIT_VM_SECONDS:-45}"
SCREENSHOT_PATH="${BEAGLE_THINCLIENT_SCREENSHOT_PATH:-/tmp/${VM_NAME}-smoke.ppm}"
REQUIRE_SCREENSHOT="${BEAGLE_THINCLIENT_REQUIRE_SCREENSHOT:-1}"
SCREENSHOT_MIN_BYTES="${BEAGLE_THINCLIENT_SCREENSHOT_MIN_BYTES:-2048}"
TAIL_LOG_LINES="${BEAGLE_THINCLIENT_LOG_LINES:-40}"
SMOKE_MIN_DISK_FREE_GIB="${BEAGLE_THINCLIENT_MIN_DISK_FREE_GIB:-$((DISK_SIZE_GB + 2))}"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[ERROR] Missing required command: $cmd" >&2
    exit 1
  fi
}

default_iso_path() {
  local candidate=""
  for candidate in \
    "$ROOT_DIR/dist/pve-thin-client-installer/pve-thin-client-installer.iso" \
    "$ROOT_DIR/dist/pve-thin-client-installer/pve-thin-client-installer-amd64.iso" \
    "$ROOT_DIR/dist/pve-thin-client-installer/beagle-os-installer.iso" \
    "$ROOT_DIR/dist/pve-thin-client-installer/beagle-os-installer-amd64.iso"
  do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

domain_exists() {
  virsh --connect qemu:///system dominfo "$VM_NAME" >/dev/null 2>&1
}

current_state() {
  virsh --connect qemu:///system domstate "$VM_NAME" 2>/dev/null | tr -d '\r' | tr '[:upper:]' '[:lower:]' | xargs echo -n
}

wait_for_vm_running() {
  local deadline state
  deadline=$((SECONDS + WAIT_VM_SECONDS))
  while (( SECONDS < deadline )); do
    state="$(current_state || true)"
    if [[ "$state" == "running" ]]; then
      return 0
    fi
    sleep 2
  done
  return 1
}

graphics_supports_screenshot() {
  case "$(printf '%s' "$GRAPHICS_MODE" | tr '[:upper:]' '[:lower:]')" in
    none|nographics)
      return 1
      ;;
    *)
      return 0
      ;;
  esac
}

screenshot_has_content() {
  local image="$1"
  [[ -s "$image" ]] || return 1
  [[ "$(stat -c%s "$image" 2>/dev/null || echo 0)" -ge "$SCREENSHOT_MIN_BYTES" ]]
}

qemu_log_path() {
  printf '/var/log/libvirt/qemu/%s.log\n' "$VM_NAME"
}

tail_qemu_log() {
  local log_path="$1"
  if [[ -r "$log_path" ]]; then
    tail -n "$TAIL_LOG_LINES" "$log_path"
    return 0
  fi
  if command -v sudo >/dev/null 2>&1 && sudo -n test -r "$log_path" 2>/dev/null; then
    sudo -n tail -n "$TAIL_LOG_LINES" "$log_path"
    return 0
  fi
  echo "[WARN] QEMU log not readable without elevated access: $log_path" >&2
  return 1
}

create_domain_if_missing() {
  local resolved_iso=""
  if domain_exists; then
    return 0
  fi
  if [[ "$CREATE_IF_MISSING" != "1" ]]; then
    echo "[ERROR] Thinclient VM $VM_NAME does not exist and auto-create is disabled." >&2
    exit 1
  fi

  require_cmd virt-install
  resolved_iso="$ISO_PATH"
  if [[ -z "$resolved_iso" ]]; then
    resolved_iso="$(default_iso_path || true)"
  fi
  if [[ -z "$resolved_iso" || ! -f "$resolved_iso" ]]; then
    echo "[ERROR] No thinclient ISO available for VM creation. Checked dist/pve-thin-client-installer/*.iso." >&2
    exit 1
  fi

  ensure_free_space_with_cleanup \
    "thinclient smoke VM disk" \
    "$(dirname "$DISK_PATH")" \
    "$((SMOKE_MIN_DISK_FREE_GIB * 1024 * 1024))" \
    "$ROOT_DIR" \
    "$ROOT_DIR/.build" \
    "$ROOT_DIR/dist/pve-thin-client-installer" \
    "$ROOT_DIR/dist/beagle-os" \
    "$ROOT_DIR/beagle-kiosk/dist"

  echo "[INFO] Creating thinclient VM $VM_NAME from $resolved_iso"
  virt-install \
    --connect qemu:///system \
    --name "$VM_NAME" \
    --memory "$MEMORY_MB" \
    --vcpus "$VCPUS" \
    --cdrom "$resolved_iso" \
    --disk "path=$DISK_PATH,size=$DISK_SIZE_GB,format=qcow2" \
    --network "network=$NETWORK_NAME" \
    --graphics "$GRAPHICS_MODE" \
    --boot cdrom \
    --osinfo detect=on,require=off \
    --noautoconsole >/dev/null
}

require_cmd virsh
require_cmd awk

create_domain_if_missing

state="$(current_state || true)"
if [[ "$state" == "shut off" || "$state" == "paused" || "$state" == "pmsuspended" ]]; then
  echo "[INFO] Starting thinclient VM: $VM_NAME"
  virsh --connect qemu:///system start "$VM_NAME" >/dev/null
elif [[ -z "$state" ]]; then
  echo "[ERROR] Could not determine current state for $VM_NAME" >&2
  exit 1
fi

if ! wait_for_vm_running; then
  echo "[ERROR] Thinclient VM did not reach running state within ${WAIT_VM_SECONDS}s" >&2
  exit 1
fi

DISPLAY_URI="$(virsh --connect qemu:///system domdisplay "$VM_NAME" 2>/dev/null | tr -d '\r' || true)"
LOG_PATH="$(qemu_log_path)"

if [[ "$REQUIRE_SCREENSHOT" == "1" ]]; then
  if ! graphics_supports_screenshot; then
    echo "[ERROR] Screenshot requested but graphics mode disables framebuffer access: $GRAPHICS_MODE" >&2
    exit 1
  fi
  rm -f "$SCREENSHOT_PATH"
  virsh --connect qemu:///system screenshot "$VM_NAME" "$SCREENSHOT_PATH" >/dev/null
  if ! screenshot_has_content "$SCREENSHOT_PATH"; then
    echo "[ERROR] Thinclient VM screenshot is missing or too small: $SCREENSHOT_PATH" >&2
    exit 1
  fi
fi

echo "[INFO] Thinclient VM state: $(current_state)"
if [[ -n "$DISPLAY_URI" ]]; then
  echo "[INFO] Thinclient display: $DISPLAY_URI"
fi
if [[ "$REQUIRE_SCREENSHOT" == "1" ]]; then
  echo "[INFO] Screenshot: $SCREENSHOT_PATH ($(stat -c%s "$SCREENSHOT_PATH" 2>/dev/null || echo 0) bytes)"
fi
tail_qemu_log "$LOG_PATH" >/dev/null || true

echo "[OK] Thinclient VM smoke passed"
echo "[OK] VM=$VM_NAME STATE=$(current_state) DISPLAY=${DISPLAY_URI:-n/a}"