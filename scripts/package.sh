#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/disk_guardrails.sh"
source "$ROOT_DIR/scripts/lib/artifact_lock.sh"
beagle_artifact_lock_acquire "package"
DIST_DIR="$ROOT_DIR/dist"
INSTALLER_BUILD_DIR="${INSTALLER_BUILD_DIR:-${THINCLIENT_DIST_DIR:-$DIST_DIR/pve-thin-client-installer}}"
SERVER_INSTALLER_DIST_DIR="${SERVER_INSTALLER_DIST_DIR:-$DIST_DIR/beagle-os-server-installer}"
SERVER_INSTALLIMAGE_DIST_DIR="${SERVER_INSTALLIMAGE_DIST_DIR:-$DIST_DIR/beagle-os-server-installimage}"
KIOSK_DIST_DIR="${KIOSK_DIST_DIR:-$ROOT_DIR/beagle-kiosk/dist}"
EXT_DIR="$ROOT_DIR/extension"
THIN_CLIENT_DIR="$ROOT_DIR/thin-client-assistant"
BEAGLE_OS_DIST_DIR="${BEAGLE_OS_DIST_DIR:-$DIST_DIR/beagle-os}"
VERSION="$(tr -d ' \n\r' < "$ROOT_DIR/VERSION")"
ZIP_NAME="beagle-extension-v${VERSION}.zip"
TARBALL_NAME="beagle-os-v${VERSION}.tar.gz"
TARBALL_LATEST_NAME="beagle-os-latest.tar.gz"
USB_PAYLOAD_NAME="pve-thin-client-usb-payload-v${VERSION}.tar.gz"
USB_PAYLOAD_LATEST_NAME="pve-thin-client-usb-payload-latest.tar.gz"
USB_BOOTSTRAP_NAME="pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz"
USB_BOOTSTRAP_LATEST_NAME="pve-thin-client-usb-bootstrap-latest.tar.gz"
USB_INSTALLER_NAME="pve-thin-client-usb-installer-v${VERSION}.sh"
USB_INSTALLER_LATEST_NAME="pve-thin-client-usb-installer-latest.sh"
LIVE_USB_INSTALLER_NAME="pve-thin-client-live-usb-v${VERSION}.sh"
LIVE_USB_INSTALLER_LATEST_NAME="pve-thin-client-live-usb-latest.sh"
WINDOWS_USB_INSTALLER_NAME="pve-thin-client-usb-installer-v${VERSION}.ps1"
WINDOWS_USB_INSTALLER_LATEST_NAME="pve-thin-client-usb-installer-latest.ps1"
WINDOWS_LIVE_USB_INSTALLER_NAME="pve-thin-client-live-usb-v${VERSION}.ps1"
WINDOWS_LIVE_USB_INSTALLER_LATEST_NAME="pve-thin-client-live-usb-latest.ps1"
INSTALLER_ISO_NAME="beagle-os-installer.iso"
INSTALLER_ISO_ARCH_NAME="beagle-os-installer-amd64.iso"
SERVER_INSTALLER_ISO_NAME="beagle-os-server-installer.iso"
SERVER_INSTALLER_ISO_ARCH_NAME="beagle-os-server-installer-amd64.iso"
SERVER_INSTALLIMAGE_NAME="${BEAGLE_SERVER_INSTALLIMAGE_TARBALL_FILENAME:-Debian-1201-bookworm-amd64-beagle-server.tar.gz}"
KIOSK_APPIMAGE_NAME="beagle-kiosk-v${VERSION}-linux-x64.AppImage"
KIOSK_RELEASE_MANIFEST_NAME="kiosk-release.json"
KIOSK_RELEASE_HASH_NAME="kiosk-release-hash.txt"
CHECKSUM_FILE="SHA256SUMS"
BUILD_BEAGLE_OS="${BUILD_BEAGLE_OS:-0}"
SKIP_THIN_CLIENT_BUILD="${SKIP_THIN_CLIENT_BUILD:-0}"
SKIP_SERVER_INSTALLER_BUILD="${SKIP_SERVER_INSTALLER_BUILD:-0}"
SKIP_SERVER_INSTALLIMAGE_BUILD="${SKIP_SERVER_INSTALLIMAGE_BUILD:-0}"
SKIP_KIOSK_BUILD="${SKIP_KIOSK_BUILD:-0}"
BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS="${BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS:-1}"
PUBLIC_UPDATE_BASE_URL="${BEAGLE_PUBLIC_UPDATE_BASE_URL:-https://beagle-os.com/beagle-updates}"
PUBLIC_UPDATE_BASE_URL="${PUBLIC_UPDATE_BASE_URL%/}"
PACKAGE_MIN_FREE_GIB="${BEAGLE_PACKAGE_MIN_FREE_GIB:-}"

