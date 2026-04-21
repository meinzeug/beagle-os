#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${BEAGLE_RELEASE_DIST_DIR:-$ROOT_DIR/dist}"
REQUIRE_SIGNATURES="${BEAGLE_VERIFY_REQUIRE_SIGNATURES:-1}"

ISO_FILES=(
  "$DIST_DIR/beagle-os-server-installer.iso"
  "$DIST_DIR/beagle-os-server-installer-amd64.iso"
)
CHECKSUM_FILE="$DIST_DIR/SHA256SUMS"
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

main() {
  for iso in "${ISO_FILES[@]}"; do
    require_file "$iso"
  done
  require_file "$CHECKSUM_FILE"

  verify_checksums
  verify_signatures
  echo "Server-installer artifacts verified successfully."
}

main "$@"
