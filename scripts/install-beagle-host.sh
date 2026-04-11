#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/opt/beagle}"
VERSION="$(tr -d ' \n\r' < "$ROOT_DIR/VERSION")"
SERVER_NAME="${PVE_DCV_PROXY_SERVER_NAME:-$(hostname -f 2>/dev/null || hostname)}"
LISTEN_PORT="${PVE_DCV_PROXY_LISTEN_PORT:-8443}"
SITE_PORT="${BEAGLE_SITE_PORT:-443}"
DOWNLOADS_PATH="${PVE_DCV_DOWNLOADS_PATH:-/beagle-downloads}"
DOWNLOADS_BASE_URL="${PVE_DCV_DOWNLOADS_BASE_URL:-https://${SERVER_NAME}:${LISTEN_PORT}${DOWNLOADS_PATH}}"
PUBLIC_UPDATE_BASE_URL="${BEAGLE_PUBLIC_UPDATE_BASE_URL:-https://beagle-os.com/beagle-updates}"
DEFAULT_USB_INSTALLER_URL="https://{host}:${LISTEN_PORT}/beagle-api/api/v1/vms/{vmid}/installer.sh"
USB_INSTALLER_URL="${PVE_DCV_USB_INSTALLER_URL:-$DEFAULT_USB_INSTALLER_URL}"
CONFIG_DIR="${PVE_DCV_CONFIG_DIR:-/etc/beagle}"
WEB_UI_TITLE="${BEAGLE_WEB_UI_TITLE:-Beagle OS Web UI}"
BEAGLE_HOST_PROVIDER="${BEAGLE_HOST_PROVIDER:-proxmox}"
DEFAULT_PROXMOX_USERNAME="${PVE_THIN_CLIENT_DEFAULT_PROXMOX_USERNAME:-${PVE_DCV_PROXMOX_USERNAME:-}}"
DEFAULT_PROXMOX_PASSWORD="${PVE_THIN_CLIENT_DEFAULT_PROXMOX_PASSWORD:-${PVE_DCV_PROXMOX_PASSWORD:-}}"
DEFAULT_PROXMOX_TOKEN="${PVE_THIN_CLIENT_DEFAULT_PROXMOX_TOKEN:-${PVE_DCV_PROXMOX_TOKEN:-}}"

default_web_ui_url() {
  if [[ "$SITE_PORT" == "443" ]]; then
    printf 'https://%s\n' "$SERVER_NAME"
    return 0
  fi
  printf 'https://%s:%s\n' "$SERVER_NAME" "$SITE_PORT"
}

WEB_UI_URL="${BEAGLE_WEB_UI_URL:-$(default_web_ui_url)}"

ensure_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi

  if command -v sudo >/dev/null 2>&1; then
    exec sudo \
      INSTALL_DIR="$INSTALL_DIR" \
      PVE_DCV_PROXY_SERVER_NAME="$SERVER_NAME" \
      PVE_DCV_PROXY_LISTEN_PORT="$LISTEN_PORT" \
      BEAGLE_SITE_PORT="$SITE_PORT" \
      BEAGLE_WEB_UI_URL="$WEB_UI_URL" \
      BEAGLE_WEB_UI_TITLE="$WEB_UI_TITLE" \
      BEAGLE_HOST_PROVIDER="$BEAGLE_HOST_PROVIDER" \
      BEAGLE_INSTALL_NONINTERACTIVE="${BEAGLE_INSTALL_NONINTERACTIVE:-0}" \
      PVE_DCV_DOWNLOADS_PATH="$DOWNLOADS_PATH" \
      PVE_DCV_DOWNLOADS_BASE_URL="$DOWNLOADS_BASE_URL" \
      BEAGLE_PUBLIC_UPDATE_BASE_URL="$PUBLIC_UPDATE_BASE_URL" \
      PVE_DCV_USB_INSTALLER_URL="$USB_INSTALLER_URL" \
      PVE_DCV_CONFIG_DIR="$CONFIG_DIR" \
      PVE_THIN_CLIENT_DEFAULT_PROXMOX_USERNAME="$DEFAULT_PROXMOX_USERNAME" \
      PVE_THIN_CLIENT_DEFAULT_PROXMOX_PASSWORD="$DEFAULT_PROXMOX_PASSWORD" \
      PVE_THIN_CLIENT_DEFAULT_PROXMOX_TOKEN="$DEFAULT_PROXMOX_TOKEN" \
      "$0" "$@"
  fi

  echo "This installer must run as root or use sudo." >&2
  exit 1
}

prompt_value() {
  local prompt="$1"
  local current="$2"
  local response=""

  [[ -t 0 ]] || {
    printf '%s\n' "$current"
    return 0
  }

  read -r -p "$prompt [$current]: " response
  if [[ -n "$response" ]]; then
    printf '%s\n' "$response"
    return 0
  fi
  printf '%s\n' "$current"
}

