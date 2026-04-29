#!/usr/bin/env bash

partition_suffix() {
  local device="$1"
  local number="$2"
  if [[ "$device" =~ [0-9]$ ]]; then
    printf '%sp%s\n' "$device" "$number"
  else
    printf '%s%s\n' "$device" "$number"
  fi
}

release_target_device() {
  local mountpoint=""
  local part=""
  local parts=()

  mapfile -t parts < <(lsblk -nrpo NAME "$TARGET_DEVICE" | tail -n +2)
  for part in "${parts[@]}"; do
    while IFS= read -r mountpoint; do
      [[ -n "$mountpoint" ]] || continue
      umount "$mountpoint"
    done < <(findmnt -rn -S "$part" -o TARGET 2>/dev/null || true)
  done

  partprobe "$TARGET_DEVICE" || true
  udevadm settle || true
}

write_usb_manifest() {
  local mount_dir="$1"
  local payload_source installer_sha payload_sha bundled_payload_relpath
  local live_dir

  if [[ "$USB_WRITER_VARIANT" == "live" ]]; then
    live_dir="$mount_dir/live"
    bundled_payload_relpath="live"
  else
    live_dir="$mount_dir/pve-thin-client/live"
    bundled_payload_relpath="pve-thin-client/live"
  fi
  payload_source="$(resolve_usb_install_payload_source "$REPO_ROOT")"
  if [[ -f "$mount_dir/start-installer-menu.sh" ]]; then
    installer_sha="$(sha256sum "$mount_dir/start-installer-menu.sh" | awk '{print $1}')"
  else
    installer_sha=""
  fi
  payload_sha="$(sha256sum "$live_dir/filesystem.squashfs" | awk '{print $1}')"

  python3 "$(usb_manifest_helper)" write-usb-manifest \
    --path "$mount_dir/.pve-dcv-usb-manifest.json" \
    --project-version "$PROJECT_VERSION" \
    --usb-label "$USB_LABEL" \
    --target-device "$TARGET_DEVICE" \
    --payload-source "$payload_source" \
    --payload-source-url "$payload_source" \
    --payload-source-kind bundled-usb \
    --bundled-payload-relpath "$bundled_payload_relpath" \
    --start-installer-menu-sha256 "$installer_sha" \
    --filesystem-squashfs-sha256 "$payload_sha" \
    --preset-name "${PVE_THIN_CLIENT_PRESET_NAME:-}" \
    --usb-writer-variant "$USB_WRITER_VARIANT"

  if [[ -d "$mount_dir/pve-thin-client/live" ]]; then
    install -m 0644 "$mount_dir/.pve-dcv-usb-manifest.json" "$mount_dir/pve-thin-client/live/.pve-dcv-usb-manifest.json"
  elif [[ -d "$mount_dir/live" ]]; then
    install -m 0644 "$mount_dir/.pve-dcv-usb-manifest.json" "$mount_dir/live/.pve-dcv-usb-manifest.json"
  fi
}

write_usb_preset() {
  local mount_dir="$1"
  local preset_file
  local preset_live_file

  [[ -n "$PVE_THIN_CLIENT_PRESET_B64" ]] || return 0

  preset_file="$mount_dir/pve-thin-client/preset.env"
  if [[ "$USB_WRITER_VARIANT" == "live" ]]; then
    preset_live_file="$mount_dir/live/preset.env"
  else
    preset_live_file="$mount_dir/pve-thin-client/live/preset.env"
  fi
  install -d -m 0755 "$mount_dir/pve-thin-client"
  python3 - "$preset_file" "$PVE_THIN_CLIENT_PRESET_B64" <<'PY'
import base64
import sys
from pathlib import Path

target = Path(sys.argv[1])
payload = sys.argv[2].strip()
if not payload:
    raise SystemExit(0)

decoded = base64.b64decode(payload.encode("ascii"), validate=True)
target.write_bytes(decoded)
target.chmod(0o600)
PY

  # The live installer UI probes presets before escalating privileges.
  # Keep preset readable inside the live medium to avoid false "no preset" states.
  install -m 0644 "$preset_file" "$preset_live_file"
}

