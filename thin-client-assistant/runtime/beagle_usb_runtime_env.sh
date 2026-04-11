#!/usr/bin/env bash

usb_enabled() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_ENABLED:-1}"
}

usb_host() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_HOST:-}"
}

usb_user() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_USER:-beagle}"
}

usb_port() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PORT:-}"
}

usb_attach_host() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_ATTACH_HOST:-10.10.10.1}"
}

usb_key_file() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PRIVATE_KEY_FILE:-/etc/pve-thin-client/usb-tunnel.key}"
}

usb_known_hosts_file() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_KNOWN_HOSTS_FILE:-/etc/pve-thin-client/usb-tunnel-known_hosts}"
}

usbip_bin() {
  printf '%s\n' "${BEAGLE_USBIP_BIN:-usbip}"
}

pgrep_bin() {
  printf '%s\n' "${BEAGLE_PGREP_BIN:-pgrep}"
}

require_enabled() {
  [[ "$(usb_enabled)" == "1" ]] || {
    echo "usb disabled" >&2
    exit 0
  }
}
