#!/usr/bin/env bash

candidate_live_devices() {
  local token value

  if [[ -r /proc/cmdline ]]; then
    for token in $(< /proc/cmdline); do
      case "$token" in
        live-media=*)
          value="${token#live-media=}"
          case "$value" in
            /dev/*)
              printf '%s\n' "$value"
              ;;
            UUID=*)
              blkid -U "${value#UUID=}" 2>/dev/null || true
              ;;
            LABEL=*)
              blkid -L "${value#LABEL=}" 2>/dev/null || true
              ;;
          esac
          ;;
      esac
    done
  fi

  blkid -L BEAGLEOS 2>/dev/null || blkid -L PVETHIN 2>/dev/null || true
  lsblk -lnpo PATH,TYPE,FSTYPE,LABEL,RM,TRAN 2>/dev/null | awk '
    $2 == "part" {
      # Only treat explicit Beagle labels or actually removable/USB media as
      # live-medium candidates. A normal internal EFI vfat partition must not
      # cause the whole system disk to be excluded from the target picker.
      if ($4 == "BEAGLEOS" || $4 == "PVETHIN" || $5 == "1" || $6 == "usb") {
        print $1
      }
    }
  '
}

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
