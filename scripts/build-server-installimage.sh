#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/disk_guardrails.sh"

BUILD_DIR="${BEAGLE_SERVER_INSTALLIMAGE_BUILD_DIR:-$ROOT_DIR/.build/beagle-os-server-installimage}"
DIST_DIR="${BEAGLE_SERVER_INSTALLIMAGE_DIST_DIR:-$ROOT_DIR/dist/beagle-os-server-installimage}"
ROOTFS_DIR="$BUILD_DIR/rootfs"
STATE_DIR="$BUILD_DIR/state"
DEBIAN_RELEASE="${BEAGLE_SERVER_INSTALLIMAGE_RELEASE:-bookworm}"
DEBIAN_ARCH="${BEAGLE_SERVER_INSTALLIMAGE_ARCH:-amd64}"
DEBIAN_MIRROR="${BEAGLE_SERVER_INSTALLIMAGE_MIRROR:-https://deb.debian.org/debian}"
DEBIAN_SECURITY_MIRROR="${BEAGLE_SERVER_INSTALLIMAGE_SECURITY_MIRROR:-https://security.debian.org/debian-security}"
DEBIAN_VERSION_CODE="${BEAGLE_SERVER_INSTALLIMAGE_VERSION_CODE:-1201}"
INSTALLIMAGE_HOSTNAME="${BEAGLE_SERVER_INSTALLIMAGE_HOSTNAME:-beagle-server}"
INSTALLIMAGE_ROOT_LOGIN="${BEAGLE_SERVER_INSTALLIMAGE_ROOT_LOGIN:-yes}"
SERVER_INSTALLIMAGE_MIN_BUILD_FREE_GIB="${BEAGLE_SERVER_INSTALLIMAGE_MIN_BUILD_FREE_GIB:-8}"
SERVER_INSTALLIMAGE_MIN_DIST_FREE_GIB="${BEAGLE_SERVER_INSTALLIMAGE_MIN_DIST_FREE_GIB:-3}"
TARBALL_NAME="${BEAGLE_SERVER_INSTALLIMAGE_TARBALL_FILENAME:-Debian-${DEBIAN_VERSION_CODE}-${DEBIAN_RELEASE}-${DEBIAN_ARCH}-beagle-server.tar.gz}"
SOURCE_ARCHIVE_PATH="$ROOTFS_DIR/usr/local/share/beagle/beagle-os-source.tar.gz"
INSTALLIMAGE_FILES_DIR="$ROOT_DIR/server-installer/installimage"

CHROOT_MOUNTS=()

ensure_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi
  exec sudo \
    BEAGLE_SERVER_INSTALLIMAGE_BUILD_DIR="$BUILD_DIR" \
    BEAGLE_SERVER_INSTALLIMAGE_DIST_DIR="$DIST_DIR" \
    BEAGLE_SERVER_INSTALLIMAGE_RELEASE="$DEBIAN_RELEASE" \
    BEAGLE_SERVER_INSTALLIMAGE_ARCH="$DEBIAN_ARCH" \
    BEAGLE_SERVER_INSTALLIMAGE_MIRROR="$DEBIAN_MIRROR" \
    BEAGLE_SERVER_INSTALLIMAGE_SECURITY_MIRROR="$DEBIAN_SECURITY_MIRROR" \
    BEAGLE_SERVER_INSTALLIMAGE_VERSION_CODE="$DEBIAN_VERSION_CODE" \
    BEAGLE_SERVER_INSTALLIMAGE_HOSTNAME="$INSTALLIMAGE_HOSTNAME" \
    BEAGLE_SERVER_INSTALLIMAGE_ROOT_LOGIN="$INSTALLIMAGE_ROOT_LOGIN" \
    BEAGLE_SERVER_INSTALLIMAGE_MIN_BUILD_FREE_GIB="$SERVER_INSTALLIMAGE_MIN_BUILD_FREE_GIB" \
    BEAGLE_SERVER_INSTALLIMAGE_MIN_DIST_FREE_GIB="$SERVER_INSTALLIMAGE_MIN_DIST_FREE_GIB" \
    BEAGLE_SERVER_INSTALLIMAGE_TARBALL_FILENAME="$TARBALL_NAME" \
    "$0" "$@"
}

