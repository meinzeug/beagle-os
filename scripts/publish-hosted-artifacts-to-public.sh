#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d ' \n\r' < "$ROOT_DIR/VERSION")"
REMOTE_SSH_TARGET="${BEAGLE_PUBLIC_SSH_TARGET:-meinzeug}"
REMOTE_DIR="${BEAGLE_PUBLIC_UPDATE_DIR:-/var/www/vhosts/beagle-os.com/httpdocs/beagle-updates}"
HOSTED_BASE_URL="${BEAGLE_HOSTED_DOWNLOADS_BASE_URL:-https://srv.thinover.net:8443/beagle-downloads}"
PUBLIC_BASE_URL="${BEAGLE_PUBLIC_UPDATE_BASE_URL:-https://beagle-os.com/beagle-updates}"

ssh "$REMOTE_SSH_TARGET" 'bash -s' -- "$REMOTE_DIR" "$HOSTED_BASE_URL" "$PUBLIC_BASE_URL" "$VERSION" <<'EOF'
set -euo pipefail

remote_dir="$1"
hosted_base_url="${2%/}"
public_base_url="${3%/}"
version="$4"
payload_filename="pve-thin-client-usb-payload-v${version}.tar.gz"
payload_latest_filename="pve-thin-client-usb-payload-latest.tar.gz"
bootstrap_filename="pve-thin-client-usb-bootstrap-v${version}.tar.gz"
bootstrap_latest_filename="pve-thin-client-usb-bootstrap-latest.tar.gz"
installer_iso_filename="beagle-os-installer-amd64.iso"
server_installer_iso_filename="beagle-os-server-installer-amd64.iso"
kiosk_appimage_filename="beagle-kiosk-v${version}-linux-x64.AppImage"
kiosk_manifest_filename="kiosk-release.json"
kiosk_hash_filename="kiosk-release-hash.txt"

cd "$remote_dir"
tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

curl -fsSL "$hosted_base_url/SHA256SUMS" -o "$tmp_dir/SHA256SUMS"
curl -fsSL "$hosted_base_url/$payload_filename" -o "$tmp_dir/$payload_filename"
curl -fsSL "$hosted_base_url/$installer_iso_filename" -o "$tmp_dir/$installer_iso_filename"
curl -fsSL "$hosted_base_url/$server_installer_iso_filename" -o "$tmp_dir/$server_installer_iso_filename"
curl -fsSL "$hosted_base_url/$kiosk_appimage_filename" -o "$tmp_dir/$kiosk_appimage_filename"
curl -fsSL "$hosted_base_url/$kiosk_manifest_filename" -o "$tmp_dir/$kiosk_manifest_filename"
curl -fsSL "$hosted_base_url/$kiosk_hash_filename" -o "$tmp_dir/$kiosk_hash_filename"

expected_payload="$(awk -v name="$payload_filename" '$2 == name { print $1; exit }' "$tmp_dir/SHA256SUMS")"
expected_bootstrap="$(awk -v name="$bootstrap_filename" '$2 == name { print $1; exit }' "$tmp_dir/SHA256SUMS")"
expected_iso="$(awk -v name="$installer_iso_filename" '$2 == name { print $1; exit }' "$tmp_dir/SHA256SUMS")"
expected_server_iso="$(awk -v name="$server_installer_iso_filename" '$2 == name { print $1; exit }' "$tmp_dir/SHA256SUMS")"
expected_kiosk="$(awk -v name="$kiosk_appimage_filename" '$2 == name { print $1; exit }' "$tmp_dir/SHA256SUMS")"
actual_payload="$(sha256sum "$tmp_dir/$payload_filename" | awk '{print $1}')"
actual_iso="$(sha256sum "$tmp_dir/$installer_iso_filename" | awk '{print $1}')"
actual_server_iso="$(sha256sum "$tmp_dir/$server_installer_iso_filename" | awk '{print $1}')"
actual_kiosk="$(sha256sum "$tmp_dir/$kiosk_appimage_filename" | awk '{print $1}')"

[[ -n "$expected_payload" && "$actual_payload" == "$expected_payload" ]]
[[ -n "$expected_bootstrap" && "$actual_payload" == "$expected_bootstrap" ]]
[[ -n "$expected_iso" && "$actual_iso" == "$expected_iso" ]]
[[ -n "$expected_server_iso" && "$actual_server_iso" == "$expected_server_iso" ]]
[[ -n "$expected_kiosk" && "$actual_kiosk" == "$expected_kiosk" ]]