prompt_install_endpoints() {
  [[ "${BEAGLE_INSTALL_NONINTERACTIVE:-0}" == "1" ]] && return 0
  [[ -t 0 ]] || return 0

  SERVER_NAME="$(prompt_value 'Public Beagle host name' "$SERVER_NAME")"
  SITE_PORT="$(prompt_value 'Beagle Web UI HTTPS port' "$SITE_PORT")"
  LISTEN_PORT="$(prompt_value 'Beagle API/download HTTPS port' "$LISTEN_PORT")"
  WEB_UI_URL="$(prompt_value 'Public Beagle Web UI URL' "$(default_web_ui_url)")"
}

ensure_dependencies() {
  if command -v rsync >/dev/null 2>&1; then
    return 0
  fi

  apt_update_with_proxmox_fallback
  DEBIAN_FRONTEND=noninteractive apt-get install -y rsync
}

have_packaged_assets() {
  [[ -f "$INSTALL_DIR/dist/pve-thin-client-usb-installer-v${VERSION}.sh" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-usb-installer-latest.sh" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-usb-payload-v${VERSION}.tar.gz" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-usb-payload-latest.tar.gz" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-usb-bootstrap-latest.tar.gz" ]] &&
    [[ -f "$INSTALL_DIR/dist/beagle-os-installer-amd64.iso" ]] &&
    [[ -f "$INSTALL_DIR/dist/beagle-os-installer.iso" ]] &&
    [[ -f "$INSTALL_DIR/dist/beagle-os-server-installer-amd64.iso" ]] &&
    [[ -f "$INSTALL_DIR/dist/beagle-os-server-installer.iso" ]]
}

download_release_assets() {
  local base_url="$1"
  local dist_dir="$INSTALL_DIR/dist"

  command -v curl >/dev/null 2>&1 || return 1

  install -d -m 0755 "$dist_dir"

  curl -fsSLo "$dist_dir/pve-thin-client-usb-installer-v${VERSION}.sh" \
    "$base_url/pve-thin-client-usb-installer-v${VERSION}.sh" &&
    install -m 0755 "$dist_dir/pve-thin-client-usb-installer-v${VERSION}.sh" "$dist_dir/pve-thin-client-usb-installer-latest.sh" &&
    curl -fsSLo "$dist_dir/pve-thin-client-usb-payload-v${VERSION}.tar.gz" \
      "$base_url/pve-thin-client-usb-payload-v${VERSION}.tar.gz" &&
    install -m 0644 "$dist_dir/pve-thin-client-usb-payload-v${VERSION}.tar.gz" "$dist_dir/pve-thin-client-usb-payload-latest.tar.gz" &&
    curl -fsSLo "$dist_dir/pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz" \
      "$base_url/pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz" &&
    install -m 0644 "$dist_dir/pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz" "$dist_dir/pve-thin-client-usb-bootstrap-latest.tar.gz" &&
    curl -fsSLo "$dist_dir/beagle-os-installer-amd64.iso" \
      "$base_url/beagle-os-installer-amd64.iso" &&
    install -m 0644 "$dist_dir/beagle-os-installer-amd64.iso" "$dist_dir/beagle-os-installer.iso" &&
    curl -fsSLo "$dist_dir/beagle-os-server-installer-amd64.iso" \
      "$base_url/beagle-os-server-installer-amd64.iso" &&
    install -m 0644 "$dist_dir/beagle-os-server-installer-amd64.iso" "$dist_dir/beagle-os-server-installer.iso" &&
    curl -fsSLo "$dist_dir/SHA256SUMS" "$base_url/SHA256SUMS"
}

disable_proxmox_enterprise_repo() {
  local found=0
  local file

  while IFS= read -r file; do
    grep -q 'enterprise.proxmox.com' "$file" || continue
    cp "$file" "$file.beagle-backup"
    awk '!/enterprise\.proxmox\.com/' "$file.beagle-backup" > "$file"
    found=1
  done < <(find /etc/apt -maxdepth 2 -type f \( -name '*.list' -o -name '*.sources' \) 2>/dev/null)

  return $(( ! found ))
}

restore_proxmox_enterprise_repo() {
  local backup original

  while IFS= read -r backup; do
    original="${backup%.beagle-backup}"
    mv "$backup" "$original"
  done < <(find /etc/apt -maxdepth 2 -type f -name '*.beagle-backup' 2>/dev/null)
}

apt_update_with_proxmox_fallback() {
  if apt-get update; then
    return 0
  fi

  if ! disable_proxmox_enterprise_repo; then
    echo "apt-get update failed and no Proxmox enterprise repository fallback was available." >&2
    exit 1
  fi

  if ! apt-get update; then
    restore_proxmox_enterprise_repo
    exit 1
  fi
  restore_proxmox_enterprise_repo
}

