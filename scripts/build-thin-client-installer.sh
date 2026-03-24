#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LB_TEMPLATE_DIR="$ROOT_DIR/thin-client-assistant/live-build"
BUILD_DIR="${THINCLIENT_BUILD_DIR:-$ROOT_DIR/.build/pve-thin-client-live-build}"
DIST_DIR="${THINCLIENT_DIST_DIR:-$ROOT_DIR/dist/pve-thin-client-installer}"
THINCLIENT_ARCH="${THINCLIENT_ARCH:-amd64}"
OWNER_UID="${SUDO_UID:-$(id -u)}"
OWNER_GID="${SUDO_GID:-$(id -g)}"
MOONLIGHT_URL="${PVE_THIN_CLIENT_MOONLIGHT_URL:-https://github.com/moonlight-stream/moonlight-qt/releases/download/v6.1.0/Moonlight-6.1.0-x86_64.AppImage}"
GRUB_BACKGROUND_SRC="$ROOT_DIR/thin-client-assistant/usb/assets/grub-background.jpg"
ROOTFS_STAGE_DIR="$BUILD_DIR/rootfs-stage"
THINCLIENT_USER="thinclient"
THINCLIENT_PASSWORD="thinclient"
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

ensure_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi

  exec sudo THINCLIENT_ARCH="$THINCLIENT_ARCH" "$0" "$@"
}

disable_proxmox_enterprise_repo() {
  local found=0
  local file

  while IFS= read -r file; do
    grep -q 'enterprise.proxmox.com' "$file" || continue
    cp "$file" "$file.beagle-backup"
    awk '!/enterprise\.proxmox\.com/' "$file.beagle-backup" > "$file"
    found=1
  done < <(find /etc/apt -maxdepth 2 -type f \( -name '*.list' -o -name '*.sources' \) 2>/dev/null)

  return $(( ! found ))
}

restore_proxmox_enterprise_repo() {
  local backup original

  while IFS= read -r backup; do
    original="${backup%.beagle-backup}"
    mv "$backup" "$original"
  done < <(find /etc/apt -maxdepth 2 -type f -name '*.beagle-backup' 2>/dev/null)
}

apt_update_with_proxmox_fallback() {
  if apt-get update; then
    return 0
  fi

  if ! disable_proxmox_enterprise_repo; then
    echo "apt-get update failed and no Proxmox enterprise repository fallback was available." >&2
    exit 1
  fi

  if ! apt-get update; then
    restore_proxmox_enterprise_repo
    exit 1
  fi
  restore_proxmox_enterprise_repo
}

ensure_root "$@"
apt_update_with_proxmox_fallback
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  live-build \
  debootstrap \
  squashfs-tools \
  xorriso \
  grub-pc-bin \
  grub-efi-amd64-bin \
  dosfstools \
  mtools \
  rsync \
  curl \
  ca-certificates