write_live_state_config() {
  local mount_dir="$1"
  local preset_file=""
  local live_state_dir="$mount_dir/pve-thin-client/state"

  [[ -n "$PVE_THIN_CLIENT_PRESET_B64" ]] || {
    echo "Live USB creation requires an embedded VM preset." >&2
    exit 1
  }

  preset_file="$(mktemp)"
  python3 - "$preset_file" "$PVE_THIN_CLIENT_PRESET_B64" <<'PY'
import base64
import sys
from pathlib import Path

Path(sys.argv[1]).write_bytes(base64.b64decode(sys.argv[2].encode("ascii"), validate=True))
PY

  set -a
  # shellcheck disable=SC1090
  source "$preset_file"
  set +a

  if [[ "${PVE_THIN_CLIENT_PRESET_DEFAULT_MODE:-MOONLIGHT}" == "MOONLIGHT" ]]; then
    if [[ -z "${PVE_THIN_CLIENT_PRESET_SUNSHINE_USERNAME:-}" || -z "${PVE_THIN_CLIENT_PRESET_SUNSHINE_PASSWORD:-}" || -z "${PVE_THIN_CLIENT_PRESET_SUNSHINE_PIN:-}" ]]; then
      echo "Live USB preset is missing Sunshine auto-pair credentials (username/password/pin)." >&2
      exit 1
    fi
  fi

  install -d -m 0755 "$live_state_dir"

  MODE="${PVE_THIN_CLIENT_PRESET_DEFAULT_MODE:-MOONLIGHT}"
  if [[ -z "$MODE" && -n "${PVE_THIN_CLIENT_PRESET_MOONLIGHT_HOST:-}" ]]; then
    MODE="MOONLIGHT"
  fi
  [[ -n "$MODE" ]] || {
    echo "Live USB preset does not define a supported default mode." >&2
    exit 1
  }

  MODE="$MODE" \
  PROFILE_NAME="${PVE_THIN_CLIENT_PRESET_PROFILE_NAME:-default}" \
  RUNTIME_USER="thinclient" \
  AUTOSTART="${PVE_THIN_CLIENT_PRESET_AUTOSTART:-1}" \
  HOSTNAME_VALUE="${PVE_THIN_CLIENT_PRESET_HOSTNAME_VALUE:-beagle-live}" \
  CONNECTION_METHOD="${PVE_THIN_CLIENT_PRESET_CONNECTION_METHOD:-direct}" \
  NETWORK_MODE="${PVE_THIN_CLIENT_PRESET_NETWORK_MODE:-dhcp}" \
  NETWORK_INTERFACE="${PVE_THIN_CLIENT_PRESET_NETWORK_INTERFACE:-eth0}" \
  NETWORK_STATIC_ADDRESS="${PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_ADDRESS:-}" \
  NETWORK_STATIC_PREFIX="${PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_PREFIX:-24}" \
  NETWORK_GATEWAY="${PVE_THIN_CLIENT_PRESET_NETWORK_GATEWAY:-}" \
  NETWORK_DNS_SERVERS="${PVE_THIN_CLIENT_PRESET_NETWORK_DNS_SERVERS:-1.1.1.1 8.8.8.8}" \
  MOONLIGHT_HOST="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_HOST:-}" \
  MOONLIGHT_LOCAL_HOST="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_LOCAL_HOST:-}" \
  MOONLIGHT_PORT="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_PORT:-}" \
  MOONLIGHT_APP="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_APP:-Desktop}" \
  MOONLIGHT_BIN="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_BIN:-moonlight}" \
  MOONLIGHT_RESOLUTION="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_RESOLUTION:-auto}" \
  MOONLIGHT_FPS="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_FPS:-60}" \
  MOONLIGHT_BITRATE="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_BITRATE:-20000}" \
  MOONLIGHT_VIDEO_CODEC="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_VIDEO_CODEC:-H.264}" \
  MOONLIGHT_VIDEO_DECODER="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_VIDEO_DECODER:-auto}" \
  MOONLIGHT_AUDIO_CONFIG="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_AUDIO_CONFIG:-stereo}" \
  MOONLIGHT_ABSOLUTE_MOUSE="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_ABSOLUTE_MOUSE:-1}" \
  MOONLIGHT_QUIT_AFTER="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_QUIT_AFTER:-0}" \
  SUNSHINE_API_URL="${PVE_THIN_CLIENT_PRESET_SUNSHINE_API_URL:-}" \
  BEAGLE_SCHEME="${PVE_THIN_CLIENT_PRESET_BEAGLE_SCHEME:-https}" \
  BEAGLE_HOST="${PVE_THIN_CLIENT_PRESET_BEAGLE_HOST:-}" \
  BEAGLE_PORT="${PVE_THIN_CLIENT_PRESET_BEAGLE_PORT:-8006}" \
  BEAGLE_NODE="${PVE_THIN_CLIENT_PRESET_BEAGLE_NODE:-}" \
  BEAGLE_VMID="${PVE_THIN_CLIENT_PRESET_BEAGLE_VMID:-}" \
  BEAGLE_REALM="${PVE_THIN_CLIENT_PRESET_BEAGLE_REALM:-pam}" \
  BEAGLE_VERIFY_TLS="${PVE_THIN_CLIENT_PRESET_BEAGLE_VERIFY_TLS:-1}" \
  CONNECTION_USERNAME="${PVE_THIN_CLIENT_PRESET_BEAGLE_USERNAME:-}" \
  CONNECTION_PASSWORD="${PVE_THIN_CLIENT_PRESET_BEAGLE_PASSWORD:-}" \
  CONNECTION_TOKEN="${PVE_THIN_CLIENT_PRESET_BEAGLE_TOKEN:-}" \
  BEAGLE_MANAGER_URL="${PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_URL:-}" \
  BEAGLE_MANAGER_PINNED_PUBKEY="${PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_PINNED_PUBKEY:-}" \
  BEAGLE_ENROLLMENT_URL="${PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_URL:-}" \
  BEAGLE_MANAGER_TOKEN="${PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_TOKEN:-}" \
  BEAGLE_ENROLLMENT_TOKEN="${PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_TOKEN:-}" \
  BEAGLE_EGRESS_MODE="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_MODE:-full}" \
  BEAGLE_EGRESS_TYPE="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_TYPE:-wireguard}" \
  BEAGLE_EGRESS_INTERFACE="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_INTERFACE:-wg-beagle}" \
  BEAGLE_EGRESS_DOMAINS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_DOMAINS:-}" \
  BEAGLE_EGRESS_RESOLVERS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_RESOLVERS:-}" \
  BEAGLE_EGRESS_ALLOWED_IPS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_ALLOWED_IPS:-}" \
  BEAGLE_EGRESS_WG_ADDRESS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ADDRESS:-}" \
  BEAGLE_EGRESS_WG_DNS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_DNS:-}" \
  BEAGLE_EGRESS_WG_PUBLIC_KEY="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PUBLIC_KEY:-}" \
  BEAGLE_EGRESS_WG_ENDPOINT="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ENDPOINT:-}" \
  BEAGLE_EGRESS_WG_PRIVATE_KEY="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRIVATE_KEY:-}" \
  BEAGLE_EGRESS_WG_PRESHARED_KEY="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRESHARED_KEY:-}" \
  BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE:-25}" \
  IDENTITY_HOSTNAME="${PVE_THIN_CLIENT_PRESET_IDENTITY_HOSTNAME:-${PVE_THIN_CLIENT_PRESET_HOSTNAME_VALUE:-}}" \
  IDENTITY_TIMEZONE="${PVE_THIN_CLIENT_PRESET_IDENTITY_TIMEZONE:-}" \
  IDENTITY_LOCALE="${PVE_THIN_CLIENT_PRESET_IDENTITY_LOCALE:-}" \
  IDENTITY_KEYMAP="${PVE_THIN_CLIENT_PRESET_IDENTITY_KEYMAP:-}" \
  IDENTITY_CHROME_PROFILE="${PVE_THIN_CLIENT_PRESET_IDENTITY_CHROME_PROFILE:-default}" \
  SUNSHINE_USERNAME="${PVE_THIN_CLIENT_PRESET_SUNSHINE_USERNAME:-}" \
  SUNSHINE_PASSWORD="${PVE_THIN_CLIENT_PRESET_SUNSHINE_PASSWORD:-}" \
  SUNSHINE_PIN="${PVE_THIN_CLIENT_PRESET_SUNSHINE_PIN:-}" \
  SUNSHINE_PINNED_PUBKEY="${PVE_THIN_CLIENT_PRESET_SUNSHINE_PINNED_PUBKEY:-}" \
  SUNSHINE_SERVER_NAME="${PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_NAME:-}" \
  SUNSHINE_SERVER_STREAM_PORT="${PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_STREAM_PORT:-}" \
  SUNSHINE_SERVER_UNIQUEID="${PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_UNIQUEID:-}" \
  SUNSHINE_SERVER_CERT_B64="${PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_CERT_B64:-}" \
  RUNTIME_PASSWORD="${PVE_THIN_CLIENT_PRESET_THINCLIENT_PASSWORD:-}" \
    "$REPO_ROOT/thin-client-assistant/installer/write-config.sh" "$live_state_dir"

  if [[ ! -f "$live_state_dir/local-auth.env" ]]; then
    printf '%s\n' "local-auth.env missing after write-config; restoring runtime password file" >&2
    cat >"$live_state_dir/local-auth.env" <<EOF
