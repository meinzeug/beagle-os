#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${DIST_DIR:-$ROOT_DIR/dist}"
REMOTE_TARGET="${BEAGLE_PUBLIC_UPDATE_TARGET:-}"
PUBLIC_BASE_URL="${BEAGLE_PUBLIC_UPDATE_BASE_URL:-https://beagle-os.com/beagle-updates}"
VERSION="$(tr -d ' \n\r' < "$ROOT_DIR/VERSION")"
STATUS_JSON="$DIST_DIR/beagle-downloads-status.json"
SERVER_INSTALLIMAGE_FILENAME="${BEAGLE_SERVER_INSTALLIMAGE_TARBALL_FILENAME:-Debian-1201-bookworm-amd64-beagle-server.tar.gz}"
PUBLISH_STAGE_DIR="${PUBLISH_STAGE_DIR:-$DIST_DIR/public-update-stage}"

require_file() {
  local path="$1"
  [[ -f "$path" ]] || {
    echo "Missing required artifact: $path" >&2
    exit 1
  }
}

copy_publish_file() {
  local source="$1"
  local dest_name="$2"
  local mode="0644"
  case "$dest_name" in
    *.sh)
      mode="0755"
      ;;
  esac
  install -D -m "$mode" "$source" "$PUBLISH_STAGE_DIR/$dest_name"
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
  local server_installer_iso_filename="beagle-os-server-installer-amd64.iso"
  local server_installimage_filename="$SERVER_INSTALLIMAGE_FILENAME"
  local payload_path="$DIST_DIR/$payload_filename"
  local payload_latest_path="$DIST_DIR/$payload_latest_filename"
  local bootstrap_path="$DIST_DIR/$bootstrap_filename"
  local bootstrap_latest_path="$DIST_DIR/$bootstrap_latest_filename"
  local installer_iso_path="$DIST_DIR/$installer_iso_filename"
  local server_installer_iso_path="$DIST_DIR/$server_installer_iso_filename"
  local server_installimage_path="$DIST_DIR/$server_installimage_filename"
  local payload_sha256=""
  local bootstrap_sha256=""
  local installer_iso_sha256=""
  local server_installer_iso_sha256=""
  local server_installimage_sha256=""

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

  server_installer_iso_sha256="$(checksum_for "$server_installer_iso_filename")"
  if [[ -z "$server_installer_iso_sha256" ]]; then
    server_installer_iso_sha256="$(sha256sum "$server_installer_iso_path" | awk '{print $1}')"
  fi

  server_installimage_sha256="$(checksum_for "$server_installimage_filename")"
  if [[ -z "$server_installimage_sha256" ]]; then
    server_installimage_sha256="$(sha256sum "$server_installimage_path" | awk '{print $1}')"
  fi

  python3 - "$STATUS_JSON" "$VERSION" "$PUBLIC_BASE_URL" "$payload_filename" "$payload_latest_filename" "$payload_sha256" "$payload_path" "$payload_latest_path" "$bootstrap_filename" "$bootstrap_latest_filename" "$bootstrap_sha256" "$bootstrap_path" "$bootstrap_latest_path" "$installer_iso_filename" "$installer_iso_sha256" "$installer_iso_path" "$server_installer_iso_filename" "$server_installer_iso_sha256" "$server_installer_iso_path" "$server_installimage_filename" "$server_installimage_sha256" "$server_installimage_path" <<'PY'
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
server_installer_iso_filename = sys.argv[17]
server_installer_iso_sha256 = sys.argv[18]
server_installer_iso_path = Path(sys.argv[19])
server_installimage_filename = sys.argv[20]
server_installimage_sha256 = sys.argv[21]
server_installimage_path = Path(sys.argv[22])

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
    "server_installer_iso_filename": server_installer_iso_filename,
    "server_installer_iso_url": f"{base_url}/{server_installer_iso_filename}",
    "server_installer_iso_sha256": server_installer_iso_sha256,
    "server_installer_iso_size": server_installer_iso_path.stat().st_size,
    "server_installimage_filename": server_installimage_filename,
    "server_installimage_url": f"{base_url}/{server_installimage_filename}",
    "server_installimage_sha256": server_installimage_sha256,
    "server_installimage_size": server_installimage_path.stat().st_size,
    "sha256sums_url": f"{base_url}/SHA256SUMS",
}
status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
}

