#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LIVE_MEDIUM="${LIVE_MEDIUM:-/run/live/medium}"
TARGET_MOUNT="/mnt/pve-thin-client-target"
EFI_MOUNT="$TARGET_MOUNT/boot/efi"
LIVE_ASSET_DIR="${LIVE_MEDIUM}/pve-thin-client/live"
STATE_DIR="$TARGET_MOUNT/pve-thin-client/state"

MODE=""
CONNECTION_METHOD=""
PROFILE_NAME="default"
RUNTIME_USER="thinclient"
HOSTNAME_VALUE="pve-thin-client"
AUTOSTART="1"
NETWORK_MODE="dhcp"
NETWORK_INTERFACE="eth0"
NETWORK_STATIC_ADDRESS=""
NETWORK_STATIC_PREFIX="24"
NETWORK_GATEWAY=""
NETWORK_DNS_SERVERS="1.1.1.1 8.8.8.8"
SPICE_URL=""
NOVNC_URL=""
DCV_URL=""
REMOTE_VIEWER_BIN="remote-viewer"
BROWSER_BIN="chromium"
BROWSER_FLAGS="--kiosk --incognito --no-first-run --disable-session-crashed-bubble"
DCV_VIEWER_BIN="dcvviewer"
PROXMOX_SCHEME="https"
PROXMOX_HOST=""
PROXMOX_PORT="8006"
PROXMOX_NODE=""
PROXMOX_VMID=""
PROXMOX_REALM="pam"
PROXMOX_VERIFY_TLS="0"
CONNECTION_USERNAME=""
CONNECTION_PASSWORD=""
CONNECTION_TOKEN=""

cleanup() {
  umount "$EFI_MOUNT" >/dev/null 2>&1 || true
  umount "$TARGET_MOUNT" >/dev/null 2>&1 || true
  rmdir "$EFI_MOUNT" >/dev/null 2>&1 || true
  rmdir "$TARGET_MOUNT" >/dev/null 2>&1 || true
}
trap cleanup EXIT

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then
      exec sudo "$0" "$@"
    fi
    echo "This installer must run as root." >&2
    exit 1
  fi
}

