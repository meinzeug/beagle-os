#!/usr/bin/env bash

candidate_live_asset_dir() {
  local target="$1"
  local require_boot_assets="${2:-0}"
  local live_dir=""

  if [[ -f "$target/pve-thin-client/live/filesystem.squashfs" ]]; then
    live_dir="$target/pve-thin-client/live"
  elif [[ -f "$target/filesystem.squashfs" ]]; then
    live_dir="$target"
  else
    return 1
  fi

  if [[ "$require_boot_assets" == "1" ]]; then
    [[ -f "$live_dir/vmlinuz" && -f "$live_dir/initrd.img" ]] || return 1
  fi

  printf '%s\n' "$live_dir"
}

candidate_manifest_path() {
  local target="$1"
  local require_boot_assets="${2:-0}"

  if [[ -f "$target/.pve-dcv-usb-manifest.json" ]]; then
    printf '%s\n' "$target/.pve-dcv-usb-manifest.json"
    return 0
  fi

  if candidate_live_asset_dir "$target" "$require_boot_assets" >/dev/null 2>&1 && [[ -f "$target/.pve-dcv-usb-manifest.json" ]]; then
    printf '%s\n' "$target/.pve-dcv-usb-manifest.json"
    return 0
  fi

  return 1
}