prepare_publish_stage() {
  rm -rf "$PUBLISH_STAGE_DIR"
  install -d -m 0755 "$PUBLISH_STAGE_DIR"

  copy_publish_file "$DIST_DIR/SHA256SUMS" "SHA256SUMS"
  copy_publish_file "$STATUS_JSON" "beagle-downloads-status.json"
  copy_publish_file "$DIST_DIR/beagle-os-v${VERSION}.tar.gz" "beagle-os-v${VERSION}.tar.gz"
  copy_publish_file "$DIST_DIR/beagle-os-latest.tar.gz" "beagle-os-latest.tar.gz"
  copy_publish_file "$DIST_DIR/pve-thin-client-usb-payload-v${VERSION}.tar.gz" "pve-thin-client-usb-payload-v${VERSION}.tar.gz"
  copy_publish_file "$DIST_DIR/pve-thin-client-usb-payload-latest.tar.gz" "pve-thin-client-usb-payload-latest.tar.gz"
  copy_publish_file "$DIST_DIR/pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz" "pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz"
  copy_publish_file "$DIST_DIR/pve-thin-client-usb-bootstrap-latest.tar.gz" "pve-thin-client-usb-bootstrap-latest.tar.gz"
  copy_publish_file "$DIST_DIR/pve-thin-client-usb-installer-v${VERSION}.sh" "pve-thin-client-usb-installer-v${VERSION}.sh"
  copy_publish_file "$DIST_DIR/pve-thin-client-usb-installer-latest.sh" "pve-thin-client-usb-installer-latest.sh"
  copy_publish_file "$DIST_DIR/pve-thin-client-usb-installer-v${VERSION}.ps1" "pve-thin-client-usb-installer-v${VERSION}.ps1"
  copy_publish_file "$DIST_DIR/pve-thin-client-usb-installer-latest.ps1" "pve-thin-client-usb-installer-latest.ps1"
  copy_publish_file "$DIST_DIR/pve-thin-client-live-usb-v${VERSION}.sh" "pve-thin-client-live-usb-v${VERSION}.sh"
  copy_publish_file "$DIST_DIR/pve-thin-client-live-usb-latest.sh" "pve-thin-client-live-usb-latest.sh"
  copy_publish_file "$DIST_DIR/pve-thin-client-live-usb-v${VERSION}.ps1" "pve-thin-client-live-usb-v${VERSION}.ps1"
  copy_publish_file "$DIST_DIR/pve-thin-client-live-usb-latest.ps1" "pve-thin-client-live-usb-latest.ps1"
  copy_publish_file "$DIST_DIR/beagle-os-installer.iso" "beagle-os-installer.iso"
  copy_publish_file "$DIST_DIR/beagle-os-installer-amd64.iso" "beagle-os-installer-amd64.iso"
  copy_publish_file "$DIST_DIR/beagle-os-server-installer.iso" "beagle-os-server-installer.iso"
  copy_publish_file "$DIST_DIR/beagle-os-server-installer-amd64.iso" "beagle-os-server-installer-amd64.iso"
  copy_publish_file "$DIST_DIR/$SERVER_INSTALLIMAGE_FILENAME" "$SERVER_INSTALLIMAGE_FILENAME"
  copy_publish_file "$DIST_DIR/beagle-kiosk-v${VERSION}-linux-x64.AppImage" "beagle-kiosk-v${VERSION}-linux-x64.AppImage"
  copy_publish_file "$DIST_DIR/kiosk-release.json" "kiosk-release.json"
  copy_publish_file "$DIST_DIR/kiosk-release-hash.txt" "kiosk-release-hash.txt"
}

require_file "$DIST_DIR/SHA256SUMS"
require_file "$DIST_DIR/beagle-os-v${VERSION}.tar.gz"
require_file "$DIST_DIR/beagle-os-latest.tar.gz"
require_file "$DIST_DIR/pve-thin-client-usb-payload-v${VERSION}.tar.gz"
require_file "$DIST_DIR/pve-thin-client-usb-payload-latest.tar.gz"
require_file "$DIST_DIR/pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz"
require_file "$DIST_DIR/pve-thin-client-usb-bootstrap-latest.tar.gz"
require_file "$DIST_DIR/beagle-os-installer-amd64.iso"
require_file "$DIST_DIR/beagle-os-server-installer-amd64.iso"
require_file "$DIST_DIR/$SERVER_INSTALLIMAGE_FILENAME"
require_file "$DIST_DIR/beagle-kiosk-v${VERSION}-linux-x64.AppImage"
require_file "$DIST_DIR/kiosk-release.json"
require_file "$DIST_DIR/kiosk-release-hash.txt"
[[ -n "$REMOTE_TARGET" ]] || {
  echo "Set BEAGLE_PUBLIC_UPDATE_TARGET to an SSH rsync target." >&2
  exit 1
}
write_public_status_json
prepare_publish_stage

rsync -av --progress --delete \
  --exclude '.htaccess' \
  "$PUBLISH_STAGE_DIR/" \
  "$REMOTE_TARGET/"

echo "Published public update artifacts to $REMOTE_TARGET"