PVE_THIN_CLIENT_RUNTIME_PASSWORD="${PVE_THIN_CLIENT_PRESET_THINCLIENT_PASSWORD:-}"
EOF
  fi

  if [[ ! -f "$live_state_dir/local-auth.env" ]]; then
    echo "Failed to persist local-auth.env to $live_state_dir" >&2
    exit 1
  fi

  rm -f "$preset_file"
}

boot_ip_arg() {
  local network_mode="$1"
  local network_static_address="$2"
  local network_static_prefix="$3"
  local network_gateway="$4"
  local hostname_value="$5"
  local network_interface="$6"
  local netmask=""

  if [[ "$network_mode" == "dhcp" || -z "$network_static_address" || -z "$network_interface" ]]; then
    printf 'ip=dhcp'
    return 0
  fi

  netmask="$(python3 - "$network_static_prefix" <<'PY'
import ipaddress
import sys
print(ipaddress.ip_network(f"0.0.0.0/{int(sys.argv[1])}").netmask)
PY
)"
  printf 'ip=%s::%s:%s:%s:%s:none' \
    "$network_static_address" \
    "$network_gateway" \
    "$netmask" \
    "$hostname_value" \
    "$network_interface"
}

usb_writer_print_write_plan() {
  local bootstrap_source install_payload_source media_label live_assets_path

  bootstrap_source="$(resolve_usb_plan_bootstrap_source "$REPO_ROOT")"
  install_payload_source="$(resolve_usb_install_payload_source "$REPO_ROOT")"
  media_label="$(usb_writer_media_label "$USB_WRITER_VARIANT")"
  live_assets_path="$(usb_writer_live_assets_path "$USB_WRITER_VARIANT")"
  cat <<EOF
Dry run only. No changes were written.
Target device: $TARGET_DEVICE
USB label: $USB_LABEL
Project version: $PROJECT_VERSION
Bootstrap source: ${bootstrap_source}
Install payload source: ${install_payload_source}
Preset profile: ${PVE_THIN_CLIENT_PRESET_NAME:-generic}
USB variant: ${USB_WRITER_VARIANT}
Planned partitions:
  1. BIOS boot partition (1 MiB - 3 MiB)
  2. FAT32 EFI/data partition (3 MiB - 100%)
Copied assets:
  - live kernel, initrd and squashfs from ${install_payload_source} to ${live_assets_path}
  - thin-client assistant sources
  - embedded VM preset profile$( [[ "$USB_WRITER_VARIANT" == "live" ]] && printf ' and runtime state' )
  - docs, README, LICENSE, CHANGELOG
  - generated USB manifest
Result:
  - bootable Beagle OS ${media_label} USB medium
EOF
}