sync_web_ui_asset_versions() {
  python3 - "$ROOT_DIR/website/index.html" "$VERSION" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
version = sys.argv[2]
content = path.read_text()
content = re.sub(r'/styles\.css\?v=[^"\']+', f'/styles.css?v={version}', content)
content = re.sub(r'/main\.js\?v=[^"\']+', f'/main.js?v={version}', content)
path.write_text(content)
PY
}

sync_kiosk_version() {
  python3 - "$ROOT_DIR/beagle-kiosk/package.json" "$VERSION" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
version = sys.argv[2]
data = json.loads(path.read_text())
if data.get("version") != version:
    data["version"] = version
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
PY
}

collect_beagle_os_assets() {
  local path
  [[ -d "$BEAGLE_OS_DIST_DIR" ]] || return 0

  while IFS= read -r path; do
    BEAGLE_OS_ASSETS+=("${path#$DIST_DIR/}")
  done < <(
    find "$BEAGLE_OS_DIST_DIR" -maxdepth 1 -type f \
      \( -name '*.qcow2' -o -name '*.raw' -o -name '*.deb' -o -name '*.txt' \) \
      | sort
  )
}

require_tool() {
  local tool="$1"
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing required tool: $tool" >&2
    exit 1
  fi
}

clean_stale_npm_rename_dirs() {
  local modules_dir="$1"
  [[ -d "$modules_dir" ]] || return 0
  find "$modules_dir" -mindepth 1 -maxdepth 1 -type d -name '.*-*' -exec rm -rf {} + 2>/dev/null || true
}

install_kiosk_node_modules() {
  local npm_log
  npm_log="$(mktemp)"
  clean_stale_npm_rename_dirs "$ROOT_DIR/beagle-kiosk/node_modules"
  if npm install 2> >(tee "$npm_log" >&2); then
    rm -f "$npm_log"
    return 0
  fi
  if grep -Eq 'ENOTEMPTY|directory not empty|syscall rename' "$npm_log"; then
    echo "npm install hit stale node_modules rename state; pruning node_modules and retrying once" >&2
    rm -rf "$ROOT_DIR/beagle-kiosk/node_modules"
    npm cache verify >/dev/null 2>&1 || true
    rm -f "$npm_log"
    npm install
    return 0
  fi
  rm -f "$npm_log"
  return 1
}

require_tool zip
require_tool tar
require_tool sha256sum
require_tool python3
require_tool node
require_tool npm

sync_web_ui_asset_versions

if [[ -z "$PACKAGE_MIN_FREE_GIB" ]]; then
  PACKAGE_MIN_FREE_GIB=4
  [[ "$SKIP_THIN_CLIENT_BUILD" != "1" ]] && PACKAGE_MIN_FREE_GIB=$((PACKAGE_MIN_FREE_GIB + 8))
  if [[ "$BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS" == "1" ]]; then
    [[ "$SKIP_SERVER_INSTALLER_BUILD" != "1" ]] && PACKAGE_MIN_FREE_GIB=$((PACKAGE_MIN_FREE_GIB + 6))
    [[ "$SKIP_SERVER_INSTALLIMAGE_BUILD" != "1" ]] && PACKAGE_MIN_FREE_GIB=$((PACKAGE_MIN_FREE_GIB + 4))
  fi
  [[ "$SKIP_KIOSK_BUILD" != "1" ]] && PACKAGE_MIN_FREE_GIB=$((PACKAGE_MIN_FREE_GIB + 2))
  [[ "$BUILD_BEAGLE_OS" == "1" ]] && PACKAGE_MIN_FREE_GIB=$((PACKAGE_MIN_FREE_GIB + 2))
