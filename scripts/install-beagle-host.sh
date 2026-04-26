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
BEAGLE_WEB_UI_TRUSTED_API_ORIGINS="${BEAGLE_WEB_UI_TRUSTED_API_ORIGINS:-}"
BEAGLE_WEB_UI_ALLOW_HASH_TOKEN="${BEAGLE_WEB_UI_ALLOW_HASH_TOKEN:-0}"
BEAGLE_WEB_UI_ALLOW_ABSOLUTE_API_TARGETS="${BEAGLE_WEB_UI_ALLOW_ABSOLUTE_API_TARGETS:-0}"
BEAGLE_WEB_UI_SEND_LEGACY_API_TOKEN_HEADER="${BEAGLE_WEB_UI_SEND_LEGACY_API_TOKEN_HEADER:-0}"
BEAGLE_WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS="${BEAGLE_WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS:-0}"
BEAGLE_HOST_PROVIDER="${BEAGLE_HOST_PROVIDER:-}"
BEAGLE_SERVER_INSTALL_MODE="${BEAGLE_SERVER_INSTALL_MODE:-}"
BEAGLE_HOST_TLS_CERT_FILE="${BEAGLE_HOST_TLS_CERT_FILE:-}"
BEAGLE_HOST_TLS_KEY_FILE="${BEAGLE_HOST_TLS_KEY_FILE:-}"
BEAGLE_CLUSTER_JOIN_REQUESTED="${BEAGLE_CLUSTER_JOIN_REQUESTED:-no}"
BEAGLE_CLUSTER_JOIN_TARGET="${BEAGLE_CLUSTER_JOIN_TARGET:-}"
DEFAULT_PROXMOX_USERNAME="${PVE_THIN_CLIENT_DEFAULT_PROXMOX_USERNAME:-${PVE_DCV_PROXMOX_USERNAME:-}}"
DEFAULT_PROXMOX_PASSWORD="${PVE_THIN_CLIENT_DEFAULT_PROXMOX_PASSWORD:-${PVE_DCV_PROXMOX_PASSWORD:-}}"
DEFAULT_PROXMOX_TOKEN="${PVE_THIN_CLIENT_DEFAULT_PROXMOX_TOKEN:-${PVE_DCV_PROXMOX_TOKEN:-}}"
BEAGLE_AUTH_BOOTSTRAP_USERNAME="${BEAGLE_AUTH_BOOTSTRAP_USERNAME:-admin}"
BEAGLE_AUTH_BOOTSTRAP_PASSWORD="${BEAGLE_AUTH_BOOTSTRAP_PASSWORD:-}"
BEAGLE_AUTH_BOOTSTRAP_DISABLE="${BEAGLE_AUTH_BOOTSTRAP_DISABLE:-0}"

resolve_host_provider() {
  local mode
  if [[ -n "$BEAGLE_HOST_PROVIDER" ]]; then
    mode="$(printf '%s' "$BEAGLE_HOST_PROVIDER" | tr '[:upper:]' '[:lower:]')"
    case "$mode" in
      ""|pve|proxmox|with-proxmox|with_proxmox)
        printf 'beagle\n'
        ;;
      *)
        printf '%s\n' "$mode"
        ;;
    esac
    return 0
  fi

  # Even if package.sh could not run (e.g. no thin-client live-build toolchain),
  # prepare-host-downloads.sh may still be able to build the bootstrap tarball
  # from an already-deployed installer ISO. Run it first, then re-validate.

  printf 'beagle\n'
}