build_manual_iso() {
  local iso_root grub_cfg iso_output iso_output_short legacy_output legacy_output_short

  iso_root="$(mktemp -d)"
  iso_output="$DIST_DIR/beagle-os-installer-${THINCLIENT_ARCH}.iso"
  iso_output_short="$DIST_DIR/beagle-os-installer.iso"
  legacy_output="$DIST_DIR/pve-thin-client-installer-${THINCLIENT_ARCH}.iso"
  legacy_output_short="$DIST_DIR/pve-thin-client-installer.iso"
  grub_cfg="$iso_root/boot/grub/grub.cfg"

  cleanup_iso_root() {
    rm -rf "$iso_root"
  }
  trap cleanup_iso_root RETURN

  install -d -m 0755 "$iso_root/boot/grub" "$iso_root/live"
  install -m 0644 "$DIST_DIR/live/vmlinuz" "$iso_root/live/vmlinuz"
  install -m 0644 "$DIST_DIR/live/initrd.img" "$iso_root/live/initrd.img"
  install -m 0644 "$DIST_DIR/live/filesystem.squashfs" "$iso_root/live/filesystem.squashfs"
  install -m 0644 "$DIST_DIR/live/SHA256SUMS" "$iso_root/live/SHA256SUMS"
  if [[ -f "$GRUB_BACKGROUND_SRC" ]]; then
    install -m 0644 "$GRUB_BACKGROUND_SRC" "$iso_root/boot/grub/background.jpg"
  fi

  cat > "$grub_cfg" <<'EOF'
set default=0
set timeout_style=menu
set timeout=5

menuentry 'Beagle OS Installer' {
  linux /live/vmlinuz boot=live components username=thinclient hostname=beagle-installer ip=dhcp quiet loglevel=3 systemd.show_status=0 vt.global_cursor_default=0 splash pve_thin_client.mode=installer
  initrd /live/initrd.img
}

menuentry 'Beagle OS Installer (compatibility mode)' {
  linux /live/vmlinuz boot=live components username=thinclient hostname=beagle-installer ip=dhcp quiet loglevel=3 systemd.show_status=0 vt.global_cursor_default=0 splash nomodeset irqpoll pci=nomsi noapic pve_thin_client.mode=installer
  initrd /live/initrd.img
}

menuentry 'Beagle OS Installer (legacy IRQ mode)' {
  linux /live/vmlinuz boot=live components username=thinclient hostname=beagle-installer ip=dhcp quiet loglevel=3 systemd.show_status=0 vt.global_cursor_default=0 splash nomodeset irqpoll noapic nolapic pve_thin_client.mode=installer
  initrd /live/initrd.img
}
EOF

  grub-mkrescue -o "$iso_output" "$iso_root" -- -volid "BEAGLE_OS" >/dev/null
  install -m 0644 "$iso_output" "$iso_output_short"
  install -m 0644 "$iso_output" "$legacy_output"
  install -m 0644 "$iso_output" "$legacy_output_short"
}

prepare_rootfs_stage() {
  rm -rf "$ROOTFS_STAGE_DIR"
  install -d -m 0755 "$ROOTFS_STAGE_DIR"

  rsync -a --delete \
    --exclude proc/ \
    --exclude sys/ \
    --exclude dev/ \
    --exclude run/ \
    --exclude tmp/ \
    --exclude boot/ \
    "$BUILD_DIR/chroot/" "$ROOTFS_STAGE_DIR/"

  # live-build can fail before chroot includes are copied into the rootfs.
  # Normalize ownership here so the staged filesystem matches a real image.
  rsync -a --chown=root:root "$BUILD_DIR/config/includes.chroot/" "$ROOTFS_STAGE_DIR/"

  install -d -m 1777 "$ROOTFS_STAGE_DIR/tmp"
  install -d -m 0755 \
    "$ROOTFS_STAGE_DIR/proc" \
    "$ROOTFS_STAGE_DIR/sys" \
    "$ROOTFS_STAGE_DIR/dev" \
    "$ROOTFS_STAGE_DIR/run"

  chroot "$ROOTFS_STAGE_DIR" /bin/sh -lc "
    id '$THINCLIENT_USER' >/dev/null 2>&1 || \
      useradd -m -s /usr/local/bin/pve-thin-client-login-shell -G audio,video,plugdev,users,netdev '$THINCLIENT_USER'
    usermod -s /usr/local/bin/pve-thin-client-login-shell '$THINCLIENT_USER'
    echo '$THINCLIENT_USER:$THINCLIENT_PASSWORD' | chpasswd
    install -d -m 0755 -o '$THINCLIENT_USER' -g '$THINCLIENT_USER' '/home/$THINCLIENT_USER'
  "

  if [[ -e "$ROOTFS_STAGE_DIR/etc/sudoers.d" ]]; then
    chown root:root "$ROOTFS_STAGE_DIR/etc/sudoers.d"
    chmod 0755 "$ROOTFS_STAGE_DIR/etc/sudoers.d"
  fi
  if [[ -e "$ROOTFS_STAGE_DIR/etc/sudoers.d/pve-thin-client" ]]; then
    chown root:root "$ROOTFS_STAGE_DIR/etc/sudoers.d/pve-thin-client"
    chmod 0440 "$ROOTFS_STAGE_DIR/etc/sudoers.d/pve-thin-client"
  fi

  rm -f "$ROOTFS_STAGE_DIR/etc/systemd/system/multi-user.target.wants/pve-thin-client-installer-menu.service"
  systemctl --root="$ROOTFS_STAGE_DIR" enable \
    pve-thin-client-installer-gui.service \
    pve-thin-client-runtime.service \
    systemd-networkd.service \
    systemd-networkd-wait-online.service \
    ssh.service \
    getty@tty1.service >/dev/null
}

