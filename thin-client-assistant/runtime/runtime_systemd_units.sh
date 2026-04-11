#!/usr/bin/env bash

runtime_systemctl_bin() {
  printf '%s\n' "${BEAGLE_SYSTEMCTL_BIN:-systemctl}"
}

ensure_usb_tunnel_service() {
  local systemctl_bin
  systemctl_bin="$(runtime_systemctl_bin)"

  if ! beagle_unit_file_present "beagle-usb-tunnel.service"; then
    return 0
  fi
  "$systemctl_bin" enable beagle-usb-tunnel.service >/dev/null 2>&1 || true
  if [[ "${PVE_THIN_CLIENT_BEAGLE_USB_ENABLED:-0}" == "1" ]]; then
    "$systemctl_bin" restart --no-block beagle-usb-tunnel.service >/dev/null 2>&1 || true
  else
    "$systemctl_bin" stop --no-block beagle-usb-tunnel.service >/dev/null 2>&1 || true
  fi
}

ensure_beagle_management_units() {
  local systemctl_bin unit
  systemctl_bin="$(runtime_systemctl_bin)"

  for unit in \
    beagle-endpoint-report.timer \
    beagle-endpoint-dispatch.timer \
    beagle-runtime-heartbeat.timer \
    beagle-update-scan.timer
  do
    if beagle_unit_file_present "$unit"; then
      "$systemctl_bin" enable "$unit" >/dev/null 2>&1 || true
      "$systemctl_bin" restart --no-block "$unit" >/dev/null 2>&1 || true
    fi
  done

  for unit in beagle-endpoint-report.service beagle-endpoint-dispatch.service; do
    if beagle_unit_file_present "$unit"; then
      "$systemctl_bin" start --no-block "$unit" >/dev/null 2>&1 || true
    fi
  done

  if beagle_unit_file_present "beagle-update-boot-scan.service"; then
    "$systemctl_bin" enable beagle-update-boot-scan.service >/dev/null 2>&1 || true
    "$systemctl_bin" start --no-block beagle-update-boot-scan.service >/dev/null 2>&1 || true
  fi
}