BEAGLE_HOST_PROVIDER="$(resolve_host_provider)"

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
      BEAGLE_WEB_UI_TRUSTED_API_ORIGINS="$BEAGLE_WEB_UI_TRUSTED_API_ORIGINS" \
      BEAGLE_WEB_UI_ALLOW_HASH_TOKEN="$BEAGLE_WEB_UI_ALLOW_HASH_TOKEN" \
      BEAGLE_WEB_UI_ALLOW_ABSOLUTE_API_TARGETS="$BEAGLE_WEB_UI_ALLOW_ABSOLUTE_API_TARGETS" \
      BEAGLE_WEB_UI_SEND_LEGACY_API_TOKEN_HEADER="$BEAGLE_WEB_UI_SEND_LEGACY_API_TOKEN_HEADER" \
      BEAGLE_WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS="$BEAGLE_WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS" \
      BEAGLE_HOST_PROVIDER="$BEAGLE_HOST_PROVIDER" \
      BEAGLE_SERVER_INSTALL_MODE="$BEAGLE_SERVER_INSTALL_MODE" \
      BEAGLE_HOST_TLS_CERT_FILE="$BEAGLE_HOST_TLS_CERT_FILE" \
      BEAGLE_HOST_TLS_KEY_FILE="$BEAGLE_HOST_TLS_KEY_FILE" \
      BEAGLE_CLUSTER_JOIN_REQUESTED="$BEAGLE_CLUSTER_JOIN_REQUESTED" \
      BEAGLE_CLUSTER_JOIN_TARGET="$BEAGLE_CLUSTER_JOIN_TARGET" \
      BEAGLE_AUTH_BOOTSTRAP_USERNAME="$BEAGLE_AUTH_BOOTSTRAP_USERNAME" \
      BEAGLE_AUTH_BOOTSTRAP_PASSWORD="$BEAGLE_AUTH_BOOTSTRAP_PASSWORD" \
      BEAGLE_AUTH_BOOTSTRAP_DISABLE="$BEAGLE_AUTH_BOOTSTRAP_DISABLE" \
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

prompt_secret_value() {
  local prompt="$1"
  local response=""

  [[ -t 0 ]] || {
    printf '\n'
    return 0
  }

  read -r -s -p "$prompt: " response
  printf '\n' >&2
  printf '%s\n' "$response"
}

prompt_bootstrap_admin() {
  local first_pass=""
  local second_pass=""
  local bootstrap_disable=""

  bootstrap_disable="$(printf '%s' "$BEAGLE_AUTH_BOOTSTRAP_DISABLE" | tr '[:upper:]' '[:lower:]')"
  case "$bootstrap_disable" in
    1|true|yes|on)
      return 0
      ;;
  esac

  [[ "${BEAGLE_INSTALL_NONINTERACTIVE:-0}" == "1" ]] && return 0
  [[ -t 0 ]] || return 0

  echo ""
  echo "Beagle Web-Login (Erstzugang)"
  BEAGLE_AUTH_BOOTSTRAP_USERNAME="$(prompt_value 'Admin username' "$BEAGLE_AUTH_BOOTSTRAP_USERNAME")"

  if [[ -n "$BEAGLE_AUTH_BOOTSTRAP_PASSWORD" ]]; then
    return 0
  fi

  while true; do
    first_pass="$(prompt_secret_value 'Admin password')"
    [[ -n "$first_pass" ]] || {
      echo "Admin password darf nicht leer sein." >&2
      continue
    }
    second_pass="$(prompt_secret_value 'Admin password bestaetigen')"
    [[ "$first_pass" == "$second_pass" ]] || {
      echo "Passwoerter stimmen nicht ueberein." >&2
      continue
    }
    BEAGLE_AUTH_BOOTSTRAP_PASSWORD="$first_pass"
    break
  done
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
  if command -v rsync >/dev/null 2>&1 && command -v curl >/dev/null 2>&1; then
    return 0
  fi

  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y rsync curl
}

have_packaged_assets() {
  local server_installimage_filename="${BEAGLE_SERVER_INSTALLIMAGE_TARBALL_FILENAME:-Debian-1201-bookworm-amd64-beagle-server.tar.gz}"
  [[ -f "$INSTALL_DIR/dist/pve-thin-client-usb-installer-v${VERSION}.sh" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-usb-installer-latest.sh" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-live-usb-v${VERSION}.sh" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-live-usb-latest.sh" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-usb-installer-v${VERSION}.ps1" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-usb-installer-latest.ps1" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-live-usb-v${VERSION}.ps1" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-live-usb-latest.ps1" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-usb-payload-v${VERSION}.tar.gz" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-usb-payload-latest.tar.gz" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz" ]] &&
    [[ -f "$INSTALL_DIR/dist/pve-thin-client-usb-bootstrap-latest.tar.gz" ]] &&
    [[ -f "$INSTALL_DIR/dist/beagle-os-installer-amd64.iso" ]] &&
    [[ -f "$INSTALL_DIR/dist/beagle-os-installer.iso" ]] &&
    [[ -f "$INSTALL_DIR/dist/beagle-os-server-installer-amd64.iso" ]] &&
    [[ -f "$INSTALL_DIR/dist/beagle-os-server-installer.iso" ]] &&
    [[ -f "$INSTALL_DIR/dist/$server_installimage_filename" ]]
}

