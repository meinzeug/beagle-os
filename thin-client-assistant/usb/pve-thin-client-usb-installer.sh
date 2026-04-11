#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_BASENAME="$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
USB_MANIFEST_HELPER_RELATIVE="thin-client-assistant/usb/usb_manifest.py"
USB_WRITER_SOURCES_HELPER_RELATIVE="thin-client-assistant/usb/usb_writer_sources.sh"
USB_WRITER_BOOTSTRAP_HELPER_RELATIVE="thin-client-assistant/usb/usb_writer_bootstrap.sh"
USB_WRITER_WRITE_STAGE_HELPER_RELATIVE="thin-client-assistant/usb/usb_writer_write_stage.sh"
DIST_DIR="$REPO_ROOT/dist/pve-thin-client-installer"
ASSET_DIR="$DIST_DIR/live"
USB_WRITER_VARIANT="${PVE_THIN_CLIENT_USB_WRITER_VARIANT:-${PVE_THIN_CLIENT_USB_WRITER_VARIANT_DEFAULT:-}}"
if [[ -z "$USB_WRITER_VARIANT" ]]; then
  case "$SCRIPT_BASENAME" in
    *live-usb*.sh)
      USB_WRITER_VARIANT="live"
      ;;
    *)
      USB_WRITER_VARIANT="installer"
      ;;
  esac
fi
case "$USB_WRITER_VARIANT" in
  installer|live)
    ;;
  *)
    echo "Unsupported USB writer variant: $USB_WRITER_VARIANT" >&2
    exit 1
    ;;
esac
USB_LABEL="${USB_LABEL:-$([[ "$USB_WRITER_VARIANT" == "live" ]] && printf 'BEAGLELIVE' || printf 'BEAGLEOS')}"
TARGET_DEVICE="${TARGET_DEVICE:-}"
ASSUME_YES="0"
LIST_DEVICES="0"
LIST_JSON="0"
DRY_RUN="0"
REQUIRE_CHECKSUMS="0"
ALLOW_NON_USB_DEVICE="0"
ALLOW_SYSTEM_DISK="0"
RELEASE_PAYLOAD_URL="${RELEASE_PAYLOAD_URL:-}"
INSTALL_PAYLOAD_URL="${INSTALL_PAYLOAD_URL:-${RELEASE_PAYLOAD_URL:-}}"
RELEASE_BOOTSTRAP_URL="${RELEASE_BOOTSTRAP_URL:-${RELEASE_PAYLOAD_URL:-}}"
RELEASE_ISO_URL="${RELEASE_ISO_URL:-}"
BOOTSTRAP_DISABLE_CACHE="${PVE_DCV_BOOTSTRAP_DISABLE_CACHE:-0}"
BOOTSTRAP_CACHE_DIR="${PVE_DCV_BOOTSTRAP_CACHE_DIR:-${XDG_CACHE_HOME:-${HOME:-/root}/.cache}/pve-dcv-usb}"
BOOTSTRAP_DIR=""
BOOTSTRAPPED_STANDALONE="0"
SKIP_CONFIRMATION="${PVE_DCV_SKIP_CONFIRMATION:-0}"
MIN_DEVICE_BYTES="${MIN_DEVICE_BYTES:-4294967296}"
PVE_THIN_CLIENT_PRESET_NAME="${PVE_THIN_CLIENT_PRESET_NAME:-}"
PVE_THIN_CLIENT_PRESET_B64="${PVE_THIN_CLIENT_PRESET_B64:-}"
GRUB_BACKGROUND_SRC="$REPO_ROOT/thin-client-assistant/usb/assets/grub-background.jpg"

project_version_from_root() {
  if [[ -f "$REPO_ROOT/VERSION" ]]; then
    tr -d ' \n\r' < "$REPO_ROOT/VERSION"
    return 0
  fi

  printf 'dev\n'
}

PROJECT_VERSION="$(project_version_from_root)"

