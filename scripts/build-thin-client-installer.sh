#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/disk_guardrails.sh"
LB_TEMPLATE_DIR="$ROOT_DIR/thin-client-assistant/live-build"
BUILD_DIR="${THINCLIENT_BUILD_DIR:-$ROOT_DIR/.build/pve-thin-client-live-build}"
DIST_DIR="${THINCLIENT_DIST_DIR:-$ROOT_DIR/dist/pve-thin-client-installer}"
THINCLIENT_ARCH="${THINCLIENT_ARCH:-amd64}"
PROJECT_VERSION="$(tr -d ' \n\r' < "$ROOT_DIR/VERSION" 2>/dev/null || echo dev)"
THINCLIENT_MIN_BUILD_FREE_GIB="${BEAGLE_THINCLIENT_MIN_BUILD_FREE_GIB:-16}"
THINCLIENT_MIN_DIST_FREE_GIB="${BEAGLE_THINCLIENT_MIN_DIST_FREE_GIB:-4}"
THINCLIENT_LB_BUILD_ATTEMPTS="${BEAGLE_THINCLIENT_LB_BUILD_ATTEMPTS:-2}"
THINCLIENT_SKIP_MANUAL_ISO="${BEAGLE_THINCLIENT_SKIP_MANUAL_ISO:-0}"
OWNER_UID="${SUDO_UID:-$(id -u)}"
OWNER_GID="${SUDO_GID:-$(id -g)}"
BEAGLE_STREAM_CLIENT_DEFAULT_URL="https://github.com/meinzeug/beagle-stream-client/releases/download/beagle-phase-a/BeagleStream-latest-x86_64.AppImage"
BEAGLE_STREAM_CLIENT_URL="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_URL:-${BEAGLE_STREAM_CLIENT_URL:-$BEAGLE_STREAM_CLIENT_DEFAULT_URL}}"
GRUB_BACKGROUND_SRC="$ROOT_DIR/thin-client-assistant/usb/assets/grub-background.jpg"
ROOTFS_STAGE_DIR="$BUILD_DIR/rootfs-stage"
THINCLIENT_USER="thinclient"
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

ensure_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi

  exec sudo \
    THINCLIENT_ARCH="$THINCLIENT_ARCH" \
    BEAGLE_THINCLIENT_MIN_BUILD_FREE_GIB="$THINCLIENT_MIN_BUILD_FREE_GIB" \
    BEAGLE_THINCLIENT_MIN_DIST_FREE_GIB="$THINCLIENT_MIN_DIST_FREE_GIB" \
    "$0" "$@"
}

disable_beagle_enterprise_repo() {
  local found=0
  local file

  while IFS= read -r file; do
    grep -q 'enterprise.beagle.com' "$file" || continue
    cp "$file" "$file.beagle-backup"
    awk '!/enterprise\.beagle\.com/' "$file.beagle-backup" > "$file"
    found=1
  done < <(find /etc/apt -maxdepth 2 -type f \( -name '*.list' -o -name '*.sources' \) 2>/dev/null)

  return $(( ! found ))
}

restore_beagle_enterprise_repo() {
  local backup original

  while IFS= read -r backup; do
    original="${backup%.beagle-backup}"
    mv "$backup" "$original"
  done < <(find /etc/apt -maxdepth 2 -type f -name '*.beagle-backup' 2>/dev/null)
}

apt_update_with_beagle_fallback() {
  if apt-get update; then
    return 0
  fi

  if ! disable_beagle_enterprise_repo; then
    echo "apt-get update failed and no Beagle enterprise repository fallback was available." >&2
    exit 1
  fi

  if ! apt-get update; then
    restore_beagle_enterprise_repo
    exit 1
  fi
  restore_beagle_enterprise_repo
}

ensure_root "$@"
ensure_free_space_with_cleanup \
  "thin client live-build workspace" \
  "$BUILD_DIR" \
  "$((THINCLIENT_MIN_BUILD_FREE_GIB * 1024 * 1024))" \
  "$ROOT_DIR" \
  "$BUILD_DIR" \
  "$DIST_DIR"
ensure_free_space_with_cleanup \
  "thin client installer artifacts" \
  "$DIST_DIR" \
  "$((THINCLIENT_MIN_DIST_FREE_GIB * 1024 * 1024))" \
  "$ROOT_DIR" \
  "$BUILD_DIR" \
  "$DIST_DIR"
