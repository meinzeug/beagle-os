#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/disk_guardrails.sh"
ISO_PATH="${BEAGLE_SERVER_INSTALLER_ISO:-$ROOT_DIR/dist/beagle-os-server-installer/beagle-os-server-installer-amd64.iso}"
VM_NAME="${BEAGLE_LIVE_SMOKE_VM_NAME:-beagle-live-smoke}"
DISK_PATH="${BEAGLE_LIVE_SMOKE_DISK_PATH:-/var/lib/libvirt/images/${VM_NAME}.qcow2}"
DISK_SIZE_GB="${BEAGLE_LIVE_SMOKE_DISK_GB:-20}"
MEMORY_MB="${BEAGLE_LIVE_SMOKE_MEMORY_MB:-2048}"
VCPUS="${BEAGLE_LIVE_SMOKE_VCPUS:-2}"
NETWORK_NAME="${BEAGLE_LIVE_SMOKE_NETWORK:-default}"
ISO_STAGING_PATH="${BEAGLE_LIVE_SMOKE_ISO_STAGING:-/tmp/${VM_NAME}.iso}"
GRAPHICS_MODE="${BEAGLE_LIVE_SMOKE_GRAPHICS:-vnc,listen=127.0.0.1}"
WAIT_VM_SECONDS="${BEAGLE_LIVE_SMOKE_WAIT_VM_SECONDS:-45}"
WAIT_DHCP_SECONDS="${BEAGLE_LIVE_SMOKE_WAIT_DHCP_SECONDS:-120}"
WAIT_HEALTH_SECONDS="${BEAGLE_LIVE_SMOKE_WAIT_HEALTH_SECONDS:-240}"
REQUIRE_HEALTH="${BEAGLE_LIVE_SMOKE_REQUIRE_HEALTH:-0}"
REQUIRE_INSTALLER_BANNER="${BEAGLE_LIVE_SMOKE_REQUIRE_INSTALLER_BANNER:-0}"
REQUIRE_INSTALLER_SCREENSHOT="${BEAGLE_LIVE_SMOKE_REQUIRE_INSTALLER_SCREENSHOT:-1}"
WAIT_BANNER_SECONDS="${BEAGLE_LIVE_SMOKE_WAIT_BANNER_SECONDS:-120}"
WAIT_SCREENSHOT_SECONDS="${BEAGLE_LIVE_SMOKE_WAIT_SCREENSHOT_SECONDS:-120}"
SKIP_DHCP="${BEAGLE_LIVE_SMOKE_SKIP_DHCP:-1}"
KEEP_VM="${BEAGLE_LIVE_SMOKE_KEEP_VM:-0}"
LIVE_SMOKE_MIN_DISK_FREE_GIB="${BEAGLE_LIVE_SMOKE_MIN_DISK_FREE_GIB:-$((DISK_SIZE_GB + 4))}"
LIVE_SMOKE_MIN_STAGE_FREE_GIB="${BEAGLE_LIVE_SMOKE_MIN_STAGE_FREE_GIB:-4}"
SCREENSHOT_PATH="${BEAGLE_LIVE_SMOKE_SCREENSHOT_PATH:-/tmp/${VM_NAME}-installer.ppm}"

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
    BEAGLE_LIVE_SMOKE_GRAPHICS="$GRAPHICS_MODE" \
    BEAGLE_LIVE_SMOKE_WAIT_VM_SECONDS="$WAIT_VM_SECONDS" \
    BEAGLE_LIVE_SMOKE_WAIT_DHCP_SECONDS="$WAIT_DHCP_SECONDS" \
    BEAGLE_LIVE_SMOKE_WAIT_HEALTH_SECONDS="$WAIT_HEALTH_SECONDS" \
    BEAGLE_LIVE_SMOKE_REQUIRE_HEALTH="$REQUIRE_HEALTH" \
    BEAGLE_LIVE_SMOKE_REQUIRE_INSTALLER_BANNER="$REQUIRE_INSTALLER_BANNER" \
    BEAGLE_LIVE_SMOKE_REQUIRE_INSTALLER_SCREENSHOT="$REQUIRE_INSTALLER_SCREENSHOT" \
    BEAGLE_LIVE_SMOKE_WAIT_BANNER_SECONDS="$WAIT_BANNER_SECONDS" \
    BEAGLE_LIVE_SMOKE_WAIT_SCREENSHOT_SECONDS="$WAIT_SCREENSHOT_SECONDS" \
    BEAGLE_LIVE_SMOKE_SKIP_DHCP="$SKIP_DHCP" \
    BEAGLE_LIVE_SMOKE_SCREENSHOT_PATH="$SCREENSHOT_PATH" \
    BEAGLE_LIVE_SMOKE_KEEP_VM="$KEEP_VM" \
    BEAGLE_LIVE_SMOKE_MIN_DISK_FREE_GIB="$LIVE_SMOKE_MIN_DISK_FREE_GIB" \
    BEAGLE_LIVE_SMOKE_MIN_STAGE_FREE_GIB="$LIVE_SMOKE_MIN_STAGE_FREE_GIB" \
    "$0"
}

