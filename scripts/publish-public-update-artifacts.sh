#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${DIST_DIR:-$ROOT_DIR/dist}"
REMOTE_TARGET="${BEAGLE_PUBLIC_UPDATE_TARGET:-meinzeug:/opt/beagle-os-saas/src/public/beagle-updates/}"
PUBLIC_BASE_URL="${BEAGLE_PUBLIC_UPDATE_BASE_URL:-https://beagle-os.com/beagle-updates}"
VERSION="$(tr -d ' \n\r' < "$ROOT_DIR/VERSION")"
STATUS_JSON="$DIST_DIR/beagle-downloads-status.json"

require_file() {
  local path="$1"
  [[ -f "$path" ]] || {
    echo "Missing required artifact: $path" >&2
    exit 1
  }
}

checksum_for() {
  local filename="$1"
  awk -v target="$filename" '$2 == target { print $1; exit }' "$DIST_DIR/SHA256SUMS"
}

write_public_status_json() {
  local payload_filename="pve-thin-client-usb-payload-v${VERSION}.tar.gz"
  local payload_latest_filename="pve-thin-client-usb-payload-latest.tar.gz"
  local bootstrap_filename="pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz"
  local bootstrap_latest_filename="pve-thin-client-usb-bootstrap-latest.tar.gz"
  local installer_iso_filename="beagle-os-installer-amd64.iso"
  local payload_path="$DIST_DIR/$payload_filename"
  local payload_latest_path="$DIST_DIR/$payload_latest_filename"
  local bootstrap_path="$DIST_DIR/$bootstrap_filename"
  local bootstrap_latest_path="$DIST_DIR/$bootstrap_latest_filename"
  local installer_iso_path="$DIST_DIR/$installer_iso_filename"
  local payload_sha256=""
  local bootstrap_sha256=""
  local installer_iso_sha256=""

  payload_sha256="$(checksum_for "$payload_filename")"
  if [[ -z "$payload_sha256" ]]; then
    payload_sha256="$(sha256sum "$payload_path" | awk '{print $1}')"
  fi

  bootstrap_sha256="$(checksum_for "$bootstrap_filename")"
  if [[ -z "$bootstrap_sha256" ]]; then
    bootstrap_sha256="$(sha256sum "$bootstrap_path" | awk '{print $1}')"
  fi

  installer_iso_sha256="$(checksum_for "$installer_iso_filename")"
  if [[ -z "$installer_iso_sha256" ]]; then
    installer_iso_sha256="$(sha256sum "$installer_iso_path" | awk '{print $1}')"
  fi

  python3 - "$STATUS_JSON" "$VERSION" "$PUBLIC_BASE_URL" "$payload_filename" "$payload_latest_filename" "$payload_sha256" "$payload_path" "$payload_latest_path" "$bootstrap_filename" "$bootstrap_latest_filename" "$bootstrap_sha256" "$bootstrap_path" "$bootstrap_latest_path" "$installer_iso_filename" "$installer_iso_sha256" "$installer_iso_path" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
version = sys.argv[2]
base_url = sys.argv[3].rstrip("/")
payload_filename = sys.argv[4]
payload_latest_filename = sys.argv[5]
payload_sha256 = sys.argv[6]
payload_path = Path(sys.argv[7])
payload_latest_path = Path(sys.argv[8])
bootstrap_filename = sys.argv[9]
bootstrap_latest_filename = sys.argv[10]
bootstrap_sha256 = sys.argv[11]
bootstrap_path = Path(sys.argv[12])
bootstrap_latest_path = Path(sys.argv[13])
installer_iso_filename = sys.argv[14]
installer_iso_sha256 = sys.argv[15]
installer_iso_path = Path(sys.argv[16])

payload = {
    "service": "beagle-public-updates",
    "version": version,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "channel": "stable",
    "public_base_url": base_url,
    "payload_filename": payload_filename,
    "payload_latest_filename": payload_latest_filename,
    "payload_url": f"{base_url}/{payload_filename}",
    "payload_latest_url": f"{base_url}/{payload_latest_filename}",
    "payload_sha256": payload_sha256,
    "payload_size": payload_path.stat().st_size,
    "payload_latest_size": payload_latest_path.stat().st_size,
    "bootstrap_filename": bootstrap_filename,
    "bootstrap_latest_filename": bootstrap_latest_filename,
    "bootstrap_url": f"{base_url}/{bootstrap_filename}",
    "bootstrap_latest_url": f"{base_url}/{bootstrap_latest_filename}",
    "bootstrap_sha256": bootstrap_sha256,
    "bootstrap_size": bootstrap_path.stat().st_size,
    "bootstrap_latest_size": bootstrap_latest_path.stat().st_size,
    "installer_iso_filename": installer_iso_filename,
    "installer_iso_url": f"{base_url}/{installer_iso_filename}",
    "installer_iso_sha256": installer_iso_sha256,
    "installer_iso_size": installer_iso_path.stat().st_size,
    "sha256sums_url": f"{base_url}/SHA256SUMS",
}
status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

require_file "$DIST_DIR/SHA256SUMS"
require_file "$DIST_DIR/pve-thin-client-usb-payload-v${VERSION}.tar.gz"
require_file "$DIST_DIR/pve-thin-client-usb-payload-latest.tar.gz"
require_file "$DIST_DIR/pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz"
require_file "$DIST_DIR/pve-thin-client-usb-bootstrap-latest.tar.gz"
require_file "$DIST_DIR/beagle-os-installer-amd64.iso"
write_public_status_json

rsync -av --progress \
  "$DIST_DIR/SHA256SUMS" \
  "$STATUS_JSON" \
  "$DIST_DIR/pve-thin-client-usb-payload-v${VERSION}.tar.gz" \
  "$DIST_DIR/pve-thin-client-usb-payload-latest.tar.gz" \
  "$DIST_DIR/pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz" \
  "$DIST_DIR/pve-thin-client-usb-bootstrap-latest.tar.gz" \
  "$DIST_DIR/beagle-os-installer-amd64.iso" \
  "$REMOTE_TARGET"

echo "Published public update artifacts to $REMOTE_TARGET"
