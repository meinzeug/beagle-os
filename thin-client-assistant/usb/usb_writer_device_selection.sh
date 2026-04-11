#!/usr/bin/env bash

choose_device() {
  local options=()
  local zenity_rows=()
  local device tty_path name size model type rm transport answer index zenity_status selected_device
  local menu_height=16

  tty_path="$(detect_tty_path || true)"

  while IFS=$'\x1f' read -r name size model type rm transport; do
    [[ "$type" == "disk" ]] || continue
    device="/dev/${name}"
    [[ "$device" == /dev/loop* || "$device" == /dev/sr* || "$device" == /dev/ram* || "$device" == /dev/zram* ]] && continue
    if [[ "$ALLOW_NON_USB_DEVICE" != "1" && "${rm:-0}" != "1" && "${transport:-}" != "usb" ]]; then
      continue
    fi
    options+=("$device" "${model:-disk} ${size:-unknown} usb=${transport:-}")
    zenity_rows+=("$device" "${size:-unknown}" "${model:-disk}" "${transport:-unknown}")
  done < <(list_candidate_devices_tsv)

  if (( ${#options[@]} == 0 )); then
    if [[ "$ALLOW_NON_USB_DEVICE" != "1" ]]; then
      echo "No removable/USB target device found. Re-run with --allow-non-usb to show all disks." >&2
      exit 1
    fi
    echo "No writable block device found." >&2
    exit 1
  fi

  if have_tui_dialog "$tty_path"; then
    if (( ${#options[@]} / 2 < menu_height )); then
      menu_height=$(( ${#options[@]} / 2 + 6 ))
    fi
    answer="$(run_whiptail "$tty_path" \
      --title "Beagle OS USB Writer" \
      --backtitle "Bootable USB installer creation" \
      --menu "Select the USB target device. The selected drive will be erased completely." \
      22 100 "$menu_height" \
      "${options[@]}")" || return $?
    selected_device="$(extract_block_device_from_text "$answer")"
    [[ -n "$selected_device" && -b "$selected_device" ]] || {
      echo "Terminal device picker returned an invalid selection: ${answer:-<empty>}" >&2
      exit 1
    }
    printf '%s\n' "$selected_device"
    return 0
  fi

  if have_graphical_dialog; then
    if answer="$(run_zenity --list \
      --title="Beagle OS USB Writer" \
      --text="Choose the USB target device for the installer media." \
      --width=920 \
      --height=520 \
      --column="Device" \
      --column="Size" \
      --column="Model" \
      --column="Transport" \
      "${zenity_rows[@]}")"; then
      selected_device="$(extract_block_device_from_text "$answer")"
      if [[ -n "$selected_device" ]]; then
        printf '%s\n' "$selected_device"
        return 0
      fi
      echo "Graphical device picker returned an invalid selection, falling back to terminal selection." >&2
    fi
    zenity_status=$?
    if [[ "$zenity_status" -eq 1 ]]; then
      exit 1
    fi
    echo "Graphical device picker failed, falling back to terminal selection." >&2
  fi

  if [[ -z "$tty_path" ]]; then
    echo "Interactive device selection requires a TTY. Re-run with --device /dev/sdX." >&2
    exit 1
  fi

  {
    echo "Available target devices:"
    print_devices
    echo
  } >"$tty_path"

  index=1
  while (( index <= ${#options[@]} / 2 )); do
    printf '%s) %s %s\n' "$index" "${options[$(( (index - 1) * 2 ))]}" "${options[$(( (index - 1) * 2 + 1 ))]}" >"$tty_path"
    index=$((index + 1))
  done
  printf 'Choice: ' >"$tty_path"
  read -r answer <"$tty_path"
  [[ "$answer" =~ ^[0-9]+$ ]] || {
    echo "Invalid selection: $answer" >&2
    exit 1
  }
  (( answer >= 1 && answer <= ${#options[@]} / 2 )) || {
    echo "Selection out of range: $answer" >&2
    exit 1
  }
  printf '%s\n' "${options[$(( (answer - 1) * 2 ))]}"
}

device_is_usb_like() {
  local device="$1"
  local rm transport

  rm="$(lsblk -dn -o RM "$device" 2>/dev/null | head -n1 | tr -d ' ')"
  transport="$(lsblk -dn -o TRAN "$device" 2>/dev/null | head -n1 | tr -d ' ')"
  [[ "$rm" == "1" || "$transport" == "usb" ]]
}

root_backing_disk() {
  local source pkname
  source="$(findmnt -no SOURCE / 2>/dev/null || true)"
  [[ -n "$source" ]] || return 1
  pkname="$(lsblk -ndo PKNAME "$source" 2>/dev/null | head -n1)"
  [[ -n "$pkname" ]] || return 1
  printf '/dev/%s\n' "$pkname"
}

device_contains_path_source() {
  local path="$1"
  local source

  source="$(findmnt -no SOURCE "$path" 2>/dev/null || true)"
  [[ -n "$source" ]] || return 1
  lsblk -nrpo NAME "$TARGET_DEVICE" 2>/dev/null | grep -Fxq "$source"
}

ensure_target_is_safe() {
  local root_disk device_size

  if [[ "$ALLOW_NON_USB_DEVICE" != "1" ]] && ! device_is_usb_like "$TARGET_DEVICE"; then
    echo "Refusing to write non-USB/non-removable device $TARGET_DEVICE. Use --allow-non-usb to override." >&2
    exit 1
  fi

  root_disk="$(root_backing_disk || true)"
  if [[ "$ALLOW_SYSTEM_DISK" != "1" ]]; then
    if [[ -n "$root_disk" && "$TARGET_DEVICE" == "$root_disk" ]]; then
      echo "Refusing to overwrite the current system disk $TARGET_DEVICE. Use --allow-system-disk to override." >&2
      exit 1
    fi
    if device_contains_path_source / || device_contains_path_source /boot || device_contains_path_source /boot/efi; then
      echo "Refusing to overwrite a disk backing the running system. Use --allow-system-disk to override." >&2
      exit 1
    fi
  fi

  device_size="$(blockdev --getsize64 "$TARGET_DEVICE")"
  if (( device_size < MIN_DEVICE_BYTES )); then
    echo "Target device $TARGET_DEVICE is too small (${device_size} bytes). Need at least ${MIN_DEVICE_BYTES} bytes." >&2
    exit 1
  fi
}

show_target_device() {
  [[ -b "$TARGET_DEVICE" ]] || {
    echo "Block device not found: $TARGET_DEVICE" >&2
    print_devices >&2
    exit 1
  }

  lsblk "$TARGET_DEVICE" 2>/dev/null || true
}

confirm_device_selection() {
  local answer zenity_status tty_path

  show_target_device
  if [[ "$DRY_RUN" == "1" ]]; then
    return 0
  fi
  if [[ "$ASSUME_YES" == "1" ]]; then
    return 0
  fi

  tty_path="$(detect_tty_path || true)"
  if have_tui_dialog "$tty_path"; then
    run_whiptail "$tty_path" \
      --title "Write USB Installer" \
      --backtitle "Beagle OS USB Writer" \
      --yesno "The selected drive will be erased completely and turned into a bootable Beagle OS installer.\n\nTarget: ${TARGET_DEVICE}\nPreset: ${PVE_THIN_CLIENT_PRESET_NAME:-generic}" \
      16 84
    return $?
  fi

  if have_graphical_dialog; then
    if run_zenity --question \
      --title="Write USB Installer" \
      --width=760 \
      --text="The selected drive will be erased completely and turned into a bootable Beagle OS installer.\n\nTarget: ${TARGET_DEVICE}\nPreset: ${PVE_THIN_CLIENT_PRESET_NAME:-generic}" \
      --ok-label="Write USB" \
      --cancel-label="Cancel"; then
      return 0
    fi
    zenity_status=$?
    if [[ "$zenity_status" -eq 1 ]]; then
      return 1
    fi
    echo "Graphical confirmation dialog failed, falling back to terminal prompt." >&2
  fi

  read -r -p "Erase and re-create $TARGET_DEVICE as Beagle OS USB? [y/N]: " answer
  [[ "$answer" =~ ^[Yy]$ ]]
}

confirm_device() {
  show_target_device
  ensure_target_is_safe
}
