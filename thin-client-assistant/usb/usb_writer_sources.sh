#!/usr/bin/env bash

usb_payload_bundle_path() {
  local repo_root="$1"
  printf '%s\n' "$repo_root/dist/pve-thin-client-usb-payload-latest.tar.gz"
}

resolve_usb_install_payload_source() {
  local repo_root="$1"
  printf '%s\n' "${INSTALL_PAYLOAD_URL:-${RELEASE_PAYLOAD_URL:-${RELEASE_ISO_URL:-$(usb_payload_bundle_path "$repo_root")}}}"
}

resolve_usb_plan_bootstrap_source() {
  local repo_root="$1"
  printf '%s\n' "${RELEASE_BOOTSTRAP_URL:-${RELEASE_PAYLOAD_URL:-$(usb_payload_bundle_path "$repo_root")}}"
}

usb_writer_media_label() {
  local variant="$1"
  if [[ "$variant" == "live" ]]; then
    printf 'live\n'
    return 0
  fi
  printf 'installer\n'
}

usb_writer_live_assets_path() {
  local variant="$1"
  if [[ "$variant" == "live" ]]; then
    printf '/live\n'
    return 0
  fi
  printf '/pve-thin-client/live\n'
}