install_builder_dependencies() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y \
    debootstrap \
    ca-certificates \
    curl \
    rsync \
    xz-utils \
    tar \
    gnupg
}

cleanup_mounts() {
  local idx
  for (( idx=${#CHROOT_MOUNTS[@]}-1; idx>=0; idx-- )); do
    if mountpoint -q "${CHROOT_MOUNTS[$idx]}"; then
      umount "${CHROOT_MOUNTS[$idx]}" || true
    fi
  done
  CHROOT_MOUNTS=()
}

cleanup() {
  cleanup_mounts
}
trap cleanup EXIT

mount_chroot_fs() {
  mount --bind /dev "$ROOTFS_DIR/dev"
  CHROOT_MOUNTS+=("$ROOTFS_DIR/dev")
  mount -t devpts devpts "$ROOTFS_DIR/dev/pts"
  CHROOT_MOUNTS+=("$ROOTFS_DIR/dev/pts")
  mount -t proc proc "$ROOTFS_DIR/proc"
  CHROOT_MOUNTS+=("$ROOTFS_DIR/proc")
  mount -t sysfs sysfs "$ROOTFS_DIR/sys"
  CHROOT_MOUNTS+=("$ROOTFS_DIR/sys")
  mount --bind /run "$ROOTFS_DIR/run"
  CHROOT_MOUNTS+=("$ROOTFS_DIR/run")
}

run_in_chroot() {
  chroot "$ROOTFS_DIR" /usr/bin/env -i \
    HOME=/root \
    TERM="${TERM:-xterm}" \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    "$@"
}

prepare_sources_list() {
  cat >"$ROOTFS_DIR/etc/apt/sources.list" <<EOF
deb $DEBIAN_MIRROR $DEBIAN_RELEASE main contrib non-free non-free-firmware
deb $DEBIAN_MIRROR ${DEBIAN_RELEASE}-updates main contrib non-free non-free-firmware
deb $DEBIAN_SECURITY_MIRROR ${DEBIAN_RELEASE}-security main contrib non-free non-free-firmware
EOF
}

install_policy_rc_d() {
  cat >"$ROOTFS_DIR/usr/sbin/policy-rc.d" <<'EOF'
#!/bin/sh
exit 101
EOF
  chmod 0755 "$ROOTFS_DIR/usr/sbin/policy-rc.d"
}

remove_policy_rc_d() {
  rm -f "$ROOTFS_DIR/usr/sbin/policy-rc.d"
}

configure_base_system() {
  mkdir -p "$ROOTFS_DIR/etc"
  printf '%s\n' "$INSTALLIMAGE_HOSTNAME" >"$ROOTFS_DIR/etc/hostname"
  cat >"$ROOTFS_DIR/etc/hosts" <<EOF
127.0.0.1 localhost
127.0.1.1 $INSTALLIMAGE_HOSTNAME

::1 localhost ip6-localhost ip6-loopback
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
EOF
  install -d -m 0755 "$ROOTFS_DIR/etc/ssh/sshd_config.d"
  cat >"$ROOTFS_DIR/etc/ssh/sshd_config.d/99-beagle-installimage.conf" <<EOF
PermitRootLogin ${INSTALLIMAGE_ROOT_LOGIN}
PasswordAuthentication yes
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no
EOF
  install -d -m 0700 "$ROOTFS_DIR/root"
  cat >"$ROOTFS_DIR/root/README-beagle-installimage.txt" <<'EOF'
This system was installed from the Beagle installimage artifact.

- Hetzner installimage sets the installed root password to the rescue-system root password.
- Beagle host bootstrap runs automatically on first boot.
- Bootstrap logs: /var/log/beagle-installimage-bootstrap.log
- Generated Beagle web credentials: /root/beagle-firstboot-credentials.txt
EOF

  # Hetzner installimage runs sed/rm against /etc/default/grub and
  # /etc/kernel-img.conf during its grub stage. For RAID installs it also
  # expects /etc/default/mdadm and /etc/mdadm to exist before it generates
  # the array config. If these files are missing the boot loader install
  # partially fails and the system never reboots into the installed disk.
  # Seed them with safe defaults so installimage always finds a target file
  # to edit.
  install -d -m 0755 "$ROOTFS_DIR/etc/default"
  install -d -m 0755 "$ROOTFS_DIR/etc/mdadm"
  cat >"$ROOTFS_DIR/etc/default/grub" <<'EOF'
# Beagle OS installimage default grub configuration.
# Hetzner installimage rewrites these values during the grub stage.
GRUB_DEFAULT=0
GRUB_TIMEOUT=5
GRUB_DISTRIBUTOR="Beagle OS"
GRUB_CMDLINE_LINUX_DEFAULT="quiet"
GRUB_CMDLINE_LINUX="consoleblank=0"
GRUB_DISABLE_OS_PROBER=true
GRUB_TERMINAL=console
EOF
  cat >"$ROOTFS_DIR/etc/kernel-img.conf" <<'EOF'
# Beagle OS installimage kernel-img defaults.
do_symlinks = no
do_bootloader = no
do_initrd = yes
link_in_boot = no
EOF
  cat >"$ROOTFS_DIR/etc/default/mdadm" <<'EOF'
# Beagle OS installimage mdadm defaults.
# Hetzner installimage rewrites these values during its RAID stage.
START_DAEMON=true
INITRDSTART='all'
AUTO='+all'
DAEMON_OPTIONS='--syslog'
EOF
  : >"$ROOTFS_DIR/etc/mdadm/mdadm.conf"
}

bundle_source_tree() {
  mkdir -p "$(dirname "$SOURCE_ARCHIVE_PATH")"
  (
    cd "$ROOT_DIR"
    tar -czf "$SOURCE_ARCHIVE_PATH" \
      --exclude='AGENTS.md' \
      beagle-kiosk \
      beagle-host \
      beagle-os \
      core \
      docs \
      extension \
      providers \
      scripts \
      server-installer \
      thin-client-assistant \
      website \
      README.md \
      LICENSE \
      CHANGELOG.md \
      VERSION \
      .gitignore
  )
}

install_bootstrap_files() {
  install -d -m 0755 "$ROOTFS_DIR/usr/local/bin" "$ROOTFS_DIR/usr/local/sbin"
  install -d -m 0755 "$ROOTFS_DIR/etc/systemd/system/ssh.service.d"
  install -m 0755 \
    "$INSTALLIMAGE_FILES_DIR/usr/local/bin/beagle-installimage-bootstrap" \
    "$ROOTFS_DIR/usr/local/bin/beagle-installimage-bootstrap"
  install -m 0755 \
    "$INSTALLIMAGE_FILES_DIR/usr/local/sbin/beagle-ssh-hostkeys-prepare" \
    "$ROOTFS_DIR/usr/local/sbin/beagle-ssh-hostkeys-prepare"
  install -m 0755 \
    "$INSTALLIMAGE_FILES_DIR/usr/local/sbin/beagle-network-interface-heal" \
    "$ROOTFS_DIR/usr/local/sbin/beagle-network-interface-heal"
  install -m 0644 \
    "$INSTALLIMAGE_FILES_DIR/etc/systemd/system/beagle-installimage-bootstrap.service" \
    "$ROOTFS_DIR/etc/systemd/system/beagle-installimage-bootstrap.service"
  install -m 0644 \
    "$INSTALLIMAGE_FILES_DIR/etc/systemd/system/beagle-ssh-hostkeys.service" \
    "$ROOTFS_DIR/etc/systemd/system/beagle-ssh-hostkeys.service"
  install -m 0644 \
    "$INSTALLIMAGE_FILES_DIR/etc/systemd/system/beagle-network-interface-heal.service" \
    "$ROOTFS_DIR/etc/systemd/system/beagle-network-interface-heal.service"
  install -m 0644 \
    "$INSTALLIMAGE_FILES_DIR/etc/systemd/system/ssh.service.d/10-beagle-hostkeys.conf" \
    "$ROOTFS_DIR/etc/systemd/system/ssh.service.d/10-beagle-hostkeys.conf"
  run_in_chroot systemctl enable beagle-installimage-bootstrap.service >/dev/null 2>&1 || true
  run_in_chroot systemctl enable beagle-network-interface-heal.service >/dev/null 2>&1 || true
}

sanitize_rootfs() {
  rm -f "$ROOTFS_DIR"/etc/ssh/ssh_host_*_key "$ROOTFS_DIR"/etc/ssh/ssh_host_*_key.pub
  rm -f "$ROOTFS_DIR/var/lib/systemd/random-seed"
  rm -f "$ROOTFS_DIR/etc/machine-id" "$ROOTFS_DIR/var/lib/dbus/machine-id"
  : >"$ROOTFS_DIR/etc/machine-id"
  mkdir -p "$ROOTFS_DIR/var/lib/dbus"
  ln -sf /etc/machine-id "$ROOTFS_DIR/var/lib/dbus/machine-id"
  rm -rf "$ROOTFS_DIR/tmp/"* "$ROOTFS_DIR/var/tmp/"*
  run_in_chroot apt-get clean
  rm -rf "$ROOTFS_DIR/var/lib/apt/lists/"*
  rm -f "$ROOTFS_DIR/root/.bash_history"
}

create_tarball() {
  mkdir -p "$DIST_DIR"
  (
    cd "$ROOTFS_DIR"
    tar \
      --xattrs \
      --acls \
      --numeric-owner \
      --exclude='./dev/*' \
      --exclude='./proc/*' \
      --exclude='./sys/*' \
      --exclude='./run/*' \
      --exclude='./tmp/*' \
      --exclude='./var/tmp/*' \
      -czf "$DIST_DIR/$TARBALL_NAME" .
  )
}

ensure_root "$@"

ensure_free_space_with_cleanup \
  "server installimage build workspace" \
  "$BUILD_DIR" \
  "$((SERVER_INSTALLIMAGE_MIN_BUILD_FREE_GIB * 1024 * 1024))" \
  "$ROOT_DIR" \
  "$ROOT_DIR/.build" \
  "$ROOT_DIR/dist"
ensure_free_space_with_cleanup \
  "server installimage artifacts" \
  "$DIST_DIR" \
  "$((SERVER_INSTALLIMAGE_MIN_DIST_FREE_GIB * 1024 * 1024))" \
  "$ROOT_DIR" \
  "$ROOT_DIR/.build" \
  "$ROOT_DIR/dist"

install_builder_dependencies

rm -rf "$BUILD_DIR"
mkdir -p "$ROOTFS_DIR" "$STATE_DIR" "$DIST_DIR"

debootstrap --arch "$DEBIAN_ARCH" --variant=minbase "$DEBIAN_RELEASE" "$ROOTFS_DIR" "$DEBIAN_MIRROR"
prepare_sources_list
cp -L /etc/resolv.conf "$ROOTFS_DIR/etc/resolv.conf"
install_policy_rc_d
mount_chroot_fs

run_in_chroot apt-get update
# Pre-seed grub-pc so its postinst does not block on the install_devices
# prompt during chroot install. Hetzner installimage decides the boot
# device at install time anyway.
run_in_chroot apt-get install -y debconf-utils
run_in_chroot bash -c 'echo "grub-pc grub-pc/install_devices multiselect " | debconf-set-selections; echo "grub-pc grub-pc/install_devices_empty boolean true" | debconf-set-selections'
run_in_chroot apt-get install -y \
  systemd-sysv \
  locales \
  openssh-server \
  ca-certificates \
  curl \
  rsync \
  sudo \
  wget \
  gnupg \
  iproute2 \
  ifupdown \
  isc-dhcp-client \
  netbase \
  linux-image-amd64 \
  lvm2 \
  grub-common \
  grub-pc \
  grub-pc-bin \
  grub-efi-amd64-bin \
  os-prober \
  openssl \
  nftables \
  python3 \
  mdadm
# Ensure /boot/grub/grub.cfg exists with valid entries for the kernel that
# was just installed. Hetzner installimage's grub stage rewrites
# /etc/default/grub, runs `grub-install $TARGET`, and re-runs update-grub
# on the host - but if the chroot ships no grub.cfg at all, some installimage
# code paths produce a system that boots stage1 from the MBR but cannot find
# a stage2 menu and never reaches the kernel.
run_in_chroot update-grub 2>/dev/null || true

configure_base_system
bundle_source_tree
install_bootstrap_files
sanitize_rootfs
remove_policy_rc_d
cleanup_mounts

create_tarball

echo "Created: $DIST_DIR/$TARBALL_NAME"