fi

package_cleanup_paths=("$ROOT_DIR/.build")
if [[ "$SKIP_THIN_CLIENT_BUILD" != "1" ]]; then
  package_cleanup_paths+=("$INSTALLER_BUILD_DIR")
fi
if [[ "$BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS" == "1" && "$SKIP_SERVER_INSTALLER_BUILD" != "1" ]]; then
  package_cleanup_paths+=("$SERVER_INSTALLER_DIST_DIR")
fi
if [[ "$BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS" == "1" && "$SKIP_SERVER_INSTALLIMAGE_BUILD" != "1" ]]; then
  package_cleanup_paths+=("$SERVER_INSTALLIMAGE_DIST_DIR")
fi
if [[ "$SKIP_KIOSK_BUILD" != "1" ]]; then
  package_cleanup_paths+=("$KIOSK_DIST_DIR")
fi
if [[ "$BUILD_BEAGLE_OS" == "1" ]]; then
  package_cleanup_paths+=("$BEAGLE_OS_DIST_DIR")
fi

beagle_unmount_recursive_path "$ROOT_DIR/.build"

ensure_free_space_with_cleanup \
  "package workspace" \
  "$DIST_DIR" \
  "$((PACKAGE_MIN_FREE_GIB * 1024 * 1024))" \
  "$ROOT_DIR" \
  "${package_cleanup_paths[@]}"

mkdir -p "$DIST_DIR"
BEAGLE_OS_ASSETS=()
# Keep the currently published download set in place until replacements are
# ready. Removing host-facing files at build start causes temporary 404s on
# /beagle-downloads/* during long ISO/package rebuilds.

if [[ "$SKIP_THIN_CLIENT_BUILD" != "1" ]]; then
  # The live payload is usually rebuilt for every package run so runtime/script
  # changes land in the published squashfs and USB bootstrap.
  "$ROOT_DIR/scripts/build-thin-client-installer.sh"
elif [[ ! -f "$INSTALLER_BUILD_DIR/$INSTALLER_ISO_NAME" || ! -f "$INSTALLER_BUILD_DIR/$INSTALLER_ISO_ARCH_NAME" || ! -f "$INSTALLER_BUILD_DIR/live/filesystem.squashfs" ]]; then
  echo "SKIP_THIN_CLIENT_BUILD=1 requires an existing installer build under $INSTALLER_BUILD_DIR" >&2
  exit 1
fi

install -m 0644 "$INSTALLER_BUILD_DIR/$INSTALLER_ISO_NAME" "$DIST_DIR/$INSTALLER_ISO_NAME"
install -m 0644 "$INSTALLER_BUILD_DIR/$INSTALLER_ISO_ARCH_NAME" "$DIST_DIR/$INSTALLER_ISO_ARCH_NAME"