install -m 0644 "$tmp_dir/SHA256SUMS" SHA256SUMS
mv -f "$tmp_dir/$payload_filename" "$payload_filename"
ln -f "$payload_filename" "$payload_latest_filename"
ln -f "$payload_filename" "$bootstrap_filename"
ln -f "$payload_filename" "$bootstrap_latest_filename"
mv -f "$tmp_dir/$installer_iso_filename" "$installer_iso_filename"
ln -f "$installer_iso_filename" beagle-os-installer.iso
mv -f "$tmp_dir/$server_installer_iso_filename" "$server_installer_iso_filename"
ln -f "$server_installer_iso_filename" beagle-os-server-installer.iso
mv -f "$tmp_dir/$kiosk_appimage_filename" "$kiosk_appimage_filename"
mv -f "$tmp_dir/$kiosk_manifest_filename" "$kiosk_manifest_filename"
mv -f "$tmp_dir/$kiosk_hash_filename" "$kiosk_hash_filename"

python3 - "$remote_dir" "$public_base_url" "$version" "$payload_filename" "$payload_latest_filename" "$bootstrap_filename" "$bootstrap_latest_filename" "$installer_iso_filename" "$server_installer_iso_filename" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

base = Path(sys.argv[1])
public_base_url = sys.argv[2].rstrip("/")
version = sys.argv[3]
payload_filename = sys.argv[4]
payload_latest_filename = sys.argv[5]
bootstrap_filename = sys.argv[6]
bootstrap_latest_filename = sys.argv[7]
installer_iso_filename = sys.argv[8]
server_installer_iso_filename = sys.argv[9]

sha_map = {}
for line in (base / "SHA256SUMS").read_text().splitlines():
    parts = line.split()
    if len(parts) >= 2:
        sha_map[parts[1]] = parts[0]

payload_path = base / payload_filename
payload_latest_path = base / payload_latest_filename
bootstrap_path = base / bootstrap_filename
bootstrap_latest_path = base / bootstrap_latest_filename
installer_iso_path = base / installer_iso_filename
server_installer_iso_path = base / server_installer_iso_filename

payload = {
    "service": "beagle-public-updates",
    "version": version,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "channel": "stable",
    "public_base_url": public_base_url,
    "payload_filename": payload_filename,
    "payload_latest_filename": payload_latest_filename,
    "payload_url": f"{public_base_url}/{payload_filename}",
    "payload_latest_url": f"{public_base_url}/{payload_latest_filename}",
    "payload_sha256": sha_map.get(payload_filename, ""),
    "payload_size": payload_path.stat().st_size,
    "payload_latest_size": payload_latest_path.stat().st_size,
    "bootstrap_filename": bootstrap_filename,
    "bootstrap_latest_filename": bootstrap_latest_filename,
    "bootstrap_url": f"{public_base_url}/{bootstrap_filename}",
    "bootstrap_latest_url": f"{public_base_url}/{bootstrap_latest_filename}",
    "bootstrap_sha256": sha_map.get(bootstrap_filename, ""),
    "bootstrap_size": bootstrap_path.stat().st_size,
    "bootstrap_latest_size": bootstrap_latest_path.stat().st_size,
    "installer_iso_filename": installer_iso_filename,
    "installer_iso_url": f"{public_base_url}/{installer_iso_filename}",
    "installer_iso_sha256": sha_map.get(installer_iso_filename, ""),
    "installer_iso_size": installer_iso_path.stat().st_size,
    "server_installer_iso_filename": server_installer_iso_filename,
    "server_installer_iso_url": f"{public_base_url}/{server_installer_iso_filename}",
    "server_installer_iso_sha256": sha_map.get(server_installer_iso_filename, ""),
    "server_installer_iso_size": server_installer_iso_path.stat().st_size,
    "sha256sums_url": f"{public_base_url}/SHA256SUMS",
}

(base / "beagle-downloads-status.json").write_text(json.dumps(payload, indent=2) + "\n")
PY
EOF

echo "Published hosted artifacts from $HOSTED_BASE_URL to $REMOTE_SSH_TARGET:$REMOTE_DIR"
