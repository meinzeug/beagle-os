#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROVIDER_MODULE_PATH="${BEAGLE_PROVIDER_MODULE_PATH:-$ROOT_DIR/scripts/lib/beagle_provider.py}"
PREPARE_HOST_DOWNLOADS_HELPER="$ROOT_DIR/scripts/lib/prepare_host_downloads.py"
DIST_DIR="$ROOT_DIR/dist"
VERSION="$(tr -d ' \n\r' < "$ROOT_DIR/VERSION")"
HOST_ENV_FILE="${PVE_DCV_HOST_ENV_FILE:-/etc/beagle/host.env}"
if [[ -f "$HOST_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$HOST_ENV_FILE"
fi
SERVER_NAME="${PVE_DCV_PROXY_SERVER_NAME:-$(hostname -f 2>/dev/null || hostname)}"
LISTEN_PORT="${PVE_DCV_PROXY_LISTEN_PORT:-8443}"
DOWNLOADS_PATH="${PVE_DCV_DOWNLOADS_PATH:-/beagle-downloads}"
BASE_URL="${PVE_DCV_DOWNLOADS_BASE_URL:-https://${SERVER_NAME}:${LISTEN_PORT}${DOWNLOADS_PATH}}"
PUBLIC_ARTIFACT_BASE_URL="${BEAGLE_PUBLIC_UPDATE_BASE_URL:-$BASE_URL}"
PUBLIC_ARTIFACT_BASE_URL="${PUBLIC_ARTIFACT_BASE_URL%/}"
HOST_INSTALLER_VERSIONED="$DIST_DIR/pve-thin-client-usb-installer-host-v${VERSION}.sh"
HOST_INSTALLER_LATEST="$DIST_DIR/pve-thin-client-usb-installer-host-latest.sh"
HOST_LIVE_USB_VERSIONED="$DIST_DIR/pve-thin-client-live-usb-host-v${VERSION}.sh"
HOST_LIVE_USB_LATEST="$DIST_DIR/pve-thin-client-live-usb-host-latest.sh"
HOST_WINDOWS_INSTALLER_VERSIONED="$DIST_DIR/pve-thin-client-usb-installer-host-v${VERSION}.ps1"
HOST_WINDOWS_INSTALLER_LATEST="$DIST_DIR/pve-thin-client-usb-installer-host-latest.ps1"
GENERIC_INSTALLER="$DIST_DIR/pve-thin-client-usb-installer-v${VERSION}.sh"
GENERIC_LIVE_USB="$DIST_DIR/pve-thin-client-live-usb-v${VERSION}.sh"
GENERIC_WINDOWS_INSTALLER="$DIST_DIR/pve-thin-client-usb-installer-v${VERSION}.ps1"
PAYLOAD_URL="${PUBLIC_ARTIFACT_BASE_URL}/pve-thin-client-usb-payload-latest.tar.gz"
BOOTSTRAP_URL="${PUBLIC_ARTIFACT_BASE_URL}/pve-thin-client-usb-bootstrap-latest.tar.gz"
INSTALLER_ISO_URL="${PUBLIC_ARTIFACT_BASE_URL}/beagle-os-installer-amd64.iso"
INSTALLER_URL="${BASE_URL%/}/pve-thin-client-usb-installer-host-latest.sh"
LIVE_USB_URL="${BASE_URL%/}/pve-thin-client-live-usb-host-latest.sh"
WINDOWS_INSTALLER_URL="${BASE_URL%/}/pve-thin-client-usb-installer-host-latest.ps1"
VM_INSTALLER_URL_TEMPLATE="https://${SERVER_NAME}:${LISTEN_PORT}/beagle-api/api/v1/vms/{vmid}/installer.sh"
VM_LIVE_USB_URL_TEMPLATE="https://${SERVER_NAME}:${LISTEN_PORT}/beagle-api/api/v1/vms/{vmid}/live-usb.sh"
VM_WINDOWS_INSTALLER_URL_TEMPLATE="https://${SERVER_NAME}:${LISTEN_PORT}/beagle-api/api/v1/vms/{vmid}/installer.ps1"
STATUS_URL="${BASE_URL%/}/beagle-downloads-status.json"
SHA256SUMS_URL="${PUBLIC_ARTIFACT_BASE_URL}/SHA256SUMS"
SERVER_INSTALLER_ISO_URL="${PUBLIC_ARTIFACT_BASE_URL}/beagle-os-server-installer-amd64.iso"
STATUS_JSON_PATH="$DIST_DIR/beagle-downloads-status.json"
VM_INSTALLERS_METADATA_PATH="$DIST_DIR/beagle-vm-installers.json"
INSTALLER_SHA256=""
PAYLOAD_SHA256=""
BOOTSTRAP_SHA256=""
CREDENTIALS_ENV_FILE="${PVE_DCV_CREDENTIALS_ENV_FILE:-/etc/beagle/credentials.env}"
BEAGLE_MANAGER_ENV_FILE="${PVE_DCV_BEAGLE_MANAGER_ENV_FILE:-/etc/beagle/beagle-manager.env}"

if [[ -f "$CREDENTIALS_ENV_FILE" ]]; then
  # Optional operator-managed defaults for VM installer preset generation.
  # Expected keys: PVE_THIN_CLIENT_DEFAULT_PROXMOX_USERNAME / PASSWORD / TOKEN
  # shellcheck disable=SC1090
  source "$CREDENTIALS_ENV_FILE"
fi

if [[ -f "$BEAGLE_MANAGER_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$BEAGLE_MANAGER_ENV_FILE"
fi

DEFAULT_PROXMOX_USERNAME="${PVE_THIN_CLIENT_DEFAULT_PROXMOX_USERNAME:-${PVE_DCV_PROXMOX_USERNAME:-}}"
DEFAULT_PROXMOX_PASSWORD="${PVE_THIN_CLIENT_DEFAULT_PROXMOX_PASSWORD:-${PVE_DCV_PROXMOX_PASSWORD:-}}"
DEFAULT_PROXMOX_TOKEN="${PVE_THIN_CLIENT_DEFAULT_PROXMOX_TOKEN:-${PVE_DCV_PROXMOX_TOKEN:-}}"
BEAGLE_MANAGER_URL="${PVE_DCV_BEAGLE_MANAGER_URL:-https://${SERVER_NAME}:${LISTEN_PORT}/beagle-api}"

ensure_dist_permissions() {
  install -d -m 0755 "$DIST_DIR"
  find "$DIST_DIR" -type d -exec chmod 0755 {} +
  find "$DIST_DIR" -type f -exec chmod 0644 {} +
  find "$DIST_DIR" -type f -name '*.sh' -exec chmod 0755 {} +
}

ensure_current_packaged_artifacts() {
  local needs_package=0
  local installer_build_iso="$DIST_DIR/pve-thin-client-installer/beagle-os-installer-amd64.iso"
  local installer_build_rootfs="$DIST_DIR/pve-thin-client-installer/live/filesystem.squashfs"
  local server_installer_build_iso="$DIST_DIR/beagle-os-server-installer/beagle-os-server-installer-amd64.iso"
  local root_iso="$DIST_DIR/beagle-os-installer-amd64.iso"
  local root_server_iso="$DIST_DIR/beagle-os-server-installer-amd64.iso"
  local packaged_payload="$DIST_DIR/pve-thin-client-usb-payload-latest.tar.gz"
  local packaged_bootstrap="$DIST_DIR/pve-thin-client-usb-bootstrap-latest.tar.gz"
  local packaged_installer="$DIST_DIR/pve-thin-client-usb-installer-latest.sh"
  local packaged_live_usb="$DIST_DIR/pve-thin-client-live-usb-latest.sh"
  local packaged_windows_installer="$DIST_DIR/pve-thin-client-usb-installer-latest.ps1"
  local source_installer="$ROOT_DIR/thin-client-assistant/usb/pve-thin-client-usb-installer.sh"
  local source_windows_installer="$ROOT_DIR/thin-client-assistant/usb/pve-thin-client-usb-installer.ps1"
  local source_server_installer="$ROOT_DIR/scripts/build-server-installer.sh"

  if [[ ! -f "$root_iso" || ! -f "$root_server_iso" || ! -f "$packaged_payload" || ! -f "$packaged_bootstrap" || ! -f "$packaged_installer" || ! -f "$packaged_live_usb" || ! -f "$packaged_windows_installer" ]]; then
    needs_package=1
  fi

  if [[ "$needs_package" -eq 0 && -f "$installer_build_iso" && "$installer_build_iso" -nt "$root_iso" ]]; then
    needs_package=1
  fi

  if [[ "$needs_package" -eq 0 && -f "$installer_build_rootfs" && "$installer_build_rootfs" -nt "$packaged_payload" ]]; then
    needs_package=1
  fi

  if [[ "$needs_package" -eq 0 && -f "$server_installer_build_iso" && "$server_installer_build_iso" -nt "$root_server_iso" ]]; then
    needs_package=1
  fi

  if [[ "$needs_package" -eq 0 && -f "$source_installer" && ( "$source_installer" -nt "$packaged_installer" || "$source_installer" -nt "$packaged_live_usb" ) ]]; then
    needs_package=1
  fi

  if [[ "$needs_package" -eq 0 && -f "$source_windows_installer" && "$source_windows_installer" -nt "$packaged_windows_installer" ]]; then
    needs_package=1
  fi

  if [[ "$needs_package" -eq 0 && -f "$source_server_installer" && "$source_server_installer" -nt "$root_server_iso" ]]; then
    needs_package=1
  fi

  if [[ "$needs_package" -eq 0 ]] && find "$ROOT_DIR/server-installer" -type f -newer "$root_server_iso" | grep -q .; then
    needs_package=1
  fi

  if [[ "$needs_package" -eq 1 ]]; then
    "$ROOT_DIR/scripts/package.sh"
  fi
}

ensure_current_packaged_artifacts

[[ -f "$GENERIC_INSTALLER" ]] || {
  echo "Missing packaged USB installer: $GENERIC_INSTALLER" >&2
  exit 1
}
[[ -f "$GENERIC_LIVE_USB" ]] || {
  echo "Missing packaged live USB installer: $GENERIC_LIVE_USB" >&2
  exit 1
}
[[ -f "$GENERIC_WINDOWS_INSTALLER" ]] || {
  echo "Missing packaged Windows USB installer: $GENERIC_WINDOWS_INSTALLER" >&2
  exit 1
}

[[ -f "$DIST_DIR/pve-thin-client-usb-payload-latest.tar.gz" ]] || {
  echo "Missing packaged USB payload: $DIST_DIR/pve-thin-client-usb-payload-latest.tar.gz" >&2
  exit 1
}
[[ -f "$DIST_DIR/pve-thin-client-usb-bootstrap-latest.tar.gz" ]] || {
  echo "Missing packaged USB bootstrap: $DIST_DIR/pve-thin-client-usb-bootstrap-latest.tar.gz" >&2
  exit 1
}
[[ -f "$DIST_DIR/beagle-os-installer-amd64.iso" ]] || {
  echo "Missing packaged installer ISO: $DIST_DIR/beagle-os-installer-amd64.iso" >&2
  exit 1
}
[[ -f "$DIST_DIR/beagle-os-server-installer-amd64.iso" ]] || {
  echo "Missing packaged server installer ISO: $DIST_DIR/beagle-os-server-installer-amd64.iso" >&2
  exit 1
}

rm -f "$DIST_DIR"/pve-thin-client-usb-installer-vm-*.sh "$DIST_DIR"/pve-thin-client-usb-installer-vm-*.ps1 "$DIST_DIR"/pve-thin-client-live-usb-vm-*.sh "$VM_INSTALLERS_METADATA_PATH"
install -m 0755 "$GENERIC_INSTALLER" "$HOST_INSTALLER_VERSIONED"
install -m 0755 "$GENERIC_LIVE_USB" "$HOST_LIVE_USB_VERSIONED"
install -m 0644 "$GENERIC_WINDOWS_INSTALLER" "$HOST_WINDOWS_INSTALLER_VERSIONED"

python3 "$PREPARE_HOST_DOWNLOADS_HELPER" patch-host-shell-template \
  --path "$HOST_INSTALLER_VERSIONED" \
  --writer-variant installer \
  --installer-iso-url "$INSTALLER_ISO_URL" \
  --installer-bootstrap-url "$BOOTSTRAP_URL" \
  --installer-payload-url "$PAYLOAD_URL"

install -m 0755 "$HOST_INSTALLER_VERSIONED" "$HOST_INSTALLER_LATEST"
python3 "$PREPARE_HOST_DOWNLOADS_HELPER" patch-host-shell-template \
  --path "$HOST_LIVE_USB_VERSIONED" \
  --writer-variant live \
  --installer-iso-url "$INSTALLER_ISO_URL" \
  --installer-bootstrap-url "$BOOTSTRAP_URL" \
  --installer-payload-url "$PAYLOAD_URL"

install -m 0755 "$HOST_LIVE_USB_VERSIONED" "$HOST_LIVE_USB_LATEST"

python3 "$PREPARE_HOST_DOWNLOADS_HELPER" patch-host-windows-template \
  --path "$HOST_WINDOWS_INSTALLER_VERSIONED" \
  --installer-iso-url "$INSTALLER_ISO_URL"

install -m 0644 "$HOST_WINDOWS_INSTALLER_VERSIONED" "$HOST_WINDOWS_INSTALLER_LATEST"

python3 "$PREPARE_HOST_DOWNLOADS_HELPER" generate-vm-installers-metadata \
  --provider-module-path "$PROVIDER_MODULE_PATH" \
  --metadata-path "$VM_INSTALLERS_METADATA_PATH" \
  --server-name "$SERVER_NAME" \
  --installer-iso-url "$INSTALLER_ISO_URL" \
  --default-proxmox-username "$DEFAULT_PROXMOX_USERNAME" \
  --default-proxmox-password "$DEFAULT_PROXMOX_PASSWORD" \
  --default-proxmox-token "$DEFAULT_PROXMOX_TOKEN" \
  --beagle-manager-url "$BEAGLE_MANAGER_URL"

CHECKSUM_FILE="$DIST_DIR/SHA256SUMS"
checksum_entries=(
  "beagle-extension-v${VERSION}.zip"
  "beagle-os-v${VERSION}.tar.gz"
  "beagle-os-latest.tar.gz"
  "pve-thin-client-usb-payload-v${VERSION}.tar.gz"
  "pve-thin-client-usb-payload-latest.tar.gz"
  "pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz"
  "pve-thin-client-usb-bootstrap-latest.tar.gz"
  "pve-thin-client-usb-installer-v${VERSION}.sh"
  "pve-thin-client-usb-installer-latest.sh"
  "pve-thin-client-live-usb-v${VERSION}.sh"
  "pve-thin-client-live-usb-latest.sh"
  "pve-thin-client-usb-installer-v${VERSION}.ps1"
  "pve-thin-client-usb-installer-latest.ps1"
  "pve-thin-client-usb-installer-host-v${VERSION}.sh"
  "pve-thin-client-usb-installer-host-latest.sh"
  "pve-thin-client-live-usb-host-v${VERSION}.sh"
  "pve-thin-client-live-usb-host-latest.sh"
  "pve-thin-client-usb-installer-host-v${VERSION}.ps1"
  "pve-thin-client-usb-installer-host-latest.ps1"
  "beagle-os-installer.iso"
  "beagle-os-installer-amd64.iso"
  "beagle-os-server-installer.iso"
  "beagle-os-server-installer-amd64.iso"
)

while IFS= read -r installer_name; do
  checksum_entries+=("$installer_name")
done < <(
  cd "$DIST_DIR"
  compgen -G 'pve-thin-client-usb-installer-vm-*.sh' | sort || true
)

while IFS= read -r installer_name; do
  checksum_entries+=("$installer_name")
done < <(
  cd "$DIST_DIR"
  compgen -G 'pve-thin-client-usb-installer-vm-*.ps1' | sort || true
)

while IFS= read -r installer_name; do
  checksum_entries+=("$installer_name")
done < <(
  cd "$DIST_DIR"
  compgen -G 'pve-thin-client-live-usb-vm-*.sh' | sort || true
)

(
  cd "$DIST_DIR"
  sha256sum "${checksum_entries[@]}" > "$(basename "$CHECKSUM_FILE")"
)

ensure_dist_permissions

INSTALLER_SHA256="$(sha256sum "$HOST_INSTALLER_LATEST" | awk '{print $1}')"
PAYLOAD_SHA256="$(sha256sum "$DIST_DIR/pve-thin-client-usb-payload-latest.tar.gz" | awk '{print $1}')"
BOOTSTRAP_SHA256="$(sha256sum "$DIST_DIR/pve-thin-client-usb-bootstrap-latest.tar.gz" | awk '{print $1}')"
INSTALLER_ISO_SHA256="$(sha256sum "$DIST_DIR/beagle-os-installer-amd64.iso" | awk '{print $1}')"
SERVER_INSTALLER_ISO_SHA256="$(sha256sum "$DIST_DIR/beagle-os-server-installer-amd64.iso" | awk '{print $1}')"

cat > "$DIST_DIR/beagle-downloads-index.html" <<EOF
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Beagle OS Downloads</title>
  <style>
    body { font-family: sans-serif; margin: 2rem auto; max-width: 60rem; line-height: 1.5; padding: 0 1rem; }
    code { background: #f4f4f4; padding: 0.15rem 0.3rem; border-radius: 0.25rem; }
    table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
    th, td { border-bottom: 1px solid #ddd; padding: 0.55rem; text-align: left; vertical-align: top; }
    th { width: 18rem; }
  </style>
</head>
<body>
  <h1>Beagle OS Downloads</h1>
  <p>Host-local thin-client media downloads for this Proxmox server.</p>
  <ul>
    <li><a href="${DOWNLOADS_PATH%/}/pve-thin-client-usb-installer-host-latest.sh">Generic USB installer launcher (fallback)</a></li>
    <li><a href="${DOWNLOADS_PATH%/}/pve-thin-client-live-usb-host-latest.sh">Generic live USB launcher</a></li>
    <li><a href="${DOWNLOADS_PATH%/}/pve-thin-client-usb-installer-host-latest.ps1">Generic Windows USB installer launcher</a></li>
    <li><a href="${DOWNLOADS_PATH%/}/beagle-os-installer-amd64.iso">Beagle OS installer ISO</a></li>
    <li><a href="${DOWNLOADS_PATH%/}/beagle-os-server-installer-amd64.iso">Beagle OS server installer ISO</a></li>
    <li><a href="${DOWNLOADS_PATH%/}/pve-thin-client-usb-bootstrap-latest.tar.gz">USB bootstrap bundle (used while creating installer media)</a></li>
    <li><a href="${DOWNLOADS_PATH%/}/pve-thin-client-usb-payload-latest.tar.gz">USB payload bundle</a></li>
    <li>VM-specific installer scripts now download the installer ISO, write the USB stick and embed the selected VM profile for unattended Beagle deployment.</li>
    <li>The generic installer remains available as fallback when no VM-specific preset should be embedded.</li>
    <li><a href="${DOWNLOADS_PATH%/}/beagle-downloads-status.json">Status JSON</a></li>
    <li><a href="${DOWNLOADS_PATH%/}/SHA256SUMS">SHA256SUMS</a></li>
  </ul>
  <p>The hosted USB installers pull the Beagle installer ISO during USB creation, then embed the selected VM profile so the installed thin client boots directly into Moonlight for that target VM.</p>
  <table>
    <tr><th>Release version</th><td><code>${VERSION}</code></td></tr>
    <tr><th>Server</th><td><code>${SERVER_NAME}:${LISTEN_PORT}</code></td></tr>
    <tr><th>VM installer template</th><td><code>${VM_INSTALLER_URL_TEMPLATE}</code></td></tr>
    <tr><th>VM Windows installer template</th><td><code>${VM_WINDOWS_INSTALLER_URL_TEMPLATE}</code></td></tr>
    <tr><th>Status JSON</th><td><a href="${DOWNLOADS_PATH%/}/beagle-downloads-status.json">${STATUS_URL}</a></td></tr>
    <tr><th>SHA256SUMS</th><td><a href="${DOWNLOADS_PATH%/}/SHA256SUMS">${SHA256SUMS_URL}</a></td></tr>
    <tr><th>Hosted installer SHA256</th><td><code>${INSTALLER_SHA256}</code></td></tr>
    <tr><th>Endpoint ISO SHA256</th><td><code>${INSTALLER_ISO_SHA256}</code></td></tr>
    <tr><th>Server ISO SHA256</th><td><code>${SERVER_INSTALLER_ISO_SHA256}</code></td></tr>
    <tr><th>Bootstrap SHA256</th><td><code>${BOOTSTRAP_SHA256}</code></td></tr>
    <tr><th>Payload SHA256</th><td><code>${PAYLOAD_SHA256}</code></td></tr>
  </table>
</body>
</html>
EOF

python3 "$PREPARE_HOST_DOWNLOADS_HELPER" write-download-status \
  --status-path "$STATUS_JSON_PATH" \
  --version "$VERSION" \
  --server-name "$SERVER_NAME" \
  --listen-port "$LISTEN_PORT" \
  --downloads-path "$DOWNLOADS_PATH" \
  --installer-url "$INSTALLER_URL" \
  --live-usb-url "$LIVE_USB_URL" \
  --installer-windows-url "$WINDOWS_INSTALLER_URL" \
  --bootstrap-url "$BOOTSTRAP_URL" \
  --payload-url "$PAYLOAD_URL" \
  --installer-iso-url "$INSTALLER_ISO_URL" \
  --server-installer-iso-url "$SERVER_INSTALLER_ISO_URL" \
  --status-url "$STATUS_URL" \
  --sha256sums-url "$SHA256SUMS_URL" \
  --installer-path "$HOST_INSTALLER_LATEST" \
  --live-usb-path "$HOST_LIVE_USB_LATEST" \
  --installer-windows-path "$HOST_WINDOWS_INSTALLER_LATEST" \
  --bootstrap-path "$DIST_DIR/pve-thin-client-usb-bootstrap-latest.tar.gz" \
  --payload-path "$DIST_DIR/pve-thin-client-usb-payload-latest.tar.gz" \
  --installer-iso-path "$DIST_DIR/beagle-os-installer-amd64.iso" \
  --server-installer-iso-path "$DIST_DIR/beagle-os-server-installer-amd64.iso" \
  --installer-sha256 "$INSTALLER_SHA256" \
  --bootstrap-sha256 "$BOOTSTRAP_SHA256" \
  --payload-sha256 "$PAYLOAD_SHA256" \
  --installer-iso-sha256 "$INSTALLER_ISO_SHA256" \
  --server-installer-iso-sha256 "$SERVER_INSTALLER_ISO_SHA256" \
  --vm-installer-url-template "$VM_INSTALLER_URL_TEMPLATE" \
  --vm-windows-installer-url-template "$VM_WINDOWS_INSTALLER_URL_TEMPLATE" \
  --vm-live-usb-url-template "$VM_LIVE_USB_URL_TEMPLATE" \
  --vm-installers-path "$VM_INSTALLERS_METADATA_PATH"

echo "Prepared host-local download artifacts under $DIST_DIR"
echo "Hosted USB installer URL: $INSTALLER_URL"
echo "Hosted live USB URL: $LIVE_USB_URL"