if [[ "$BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS" == "1" ]]; then
  if [[ "$SKIP_SERVER_INSTALLER_BUILD" != "1" ]]; then
    "$ROOT_DIR/scripts/build-server-installer.sh"
  elif [[ ! -f "$SERVER_INSTALLER_DIST_DIR/$SERVER_INSTALLER_ISO_NAME" || ! -f "$SERVER_INSTALLER_DIST_DIR/$SERVER_INSTALLER_ISO_ARCH_NAME" ]]; then
    echo "SKIP_SERVER_INSTALLER_BUILD=1 requires an existing server installer build under $SERVER_INSTALLER_DIST_DIR" >&2
    exit 1
  fi

  install -m 0644 "$SERVER_INSTALLER_DIST_DIR/$SERVER_INSTALLER_ISO_NAME" "$DIST_DIR/$SERVER_INSTALLER_ISO_NAME"
  install -m 0644 "$SERVER_INSTALLER_DIST_DIR/$SERVER_INSTALLER_ISO_ARCH_NAME" "$DIST_DIR/$SERVER_INSTALLER_ISO_ARCH_NAME"

  if [[ "$SKIP_SERVER_INSTALLIMAGE_BUILD" != "1" ]]; then
    "$ROOT_DIR/scripts/build-server-installimage.sh"
  elif [[ ! -f "$SERVER_INSTALLIMAGE_DIST_DIR/$SERVER_INSTALLIMAGE_NAME" ]]; then
    echo "SKIP_SERVER_INSTALLIMAGE_BUILD=1 requires an existing installimage build under $SERVER_INSTALLIMAGE_DIST_DIR" >&2
    exit 1
  fi

  install -m 0644 "$SERVER_INSTALLIMAGE_DIST_DIR/$SERVER_INSTALLIMAGE_NAME" "$DIST_DIR/$SERVER_INSTALLIMAGE_NAME"

  # The server-installer verifier expects a checksum manifest to exist already.
  # Seed a temporary checksum file here so the verifier can validate the current
  # ISO set before the final release bundle checksum is regenerated below.
  (
    cd "$DIST_DIR"
    sha256sum \
      "$SERVER_INSTALLER_ISO_NAME" \
      "$SERVER_INSTALLER_ISO_ARCH_NAME" \
      > "$CHECKSUM_FILE"
  )

  BEAGLE_VERIFY_REQUIRE_SIGNATURES=0 \
  BEAGLE_VERIFY_SERVER_INSTALLER_DIR="$DIST_DIR" \
  BEAGLE_VERIFY_SERVER_INSTALLIMAGE_DIR="$DIST_DIR" \
    "$ROOT_DIR/scripts/verify-server-installer-artifacts.sh"
fi

if [[ "$SKIP_KIOSK_BUILD" != "1" ]]; then
  sync_kiosk_version
  rm -rf "$KIOSK_DIST_DIR"
  (
    cd "$ROOT_DIR/beagle-kiosk"
    install_kiosk_node_modules
    npm run dist
    npm run release-metadata -- "dist/$KIOSK_APPIMAGE_NAME" "$PUBLIC_UPDATE_BASE_URL/$KIOSK_APPIMAGE_NAME"
  )
elif [[ ! -f "$KIOSK_DIST_DIR/$KIOSK_APPIMAGE_NAME" || ! -f "$KIOSK_DIST_DIR/$KIOSK_RELEASE_MANIFEST_NAME" || ! -f "$KIOSK_DIST_DIR/$KIOSK_RELEASE_HASH_NAME" ]]; then
  echo "SKIP_KIOSK_BUILD=1 requires an existing kiosk build under $KIOSK_DIST_DIR" >&2
  exit 1
fi

install -m 0755 "$KIOSK_DIST_DIR/$KIOSK_APPIMAGE_NAME" "$DIST_DIR/$KIOSK_APPIMAGE_NAME"
install -m 0644 "$KIOSK_DIST_DIR/$KIOSK_RELEASE_MANIFEST_NAME" "$DIST_DIR/$KIOSK_RELEASE_MANIFEST_NAME"
install -m 0644 "$KIOSK_DIST_DIR/$KIOSK_RELEASE_HASH_NAME" "$DIST_DIR/$KIOSK_RELEASE_HASH_NAME"

if [[ "$BUILD_BEAGLE_OS" == "1" ]]; then
  "$ROOT_DIR/scripts/build-beagle-os.sh"
fi

collect_beagle_os_assets