apt_update_with_beagle_fallback
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  live-build \
  debootstrap \
  squashfs-tools \
  xorriso \
  grub2-common \
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
insmod jpeg
insmod gfxterm
terminal_output gfxterm
if [ -f /boot/grub/background.jpg ]; then
  background_image /boot/grub/background.jpg
fi
set color_normal=white/black
set color_highlight=cyan/black
set default=0
set timeout_style=menu
set timeout=5
set gfxpayload=text

menuentry 'Beagle OS Installer' {
  linux /live/vmlinuz boot=live components username=thinclient hostname=beagle-installer ip=dhcp console=tty0 console=ttyS0,115200n8 systemd.gpt_auto=0 plymouth.ignore-serial-consoles systemd.unit=multi-user.target systemd.mask=pve-thin-client-installer-gui.service systemd.mask=pve-thin-client-runtime.service pve_thin_client.mode=installer pve_thin_client.installer_ui=text pve_thin_client.no_x11=1
  initrd /live/initrd.img
}

menuentry 'Beagle OS Installer (compatibility mode)' {
  linux /live/vmlinuz boot=live components username=thinclient hostname=beagle-installer ip=dhcp console=tty0 console=ttyS0,115200n8 loglevel=7 systemd.show_status=1 systemd.gpt_auto=0 plymouth.enable=0 nomodeset irqpoll pci=nomsi noapic systemd.unit=multi-user.target systemd.mask=pve-thin-client-installer-gui.service systemd.mask=pve-thin-client-runtime.service pve_thin_client.mode=installer pve_thin_client.installer_ui=text pve_thin_client.no_x11=1
  initrd /live/initrd.img
}

menuentry 'Beagle OS Installer (legacy IRQ mode)' {
  linux /live/vmlinuz boot=live components username=thinclient hostname=beagle-installer ip=dhcp console=tty0 console=ttyS0,115200n8 loglevel=7 systemd.show_status=1 systemd.gpt_auto=0 plymouth.enable=0 nomodeset irqpoll noapic nolapic systemd.unit=multi-user.target systemd.mask=pve-thin-client-installer-gui.service systemd.mask=pve-thin-client-runtime.service pve_thin_client.mode=installer pve_thin_client.installer_ui=text pve_thin_client.no_x11=1
  initrd /live/initrd.img
}
EOF

  grub-mkrescue -o "$iso_output" "$iso_root" -- -volid "BEAGLE_OS" >/dev/null
  install -m 0644 "$iso_output" "$iso_output_short"
  install -m 0644 "$iso_output" "$legacy_output"
  install -m 0644 "$iso_output" "$legacy_output_short"
}