download_release_assets() {
  local base_url="$1"
  local dist_dir="$INSTALL_DIR/dist"
  local server_installimage_filename="${BEAGLE_SERVER_INSTALLIMAGE_TARBALL_FILENAME:-Debian-1201-bookworm-amd64-beagle-server.tar.gz}"

  command -v curl >/dev/null 2>&1 || return 1

  install -d -m 0755 "$dist_dir"

  download_asset() {
    local destination="$1"
    shift
    local candidate=""
    for candidate in "$@"; do
      if curl -fsSLo "$destination" "$base_url/$candidate"; then
        return 0
      fi
    done
    return 1
  }

  download_asset \
    "$dist_dir/pve-thin-client-usb-installer-v${VERSION}.sh" \
    "pve-thin-client-usb-installer-v${VERSION}.sh" \
    "pve-thin-client-usb-installer-latest.sh" &&
    install -m 0755 "$dist_dir/pve-thin-client-usb-installer-v${VERSION}.sh" "$dist_dir/pve-thin-client-usb-installer-latest.sh" &&
    download_asset \
      "$dist_dir/pve-thin-client-live-usb-v${VERSION}.sh" \
      "pve-thin-client-live-usb-v${VERSION}.sh" \
      "pve-thin-client-live-usb-latest.sh" &&
    install -m 0755 "$dist_dir/pve-thin-client-live-usb-v${VERSION}.sh" "$dist_dir/pve-thin-client-live-usb-latest.sh" &&
    download_asset \
      "$dist_dir/pve-thin-client-usb-installer-v${VERSION}.ps1" \
      "pve-thin-client-usb-installer-v${VERSION}.ps1" \
      "pve-thin-client-usb-installer-latest.ps1" &&
    install -m 0644 "$dist_dir/pve-thin-client-usb-installer-v${VERSION}.ps1" "$dist_dir/pve-thin-client-usb-installer-latest.ps1" &&
    download_asset \
      "$dist_dir/pve-thin-client-live-usb-v${VERSION}.ps1" \
      "pve-thin-client-live-usb-v${VERSION}.ps1" \
      "pve-thin-client-live-usb-latest.ps1" &&
    install -m 0644 "$dist_dir/pve-thin-client-live-usb-v${VERSION}.ps1" "$dist_dir/pve-thin-client-live-usb-latest.ps1" &&
    download_asset \
      "$dist_dir/pve-thin-client-usb-payload-v${VERSION}.tar.gz" \
      "pve-thin-client-usb-payload-v${VERSION}.tar.gz" \
      "pve-thin-client-usb-payload-latest.tar.gz" &&
    install -m 0644 "$dist_dir/pve-thin-client-usb-payload-v${VERSION}.tar.gz" "$dist_dir/pve-thin-client-usb-payload-latest.tar.gz" &&
    download_asset \
      "$dist_dir/pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz" \
      "pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz" \
      "pve-thin-client-usb-bootstrap-latest.tar.gz" &&
    install -m 0644 "$dist_dir/pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz" "$dist_dir/pve-thin-client-usb-bootstrap-latest.tar.gz" &&
    curl -fsSLo "$dist_dir/beagle-os-installer-amd64.iso" \
      "$base_url/beagle-os-installer-amd64.iso" &&
    install -m 0644 "$dist_dir/beagle-os-installer-amd64.iso" "$dist_dir/beagle-os-installer.iso" &&
    curl -fsSLo "$dist_dir/beagle-os-server-installer-amd64.iso" \
      "$base_url/beagle-os-server-installer-amd64.iso" &&
    install -m 0644 "$dist_dir/beagle-os-server-installer-amd64.iso" "$dist_dir/beagle-os-server-installer.iso" &&
    curl -fsSLo "$dist_dir/$server_installimage_filename" \
      "$base_url/$server_installimage_filename" &&
    curl -fsSLo "$dist_dir/SHA256SUMS" "$base_url/SHA256SUMS"
}