require_tools() {
  local missing=()
  local tool
  for tool in grub-install mkfs.vfat mkfs.ext4 parted lsblk blkid findmnt python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      missing+=("$tool")
    fi
  done

  if (( ${#missing[@]} > 0 )); then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      dosfstools \
      e2fsprogs \
      parted \
      grub-pc-bin \
      grub-efi-amd64-bin \
      efibootmgr \
      python3
  fi
}

partition_suffix() {
  local device="$1"
  local number="$2"
  if [[ "$device" =~ [0-9]$ ]]; then
    printf '%sp%s\n' "$device" "$number"
  else
    printf '%s%s\n' "$device" "$number"
  fi
}

current_live_disk() {
  local medium_source parent_name
  medium_source="$(findmnt -n -o SOURCE "$LIVE_MEDIUM" 2>/dev/null || true)"
  if [[ -n "$medium_source" ]]; then
    parent_name="$(lsblk -ndo PKNAME "$medium_source" 2>/dev/null || true)"
    if [[ -n "$parent_name" ]]; then
      printf '/dev/%s\n' "$parent_name"
      return 0
    fi
  fi
  return 1
}

choose_target_disk() {
  local live_disk menu_items device label name size model type rm transport answer tty_path
  live_disk="$(current_live_disk 2>/dev/null || true)"
  menu_items=()
  tty_path="/dev/tty"

  if [[ ! -r "$tty_path" || ! -w "$tty_path" ]]; then
    tty_path=""
  fi

  while IFS= read -r line; do
    eval "$line"
    [[ "${TYPE:-}" == "disk" ]] || continue
    device="/dev/${NAME}"
    [[ "$device" == "$live_disk" ]] && continue
    [[ "$device" == /dev/loop* || "$device" == /dev/sr* || "$device" == /dev/ram* || "$device" == /dev/zram* ]] && continue
    label="${MODEL:-disk} ${SIZE:-unknown} rm=${RM:-0} ${TRAN:-}"
    menu_items+=("$device" "$label")
  done <<EOF
$(lsblk -dn -P -o NAME,SIZE,MODEL,TYPE,RM,TRAN)
EOF

  if (( ${#menu_items[@]} == 0 )); then
    echo "No writable target disk found." >&2
    exit 1
  fi

  if command -v whiptail >/dev/null 2>&1; then
    whiptail --title "PVE Thin Client Installation" --menu \
      "Choose the target disk. It will be erased completely." 22 96 10 \
      "${menu_items[@]}" 3>&1 1>&2 2>&3
    return 0
  fi

  if [[ -z "$tty_path" ]]; then
    echo "Interactive disk selection requires a TTY." >&2
    exit 1
  fi

  local index=1
  printf 'Available installation targets:\n' >"$tty_path"
  while (( index <= ${#menu_items[@]} / 2 )); do
    printf '%s) %s %s\n' "$index" "${menu_items[$(( (index - 1) * 2 ))]}" "${menu_items[$(( (index - 1) * 2 + 1 ))]}" >"$tty_path"
    index=$((index + 1))
  done

  printf 'Choice: ' >"$tty_path"
  read -r answer <"$tty_path"
  [[ "$answer" =~ ^[0-9]+$ ]] || {
    echo "Invalid selection: $answer" >&2
    exit 1
  }
  (( answer >= 1 && answer <= ${#menu_items[@]} / 2 )) || {
    echo "Selection out of range: $answer" >&2
    exit 1
  }
  printf '%s\n' "${menu_items[$(( (answer - 1) * 2 ))]}"
}

confirm_wipe() {
  local target_disk="$1"
  if command -v whiptail >/dev/null 2>&1; then
    whiptail --title "PVE Thin Client Installation" --yesno \
      "The disk ${target_disk} will be fully erased and turned into a local thin-client boot disk." 14 88
    return $?
  fi

  read -r -p "Erase ${target_disk} completely? [y/N]: " answer
  [[ "$answer" =~ ^[Yy]$ ]]
}

load_profile() {
  local output
  output="$(
    MODE="$MODE" \
    CONNECTION_METHOD="$CONNECTION_METHOD" \
    PROFILE_NAME="$PROFILE_NAME" \
    RUNTIME_USER="$RUNTIME_USER" \
    HOSTNAME_VALUE="$HOSTNAME_VALUE" \
    AUTOSTART="$AUTOSTART" \
    NETWORK_MODE="$NETWORK_MODE" \
    NETWORK_INTERFACE="$NETWORK_INTERFACE" \
    NETWORK_STATIC_ADDRESS="$NETWORK_STATIC_ADDRESS" \
    NETWORK_STATIC_PREFIX="$NETWORK_STATIC_PREFIX" \
    NETWORK_GATEWAY="$NETWORK_GATEWAY" \
    NETWORK_DNS_SERVERS="$NETWORK_DNS_SERVERS" \
    SPICE_URL="$SPICE_URL" \
    NOVNC_URL="$NOVNC_URL" \
    DCV_URL="$DCV_URL" \
    REMOTE_VIEWER_BIN="$REMOTE_VIEWER_BIN" \
    BROWSER_BIN="$BROWSER_BIN" \
    BROWSER_FLAGS="$BROWSER_FLAGS" \
    DCV_VIEWER_BIN="$DCV_VIEWER_BIN" \
    PROXMOX_SCHEME="$PROXMOX_SCHEME" \
    PROXMOX_HOST="$PROXMOX_HOST" \
    PROXMOX_PORT="$PROXMOX_PORT" \
    PROXMOX_NODE="$PROXMOX_NODE" \
    PROXMOX_VMID="$PROXMOX_VMID" \
    PROXMOX_REALM="$PROXMOX_REALM" \
    PROXMOX_VERIFY_TLS="$PROXMOX_VERIFY_TLS" \
    CONNECTION_USERNAME="$CONNECTION_USERNAME" \
    CONNECTION_PASSWORD="$CONNECTION_PASSWORD" \
    CONNECTION_TOKEN="$CONNECTION_TOKEN" \
    "$ROOT_DIR/installer/setup-menu.sh"
  )"
  eval "$output"
}

prefix_to_netmask() {
  python3 - "$1" <<'PY'
import ipaddress
import sys

prefix = int(sys.argv[1])
network = ipaddress.ip_network(f"0.0.0.0/{prefix}")
print(network.netmask)
PY
}

boot_ip_arg() {
  if [[ "$NETWORK_MODE" == "dhcp" ]]; then
    printf 'ip=dhcp'
    return 0
  fi

  local netmask
  netmask="$(prefix_to_netmask "$NETWORK_STATIC_PREFIX")"
  printf 'ip=%s::%s:%s:%s:%s:none' \
    "$NETWORK_STATIC_ADDRESS" \
    "$NETWORK_GATEWAY" \
    "$netmask" \
    "$HOSTNAME_VALUE" \
    "$NETWORK_INTERFACE"
}

write_grub_cfg() {
  local root_uuid="$1"
  local ip_arg
  ip_arg="$(boot_ip_arg)"

  cat > "$TARGET_MOUNT/boot/grub/grub.cfg" <<EOF
set default=0
set timeout=4

menuentry 'PVE Thin Client' {
  search --no-floppy --fs-uuid --set=root $root_uuid
  linux /pve-thin-client/live/vmlinuz boot=live components username=thinclient hostname=$HOSTNAME_VALUE live-media=UUID=$root_uuid live-media-path=/pve-thin-client/live quiet loglevel=3 systemd.show_status=0 vt.global_cursor_default=0 splash $ip_arg pve_thin_client.mode=runtime
  initrd /pve-thin-client/live/initrd.img
}
EOF
}

copy_assets() {
  install -d -m 0755 "$TARGET_MOUNT/pve-thin-client/live" "$STATE_DIR"
  install -m 0644 "$LIVE_ASSET_DIR/vmlinuz" "$TARGET_MOUNT/pve-thin-client/live/vmlinuz"
  install -m 0644 "$LIVE_ASSET_DIR/initrd.img" "$TARGET_MOUNT/pve-thin-client/live/initrd.img"
  install -m 0644 "$LIVE_ASSET_DIR/filesystem.squashfs" "$TARGET_MOUNT/pve-thin-client/live/filesystem.squashfs"
  MODE="$MODE" \
  CONNECTION_METHOD="$CONNECTION_METHOD" \
  PROFILE_NAME="$PROFILE_NAME" \
  RUNTIME_USER="$RUNTIME_USER" \
  HOSTNAME_VALUE="$HOSTNAME_VALUE" \
  AUTOSTART="$AUTOSTART" \
  NETWORK_MODE="$NETWORK_MODE" \
  NETWORK_INTERFACE="$NETWORK_INTERFACE" \
  NETWORK_STATIC_ADDRESS="$NETWORK_STATIC_ADDRESS" \
  NETWORK_STATIC_PREFIX="$NETWORK_STATIC_PREFIX" \
  NETWORK_GATEWAY="$NETWORK_GATEWAY" \
  NETWORK_DNS_SERVERS="$NETWORK_DNS_SERVERS" \
  SPICE_URL="$SPICE_URL" \
  NOVNC_URL="$NOVNC_URL" \
  DCV_URL="$DCV_URL" \
  REMOTE_VIEWER_BIN="$REMOTE_VIEWER_BIN" \
  BROWSER_BIN="$BROWSER_BIN" \
  BROWSER_FLAGS="$BROWSER_FLAGS" \
  DCV_VIEWER_BIN="$DCV_VIEWER_BIN" \
  PROXMOX_SCHEME="$PROXMOX_SCHEME" \
  PROXMOX_HOST="$PROXMOX_HOST" \
  PROXMOX_PORT="$PROXMOX_PORT" \
  PROXMOX_NODE="$PROXMOX_NODE" \
  PROXMOX_VMID="$PROXMOX_VMID" \
  PROXMOX_REALM="$PROXMOX_REALM" \
  PROXMOX_VERIFY_TLS="$PROXMOX_VERIFY_TLS" \
  CONNECTION_USERNAME="$CONNECTION_USERNAME" \
  CONNECTION_PASSWORD="$CONNECTION_PASSWORD" \
  CONNECTION_TOKEN="$CONNECTION_TOKEN" \
  "$ROOT_DIR/installer/write-config.sh" "$STATE_DIR"
}

install_bootloader() {
  local target_disk="$1"
  grub-install --target=i386-pc --boot-directory="$TARGET_MOUNT/boot" "$target_disk"
  grub-install \
    --target=x86_64-efi \
    --efi-directory="$EFI_MOUNT" \
    --boot-directory="$TARGET_MOUNT/boot" \
    --removable \
    --no-nvram
}

main() {
  local target_disk bios_part boot_part root_part root_uuid

  require_root "$@"
  require_tools

  if [[ ! -f "$LIVE_ASSET_DIR/filesystem.squashfs" ]]; then
    echo "Live installer assets were not found under $LIVE_ASSET_DIR" >&2
    exit 1
  fi

  load_profile
  target_disk="$(choose_target_disk)"
  [[ -n "$target_disk" ]] || exit 0
  confirm_wipe "$target_disk" || exit 0

  bios_part="$(partition_suffix "$target_disk" 1)"
  boot_part="$(partition_suffix "$target_disk" 2)"
  root_part="$(partition_suffix "$target_disk" 3)"

  wipefs -a "$target_disk"
  parted -s "$target_disk" mklabel gpt
  parted -s "$target_disk" mkpart BIOSBOOT 1MiB 3MiB
  parted -s "$target_disk" set 1 bios_grub on
  parted -s "$target_disk" mkpart ESP fat32 3MiB 515MiB
  parted -s "$target_disk" set 2 esp on
  parted -s "$target_disk" set 2 boot on
  parted -s "$target_disk" mkpart primary ext4 515MiB 100%
  partprobe "$target_disk"
  udevadm settle

  [[ -b "$bios_part" ]] || {
    echo "BIOS boot partition could not be created on $target_disk" >&2
    exit 1
  }

  mkfs.vfat -F 32 -n PVETHINBOOT "$boot_part"
  mkfs.ext4 -F -L PVETHINROOT "$root_part"

  install -d -m 0755 "$TARGET_MOUNT" "$EFI_MOUNT"
  mount "$root_part" "$TARGET_MOUNT"
  install -d -m 0755 "$EFI_MOUNT" "$TARGET_MOUNT/boot/grub"
  mount "$boot_part" "$EFI_MOUNT"

  copy_assets
  root_uuid="$(blkid -s UUID -o value "$root_part")"
  write_grub_cfg "$root_uuid"
  install_bootloader "$target_disk"
  sync

  if command -v whiptail >/dev/null 2>&1; then
    whiptail --title "PVE Thin Client Installation" --msgbox \
      "Installation complete. Remove the USB stick and boot from the target disk." 12 72
  else
    echo "Installation complete. Remove the USB stick and boot from the target disk."
  fi
}

main "$@"