prepare_rootfs_stage() {
  local script_path unit_path

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
  # Keep thin-client assets in sync with the repo even when the cached chroot is stale.
  rsync -a --delete --chown=root:root \
    "$ROOT_DIR/thin-client-assistant/runtime/" \
    "$ROOTFS_STAGE_DIR/usr/local/lib/pve-thin-client/runtime/"
  rsync -a --delete --chown=root:root \
    "$ROOT_DIR/thin-client-assistant/installer/" \
    "$ROOTFS_STAGE_DIR/usr/local/lib/pve-thin-client/installer/"
  rsync -a --delete --chown=root:root \
    "$ROOT_DIR/thin-client-assistant/usb/" \
    "$ROOTFS_STAGE_DIR/usr/local/lib/pve-thin-client/usb/"
  rsync -a --delete --chown=root:root \
    "$ROOT_DIR/thin-client-assistant/templates/" \
    "$ROOTFS_STAGE_DIR/usr/local/lib/pve-thin-client/templates/"
  install -D -m 0755 \
    "$ROOT_DIR/scripts/lib/trace-guard.sh" \
    "$ROOTFS_STAGE_DIR/usr/local/lib/scripts/lib/trace-guard.sh"
  install -D -m 0644 \
    "$ROOT_DIR/thin-client-assistant/systemd/beagle-thin-client-prepare.service" \
    "$ROOTFS_STAGE_DIR/etc/systemd/system/beagle-thin-client-prepare.service"
  install -D -m 0644 \
    "$ROOT_DIR/thin-client-assistant/systemd/pve-thin-client-prepare.service" \
    "$ROOTFS_STAGE_DIR/etc/systemd/system/pve-thin-client-prepare.service"
  install -D -m 0644 \
    "$ROOT_DIR/thin-client-assistant/systemd/pve-thin-client-network-menu.service" \
    "$ROOTFS_STAGE_DIR/etc/systemd/system/pve-thin-client-network-menu.service"
  install -d -m 0755 "$ROOTFS_STAGE_DIR/etc/beagle-os"
  cat >"$ROOTFS_STAGE_DIR/etc/beagle-os/build-info" <<EOF
PROJECT=beagle-os
PROJECT_VERSION=$PROJECT_VERSION
BUILD_FLAVOR=thin-client-live
BUILD_ARCH=$THINCLIENT_ARCH
BUILD_CREATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
  for script_path in \
    "$ROOT_DIR/beagle-os/overlay/usr/local/sbin/beagle-endpoint-report" \
    "$ROOT_DIR/beagle-os/overlay/usr/local/sbin/beagle-endpoint-dispatch" \
    "$ROOT_DIR/beagle-os/overlay/usr/local/sbin/beagle-healthcheck" \
    "$ROOT_DIR/beagle-os/overlay/usr/local/sbin/beagle-support-bundle" \
    "$ROOT_DIR/beagle-os/overlay/usr/local/sbin/beagle-identity-apply" \
    "$ROOT_DIR/beagle-os/overlay/usr/local/sbin/beagle-egress-apply" \
    "$ROOT_DIR/beagle-os/overlay/usr/local/sbin/beagle-update-client"
  do
    install -D -m 0755 "$script_path" "$ROOTFS_STAGE_DIR/usr/local/sbin/$(basename "$script_path")"
  done
  for unit_path in \
    "$ROOT_DIR/beagle-os/overlay/etc/systemd/system/beagle-endpoint-report.service" \
    "$ROOT_DIR/beagle-os/overlay/etc/systemd/system/beagle-endpoint-report.timer" \
    "$ROOT_DIR/beagle-os/overlay/etc/systemd/system/beagle-endpoint-dispatch.service" \
    "$ROOT_DIR/beagle-os/overlay/etc/systemd/system/beagle-endpoint-dispatch.timer" \
    "$ROOT_DIR/beagle-os/overlay/etc/systemd/system/beagle-healthcheck.service" \
    "$ROOT_DIR/beagle-os/overlay/etc/systemd/system/beagle-healthcheck.timer" \
    "$ROOT_DIR/beagle-os/overlay/etc/systemd/system/beagle-update-scan.service" \
    "$ROOT_DIR/beagle-os/overlay/etc/systemd/system/beagle-update-scan.timer" \
    "$ROOT_DIR/beagle-os/overlay/etc/systemd/system/beagle-update-confirm.service"
  do
    install -D -m 0644 "$unit_path" "$ROOTFS_STAGE_DIR/etc/systemd/system/$(basename "$unit_path")"
  done

  install -d -m 1777 "$ROOTFS_STAGE_DIR/tmp"
  install -d -m 0755 \
    "$ROOTFS_STAGE_DIR/proc" \
    "$ROOTFS_STAGE_DIR/sys" \
    "$ROOTFS_STAGE_DIR/dev" \
    "$ROOTFS_STAGE_DIR/run"

  chroot "$ROOTFS_STAGE_DIR" /bin/sh -lc "
    id '$THINCLIENT_USER' >/dev/null 2>&1 || \
      useradd -m -s /usr/local/bin/pve-thin-client-login-shell -G audio,video,input,render,plugdev,users,netdev '$THINCLIENT_USER'
    usermod -s /usr/local/bin/pve-thin-client-login-shell '$THINCLIENT_USER'
    printf '%s:%s\n' '$THINCLIENT_USER' 'thinclient' | chpasswd >/dev/null 2>&1 || true
    usermod -U '$THINCLIENT_USER' >/dev/null 2>&1 || passwd -u '$THINCLIENT_USER' >/dev/null 2>&1 || true
    printf 'root:%s\n' 'THINCLIENT' | chpasswd >/dev/null 2>&1 || true
    usermod -U root >/dev/null 2>&1 || passwd -u root >/dev/null 2>&1 || true
    install -d -m 0755 -o '$THINCLIENT_USER' -g '$THINCLIENT_USER' '/home/$THINCLIENT_USER'
  "

  chroot "$ROOTFS_STAGE_DIR" /bin/sh -lc "
    command -v grub-install >/dev/null 2>&1
    command -v mkfs.vfat >/dev/null 2>&1
    command -v parted >/dev/null 2>&1
  "

  if [[ -e "$ROOTFS_STAGE_DIR/etc/sudoers.d" ]]; then
    chown root:root "$ROOTFS_STAGE_DIR/etc/sudoers.d"
    chmod 0755 "$ROOTFS_STAGE_DIR/etc/sudoers.d"
  fi
  if [[ -e "$ROOTFS_STAGE_DIR/etc/sudoers.d/pve-thin-client" ]]; then
    chown root:root "$ROOTFS_STAGE_DIR/etc/sudoers.d/pve-thin-client"
    chmod 0440 "$ROOTFS_STAGE_DIR/etc/sudoers.d/pve-thin-client"
  fi

  enable_rootfs_units \
    beagle-endpoint-report.timer \
    beagle-endpoint-dispatch.timer \
    beagle-healthcheck.timer \
    beagle-update-scan.timer \
    beagle-update-confirm.service \
    beagle-runtime-heartbeat.timer \
    beagle-usb-tunnel.service \
    pve-thin-client-network-menu.service \
    beagle-thin-client-prepare.service \
    pve-thin-client-runtime.service \
    pve-thin-client-installer-menu.service \
    pve-thin-client-installer-menu-serial.service \
    systemd-networkd.service \
    systemd-networkd-wait-online.service \
    ssh.service \
    getty@tty1.service

  ensure_rootfs_wants_link beagle-thin-client-prepare.service multi-user.target
  ensure_rootfs_wants_link pve-thin-client-runtime.service multi-user.target
  ensure_rootfs_wants_link pve-thin-client-installer-menu.service multi-user.target
  ensure_rootfs_wants_link pve-thin-client-installer-menu-serial.service multi-user.target
}