cleanup() {
  if [[ "$KEEP_VM" == "1" ]]; then
    return 0
  fi
  virsh --connect qemu:///system destroy "$VM_NAME" >/dev/null 2>&1 || true
  virsh --connect qemu:///system undefine "$VM_NAME" --remove-all-storage >/dev/null 2>&1 || true
  rm -f "$ISO_STAGING_PATH" >/dev/null 2>&1 || true
  rm -f "$SCREENSHOT_PATH" >/dev/null 2>&1 || true
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

qemu_log_path() {
  printf '/var/log/libvirt/qemu/%s.log\n' "$VM_NAME"
}

wait_for_installer_banner() {
  local log_file deadline
  log_file="$(qemu_log_path)"
  deadline=$((SECONDS + WAIT_BANNER_SECONDS))
  while (( SECONDS < deadline )); do
    if [[ -f "$log_file" ]] && grep -Eiq 'Beagle OS Server Installer|Server Installer|beagle-server-installer' "$log_file"; then
      return 0
    fi
    sleep 2
  done
  return 1
}

screenshot_has_non_uniform_pixels() {
  local image="$1"
  [[ -s "$image" ]] || return 1
  # virsh screenshot commonly writes PNG, regardless of extension; a non-trivial
  # file size is a robust indicator that the guest framebuffer is available.
  [[ "$(stat -c%s "$image" 2>/dev/null || echo 0)" -ge 4096 ]]
}

wait_for_installer_screen() {
  local deadline
  deadline=$((SECONDS + WAIT_SCREENSHOT_SECONDS))
  while (( SECONDS < deadline )); do
    virsh --connect qemu:///system screenshot "$VM_NAME" "$SCREENSHOT_PATH" >/dev/null 2>&1 || true
    if screenshot_has_non_uniform_pixels "$SCREENSHOT_PATH"; then
      return 0
    fi
    sleep 3
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

ensure_free_space_with_cleanup \
  "live smoke VM disk" \
  "$(dirname "$DISK_PATH")" \
  "$((LIVE_SMOKE_MIN_DISK_FREE_GIB * 1024 * 1024))" \
  "$ROOT_DIR" \
  "$ROOT_DIR/.build" \
  "$ROOT_DIR/dist/pve-thin-client-installer" \
  "$ROOT_DIR/dist/beagle-os" \
  "$ROOT_DIR/beagle-kiosk/dist"
ensure_free_space_with_cleanup \
  "live smoke ISO staging" \
  "$(dirname "$ISO_STAGING_PATH")" \
  "$((LIVE_SMOKE_MIN_STAGE_FREE_GIB * 1024 * 1024))" \
  "$ROOT_DIR" \
  "$ROOT_DIR/.build" \
  "$ROOT_DIR/dist/pve-thin-client-installer" \
  "$ROOT_DIR/dist/beagle-os" \
  "$ROOT_DIR/beagle-kiosk/dist"

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
  --graphics "$GRAPHICS_MODE" \
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

if [[ "$REQUIRE_INSTALLER_BANNER" == "1" ]]; then
  echo "[INFO] Waiting for installer banner in QEMU log"
  if ! wait_for_installer_banner; then
    echo "[ERROR] Installer banner not observed within ${WAIT_BANNER_SECONDS}s" >&2
    echo "[ERROR] Log path: $(qemu_log_path)" >&2
    exit 1
  fi
  echo "[INFO] Installer banner detected"
fi

if [[ "$REQUIRE_INSTALLER_SCREENSHOT" == "1" ]]; then
  if ! graphics_supports_screenshot; then
    echo "[ERROR] Installer screenshot check requires graphics mode, current: $GRAPHICS_MODE" >&2
    exit 1
  fi
  echo "[INFO] Waiting for non-empty installer screen capture"
  if ! wait_for_installer_screen; then
    echo "[ERROR] Installer screen not detected within ${WAIT_SCREENSHOT_SECONDS}s" >&2
    echo "[ERROR] Screenshot path: $SCREENSHOT_PATH" >&2
    exit 1
  fi
  echo "[INFO] Installer screen detected via screenshot"
fi

if [[ "$SKIP_DHCP" == "1" ]]; then
  echo "[OK] Live-server smoke test passed (DHCP/health skipped)"
  echo "[OK] VM=$VM_NAME REQUIRE_INSTALLER_BANNER=$REQUIRE_INSTALLER_BANNER SKIP_DHCP=$SKIP_DHCP KEEP_VM=$KEEP_VM"
  exit 0
fi

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
