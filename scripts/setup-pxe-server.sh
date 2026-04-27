#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PXE_ROOT_PREFIX="${BEAGLE_PXE_ROOT_PREFIX:-}"
PXE_CONFIG_DIR="${BEAGLE_PXE_CONFIG_DIR:-${PXE_ROOT_PREFIX}/etc/dnsmasq.d}"
PXE_STATE_DIR="${BEAGLE_PXE_STATE_DIR:-${PXE_ROOT_PREFIX}/var/lib/beagle/pxe}"
PXE_TFTP_ROOT="${BEAGLE_PXE_TFTP_ROOT:-$PXE_STATE_DIR/tftp}"
PXE_BOOT_DIR="$PXE_TFTP_ROOT/beagle-installer"
PXE_DIST_DIR="${BEAGLE_PXE_DIST_DIR:-$ROOT_DIR/dist/beagle-os-server-installer}"
PXE_ISO_PATH="${BEAGLE_PXE_ISO_PATH:-$PXE_DIST_DIR/beagle-os-server-installer.iso}"
PXE_PUBLIC_HOST="${BEAGLE_PXE_PUBLIC_HOST:-$(hostname -f 2>/dev/null || hostname)}"
PXE_INTERFACE="${BEAGLE_PXE_INTERFACE:-}"
PXE_DHCP_RANGE="${BEAGLE_PXE_DHCP_RANGE:-192.168.50.100,192.168.50.199,255.255.255.0,12h}"
PXE_SEED_URL="${BEAGLE_PXE_SEED_URL:-}"
PXE_DRY_RUN="${BEAGLE_PXE_DRY_RUN:-0}"
PXE_DNSMASQ_SERVICE="${BEAGLE_PXE_DNSMASQ_SERVICE:-dnsmasq}"
PXE_GRUB_EFI="${BEAGLE_PXE_GRUB_EFI:-}"
PXE_PXELINUX_BIN="${BEAGLE_PXE_PXELINUX_BIN:-}"
PXE_LDLINUX_C32="${BEAGLE_PXE_LDLINUX_C32:-}"
PXE_BOOT_ARGS_BASE="boot=live components username=root hostname=beagle-server-installer console=tty0 console=ttyS0,115200n8 systemd.gpt_auto=0 systemd.unit=multi-user.target pve_server_installer=1 nomodeset consoleblank=0"

log() {
  printf '[%s] %s\n' "$(date -Is 2>/dev/null || date)" "$*"
}

die() {
  echo "setup-pxe-server.sh: $*" >&2
  exit 1
}

run_maybe() {
  if [[ "$PXE_DRY_RUN" == "1" ]]; then
    log "dry-run: $*"
    return 0
  fi
  "$@"
}

ensure_file() {
  local path="$1"
  [[ -f "$path" ]] || die "missing required file: $path"
}

find_first_existing() {
  local path=""
  for path in "$@"; do
    [[ -f "$path" ]] || continue
    printf '%s\n' "$path"
    return 0
  done
  return 1
}

ensure_prerequisites() {
  command -v xorriso >/dev/null 2>&1 || die "xorriso is required"
  ensure_file "$PXE_ISO_PATH"
  if [[ -z "$PXE_GRUB_EFI" ]]; then
    PXE_GRUB_EFI="$(find_first_existing \
      /usr/lib/grub/x86_64-efi-signed/grubnetx64.efi.signed \
      /usr/lib/grub/x86_64-efi/grubnetx64.efi \
      /usr/lib/grub/x86_64-efi/monolithic/grubnetx64.efi \
    )" || die "unable to locate grubnetx64.efi; install grub-efi-amd64-bin"
  fi
  if [[ -z "$PXE_PXELINUX_BIN" ]]; then
    PXE_PXELINUX_BIN="$(find_first_existing \
      /usr/lib/PXELINUX/lpxelinux.0 \
      /usr/lib/syslinux/modules/bios/lpxelinux.0 \
    )" || true
  fi
  if [[ -z "$PXE_LDLINUX_C32" ]]; then
    PXE_LDLINUX_C32="$(find_first_existing \
      /usr/lib/syslinux/modules/bios/ldlinux.c32 \
      /usr/lib/syslinux/ldlinux.c32 \
    )" || true
  fi
}

