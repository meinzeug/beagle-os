#!/usr/bin/env bash

live_medium_have_mount_privileges() {
  [[ "${EUID}" -eq 0 ]] || (command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1)
}

live_medium_run_privileged() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
    return
  fi

  sudo -n "$@"
}

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

mount_candidate_live_medium() {
  local mount_mode="$1"
  local mount_template="$2"
  local validator_fn="$3"
  local device mount_dir

  live_medium_have_mount_privileges || return 1

  while IFS= read -r device; do
    [[ -n "$device" && -b "$device" ]] || continue
    mount_dir="$(mktemp -d "$mount_template")"
    if live_medium_run_privileged mount -o "$mount_mode" "$device" "$mount_dir" >/dev/null 2>&1; then
      if "$validator_fn" "$mount_dir" "$device"; then
        printf '%s\t%s\n' "$device" "$mount_dir"
        return 0
      fi
      live_medium_run_privileged umount "$mount_dir" >/dev/null 2>&1 || true
    fi
    rmdir "$mount_dir" >/dev/null 2>&1 || true
  done < <(candidate_live_devices | awk 'NF && !seen[$0]++')

  return 1
}

candidate_live_mounts() {
  local target
  local -a candidates=("${LIVE_MEDIUM_DEFAULT:-/run/live/medium}" "/run/live/medium" "/lib/live/mount/medium")

  if command -v findmnt >/dev/null 2>&1; then
    while IFS= read -r target; do
      [[ -n "$target" ]] || continue
      candidates+=("$target")
    done < <(findmnt -rn -o TARGET 2>/dev/null || true)
  fi

  for target in "${candidates[@]}"; do
    [[ -d "$target" ]] || continue
    printf '%s\n' "$target"
  done
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

candidate_preset_path() {
  local target="$1"
  local require_boot_assets="${2:-1}"

  if [[ -f "$target/pve-thin-client/preset.env" ]]; then
    printf '%s\n' "$target/pve-thin-client/preset.env"
    return 0
  fi

  if candidate_live_asset_dir "$target" "$require_boot_assets" >/dev/null 2>&1 && [[ -f "$target/preset.env" ]]; then
    printf '%s\n' "$target/preset.env"
    return 0
  fi

  return 1
}

live_medium_contains_manifest_or_assets() {
  local target="$1"
  local require_boot_assets="${2:-0}"

  candidate_manifest_path "$target" "$require_boot_assets" >/dev/null 2>&1 || \
    candidate_live_asset_dir "$target" "$require_boot_assets" >/dev/null 2>&1
}

live_medium_contains_preset_or_assets() {
  local target="$1"
  local require_boot_assets="${2:-1}"

  candidate_preset_path "$target" "$require_boot_assets" >/dev/null 2>&1 || \
    candidate_live_asset_dir "$target" "$require_boot_assets" >/dev/null 2>&1
}

live_medium_contains_persist_root() {
  local target="$1"

  [[ -d "$target/pve-thin-client" ]]
}