enable_rootfs_units() {
  local unit unit_path had_units=0
  local -a units_to_enable=()

  for unit in "$@"; do
    unit_path="$ROOTFS_STAGE_DIR/etc/systemd/system/$unit"
    if [[ -e "$unit_path" || -e "$ROOTFS_STAGE_DIR/usr/lib/systemd/system/$unit" || -e "$ROOTFS_STAGE_DIR/lib/systemd/system/$unit" ]]; then
      units_to_enable+=("$unit")
      had_units=1
    fi
  done

  if [[ "$had_units" -eq 1 ]]; then
    systemctl --root="$ROOTFS_STAGE_DIR" enable "${units_to_enable[@]}" >/dev/null
  fi
}

ensure_rootfs_wants_link() {
  local unit="$1"
  local target="$2"
  local unit_path=""

  if [[ -e "$ROOTFS_STAGE_DIR/etc/systemd/system/$unit" ]]; then
    unit_path="/etc/systemd/system/$unit"
  elif [[ -e "$ROOTFS_STAGE_DIR/usr/lib/systemd/system/$unit" ]]; then
    unit_path="/usr/lib/systemd/system/$unit"
  elif [[ -e "$ROOTFS_STAGE_DIR/lib/systemd/system/$unit" ]]; then
    unit_path="/lib/systemd/system/$unit"
  else
    return 0
  fi

  install -d -m 0755 "$ROOTFS_STAGE_DIR/etc/systemd/system/${target}.wants"
  ln -sfn "$unit_path" "$ROOTFS_STAGE_DIR/etc/systemd/system/${target}.wants/$unit"
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

stage_beagle_stream_client_assets() {
  local work_dir target_dir beagle_stream_client_wrapper_path beagle_wrapper_path appimage_url

  work_dir="$(mktemp -d)"
  target_dir="$BUILD_DIR/config/includes.chroot/opt/beagle-stream-client"
  beagle_stream_client_wrapper_path="$BUILD_DIR/config/includes.chroot/usr/local/bin/beagle-stream-client"
  beagle_wrapper_path="$BUILD_DIR/config/includes.chroot/usr/local/bin/beagle-stream"

  cleanup_stage() {
    rm -rf "$work_dir"
  }
  trap cleanup_stage RETURN

  appimage_url="$BEAGLE_STREAM_CLIENT_URL"
  if [[ -n "$BEAGLE_STREAM_CLIENT_URL" ]]; then
    appimage_url="$BEAGLE_STREAM_CLIENT_URL"
  fi

  curl -fL \
    --retry 8 \
    --retry-delay 3 \
    --retry-connrefused \
    --continue-at - \
    --speed-limit 5000 \
    --speed-time 30 \
    -o "$work_dir/BeagleStream.AppImage" \
    "$appimage_url"

  chmod +x "$work_dir/BeagleStream.AppImage"
  (
    cd "$work_dir"
    ./BeagleStream.AppImage --appimage-extract >/dev/null
  )

  rm -rf "$target_dir"
  install -d -m 0755 "$target_dir" "$(dirname "$beagle_stream_client_wrapper_path")"
  cp -a "$work_dir/squashfs-root/." "$target_dir/"
  find "$target_dir" -type d -exec chmod 0755 {} +
  find "$target_dir" -type f -perm /111 -exec chmod 0755 {} +
  find "$target_dir" -type f ! -perm /111 -exec chmod 0644 {} +

  cat > "$beagle_stream_client_wrapper_path" <<'EOF'
#!/bin/sh
set -eu

APPDIR="/opt/beagle-stream-client"
export APPDIR
export QT_PLUGIN_PATH="${APPDIR}/usr/plugins"
export QML2_IMPORT_PATH="${APPDIR}/usr/qml"
export QT_XKB_CONFIG_ROOT="/usr/share/X11/xkb"
export LD_LIBRARY_PATH="${APPDIR}/usr/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

if [ -x "${APPDIR}/usr/bin/beagle-stream-client" ]; then
  exec "${APPDIR}/usr/bin/beagle-stream-client" "$@"
fi

exec "${APPDIR}/usr/bin/beagle-stream" "$@"
EOF
  chmod 0755 "$beagle_stream_client_wrapper_path"

  if [[ -x "$target_dir/usr/bin/beagle-stream" ]]; then
    cat > "$beagle_wrapper_path" <<'EOF'
#!/bin/sh
set -eu

APPDIR="/opt/beagle-stream-client"
export APPDIR
export QT_PLUGIN_PATH="${APPDIR}/usr/plugins"
export QML2_IMPORT_PATH="${APPDIR}/usr/qml"
export QT_XKB_CONFIG_ROOT="/usr/share/X11/xkb"
export LD_LIBRARY_PATH="${APPDIR}/usr/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

exec "${APPDIR}/usr/bin/beagle-stream" "$@"
EOF
    chmod 0755 "$beagle_wrapper_path"
  else
    rm -f "$beagle_wrapper_path"
  fi
}

cleanup_stale_build_mounts() {
  beagle_unmount_recursive_path "$BUILD_DIR/chroot"
}

cleanup_stale_build_mounts
rm -rf "$BUILD_DIR"
install -d -m 0755 "$BUILD_DIR" "$DIST_DIR/live"
rsync -a --delete "$LB_TEMPLATE_DIR/" "$BUILD_DIR/"

install -d -m 0755 "$BUILD_DIR/config/includes.chroot/usr/local/lib"
rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "$ROOT_DIR/thin-client-assistant/" \
  "$BUILD_DIR/config/includes.chroot/usr/local/lib/pve-thin-client/"
stage_beagle_stream_client_assets
chmod 0755 "$BUILD_DIR"

pushd "$BUILD_DIR" >/dev/null
chmod +x auto/config
BUILD_RC=1
attempt=1
while (( attempt <= THINCLIENT_LB_BUILD_ATTEMPTS )); do
  THINCLIENT_ARCH="$THINCLIENT_ARCH" ./auto/config
  lb clean --purge || true
  set +e
  lb build
  BUILD_RC=$?
  set -e
  if [[ "$BUILD_RC" -eq 0 ]]; then
    break
  fi
  echo "live-build attempt $attempt/$THINCLIENT_LB_BUILD_ATTEMPTS failed with status $BUILD_RC" >&2
  if (( attempt < THINCLIENT_LB_BUILD_ATTEMPTS )); then
    echo "Retrying thin-client live-build after cleanup..." >&2
    cleanup_stale_build_mounts
  fi
  attempt=$((attempt + 1))
done
if [[ "$BUILD_RC" -ne 0 ]]; then
  echo "live-build exited with status $BUILD_RC; rebuilding final live assets and installer ISO from the staged rootfs." >&2
fi
popd >/dev/null

build_live_assets_from_stage
if [[ "$THINCLIENT_SKIP_MANUAL_ISO" != "1" ]]; then
  build_manual_iso
else
  echo "Skipping thin-client installer ISO assembly; live assets were refreshed only."
fi

chown -R "$OWNER_UID:$OWNER_GID" "$DIST_DIR"
chmod -R u+rwX,go+rX "$DIST_DIR"
find "$DIST_DIR" -type f -name '*.sh' -exec chmod 0755 {} +

echo "Built Beagle OS installer assets in $DIST_DIR"