EXT_BUILD_DIR="$(mktemp -d)"
USB_PAYLOAD_STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$EXT_BUILD_DIR" "$USB_PAYLOAD_STAGE_DIR"' EXIT
cp -a "$EXT_DIR/." "$EXT_BUILD_DIR/"
python3 - "$EXT_BUILD_DIR/manifest.json" "$VERSION" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
version = sys.argv[2]
data = json.loads(path.read_text())
data["version"] = version
path.write_text(json.dumps(data, indent=2) + "\n")
PY
(
  cd "$EXT_BUILD_DIR"
  zip -qr "$DIST_DIR/$ZIP_NAME" .
)

(
  cd "$ROOT_DIR"
  tar -czf "$DIST_DIR/$TARBALL_NAME" \
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

install -m 0644 "$DIST_DIR/$TARBALL_NAME" "$DIST_DIR/$TARBALL_LATEST_NAME"

install -d -m 0755 "$USB_PAYLOAD_STAGE_DIR/dist/$(basename "$INSTALLER_BUILD_DIR")"
rsync -a --delete \
  "$INSTALLER_BUILD_DIR/live/" \
  "$USB_PAYLOAD_STAGE_DIR/dist/$(basename "$INSTALLER_BUILD_DIR")/live/"

(
  cd /
  tar -czf "$DIST_DIR/$USB_PAYLOAD_NAME" \
    -C "$ROOT_DIR" thin-client-assistant \
    -C "$ROOT_DIR" docs \
    -C "$ROOT_DIR" scripts \
    -C "$ROOT_DIR" README.md \
    -C "$ROOT_DIR" LICENSE \
    -C "$ROOT_DIR" CHANGELOG.md \
    -C "$ROOT_DIR" VERSION \
    -C "$USB_PAYLOAD_STAGE_DIR" "dist/$(basename "$INSTALLER_BUILD_DIR")/live"
)

install -m 0644 "$DIST_DIR/$USB_PAYLOAD_NAME" "$DIST_DIR/$USB_PAYLOAD_LATEST_NAME"
install -m 0644 "$DIST_DIR/$USB_PAYLOAD_NAME" "$DIST_DIR/$USB_BOOTSTRAP_NAME"
install -m 0644 "$DIST_DIR/$USB_PAYLOAD_NAME" "$DIST_DIR/$USB_BOOTSTRAP_LATEST_NAME"

install -m 0755 "$ROOT_DIR/thin-client-assistant/usb/pve-thin-client-usb-installer.sh" "$DIST_DIR/$USB_INSTALLER_NAME"
install -m 0755 "$ROOT_DIR/thin-client-assistant/usb/pve-thin-client-usb-installer.sh" "$DIST_DIR/$USB_INSTALLER_LATEST_NAME"
PVE_THIN_CLIENT_USB_WRITER_VARIANT=live install -m 0755 "$ROOT_DIR/thin-client-assistant/usb/pve-thin-client-usb-installer.sh" "$DIST_DIR/$LIVE_USB_INSTALLER_NAME"
PVE_THIN_CLIENT_USB_WRITER_VARIANT=live install -m 0755 "$ROOT_DIR/thin-client-assistant/usb/pve-thin-client-usb-installer.sh" "$DIST_DIR/$LIVE_USB_INSTALLER_LATEST_NAME"
install -m 0644 "$ROOT_DIR/thin-client-assistant/usb/pve-thin-client-usb-installer.ps1" "$DIST_DIR/$WINDOWS_USB_INSTALLER_NAME"
install -m 0644 "$ROOT_DIR/thin-client-assistant/usb/pve-thin-client-usb-installer.ps1" "$DIST_DIR/$WINDOWS_USB_INSTALLER_LATEST_NAME"
install -m 0644 "$ROOT_DIR/thin-client-assistant/usb/pve-thin-client-usb-installer.ps1" "$DIST_DIR/$WINDOWS_LIVE_USB_INSTALLER_NAME"
install -m 0644 "$ROOT_DIR/thin-client-assistant/usb/pve-thin-client-usb-installer.ps1" "$DIST_DIR/$WINDOWS_LIVE_USB_INSTALLER_LATEST_NAME"

checksum_targets=(
  "$ZIP_NAME"
  "$TARBALL_NAME"
  "$TARBALL_LATEST_NAME"
  "$USB_PAYLOAD_NAME"
  "$USB_PAYLOAD_LATEST_NAME"
  "$USB_BOOTSTRAP_NAME"
  "$USB_BOOTSTRAP_LATEST_NAME"
  "$USB_INSTALLER_NAME"
  "$USB_INSTALLER_LATEST_NAME"
  "$LIVE_USB_INSTALLER_NAME"
  "$LIVE_USB_INSTALLER_LATEST_NAME"
  "$WINDOWS_USB_INSTALLER_NAME"
  "$WINDOWS_USB_INSTALLER_LATEST_NAME"
  "$WINDOWS_LIVE_USB_INSTALLER_NAME"
  "$WINDOWS_LIVE_USB_INSTALLER_LATEST_NAME"
  "$INSTALLER_ISO_NAME"
  "$INSTALLER_ISO_ARCH_NAME"
)
if [[ "$BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS" == "1" ]]; then
  checksum_targets+=(
    "$SERVER_INSTALLER_ISO_NAME"
    "$SERVER_INSTALLER_ISO_ARCH_NAME"
    "$SERVER_INSTALLIMAGE_NAME"
  )
fi
checksum_targets+=(
  "$KIOSK_APPIMAGE_NAME"
  "$KIOSK_RELEASE_MANIFEST_NAME"
  "$KIOSK_RELEASE_HASH_NAME"
  "${BEAGLE_OS_ASSETS[@]}"
)
(
  cd "$DIST_DIR"
  sha256sum "${checksum_targets[@]}" > "$CHECKSUM_FILE"
)

echo "Created: $DIST_DIR/$ZIP_NAME"
echo "Created: $DIST_DIR/$TARBALL_NAME"
echo "Created: $DIST_DIR/$TARBALL_LATEST_NAME"
echo "Created: $DIST_DIR/$USB_PAYLOAD_NAME"
echo "Created: $DIST_DIR/$USB_PAYLOAD_LATEST_NAME"
echo "Created: $DIST_DIR/$USB_BOOTSTRAP_NAME"
echo "Created: $DIST_DIR/$USB_BOOTSTRAP_LATEST_NAME"
echo "Created: $DIST_DIR/$USB_INSTALLER_NAME"
echo "Created: $DIST_DIR/$USB_INSTALLER_LATEST_NAME"
echo "Created: $DIST_DIR/$LIVE_USB_INSTALLER_NAME"
echo "Created: $DIST_DIR/$LIVE_USB_INSTALLER_LATEST_NAME"
echo "Created: $DIST_DIR/$WINDOWS_USB_INSTALLER_NAME"
echo "Created: $DIST_DIR/$WINDOWS_USB_INSTALLER_LATEST_NAME"
echo "Created: $DIST_DIR/$WINDOWS_LIVE_USB_INSTALLER_NAME"
echo "Created: $DIST_DIR/$WINDOWS_LIVE_USB_INSTALLER_LATEST_NAME"
echo "Created: $DIST_DIR/$INSTALLER_ISO_NAME"
echo "Created: $DIST_DIR/$INSTALLER_ISO_ARCH_NAME"
if [[ "$BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS" == "1" ]]; then
  echo "Created: $DIST_DIR/$SERVER_INSTALLER_ISO_NAME"
  echo "Created: $DIST_DIR/$SERVER_INSTALLER_ISO_ARCH_NAME"
  echo "Created: $DIST_DIR/$SERVER_INSTALLIMAGE_NAME"
fi
echo "Created: $DIST_DIR/$KIOSK_APPIMAGE_NAME"
echo "Created: $DIST_DIR/$KIOSK_RELEASE_MANIFEST_NAME"
echo "Created: $DIST_DIR/$KIOSK_RELEASE_HASH_NAME"
echo "Created: $DIST_DIR/$CHECKSUM_FILE"
for asset in "${BEAGLE_OS_ASSETS[@]}"; do
  echo "Included: $DIST_DIR/$asset"
done
