#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

SCRIPT="$ROOT_DIR/scripts/setup-pxe-server.sh"
ISO_DIR="$TMP_DIR/dist"
PXE_ROOT="$TMP_DIR/root"
mkdir -p "$ISO_DIR" "$PXE_ROOT"

FAKE_ISO="$ISO_DIR/beagle-os-server-installer.iso"
EFI_BIN="$TMP_DIR/grubnetx64.efi"
PXE_BIN="$TMP_DIR/lpxelinux.0"
LDLINUX="$TMP_DIR/ldlinux.c32"

printf 'EFI' >"$EFI_BIN"
printf 'PXE' >"$PXE_BIN"
printf 'LDLINUX' >"$LDLINUX"

build_fake_iso() {
  local stage="$TMP_DIR/iso-stage"
  mkdir -p "$stage/live"
  printf 'kernel-image\n' >"$stage/live/vmlinuz"
  printf 'initrd-image\n' >"$stage/live/initrd"
  xorriso -as mkisofs -o "$FAKE_ISO" "$stage" >/dev/null 2>&1
}

assert_file() {
  local path="$1"
  [[ -f "$path" ]] || {
    echo "missing file: $path" >&2
    exit 1
  }
}

assert_contains() {
  local path="$1"
  local pattern="$2"
  grep -Fq "$pattern" "$path" || {
    echo "pattern not found in $path: $pattern" >&2
    exit 1
  }
}

build_fake_iso

BEAGLE_PXE_ROOT_PREFIX="$PXE_ROOT" \
BEAGLE_PXE_ISO_PATH="$FAKE_ISO" \
BEAGLE_PXE_GRUB_EFI="$EFI_BIN" \
BEAGLE_PXE_PXELINUX_BIN="$PXE_BIN" \
BEAGLE_PXE_LDLINUX_C32="$LDLINUX" \
BEAGLE_PXE_DHCP_RANGE="10.20.30.50,10.20.30.99,255.255.255.0,12h" \
BEAGLE_PXE_SEED_URL="https://srv1.beagle-os.com/seeds/rack-a.yaml" \
BEAGLE_PXE_DRY_RUN=1 \
bash "$SCRIPT" >/dev/null

assert_file "$PXE_ROOT/etc/dnsmasq.d/beagle-pxe.conf"
assert_file "$PXE_ROOT/var/lib/beagle/pxe/tftp/grubnetx64.efi"
assert_file "$PXE_ROOT/var/lib/beagle/pxe/tftp/lpxelinux.0"
assert_file "$PXE_ROOT/var/lib/beagle/pxe/tftp/ldlinux.c32"
assert_file "$PXE_ROOT/var/lib/beagle/pxe/tftp/beagle-installer/vmlinuz"
assert_file "$PXE_ROOT/var/lib/beagle/pxe/tftp/beagle-installer/initrd"
assert_file "$PXE_ROOT/var/lib/beagle/pxe/tftp/beagle-installer/grub/grub.cfg"
assert_file "$PXE_ROOT/var/lib/beagle/pxe/tftp/pxelinux.cfg/default"

assert_contains "$PXE_ROOT/etc/dnsmasq.d/beagle-pxe.conf" "enable-tftp"
assert_contains "$PXE_ROOT/etc/dnsmasq.d/beagle-pxe.conf" "dhcp-range=10.20.30.50,10.20.30.99,255.255.255.0,12h"
assert_contains "$PXE_ROOT/etc/dnsmasq.d/beagle-pxe.conf" "grubnetx64.efi"
assert_contains "$PXE_ROOT/etc/dnsmasq.d/beagle-pxe.conf" "seed_url=https://srv1.beagle-os.com/seeds/rack-a.yaml"
assert_contains "$PXE_ROOT/var/lib/beagle/pxe/tftp/beagle-installer/grub/grub.cfg" "beagle.seed_url=https://srv1.beagle-os.com/seeds/rack-a.yaml"
assert_contains "$PXE_ROOT/var/lib/beagle/pxe/tftp/pxelinux.cfg/default" "beagle-installer/vmlinuz"
assert_contains "$PXE_ROOT/var/lib/beagle/pxe/tftp/pxelinux.cfg/default" "beagle.seed_url=https://srv1.beagle-os.com/seeds/rack-a.yaml"

cmp "$PXE_ROOT/var/lib/beagle/pxe/tftp/beagle-installer/vmlinuz" "$TMP_DIR/iso-stage/live/vmlinuz"
cmp "$PXE_ROOT/var/lib/beagle/pxe/tftp/beagle-installer/initrd" "$TMP_DIR/iso-stage/live/initrd"

echo "PXE_BOOT_TEST=PASS"