write_usb() {
  local mount_dir bios_partition usb_partition usb_uuid runtime_ip_args
  local live_mount_dir hostname_value network_mode network_static_address network_static_prefix network_gateway network_interface
  local grub_default_index="0" grub_timeout="5"

  if [[ "$DRY_RUN" == "1" ]]; then
    print_write_plan
    return 0
  fi

  mount_dir="$(mktemp -d)"
  trap 'umount "$mount_dir" >/dev/null 2>&1 || true; rmdir "$mount_dir" >/dev/null 2>&1 || true' RETURN

  release_target_device
  wipefs -a "$TARGET_DEVICE"
  parted -s "$TARGET_DEVICE" mklabel gpt
  parted -s "$TARGET_DEVICE" mkpart BIOSBOOT 1MiB 3MiB
  parted -s "$TARGET_DEVICE" set 1 bios_grub on
  parted -s "$TARGET_DEVICE" mkpart ESP fat32 3MiB 100%
  parted -s "$TARGET_DEVICE" set 2 esp on
  parted -s "$TARGET_DEVICE" set 2 boot on
  partprobe "$TARGET_DEVICE"
  udevadm settle

  bios_partition="$(partition_suffix "$TARGET_DEVICE" 1)"
  usb_partition="$(partition_suffix "$TARGET_DEVICE" 2)"
  [[ -b "$bios_partition" ]] || {
    echo "BIOS boot partition was not created on $TARGET_DEVICE" >&2
    exit 1
  }
  for _ in $(seq 1 20); do
    [[ -b "$usb_partition" ]] && break
    sleep 1
    udevadm settle || true
  done
  [[ -b "$usb_partition" ]] || {
    echo "EFI/data partition was not created on $TARGET_DEVICE" >&2
    exit 1
  }
  mkfs.vfat -F 32 -n "$USB_LABEL" "$usb_partition"
  usb_uuid="$(blkid -s UUID -o value "$usb_partition" 2>/dev/null || true)"
  [[ -n "$usb_uuid" ]] || {
    echo "Unable to determine UUID for USB installer partition $usb_partition" >&2
    exit 1
  }
  mount "$usb_partition" "$mount_dir"

  if [[ "$USB_WRITER_VARIANT" == "live" ]]; then
    live_mount_dir="$mount_dir/live"
  else
    live_mount_dir="$mount_dir/pve-thin-client/live"
  fi

  install -d -m 0755 \
    "$mount_dir/boot/grub" \
    "$live_mount_dir" \
    "$mount_dir/pve-dcv-integration"
  install -d -m 0755 "$mount_dir/pve-thin-client"

  install -m 0644 "$ASSET_DIR/vmlinuz" "$live_mount_dir/vmlinuz"
  install -m 0644 "$ASSET_DIR/initrd.img" "$live_mount_dir/initrd.img"
  install -m 0644 "$ASSET_DIR/filesystem.squashfs" "$live_mount_dir/filesystem.squashfs"
  install -m 0644 "$ASSET_DIR/SHA256SUMS" "$live_mount_dir/SHA256SUMS"

  rsync -rlt --delete \
    --no-owner \
    --no-group \
    --no-perms \
    --exclude 'live-build' \
    "$REPO_ROOT/thin-client-assistant/" "$mount_dir/pve-dcv-integration/thin-client-assistant/"
  rsync -rlt \
    --no-owner \
    --no-group \
    --no-perms \
    "$REPO_ROOT/docs/" "$mount_dir/pve-dcv-integration/docs/"
  install -m 0644 "$REPO_ROOT/README.md" "$mount_dir/pve-dcv-integration/README.md"
  install -m 0644 "$REPO_ROOT/LICENSE" "$mount_dir/pve-dcv-integration/LICENSE"
  install -m 0644 "$REPO_ROOT/CHANGELOG.md" "$mount_dir/pve-dcv-integration/CHANGELOG.md"
  if [[ "$USB_WRITER_VARIANT" == "installer" ]]; then
    install -m 0755 "$REPO_ROOT/thin-client-assistant/usb/start-installer-menu.sh" "$mount_dir/start-installer-menu.sh"
  fi
  if [[ -f "$GRUB_BACKGROUND_SRC" ]]; then
    install -m 0644 "$GRUB_BACKGROUND_SRC" "$mount_dir/boot/grub/background.jpg"
  fi
  write_usb_preset "$mount_dir"
  if [[ "$USB_WRITER_VARIANT" == "live" ]]; then
    write_live_state_config "$mount_dir"
  fi
  write_usb_manifest "$mount_dir"
  if [[ "$USB_WRITER_VARIANT" == "live" ]]; then
    hostname_value="beagle-live"
    network_mode="dhcp"
    network_static_address=""
    network_static_prefix="24"
    network_gateway=""
    network_interface="eth0"

    if [[ -f "$mount_dir/pve-thin-client/state/thinclient.conf" ]]; then
      hostname_value="$(sed -n 's/^HOSTNAME=//p' "$mount_dir/pve-thin-client/state/thinclient.conf" | head -n1)"
      [[ -n "$hostname_value" ]] || hostname_value="beagle-live"
    fi
    if [[ -f "$mount_dir/pve-thin-client/state/network.env" ]]; then
      network_mode="$(sed -n 's/^NETWORK_MODE=//p' "$mount_dir/pve-thin-client/state/network.env" | head -n1)"
      network_static_address="$(sed -n 's/^STATIC_IP=//p' "$mount_dir/pve-thin-client/state/network.env" | head -n1)"
      network_static_prefix="$(sed -n 's/^STATIC_PREFIX=//p' "$mount_dir/pve-thin-client/state/network.env" | head -n1)"
      network_gateway="$(sed -n 's/^GATEWAY=//p' "$mount_dir/pve-thin-client/state/network.env" | head -n1)"
      network_interface="$(sed -n 's/^INTERFACE=//p' "$mount_dir/pve-thin-client/state/network.env" | head -n1)"
    fi
    [[ -n "$network_static_prefix" ]] || network_static_prefix="24"
    [[ -n "$network_interface" ]] || network_interface="eth0"
    runtime_ip_args="$(boot_ip_arg "$network_mode" "$network_static_address" "$network_static_prefix" "$network_gateway" "$hostname_value" "$network_interface")"

cat > "$mount_dir/boot/grub/grub.cfg" <<EOF
insmod part_gpt
insmod fat
terminal_output console
set default=0
set timeout=5

menuentry 'Beagle OS Live' {
  search --no-floppy --fs-uuid --set=root ${usb_uuid}
  linux /live/vmlinuz boot=live components username=thinclient hostname=${hostname_value} live-media=/dev/disk/by-uuid/${usb_uuid} live-media-path=/live live-media-timeout=10 ignore_uuid ${runtime_ip_args} quiet splash loglevel=3 systemd.show_status=0 systemd.gpt_auto=0 vt.global_cursor_default=0 console=tty0 console=ttyS0,115200n8 plymouth.ignore-serial-consoles pve_thin_client.mode=runtime
  initrd /live/initrd.img
}

menuentry 'Beagle OS Live (safe mode)' {
  search --no-floppy --fs-uuid --set=root ${usb_uuid}
  linux /live/vmlinuz boot=live components username=thinclient hostname=${hostname_value} live-media=/dev/disk/by-uuid/${usb_uuid} live-media-path=/live live-media-timeout=10 ignore_uuid ${runtime_ip_args} loglevel=7 systemd.show_status=1 systemd.gpt_auto=0 vt.global_cursor_default=0 console=tty0 console=ttyS0,115200n8 plymouth.enable=0 nomodeset irqpoll pci=nomsi noapic pve_thin_client.mode=runtime
  initrd /live/initrd.img
}

menuentry 'Beagle OS Live (legacy IRQ mode)' {
  search --no-floppy --fs-uuid --set=root ${usb_uuid}
  linux /live/vmlinuz boot=live components username=thinclient hostname=${hostname_value} live-media=/dev/disk/by-uuid/${usb_uuid} live-media-path=/live live-media-timeout=10 ignore_uuid ${runtime_ip_args} loglevel=7 systemd.show_status=1 systemd.gpt_auto=0 vt.global_cursor_default=0 console=tty0 console=ttyS0,115200n8 plymouth.enable=0 nomodeset irqpoll noapic nolapic pve_thin_client.mode=runtime
  initrd /live/initrd.img
}
EOF
  else
    # Preset-specific installer media should boot straight into the text
    # installer path. The installer stick itself is TUI-only; there is no
    # graphical installer session on USB media anymore.
    if [[ -n "${PVE_THIN_CLIENT_PRESET_B64:-}" || -n "${PVE_THIN_CLIENT_PRESET_NAME:-}" ]]; then
      grub_default_index="0"
      grub_timeout="0"
    fi

    cat > "$mount_dir/boot/grub/grub.cfg" <<EOF
terminal_output console
set default=${grub_default_index}
set timeout=${grub_timeout}
set gfxpayload=text

menuentry 'Beagle OS Installer' {
  linux /pve-thin-client/live/vmlinuz boot=live components username=thinclient hostname=beagle-installer live-media=/dev/disk/by-uuid/${usb_uuid} live-media-path=/pve-thin-client/live live-media-timeout=10 ip=dhcp console=tty0 console=ttyS0,115200n8 systemd.gpt_auto=0 plymouth.ignore-serial-consoles systemd.unit=multi-user.target systemd.mask=pve-thin-client-installer-gui.service systemd.mask=pve-thin-client-runtime.service pve_thin_client.mode=installer pve_thin_client.installer_ui=text pve_thin_client.no_x11=1
  initrd /pve-thin-client/live/initrd.img
}

menuentry 'Beagle OS Installer (compatibility mode)' {
  linux /pve-thin-client/live/vmlinuz boot=live components username=thinclient hostname=beagle-installer live-media=/dev/disk/by-uuid/${usb_uuid} live-media-path=/pve-thin-client/live live-media-timeout=10 ip=dhcp console=tty0 console=ttyS0,115200n8 loglevel=7 systemd.show_status=1 systemd.gpt_auto=0 plymouth.enable=0 nomodeset irqpoll pci=nomsi noapic systemd.unit=multi-user.target systemd.mask=pve-thin-client-installer-gui.service systemd.mask=pve-thin-client-runtime.service pve_thin_client.mode=installer pve_thin_client.installer_ui=text pve_thin_client.no_x11=1
  initrd /pve-thin-client/live/initrd.img
}

menuentry 'Beagle OS Installer (legacy IRQ mode)' {
  linux /pve-thin-client/live/vmlinuz boot=live components username=thinclient hostname=beagle-installer live-media=/dev/disk/by-uuid/${usb_uuid} live-media-path=/pve-thin-client/live live-media-timeout=10 ip=dhcp console=tty0 console=ttyS0,115200n8 loglevel=7 systemd.show_status=1 systemd.gpt_auto=0 plymouth.enable=0 nomodeset irqpoll noapic nolapic systemd.unit=multi-user.target systemd.mask=pve-thin-client-installer-gui.service systemd.mask=pve-thin-client-runtime.service pve_thin_client.mode=installer pve_thin_client.installer_ui=text pve_thin_client.no_x11=1
  initrd /pve-thin-client/live/initrd.img
}

menuentry 'Boot from local disk' {
  exit
}
EOF
  fi

  grub-install --target=i386-pc --boot-directory="$mount_dir/boot" "$TARGET_DEVICE"
  grub-install \
    --target=x86_64-efi \
    --efi-directory="$mount_dir" \
    --boot-directory="$mount_dir/boot" \
    --removable \
    --no-nvram

  (
    cd "$live_mount_dir"
    sha256sum -c SHA256SUMS
  )

  sync
}
