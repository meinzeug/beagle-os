#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/disk_guardrails.sh"
BUILD_ENV_FILE="$ROOT_DIR/server-installer/build.env"

if [[ -f "$BUILD_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$BUILD_ENV_FILE"
fi

LB_TEMPLATE_DIR="$ROOT_DIR/server-installer/live-build"
BUILD_DIR="${SERVER_INSTALLER_BUILD_DIR:-$ROOT_DIR/.build/beagle-server-installer-live-build}"
DIST_DIR="${SERVER_INSTALLER_DIST_DIR:-$ROOT_DIR/dist/beagle-os-server-installer}"
SERVER_INSTALLER_ARCH="${SERVER_INSTALLER_ARCH:-amd64}"
VERSION="$(tr -d ' \n\r' < "$ROOT_DIR/VERSION")"
SERVER_INSTALLER_MIN_BUILD_FREE_GIB="${BEAGLE_SERVER_INSTALLER_MIN_BUILD_FREE_GIB:-14}"
SERVER_INSTALLER_MIN_DIST_FREE_GIB="${BEAGLE_SERVER_INSTALLER_MIN_DIST_FREE_GIB:-4}"
BUNDLED_SOURCE_ARCHIVE_PATH="config/includes.chroot/usr/local/share/beagle/beagle-os-source.tar.gz"
SERVER_INSTALLER_BUILD_DEPENDENCIES="${BEAGLE_SERVER_INSTALLER_BUILD_DEPENDENCIES:-live-build debootstrap squashfs-tools xorriso grub2-common grub-pc-bin grub-efi-amd64-bin dosfstools mtools syslinux-utils rsync curl ca-certificates}"

ensure_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi
  exec sudo \
    SERVER_INSTALLER_ARCH="$SERVER_INSTALLER_ARCH" \
    BEAGLE_SERVER_INSTALLER_MIN_BUILD_FREE_GIB="$SERVER_INSTALLER_MIN_BUILD_FREE_GIB" \
    BEAGLE_SERVER_INSTALLER_MIN_DIST_FREE_GIB="$SERVER_INSTALLER_MIN_DIST_FREE_GIB" \
    "$0" "$@"
}

ensure_root "$@"

ensure_free_space_with_cleanup \
  "server installer build workspace" \
  "$BUILD_DIR" \
  "$((SERVER_INSTALLER_MIN_BUILD_FREE_GIB * 1024 * 1024))" \
  "$ROOT_DIR" \
  "$BUILD_DIR" \
  "$DIST_DIR"
ensure_free_space_with_cleanup \
  "server installer artifacts" \
  "$DIST_DIR" \
  "$((SERVER_INSTALLER_MIN_DIST_FREE_GIB * 1024 * 1024))" \
  "$ROOT_DIR" \
  "$BUILD_DIR" \
  "$DIST_DIR"

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y $SERVER_INSTALLER_BUILD_DEPENDENCIES

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"
rsync -a "$LB_TEMPLATE_DIR/" "$BUILD_DIR/"
sed -i "s/__BEAGLE_RELEASE_VERSION__/${VERSION}/g" \
  "$BUILD_DIR/config/includes.chroot/usr/local/bin/beagle-server-installer"
mkdir -p "$(dirname "$BUILD_DIR/$BUNDLED_SOURCE_ARCHIVE_PATH")"
(
  cd "$ROOT_DIR"
  tar -czf "$BUILD_DIR/$BUNDLED_SOURCE_ARCHIVE_PATH" \
    --exclude='AGENTS.md' \
    --exclude='CLAUDE.md' \
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

(
  cd "$BUILD_DIR"
  chmod +x auto/config
  find config/hooks -type f -name '*.hook.chroot' -exec chmod +x {} +
  find config/includes.chroot/usr/local/bin -type f -exec chmod +x {} +
  ./auto/config
  lb build
)

ISO_PATH="$(find "$BUILD_DIR" -maxdepth 1 -type f \( -name '*.iso' -o -name '*.hybrid.iso' \) | sort | head -n 1)"
if [[ -z "$ISO_PATH" || ! -f "$ISO_PATH" ]]; then
  echo "Unable to locate built server installer ISO under $BUILD_DIR" >&2
  exit 1
fi

# Create stable /live/vmlinuz and /live/initrd names inside the ISO so
# grub.cfg can reference them without version-specific paths.
STAGE_DIR="$(mktemp -d)"
cleanup_stage() { rm -rf "$STAGE_DIR"; }
trap cleanup_stage EXIT

xorriso -osirrox on -indev "$ISO_PATH" -extract /live "$STAGE_DIR/live" 2>/dev/null

VMLINUZ=""
INITRD=""
for f in "$STAGE_DIR"/live/vmlinuz-*; do
  [ -e "$f" ] && VMLINUZ="$f" && break
done
for f in "$STAGE_DIR"/live/initrd.img-*; do
  [ -e "$f" ] && INITRD="$f" && break
done

if [[ -n "$VMLINUZ" && -n "$INITRD" ]]; then
  cp "$VMLINUZ" "$STAGE_DIR/vmlinuz"
  cp "$INITRD" "$STAGE_DIR/initrd"
  xorriso -indev "$ISO_PATH" -outdev "$ISO_PATH" -boot_image any keep \
    -map "$STAGE_DIR/vmlinuz" /live/vmlinuz \
    -map "$STAGE_DIR/initrd" /live/initrd \
    -commit
fi

install -m 0644 "$ISO_PATH" "$DIST_DIR/beagle-os-server-installer-${SERVER_INSTALLER_ARCH}.iso"
install -m 0644 "$ISO_PATH" "$DIST_DIR/beagle-os-server-installer.iso"

echo "Created: $DIST_DIR/beagle-os-server-installer-${SERVER_INSTALLER_ARCH}.iso"
echo "Created: $DIST_DIR/beagle-os-server-installer.iso"