ensure_release_assets_or_die() {
  local release_base_url="${PUBLIC_UPDATE_BASE_URL%/}"

  if ! have_packaged_assets; then
    echo "Required release assets are missing in $INSTALL_DIR/dist; trying public artifact download..." >&2
    if ! download_release_assets "$release_base_url"; then
      echo "Public artifact download failed; trying local packaging..." >&2
      "$INSTALL_DIR/scripts/package.sh" || true
    fi

    if ! have_packaged_assets; then
      echo "Warning: some release assets are still missing; prepare-host-downloads.sh will attempt recovery from a deployed ISO." >&2
    fi
  fi

  # Always regenerate hosted download artifacts expected by installer endpoints.
  # prepare-host-downloads.sh also builds the bootstrap tarball from a deployed
  # ISO if the bootstrap is missing but the ISO is already present in dist/.
  if ! "$INSTALL_DIR/scripts/prepare-host-downloads.sh"; then
    echo "Error: failed to prepare host downloads in $INSTALL_DIR/dist." >&2
    exit 1
  fi

  if ! have_packaged_assets; then
    echo "Error: required release assets are missing after host download preparation." >&2
    exit 1
  fi
}

ensure_root "$@"
ensure_dependencies
prompt_install_endpoints
prompt_bootstrap_admin

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

if [[ "${BEAGLE_IN_CHROOT_INSTALL:-0}" != "1" ]]; then
  ensure_release_assets_or_die
fi
PVE_DCV_PROXY_SERVER_NAME="$SERVER_NAME" \
  PVE_DCV_PROXY_LISTEN_PORT="$LISTEN_PORT" \
  BEAGLE_SITE_PORT="$SITE_PORT" \
  BEAGLE_WEB_UI_URL="$WEB_UI_URL" \
  BEAGLE_WEB_UI_TITLE="$WEB_UI_TITLE" \
  BEAGLE_WEB_UI_TRUSTED_API_ORIGINS="$BEAGLE_WEB_UI_TRUSTED_API_ORIGINS" \
  BEAGLE_WEB_UI_ALLOW_HASH_TOKEN="$BEAGLE_WEB_UI_ALLOW_HASH_TOKEN" \
  BEAGLE_WEB_UI_ALLOW_ABSOLUTE_API_TARGETS="$BEAGLE_WEB_UI_ALLOW_ABSOLUTE_API_TARGETS" \
  BEAGLE_WEB_UI_SEND_LEGACY_API_TOKEN_HEADER="$BEAGLE_WEB_UI_SEND_LEGACY_API_TOKEN_HEADER" \
  BEAGLE_WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS="$BEAGLE_WEB_UI_ALLOW_INSECURE_EXTERNAL_URLS" \
  BEAGLE_HOST_PROVIDER="$BEAGLE_HOST_PROVIDER" \
  BEAGLE_SERVER_INSTALL_MODE="$BEAGLE_SERVER_INSTALL_MODE" \
  PVE_DCV_DOWNLOADS_PATH="$DOWNLOADS_PATH" \
  PVE_DCV_DOWNLOADS_BASE_URL="$DOWNLOADS_BASE_URL" \
  BEAGLE_PUBLIC_UPDATE_BASE_URL="$PUBLIC_UPDATE_BASE_URL" \
  PVE_DCV_USB_INSTALLER_URL="$USB_INSTALLER_URL" \
  PVE_DCV_CONFIG_DIR="$CONFIG_DIR" \
  BEAGLE_HOST_TLS_CERT_FILE="$BEAGLE_HOST_TLS_CERT_FILE" \
  BEAGLE_HOST_TLS_KEY_FILE="$BEAGLE_HOST_TLS_KEY_FILE" \
  BEAGLE_CLUSTER_JOIN_REQUESTED="$BEAGLE_CLUSTER_JOIN_REQUESTED" \
  BEAGLE_CLUSTER_JOIN_TARGET="$BEAGLE_CLUSTER_JOIN_TARGET" \
  PVE_THIN_CLIENT_DEFAULT_PROXMOX_USERNAME="$DEFAULT_PROXMOX_USERNAME" \
  PVE_THIN_CLIENT_DEFAULT_PROXMOX_PASSWORD="$DEFAULT_PROXMOX_PASSWORD" \
  PVE_THIN_CLIENT_DEFAULT_PROXMOX_TOKEN="$DEFAULT_PROXMOX_TOKEN" \
  BEAGLE_AUTH_BOOTSTRAP_USERNAME="$BEAGLE_AUTH_BOOTSTRAP_USERNAME" \
  BEAGLE_AUTH_BOOTSTRAP_PASSWORD="$BEAGLE_AUTH_BOOTSTRAP_PASSWORD" \
  BEAGLE_AUTH_BOOTSTRAP_DISABLE="$BEAGLE_AUTH_BOOTSTRAP_DISABLE" \
  bash "$INSTALL_DIR/scripts/install-beagle-host-postinstall.sh"

echo "Installed Beagle host assets to $INSTALL_DIR"
