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
  if [[ -n "${BEAGLE_USBIP_BIN:-}" ]]; then
    printf '%s\n' "$BEAGLE_USBIP_BIN"
  elif command -v usbip >/dev/null 2>&1; then
    command -v usbip
  else
    printf '%s\n' "/usr/sbin/usbip"
  fi
}

pgrep_bin() {
  printf '%s\n' "${BEAGLE_PGREP_BIN:-pgrep}"
}

usb_auto_bind() {
  # Auto-bind=1: forward all eligible USB devices automatically.
  # Set PVE_THIN_CLIENT_BEAGLE_USB_AUTO_BIND=0 to disable.
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_AUTO_BIND:-1}"
}

camera_tunnel_port() {
  # TCP port exposed on usb_attach_host via SSH reverse tunnel for VM-side
  # camera receive (per-VM from enrollment when available).
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_CAMERA_STREAM_PORT:-8091}"
}

camera_local_stream_port() {
  # TCP port used by local beagle-camera-stream on the endpoint.
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_CAMERA_LOCAL_STREAM_PORT:-8091}"
}

camera_stream_port() {
  # Backward-compatible alias used by older callers.
  camera_tunnel_port
}

require_enabled() {
  [[ "$(usb_enabled)" == "1" ]] || {
    echo "usb disabled" >&2
    exit 0
  }
}