usb_manifest_helper() {
  printf '%s\n' "$REPO_ROOT/$USB_MANIFEST_HELPER_RELATIVE"
}

usb_writer_sources_helper() {
  printf '%s\n' "$REPO_ROOT/$USB_WRITER_SOURCES_HELPER_RELATIVE"
}

usb_writer_bootstrap_helper() {
  printf '%s\n' "$REPO_ROOT/$USB_WRITER_BOOTSTRAP_HELPER_RELATIVE"
}

usb_writer_write_stage_helper() {
  printf '%s\n' "$REPO_ROOT/$USB_WRITER_WRITE_STAGE_HELPER_RELATIVE"
}

# shellcheck disable=SC1090
source "$(usb_writer_sources_helper)"
# shellcheck disable=SC1090
source "$(usb_writer_bootstrap_helper)"
# shellcheck disable=SC1090
source "$(usb_writer_write_stage_helper)"

usage() {
  local media_label=""
  media_label="$(usb_writer_media_label "$USB_WRITER_VARIANT")"
  cat <<EOF
Usage: $0 [--device /dev/sdX] [--list-devices] [--yes] [--allow-non-usb] [--allow-system-disk]
       [--json] [--dry-run] [--label NAME] [--require-checksums]

Writes a bootable Beagle OS ${media_label} USB stick.
The script can be started as a normal user and escalates to sudo only for the write phase.
EOF
}

cleanup() {
  if [[ -n "$BOOTSTRAP_DIR" && -d "$BOOTSTRAP_DIR" ]]; then
    rm -rf "$BOOTSTRAP_DIR"
  fi
}
trap cleanup EXIT

rerun_as_root() {
  local sudo_args=()
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi

  if ! command -v sudo >/dev/null 2>&1; then
    echo "sudo is required for USB write operations." >&2
    exit 1
  fi

  [[ -n "$TARGET_DEVICE" ]] && sudo_args+=(--device "$TARGET_DEVICE")
  [[ "$LIST_DEVICES" == "1" ]] && sudo_args+=(--list-devices)
  [[ "$LIST_JSON" == "1" ]] && sudo_args+=(--json)
  [[ "$ASSUME_YES" == "1" ]] && sudo_args+=(--yes)
  [[ "$DRY_RUN" == "1" ]] && sudo_args+=(--dry-run)
  [[ "$REQUIRE_CHECKSUMS" == "1" ]] && sudo_args+=(--require-checksums)
  [[ "$ALLOW_NON_USB_DEVICE" == "1" ]] && sudo_args+=(--allow-non-usb)
  [[ "$ALLOW_SYSTEM_DISK" == "1" ]] && sudo_args+=(--allow-system-disk)
  exec sudo \
    USB_LABEL="$USB_LABEL" \
    RELEASE_PAYLOAD_URL="$RELEASE_PAYLOAD_URL" \
    INSTALL_PAYLOAD_URL="$INSTALL_PAYLOAD_URL" \
    RELEASE_BOOTSTRAP_URL="$RELEASE_BOOTSTRAP_URL" \
    RELEASE_ISO_URL="$RELEASE_ISO_URL" \
    PVE_DCV_SKIP_CONFIRMATION="$SKIP_CONFIRMATION" \
    PVE_DCV_BOOTSTRAP_CACHE_DIR="$BOOTSTRAP_CACHE_DIR" \
    PVE_DCV_BOOTSTRAP_BASE="${PVE_DCV_BOOTSTRAP_BASE:-}" \
    MIN_DEVICE_BYTES="$MIN_DEVICE_BYTES" \
    PVE_THIN_CLIENT_PRESET_NAME="$PVE_THIN_CLIENT_PRESET_NAME" \
    PVE_THIN_CLIENT_PRESET_B64="$PVE_THIN_CLIENT_PRESET_B64" \
    "$0" "${sudo_args[@]}"
}