build_live_assets_from_stage() {
  local kernel_image initrd_image

  mapfile -t kernel_images < <(find "$BUILD_DIR/chroot/boot" -maxdepth 1 -type f -name 'vmlinuz-*' | sort)
  mapfile -t initrd_images < <(find "$BUILD_DIR/chroot/boot" -maxdepth 1 -type f -name 'initrd.img-*' | sort)

  if [[ "${#kernel_images[@]}" -eq 0 || "${#initrd_images[@]}" -eq 0 ]]; then
    echo "Thin client build did not produce a bootable kernel and initrd." >&2
    exit "${BUILD_RC:-1}"
  fi

  kernel_image="${kernel_images[0]}"
  initrd_image="${initrd_images[0]}"

  prepare_rootfs_stage

  install -m 0644 "$kernel_image" "$DIST_DIR/live/vmlinuz"
  install -m 0644 "$initrd_image" "$DIST_DIR/live/initrd.img"
  mksquashfs "$ROOTFS_STAGE_DIR" "$DIST_DIR/live/filesystem.squashfs.new" -comp xz -noappend >/dev/null
  mv "$DIST_DIR/live/filesystem.squashfs.new" "$DIST_DIR/live/filesystem.squashfs"

  (
    cd "$DIST_DIR/live"
    sha256sum vmlinuz initrd.img filesystem.squashfs > SHA256SUMS
  )
}

stage_moonlight_assets() {
  local work_dir target_dir wrapper_path

  work_dir="$(mktemp -d)"
  target_dir="$BUILD_DIR/config/includes.chroot/opt/moonlight"
  wrapper_path="$BUILD_DIR/config/includes.chroot/usr/local/bin/moonlight"

  cleanup_stage() {
    rm -rf "$work_dir"
  }
  trap cleanup_stage RETURN

  curl -fL \
    --retry 8 \
    --retry-delay 3 \
    --retry-connrefused \
    --continue-at - \
    --speed-limit 5000 \
    --speed-time 30 \
    -o "$work_dir/Moonlight.AppImage" \
    "$MOONLIGHT_URL"

  chmod +x "$work_dir/Moonlight.AppImage"
  (
    cd "$work_dir"
    ./Moonlight.AppImage --appimage-extract >/dev/null
  )

  rm -rf "$target_dir"
  install -d -m 0755 "$target_dir" "$(dirname "$wrapper_path")"
  cp -a "$work_dir/squashfs-root/." "$target_dir/"

  cat > "$wrapper_path" <<'EOF'
#!/bin/sh
set -eu

APPDIR="/opt/moonlight"
export APPDIR
export QT_PLUGIN_PATH="${APPDIR}/usr/plugins"
export QML2_IMPORT_PATH="${APPDIR}/usr/qml"
export QT_XKB_CONFIG_ROOT="/usr/share/X11/xkb"
export LD_LIBRARY_PATH="${APPDIR}/usr/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

exec "${APPDIR}/usr/bin/moonlight" "$@"
EOF
  chmod 0755 "$wrapper_path"
}

rm -rf "$BUILD_DIR"
install -d -m 0755 "$BUILD_DIR" "$DIST_DIR/live"
rsync -a --delete "$LB_TEMPLATE_DIR/" "$BUILD_DIR/"

install -d -m 0755 "$BUILD_DIR/config/includes.chroot/usr/local/lib"
rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "$ROOT_DIR/thin-client-assistant/" \
  "$BUILD_DIR/config/includes.chroot/usr/local/lib/pve-thin-client/"
stage_moonlight_assets
chmod 0755 "$BUILD_DIR"

pushd "$BUILD_DIR" >/dev/null
chmod +x auto/config
THINCLIENT_ARCH="$THINCLIENT_ARCH" ./auto/config
lb clean --purge || true
BUILD_RC=0
if ! lb build; then
  BUILD_RC=$?
fi
popd >/dev/null

build_live_assets_from_stage
build_manual_iso

chown -R "$OWNER_UID:$OWNER_GID" "$DIST_DIR"
chmod -R u+rwX,go+rX "$DIST_DIR"
find "$DIST_DIR" -type f -name '*.sh' -exec chmod 0755 {} +

echo "Built Beagle OS installer assets in $DIST_DIR"