extract_boot_assets() {
  local stage_dir=""
  stage_dir="$(mktemp -d)"
  mkdir -p "$PXE_BOOT_DIR/grub"
  xorriso -osirrox on -indev "$PXE_ISO_PATH" \
    -extract /live/vmlinuz "$stage_dir/vmlinuz" \
    -extract /live/initrd "$stage_dir/initrd" >/dev/null 2>&1
  install -m 0644 "$stage_dir/vmlinuz" "$PXE_BOOT_DIR/vmlinuz"
  install -m 0644 "$stage_dir/initrd" "$PXE_BOOT_DIR/initrd"
  install -m 0644 "$PXE_GRUB_EFI" "$PXE_TFTP_ROOT/grubnetx64.efi"
  if [[ -n "$PXE_PXELINUX_BIN" && -n "$PXE_LDLINUX_C32" ]]; then
    install -m 0644 "$PXE_PXELINUX_BIN" "$PXE_TFTP_ROOT/lpxelinux.0"
    install -m 0644 "$PXE_LDLINUX_C32" "$PXE_TFTP_ROOT/ldlinux.c32"
  fi
  rm -rf "$stage_dir"
}

write_grub_config() {
  local seed_arg=""
  if [[ -n "$PXE_SEED_URL" ]]; then
    seed_arg=" beagle.seed_url=${PXE_SEED_URL}"
  fi
  cat >"$PXE_BOOT_DIR/grub/grub.cfg" <<EOF
set default=0
set timeout=5

menuentry "Beagle OS Server Installer (PXE)" {
    linux /beagle-installer/vmlinuz ${PXE_BOOT_ARGS_BASE}${seed_arg}
    initrd /beagle-installer/initrd
}
EOF
}

write_pxelinux_config() {
  local seed_arg=""
  [[ -f "$PXE_TFTP_ROOT/lpxelinux.0" ]] || return 0
  if [[ -n "$PXE_SEED_URL" ]]; then
    seed_arg=" beagle.seed_url=${PXE_SEED_URL}"
  fi
  mkdir -p "$PXE_TFTP_ROOT/pxelinux.cfg"
  cat >"$PXE_TFTP_ROOT/pxelinux.cfg/default" <<EOF
DEFAULT beagle
PROMPT 0
TIMEOUT 50

LABEL beagle
  KERNEL beagle-installer/vmlinuz
  APPEND initrd=beagle-installer/initrd ${PXE_BOOT_ARGS_BASE}${seed_arg}
EOF
}

write_dnsmasq_config() {
  local conf_path="$PXE_CONFIG_DIR/beagle-pxe.conf"
  mkdir -p "$PXE_CONFIG_DIR"
  cat >"$conf_path" <<EOF
# Managed by scripts/setup-pxe-server.sh
port=0
log-dhcp
enable-tftp
tftp-root=$PXE_TFTP_ROOT
dhcp-range=$PXE_DHCP_RANGE
dhcp-match=set:efi-x86_64,option:client-arch,7
dhcp-match=set:efi-x86_64,option:client-arch,9
dhcp-boot=tag:efi-x86_64,grubnetx64.efi
EOF
  if [[ -n "$PXE_INTERFACE" ]]; then
    cat >>"$conf_path" <<EOF
interface=$PXE_INTERFACE
bind-interfaces
EOF
  fi
  if [[ -f "$PXE_TFTP_ROOT/lpxelinux.0" ]]; then
    cat >>"$conf_path" <<'EOF'
dhcp-boot=tag:!efi-x86_64,lpxelinux.0
EOF
  fi
  if [[ -n "$PXE_SEED_URL" ]]; then
    cat >>"$conf_path" <<EOF
# Seed URL rendered into boot menu and documented here for operators.
# seed_url=$PXE_SEED_URL
EOF
  fi
}

print_summary() {
  cat <<EOF
PXE setup complete.
  ISO:        $PXE_ISO_PATH
  TFTP root:  $PXE_TFTP_ROOT
  Boot dir:   $PXE_BOOT_DIR
  dnsmasq:    $PXE_CONFIG_DIR/beagle-pxe.conf
  Host:       $PXE_PUBLIC_HOST
  Seed URL:   ${PXE_SEED_URL:-<none>}
EOF
}

main() {
  ensure_prerequisites
  mkdir -p "$PXE_TFTP_ROOT" "$PXE_BOOT_DIR"
  extract_boot_assets
  write_grub_config
  write_pxelinux_config
  write_dnsmasq_config
  if [[ "$PXE_DRY_RUN" != "1" ]]; then
    run_maybe systemctl restart "$PXE_DNSMASQ_SERVICE"
  fi
  print_summary
}

main "$@"