require_tool() {
  local tool="$1"
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing required tool: $tool" >&2
    exit 1
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --device)
        TARGET_DEVICE="$2"
        shift 2
        ;;
      --list-devices)
        LIST_DEVICES="1"
        shift
        ;;
      --json)
        LIST_JSON="1"
        shift
        ;;
      --yes|--force)
        ASSUME_YES="1"
        shift
        ;;
      --dry-run)
        DRY_RUN="1"
        shift
        ;;
      --require-checksums)
        REQUIRE_CHECKSUMS="1"
        shift
        ;;
      --label)
        USB_LABEL="$2"
        shift 2
        ;;
      --allow-non-usb)
        ALLOW_NON_USB_DEVICE="1"
        shift
        ;;
      --allow-system-disk)
        ALLOW_SYSTEM_DISK="1"
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "Unknown argument: $1" >&2
        usage
        exit 1
        ;;
    esac
  done
}

list_candidate_devices() {
  lsblk -dn -P -o NAME,SIZE,MODEL,TYPE,RM,TRAN
}

list_candidate_devices_tsv() {
  lsblk -J -d -o NAME,SIZE,MODEL,TYPE,RM,TRAN | python3 -c '
import json
import sys

try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(1)

separator = "\x1f"

for item in payload.get("blockdevices", []):
    rm = item.get("rm", 0)
    if isinstance(rm, bool):
        rm = "1" if rm else "0"
    else:
        rm = str(rm or "0")

    values = [
        str(item.get("name", "") or ""),
        str(item.get("size", "") or ""),
        str(item.get("model", "") or ""),
        str(item.get("type", "") or ""),
        rm,
        str(item.get("tran", "") or ""),
    ]
    print(separator.join(values))
'
}

print_devices_json() {
  lsblk -J -d -o PATH,SIZE,MODEL,TYPE,RM,TRAN
}

print_devices() {
  local name size model type rm transport

  printf '%-12s %-8s %-32s %-4s %-3s %s\n' "DEVICE" "SIZE" "MODEL" "RM" "USB" "TRANSPORT"
  while IFS=$'\x1f' read -r name size model type rm transport; do
    [[ "$type" == "disk" ]] || continue
    printf '%-12s %-8s %-32s %-4s %-3s %s\n' \
      "/dev/${name}" \
      "${size:-unknown}" \
      "${model:-disk}" \
      "${rm:-0}" \
      "$([[ "${transport:-}" == "usb" ]] && printf 'yes' || printf 'no')" \
      "${transport:-unknown}"
  done < <(list_candidate_devices_tsv)
}

count_usb_candidates() {
  local count=0
  local name size model type rm transport

  while IFS=$'\x1f' read -r name size model type rm transport; do
    [[ "$type" == "disk" ]] || continue
    if [[ "${rm:-0}" == "1" || "${transport:-}" == "usb" ]]; then
      count=$((count + 1))
    fi
  done < <(list_candidate_devices_tsv)
  printf '%s\n' "$count"
}

have_graphical_dialog() {
  [[ -n "${DISPLAY:-}" ]] && command -v zenity >/dev/null 2>&1
}

detect_tty_path() {
  local tty_path="/dev/tty"

  if [[ -r "$tty_path" && -w "$tty_path" ]]; then
    printf '%s\n' "$tty_path"
  fi
}

have_tui_dialog() {
  local tty_path="${1:-}"
  [[ -n "$tty_path" ]] && command -v whiptail >/dev/null 2>&1
}

run_whiptail() {
  local tty_path="$1"
  shift

  whiptail "$@" --output-fd 3 \
    3>&1 \
    1>"$tty_path" \
    2>"$tty_path" \
    <"$tty_path"
}