write_host_env_file() {
  install -d -m 0755 "$CONFIG_DIR"
  cat > "$CONFIG_DIR/host.env" <<EOF
INSTALL_DIR="$INSTALL_DIR"
PVE_DCV_PROXY_SERVER_NAME="$SERVER_NAME"
PVE_DCV_PROXY_LISTEN_PORT="$LISTEN_PORT"
BEAGLE_SITE_PORT="$SITE_PORT"
BEAGLE_WEB_UI_URL="$WEB_UI_URL"
BEAGLE_WEB_UI_TITLE="$WEB_UI_TITLE"
BEAGLE_HOST_PROVIDER="$BEAGLE_HOST_PROVIDER"
PVE_DCV_DOWNLOADS_PATH="$DOWNLOADS_PATH"
PVE_DCV_DOWNLOADS_BASE_URL="$DOWNLOADS_BASE_URL"
BEAGLE_PUBLIC_UPDATE_BASE_URL="$PUBLIC_UPDATE_BASE_URL"
PVE_DCV_USB_INSTALLER_URL="$USB_INSTALLER_URL"
PVE_DCV_CONFIG_DIR="$CONFIG_DIR"
EOF

  cat > "$CONFIG_DIR/credentials.env" <<EOF
PVE_THIN_CLIENT_DEFAULT_PROXMOX_USERNAME="$DEFAULT_PROXMOX_USERNAME"
PVE_THIN_CLIENT_DEFAULT_PROXMOX_PASSWORD="$DEFAULT_PROXMOX_PASSWORD"
PVE_THIN_CLIENT_DEFAULT_PROXMOX_TOKEN="$DEFAULT_PROXMOX_TOKEN"
EOF
  chmod 0600 "$CONFIG_DIR/credentials.env"
}

ensure_root "$@"
ensure_dependencies
prompt_install_endpoints

case "$INSTALL_DIR/" in
  "$ROOT_DIR"/*)
    echo "INSTALL_DIR must not be inside the source tree: $INSTALL_DIR" >&2
    exit 1
    ;;
esac

install -d -m 0755 "$INSTALL_DIR"
rsync -a --delete \
  --exclude '.git' \
  --exclude '.build' \
  "$ROOT_DIR/" "$INSTALL_DIR/"
chown -R root:root "$INSTALL_DIR"
find "$INSTALL_DIR" -type d -exec chmod 0755 {} +

if ! have_packaged_assets; then
  RELEASE_BASE_URL="${PUBLIC_UPDATE_BASE_URL%/}"
  download_release_assets "$RELEASE_BASE_URL" || "$INSTALL_DIR/scripts/package.sh" || echo "Warning: could not fetch or build release assets (can be retried later)." >&2
fi
"$INSTALL_DIR/scripts/prepare-host-downloads.sh" || echo "Warning: could not prepare host downloads (can be retried later)." >&2
write_host_env_file
BEAGLE_HOST_PROVIDER="$BEAGLE_HOST_PROVIDER" \
  "$INSTALL_DIR/scripts/install-beagle-host-services.sh"

if [[ -d /usr/share/pve-manager/js ]]; then
  PVE_DCV_PROXY_SERVER_NAME="$SERVER_NAME" \
  PVE_DCV_PROXY_LISTEN_PORT="$LISTEN_PORT" \
  BEAGLE_SITE_PORT="$SITE_PORT" \
  BEAGLE_WEB_UI_URL="$WEB_UI_URL" \
  BEAGLE_WEB_UI_TITLE="$WEB_UI_TITLE" \
  PVE_DCV_DOWNLOADS_PATH="$DOWNLOADS_PATH" \
  PVE_DCV_USB_INSTALLER_URL="$USB_INSTALLER_URL" \
  "$INSTALL_DIR/scripts/install-proxmox-ui-integration.sh"

  if [[ -r /etc/pve/local/pveproxy-ssl.pem ]]; then
    PVE_DCV_PROXY_SERVER_NAME="$SERVER_NAME" \
    PVE_DCV_PROXY_LISTEN_PORT="$LISTEN_PORT" \
    BEAGLE_SITE_PORT="$SITE_PORT" \
    BEAGLE_WEB_UI_URL="$WEB_UI_URL" \
    BEAGLE_WEB_UI_TITLE="$WEB_UI_TITLE" \
    PVE_DCV_DOWNLOADS_PATH="$DOWNLOADS_PATH" \
    PVE_DCV_DOWNLOADS_BASE_URL="$DOWNLOADS_BASE_URL" \
    "$INSTALL_DIR/scripts/install-beagle-proxy.sh"
  else
    echo "Skipping proxy setup (PVE certificates not yet available; re-run after first boot)." >&2
  fi
fi

echo "Installed Beagle host assets to $INSTALL_DIR"
