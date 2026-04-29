#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${BEAGLE_RELEASE_DIST_DIR:-$ROOT_DIR/dist}"
REQUIRE_SIGNATURES="${BEAGLE_VERIFY_REQUIRE_SIGNATURES:-1}"
SERVER_INSTALLIMAGE_NAME="${BEAGLE_SERVER_INSTALLIMAGE_TARBALL_FILENAME:-Debian-1201-bookworm-amd64-beagle-server.tar.gz}"
SERVER_INSTALLER_ARTIFACT_DIR="${BEAGLE_VERIFY_SERVER_INSTALLER_DIR:-$DIST_DIR}"
SERVER_INSTALLIMAGE_ARTIFACT_DIR="${BEAGLE_VERIFY_SERVER_INSTALLIMAGE_DIR:-$DIST_DIR}"

ISO_FILES=(
  "$SERVER_INSTALLER_ARTIFACT_DIR/beagle-os-server-installer.iso"
  "$SERVER_INSTALLER_ARTIFACT_DIR/beagle-os-server-installer-amd64.iso"
)
CHECKSUM_FILE="$DIST_DIR/SHA256SUMS"
INSTALLIMAGE_FILE="$SERVER_INSTALLIMAGE_ARTIFACT_DIR/$SERVER_INSTALLIMAGE_NAME"
SIGNATURE_FILES=(
  "$DIST_DIR/beagle-os-server-installer.iso.sig"
  "$DIST_DIR/beagle-os-server-installer-amd64.iso.sig"
  "$DIST_DIR/SHA256SUMS.sig"
)

require_file() {
  local file="$1"
  [[ -f "$file" ]] || {
    echo "Missing required file: $file" >&2
    exit 1
  }
}

require_tool() {
  local tool="$1"
  command -v "$tool" >/dev/null 2>&1 || {
    echo "Missing required tool: $tool" >&2
    exit 1
  }
}

require_grep() {
  local needle="$1"
  local file="$2"
  grep -F "$needle" "$file" >/dev/null 2>&1 || {
    echo "Required marker missing in $(basename "$file"): $needle" >&2
    exit 1
  }
}

verify_checksums() {
  local tmp_file=""
  tmp_file="$(mktemp)"

  for iso in "${ISO_FILES[@]}"; do
    local base
    base="$(basename "$iso")"
    grep -F "  $base" "$CHECKSUM_FILE" >> "$tmp_file" || {
      echo "Checksum entry missing in SHA256SUMS: $base" >&2
      exit 1
    }
  done

  (
    cd "$DIST_DIR"
    sha256sum -c "$tmp_file"
  )

  rm -f "$tmp_file"
}

verify_signatures() {
  local require_sig
  require_sig="$(printf '%s' "$REQUIRE_SIGNATURES" | tr '[:upper:]' '[:lower:]')"

  case "$require_sig" in
    1|yes|true|on)
      ;;
    *)
      return 0
      ;;
  esac

  command -v gpg >/dev/null 2>&1 || {
    echo "gpg is required for signature verification" >&2
    exit 1
  }

  for sig in "${SIGNATURE_FILES[@]}"; do
    require_file "$sig"
  done

  gpg --verify "$DIST_DIR/SHA256SUMS.sig" "$CHECKSUM_FILE"
  gpg --verify "$DIST_DIR/beagle-os-server-installer.iso.sig" "$DIST_DIR/beagle-os-server-installer.iso"
  gpg --verify "$DIST_DIR/beagle-os-server-installer-amd64.iso.sig" "$DIST_DIR/beagle-os-server-installer-amd64.iso"
}

verify_iso_contents() {
  local iso="$1"
  local tmp_dir squashfs_path installer_script
  require_tool xorriso
  require_tool unsquashfs

  tmp_dir="$(mktemp -d)"
  squashfs_path="$tmp_dir/filesystem.squashfs"
  installer_script="$tmp_dir/beagle-server-installer"

  xorriso -osirrox on -indev "$iso" -extract /live/filesystem.squashfs "$squashfs_path" >/dev/null 2>&1
  unsquashfs -cat "$squashfs_path" usr/local/bin/beagle-server-installer > "$installer_script"

  require_grep "certbot python3-certbot-nginx" "$installer_script"
  require_grep "BEAGLE_AUTH_BOOTSTRAP_DISABLE='1'" "$installer_script"
  rm -rf "$tmp_dir"
}

verify_installimage_contents() {
  local tmp_dir bootstrap_script source_archive host_services_script
  require_tool tar

  require_file "$INSTALLIMAGE_FILE"
  tmp_dir="$(mktemp -d)"
  bootstrap_script="$tmp_dir/beagle-installimage-bootstrap"
  source_archive="$tmp_dir/beagle-os-source.tar.gz"
  host_services_script="$tmp_dir/install-beagle-host-services.sh"

  tar -xOf "$INSTALLIMAGE_FILE" ./usr/local/bin/beagle-installimage-bootstrap > "$bootstrap_script"
  tar -xOf "$INSTALLIMAGE_FILE" ./usr/local/share/beagle/beagle-os-source.tar.gz > "$source_archive"
  tar -xOf "$source_archive" scripts/install-beagle-host-services.sh > "$host_services_script"

  require_grep 'BEAGLE_AUTH_BOOTSTRAP_DISABLE="$BOOTSTRAP_DISABLE"' "$bootstrap_script"
  require_grep 'install_runtime_packages certbot python3-certbot-nginx' "$host_services_script"
  rm -rf "$tmp_dir"
}

main() {
  for iso in "${ISO_FILES[@]}"; do
    require_file "$iso"
  done
  require_file "$CHECKSUM_FILE"

  verify_checksums
  verify_signatures
  for iso in "${ISO_FILES[@]}"; do
    verify_iso_contents "$iso"
  done
  verify_installimage_contents
  echo "Server-installer artifacts verified successfully."
}

main "$@"