zenity_env() {
  local zenity_config_dir="$1"

  env \
    HOME="$zenity_config_dir" \
    XDG_CONFIG_HOME="$zenity_config_dir" \
    XDG_CACHE_HOME="$zenity_config_dir/.cache" \
    XDG_DATA_HOME="$zenity_config_dir/.local/share" \
    XDG_RUNTIME_DIR="$zenity_config_dir/runtime" \
    XDG_CURRENT_DESKTOP="" \
    DESKTOP_SESSION="" \
    GSETTINGS_BACKEND=memory \
    GIO_USE_VFS=local \
    GTK_THEME="${PVE_DCV_ZENITY_THEME:-Adwaita}" \
    GTK_PATH="" \
    GTK_RC_FILES=/dev/null \
    GTK2_RC_FILES=/dev/null \
    GTK_USE_PORTAL=0 \
    NO_AT_BRIDGE=1
}

extract_block_device_from_text() {
  local text="$1"
  printf '%s\n' "$text" | grep -Eo '/dev/[[:alnum:]_.+:/-]+' | tail -n1
}

run_zenity() {
  local zenity_config_dir=""
  local zenity_stderr=""
  local output=""
  local status=0

  zenity_config_dir="$(mktemp -d "${TMPDIR:-/tmp}/pve-dcv-zenity.XXXXXX")"
  zenity_stderr="$zenity_config_dir/stderr.log"
  mkdir -p \
    "$zenity_config_dir/gtk-3.0" \
    "$zenity_config_dir/.cache" \
    "$zenity_config_dir/.local/share" \
    "$zenity_config_dir/runtime"
  chmod 0700 "$zenity_config_dir/runtime"

  output="$(zenity_env "$zenity_config_dir" zenity "$@" 2>"$zenity_stderr")" || status=$?

  if [[ "$status" -ne 0 && "$status" -ne 1 ]] && command -v dbus-run-session >/dev/null 2>&1; then
    status=0
    : >"$zenity_stderr"
    output="$(
      DBUS_SESSION_BUS_ADDRESS="" \
      zenity_env "$zenity_config_dir" \
      dbus-run-session -- \
      zenity "$@" 2>"$zenity_stderr"
    )" || status=$?
  fi

  if [[ -n "$output" ]]; then
    printf '%s\n' "$output"
  fi

  if [[ "$status" -ne 0 && "$status" -ne 1 && -s "$zenity_stderr" ]]; then
    cat "$zenity_stderr" >&2
  fi

  rm -rf "$zenity_config_dir"
  return "$status"
}

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

install_dependencies() {
  local missing=()
  local need_packages="0"
  local tool

  for tool in wipefs parted mkfs.vfat grub-install rsync partprobe udevadm xorriso; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      missing+=("$tool")
      need_packages="1"
    fi
  done

  if [[ ! -d /usr/lib/grub/i386-pc || ! -d /usr/lib/grub/x86_64-efi ]]; then
    need_packages="1"
  fi

  if [[ "$need_packages" != "1" ]]; then
    return 0
  fi

  DEBIAN_FRONTEND=noninteractive apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    dosfstools \
    e2fsprogs \
    parted \
    grub-pc-bin \
    grub-efi-amd64-bin \
    efibootmgr \
    xorriso \
    rsync
}

print_write_plan() {
  usb_writer_print_write_plan
}

parse_args "$@"
if [[ "$LIST_DEVICES" == "1" ]]; then
  if [[ "$LIST_JSON" == "1" ]]; then
    print_devices_json
  else
    print_devices
  fi
  exit 0
fi
require_tool lsblk
if [[ -z "$TARGET_DEVICE" ]]; then
  TARGET_DEVICE="$(choose_device)"
fi
if [[ "$SKIP_CONFIRMATION" != "1" ]]; then
  confirm_device_selection
  SKIP_CONFIRMATION="1"
fi
rerun_as_root
confirm_device
bootstrap_repo_root
install_dependencies
ensure_live_assets
validate_live_assets
echo "Downloads completed. Writing Beagle OS installer USB to $TARGET_DEVICE ..."
write_usb
echo "USB stick completed: $TARGET_DEVICE"
echo "USB installer media prepared on $TARGET_DEVICE"
