#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PRESET_SUMMARY_HELPER="$SCRIPT_DIR/preset_summary.py"
USB_MANIFEST_HELPER="$SCRIPT_DIR/usb_manifest.py"
LIVE_MEDIUM_HELPERS="$SCRIPT_DIR/live_medium_helpers.sh"
INSTALL_PAYLOAD_HELPERS="$SCRIPT_DIR/install_payload_assets.sh"
LIVE_MEDIUM_DEFAULT="${LIVE_MEDIUM:-/run/live/medium}"
LIVE_MEDIUM=""
TEMP_LIVE_MEDIUM_MOUNT=""
TEMP_LOG_PERSIST_MOUNT=""
REMOTE_PAYLOAD_TMP_DIR=""
TARGET_MOUNT="/mnt/pve-thin-client-target"
EFI_MOUNT="$TARGET_MOUNT/boot/efi"
LIVE_ASSET_DIR=""
INSTALL_LIVE_ASSET_DIR=""
INSTALL_ROOT_DIR="$ROOT_DIR"
INSTALL_PAYLOAD_SOURCE_URL=""
STATE_DIR="$TARGET_MOUNT/pve-thin-client/state"
PRESET_FILE=""
PRESET_ACTIVE="0"
LOG_DIR="${PVE_THIN_CLIENT_LOG_DIR:-/tmp/pve-thin-client-logs}"
LOG_FILE="$LOG_DIR/local-installer.log"
RUNTIME_SNAPSHOT_LOG="$LOG_DIR/runtime-snapshot.log"
LOG_PERSIST_DIR=""
LOG_SYNC_IN_PROGRESS=0
LOG_SESSION_ID="${PVE_THIN_CLIENT_LOG_SESSION_ID:-}"
CACHED_STATE_DIR="/run/pve-thin-client"
CACHED_PRESET_FILE="$CACHED_STATE_DIR/bundled-preset.env"
CACHED_MANIFEST_FILE="$CACHED_STATE_DIR/usb-manifest.json"
CACHED_PRESET_SOURCE_FILE="$CACHED_STATE_DIR/bundled-preset.source"
PRESET_SOURCE="unresolved"
GRUB_BACKGROUND_SRC="$ROOT_DIR/usb/assets/grub-background.jpg"
TARGET_DISK_OVERRIDE=""
ASSUME_YES="0"
AUTO_INSTALL="0"
PRINT_TARGETS_JSON="0"
PRINT_PRESET_JSON="0"
PRINT_PRESET_SUMMARY="0"
PRINT_DEBUG_JSON="0"
PRINT_UI_STATE_JSON="0"
CACHE_PRESET_ONLY="0"
LIST_BEAGLE_VMS_JSON="0"
CACHE_BEAGLE_VM_PRESET="0"
CLEAR_CACHED_PRESET="0"
BEAGLE_API_HOST=""
BEAGLE_API_SCHEME="https"
BEAGLE_API_PORT="8006"
BEAGLE_API_VERIFY_TLS="0"
BEAGLE_API_USERNAME=""
BEAGLE_API_PASSWORD=""
BEAGLE_API_NODE=""
BEAGLE_API_VMID=""
PRESET_LOAD_RETRIES="${PVE_THIN_CLIENT_PRESET_LOAD_RETRIES:-6}"
PRESET_LOAD_RETRY_DELAY="${PVE_THIN_CLIENT_PRESET_LOAD_RETRY_DELAY:-1}"

# shellcheck disable=SC1090
source "$LIVE_MEDIUM_HELPERS"
# shellcheck disable=SC1090
source "$INSTALL_PAYLOAD_HELPERS"

MODE="${MODE:-BEAGLE_STREAM_CLIENT}"
CONNECTION_METHOD=""
PROFILE_NAME="default"
RUNTIME_USER="thinclient"
HOSTNAME_VALUE="beagle-os"
AUTOSTART="1"
NETWORK_MODE="dhcp"
NETWORK_INTERFACE="eth0"
NETWORK_STATIC_ADDRESS=""
NETWORK_STATIC_PREFIX="24"
NETWORK_GATEWAY=""
NETWORK_DNS_SERVERS="1.1.1.1 8.8.8.8"
SPICE_URL=""
NOVNC_URL=""
DCV_URL=""
BEAGLE_STREAM_CLIENT_HOST=""
BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST=""
BEAGLE_STREAM_CLIENT_LOCAL_HOST=""
BEAGLE_STREAM_CLIENT_PORT=""
BEAGLE_STREAM_CLIENT_APP="Desktop"
REMOTE_VIEWER_BIN="remote-viewer"
BROWSER_BIN="chromium"
BROWSER_FLAGS="--kiosk --incognito --no-first-run --disable-session-crashed-bubble"
DCV_VIEWER_BIN="dcvviewer"
BEAGLE_STREAM_CLIENT_BIN="beagle-stream-client"
BEAGLE_STREAM_CLIENT_RESOLUTION="auto"
BEAGLE_STREAM_CLIENT_FPS="60"
BEAGLE_STREAM_CLIENT_BITRATE="32000"
BEAGLE_STREAM_CLIENT_VIDEO_CODEC="H.264"
BEAGLE_STREAM_CLIENT_VIDEO_DECODER="software"
BEAGLE_STREAM_CLIENT_AUDIO_CONFIG="stereo"
BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE="1"
BEAGLE_STREAM_CLIENT_QUIT_AFTER="0"
BEAGLE_STREAM_SERVER_API_URL=""
BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL=""
BEAGLE_SCHEME="https"
BEAGLE_HOST=""
BEAGLE_PORT="8006"
BEAGLE_NODE=""
BEAGLE_VMID=""
BEAGLE_REALM="pam"
BEAGLE_VERIFY_TLS="1"
BEAGLE_MANAGER_URL=""
BEAGLE_MANAGER_PINNED_PUBKEY=""
BEAGLE_ENROLLMENT_URL=""
BEAGLE_MANAGER_TOKEN=""
BEAGLE_ENROLLMENT_TOKEN=""
BEAGLE_UPDATE_ENABLED="1"
BEAGLE_UPDATE_CHANNEL="stable"
BEAGLE_UPDATE_BEHAVIOR="prompt"
BEAGLE_UPDATE_FEED_URL=""
BEAGLE_UPDATE_VERSION_PIN=""
BEAGLE_EGRESS_MODE="full"
BEAGLE_EGRESS_TYPE="wireguard"
BEAGLE_EGRESS_INTERFACE="wg-beagle"
BEAGLE_EGRESS_DOMAINS=""
BEAGLE_EGRESS_RESOLVERS="1.1.1.1 8.8.8.8"
BEAGLE_EGRESS_ALLOWED_IPS=""
BEAGLE_EGRESS_WG_ADDRESS=""
BEAGLE_EGRESS_WG_DNS=""
BEAGLE_EGRESS_WG_PUBLIC_KEY=""
BEAGLE_EGRESS_WG_ENDPOINT=""
BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE="25"
BEAGLE_EGRESS_WG_PRIVATE_KEY=""
BEAGLE_EGRESS_WG_PRESHARED_KEY=""
IDENTITY_HOSTNAME=""
IDENTITY_TIMEZONE=""
IDENTITY_LOCALE=""
IDENTITY_KEYMAP=""
IDENTITY_CHROME_PROFILE="default"
CONNECTION_USERNAME=""
CONNECTION_PASSWORD=""
CONNECTION_TOKEN=""
BEAGLE_STREAM_SERVER_USERNAME=""
BEAGLE_STREAM_SERVER_PASSWORD=""
BEAGLE_STREAM_SERVER_PINNED_PUBKEY=""
BEAGLE_STREAM_SERVER_NAME=""
BEAGLE_STREAM_SERVER_STREAM_PORT=""
BEAGLE_STREAM_SERVER_UNIQUEID=""
BEAGLE_STREAM_SERVER_CERT_B64=""
THINCLIENT_PASSWORD=""
BEAGLE_API_HELPER="$SCRIPT_DIR/pve-thin-client-beagle-api.py"

cleanup() {
  persist_logs_to_medium
  if [[ -n "$REMOTE_PAYLOAD_TMP_DIR" && -d "$REMOTE_PAYLOAD_TMP_DIR" ]]; then
    rm -rf "$REMOTE_PAYLOAD_TMP_DIR" >/dev/null 2>&1 || true
  fi
  if [[ -n "$TEMP_LOG_PERSIST_MOUNT" ]]; then
    privileged_run umount "$TEMP_LOG_PERSIST_MOUNT" >/dev/null 2>&1 || true
    rmdir "$TEMP_LOG_PERSIST_MOUNT" >/dev/null 2>&1 || true
  fi
  if [[ -n "$TEMP_LIVE_MEDIUM_MOUNT" ]]; then
    privileged_run umount "$TEMP_LIVE_MEDIUM_MOUNT" >/dev/null 2>&1 || true
    rmdir "$TEMP_LIVE_MEDIUM_MOUNT" >/dev/null 2>&1 || true
  fi
  umount "$EFI_MOUNT" >/dev/null 2>&1 || true
  umount "$TARGET_MOUNT" >/dev/null 2>&1 || true
  rmdir "$EFI_MOUNT" >/dev/null 2>&1 || true
  rmdir "$TARGET_MOUNT" >/dev/null 2>&1 || true
}
trap cleanup EXIT

apply_shell_assignments() {
  local payload="$1"
  local key value

  while IFS=$'\t' read -r key value; do
    [[ "$key" =~ ^[A-Z0-9_]+$ ]] || continue
    declare -p "$key" >/dev/null 2>&1 || continue
    printf -v "$key" '%s' "$value"
  done < <(
    printf '%s\n' "$payload" | python3 - <<'PY'
import shlex
import sys

for raw_line in sys.stdin:
    line = raw_line.strip()
    if not line:
        continue
    parts = shlex.split(line, posix=True)
    if len(parts) != 1 or "=" not in parts[0]:
        continue
    key, value = parts[0].split("=", 1)
    print(f"{key}\t{value}")
PY
  )
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then
      exec sudo "$0" "$@"
    fi
    echo "This installer must run as root." >&2
    exit 1
  fi
}

write_installer_resolv_conf() {
  local dns_servers="${NETWORK_DNS_SERVERS:-1.1.1.1 9.9.9.9 8.8.8.8}"
  local resolver="/etc/resolv.conf"
  local dns=""

  if [[ -L "$resolver" ]]; then
    rm -f "$resolver" >/dev/null 2>&1 || true
  fi

  : >"$resolver"
  for dns in $dns_servers; do
    [[ -n "$dns" ]] || continue
    printf 'nameserver %s\n' "$dns" >>"$resolver"
  done
  printf 'options timeout:1 attempts:3 rotate\n' >>"$resolver"
}

have_apt_dns() {
  getent ahostsv4 deb.debian.org >/dev/null 2>&1 || \
    getent ahostsv4 security.debian.org >/dev/null 2>&1
}

ensure_apt_dns() {
  if have_apt_dns; then
    return 0
  fi

  write_installer_resolv_conf
  sleep 1
  have_apt_dns
}

require_tools() {
  local missing=()
  local tool
  for tool in grub-install mkfs.vfat mkfs.ext4 parted partprobe partx udevadm blockdev lsblk blkid findmnt python3 curl tar; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      missing+=("$tool")
    fi
  done

  if (( ${#missing[@]} > 0 )); then
    if ! ensure_apt_dns; then
      setup_logging
      log_msg "DNS preflight failed before apt-get update"
      {
        echo "=== /etc/resolv.conf ==="
        cat /etc/resolv.conf 2>/dev/null || true
        echo
        echo "=== ip route ==="
        ip route 2>/dev/null || true
      } >>"$LOG_FILE" 2>&1 || true
      echo "DNS resolution for Debian mirrors is unavailable in the installer environment." >&2
      exit 1
    fi
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      dosfstools \
      e2fsprogs \
      parted \
      util-linux \
      udev \
      grub2-common \
      grub-pc-bin \
      grub-efi-amd64-bin \
      efibootmgr \
      python3 \
      curl \
      ca-certificates \
      tar
  fi
}

setup_logging() {
  mkdir -p "$LOG_DIR"
  if [[ -z "$LOG_SESSION_ID" ]]; then
    LOG_SESSION_ID="$(basename "$LOG_DIR")"
  fi
  touch "$LOG_FILE"
  chmod 0644 "$LOG_FILE" >/dev/null 2>&1 || true
}

log_msg() {
  setup_logging
  printf '[%s] %s\n' "$(date -Is 2>/dev/null || date)" "$*" >>"$LOG_FILE"
}

log_unhandled_error() {
  local rc="$1"
  local line="$2"
  local cmd="$3"
  log_msg "unhandled error: rc=$rc line=$line cmd=$cmd"
  log_runtime_snapshot
  persist_logs_to_medium
}

trap 'rc=$?; log_unhandled_error "$rc" "$LINENO" "$BASH_COMMAND"; exit "$rc"' ERR

run_logged() {
  log_msg "running: $*"
  "$@" >>"$LOG_FILE" 2>&1
  sync_logs_to_medium
}

run_logged_step() {
  local label="$1"
  shift
  log_msg "$label"
  run_logged "$@"
}

run_logged_function() {
  local label="$1"
  shift
  log_msg "$label"
  "$@" >>"$LOG_FILE" 2>&1
  sync_logs_to_medium
}

device_root_disk() {
  local device="$1"
  local type="" parent_name=""

  [[ -n "$device" && -b "$device" ]] || return 1
  type="$(lsblk -ndo TYPE "$device" 2>/dev/null || true)"
  if [[ "$type" == "disk" ]]; then
    printf '%s\n' "$device"
    return 0
  fi

  parent_name="$(lsblk -ndo PKNAME "$device" 2>/dev/null || true)"
  [[ -n "$parent_name" ]] || return 1
  printf '/dev/%s\n' "$parent_name"
}

device_resolves_to_root_disk() {
  local candidate="$1"
  local root_disk="$2"
  local resolved=""

  [[ -n "$candidate" && -n "$root_disk" ]] || return 1
  resolved="$(device_root_disk "$candidate" 2>/dev/null || true)"
  [[ -n "$resolved" && "$resolved" == "$root_disk" ]]
}

wait_for_block_device() {
  local device="$1"
  local attempts="${2:-20}"
  local delay="${3:-0.5}"
  local attempt=1
  local ro_state=""

  while (( attempt <= attempts )); do
    if [[ -b "$device" ]]; then
      ro_state="$(blockdev --getro "$device" 2>/dev/null || printf '1')"
      if [[ "$ro_state" == "0" ]]; then
        return 0
      fi
      log_msg "wait_for_block_device: $device exists but is still read-only (attempt $attempt/$attempts)"
    else
      log_msg "wait_for_block_device: $device not present yet (attempt $attempt/$attempts)"
    fi
    udevadm settle >/dev/null 2>&1 || true
    sleep "$delay"
    attempt=$((attempt + 1))
  done

  log_msg "wait_for_block_device: $device did not become writable in time"
  return 1
}

refresh_partition_table() {
  local target_disk="$1"
  local attempt=1

  while (( attempt <= 10 )); do
    log_msg "refresh_partition_table: target=$target_disk attempt=$attempt"
    blockdev --rereadpt "$target_disk" >>"$LOG_FILE" 2>&1 || true
    partprobe "$target_disk" >>"$LOG_FILE" 2>&1 || true
    partx -u "$target_disk" >>"$LOG_FILE" 2>&1 || true
    udevadm settle >>"$LOG_FILE" 2>&1 || true
    sync_logs_to_medium
    sleep 0.5
    attempt=$((attempt + 1))
  done
}

wait_for_target_partitions() {
  local target_disk="$1"
  shift
  local part=""

  refresh_partition_table "$target_disk"
  for part in "$@"; do
    wait_for_block_device "$part" 20 0.5 || return 1
  done
}

run_logged_step_with_retry() {
  local label="$1"
  local attempts="$2"
  local delay="$3"
  shift 3
  local attempt=1
  local rc=0

  while (( attempt <= attempts )); do
    log_msg "$label (attempt $attempt/$attempts)"
    if "$@" >>"$LOG_FILE" 2>&1; then
      sync_logs_to_medium
      return 0
    fi
    rc=$?
    sync_logs_to_medium
    log_msg "$label failed with rc=$rc"
    if (( attempt >= attempts )); then
      return "$rc"
    fi
    sleep "$delay"
    attempt=$((attempt + 1))
  done

  return "$rc"
}

log_runtime_snapshot() {
  setup_logging
  {
    echo "=== date ==="
    date -Is 2>/dev/null || date
    echo
    echo "=== /proc/cmdline ==="
    cat /proc/cmdline 2>/dev/null || true
    echo
    echo "=== findmnt ==="
    findmnt -rn -o TARGET,SOURCE,FSTYPE,OPTIONS 2>/dev/null || true
    echo
    echo "=== lsblk ==="
    lsblk -e7 -o NAME,PATH,SIZE,TYPE,FSTYPE,LABEL,UUID,RM,TRAN,MOUNTPOINTS 2>/dev/null || true
    echo
    echo "=== blkid ==="
    blkid 2>/dev/null || true
  } >>"$RUNTIME_SNAPSHOT_LOG" 2>&1 || true
}

persist_logs_to_medium() {
  local persist_root=""
  local session_dir=""
  local marker_file=""
  local persist_parent=""

  setup_logging
  LOG_PERSIST_DIR=""

  if ! running_from_live_environment; then
    log_msg "persist_logs_to_medium: skipping because current session is not a live boot"
    return 0
  fi

  if [[ -z "$LIVE_MEDIUM" ]]; then
    LIVE_MEDIUM="$(resolve_live_medium || true)"
  fi

  if [[ -n "$LIVE_MEDIUM" ]] && [[ -d "$LIVE_MEDIUM/pve-thin-client" ]]; then
    if [[ -w "$LIVE_MEDIUM/pve-thin-client" ]]; then
      persist_root="$LIVE_MEDIUM"
    elif mountpoint -q "$LIVE_MEDIUM"; then
      privileged_run mount -o remount,rw "$LIVE_MEDIUM" >/dev/null 2>&1 || \
        privileged_run mount -o remount,rw "$(findmnt -n -o SOURCE "$LIVE_MEDIUM" 2>/dev/null || true)" "$LIVE_MEDIUM" >/dev/null 2>&1 || true
      if [[ -w "$LIVE_MEDIUM/pve-thin-client" ]]; then
        persist_root="$LIVE_MEDIUM"
      fi
    fi
  fi

  if [[ -z "$persist_root" ]]; then
    persist_root="$(mount_writable_live_medium_for_logs || true)"
  fi

  if [[ -n "$persist_root" ]]; then
    session_dir="$(sanitize_log_session_id)"
    persist_parent="$persist_root/pve-thin-client/logs"
    if mkdir -p "$persist_parent/$session_dir" >/dev/null 2>&1 && [[ -w "$persist_parent/$session_dir" ]]; then
      LOG_PERSIST_DIR="$persist_parent/$session_dir"
    else
      log_msg "persist_logs_to_medium: unable to prepare writable log directory under $persist_root"
    fi
  fi

  if [[ -n "$LOG_PERSIST_DIR" ]]; then
    cp -a "$LOG_DIR/." "$LOG_PERSIST_DIR/" 2>/dev/null || true
    printf '%s\n' "$session_dir" >"$persist_parent/LATEST.txt" 2>/dev/null || true
    marker_file="$LOG_PERSIST_DIR/session.env"
    {
      printf 'LOG_SESSION_ID=%s\n' "$session_dir"
      printf 'LOG_DIR=%s\n' "$LOG_DIR"
      printf 'LIVE_MEDIUM=%s\n' "$LIVE_MEDIUM"
      printf 'PRESET_FILE=%s\n' "$PRESET_FILE"
      printf 'PRESET_SOURCE=%s\n' "$PRESET_SOURCE"
      printf 'DATE=%s\n' "$(date -Is 2>/dev/null || date)"
    } >"$marker_file" 2>/dev/null || true
    sync "$marker_file" "$persist_parent/LATEST.txt" "$LOG_PERSIST_DIR" >/dev/null 2>&1 || sync >/dev/null 2>&1 || true
    return 0
  fi

  log_msg "persist_logs_to_medium: live medium for log persistence is still unavailable"
  return 0
}

sync_logs_to_medium() {
  [[ "$LOG_SYNC_IN_PROGRESS" == "1" ]] && return 0
  LOG_SYNC_IN_PROGRESS=1
  persist_logs_to_medium >/dev/null 2>&1 || true
  LOG_SYNC_IN_PROGRESS=0
}

have_passwordless_sudo() {
  command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1
}

privileged_run() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
    return
  fi

  if have_passwordless_sudo; then
    sudo -n "$@"
    return
  fi

  return 1
}

installer_ui_is_text() {
  if [[ "${PVE_THIN_CLIENT_INSTALLER_UI:-}" == "text" ]]; then
    return 0
  fi

  if [[ -r /proc/cmdline ]]; then
    grep -Eq '(^| )pve_thin_client\.installer_ui=text( |$)' /proc/cmdline 2>/dev/null
    return $?
  fi

  return 1
}

resolve_tty_path() {
  local path="/dev/tty"
  if [[ -r "$path" && -w "$path" ]]; then
    printf '%s\n' "$path"
    return 0
  fi
  return 1
}

tty_note() {
  local path=""
  path="$(resolve_tty_path 2>/dev/null || true)"
  if [[ -n "$path" ]]; then
    printf '%s\n' "$*" >"$path"
  else
    printf '%s\n' "$*"
  fi
}

running_from_live_environment() {
  if [[ -d /run/live/medium || -d /lib/live/mount/medium ]]; then
    return 0
  fi

  if [[ -r /proc/cmdline ]]; then
    grep -Eq '(^| )boot=live( |$)|(^| )pve_thin_client\.mode=installer( |$)' /proc/cmdline 2>/dev/null
    return $?
  fi

  return 1
}

sanitize_log_session_id() {
  local raw="${LOG_SESSION_ID:-$(basename "$LOG_DIR")}"
  raw="${raw:-session}"
  printf '%s\n' "$raw" | tr -cs 'A-Za-z0-9._-' '-'
}

partition_suffix() {
  local device="$1"
  local number="$2"
  if [[ "$device" =~ [0-9]$ ]]; then
    printf '%sp%s\n' "$device" "$number"
  else
    printf '%s%s\n' "$device" "$number"
  fi
}

append_live_disk_candidates() {
  local device="$1" type parent_name
  [[ -n "$device" ]] || return 1
  [[ -b "$device" ]] || return 1

  type="$(lsblk -ndo TYPE "$device" 2>/dev/null || true)"
  if [[ "$type" == "disk" ]]; then
    printf '%s\n' "$device"
    return 0
  fi

  parent_name="$(lsblk -ndo PKNAME "$device" 2>/dev/null || true)"
  if [[ -n "$parent_name" ]]; then
    printf '/dev/%s\n' "$parent_name"
    return 0
  fi

  return 1
}

current_live_disks() {
  local medium_source

  medium_source="$(findmnt -n -o SOURCE "$LIVE_MEDIUM" 2>/dev/null || true)"
  if [[ -n "$medium_source" ]]; then
    append_live_disk_candidates "$medium_source" 2>/dev/null || true
    return 0
  fi

  while IFS= read -r medium_source; do
    [[ -n "$medium_source" ]] || continue
    append_live_disk_candidates "$medium_source" 2>/dev/null || true
  done < <(candidate_live_devices | awk 'NF && !seen[$0]++')
}

current_live_disk() {
  local disk
  disk="$(current_live_disks | awk 'NF && !seen[$0]++ { print; exit }')"
  if [[ -n "$disk" ]]; then
    printf '%s\n' "$disk"
    return 0
  fi
  return 1
}

cached_preset_source() {
  if [[ -f "$CACHED_PRESET_SOURCE_FILE" ]]; then
    head -n 1 "$CACHED_PRESET_SOURCE_FILE" 2>/dev/null || printf 'cache\n'
    return 0
  fi

  printf 'cache\n'
}

restore_preset_from_cmdline() {
  mkdir -p "$CACHED_STATE_DIR"

  if python3 - "$CACHED_PRESET_FILE" "$CACHED_PRESET_SOURCE_FILE" <<'PY'
import base64
import gzip
import re
import sys
from pathlib import Path

target = Path(sys.argv[1])
source = Path(sys.argv[2])
cmdline = Path("/proc/cmdline").read_text(encoding="utf-8").strip()

codec = ""
chunks = {}

for token in cmdline.split():
    if token.startswith("pve_thin_client.preset_codec="):
        codec = token.split("=", 1)[1]
        continue

    match = re.match(r"pve_thin_client\.preset_b64_(\d+)=([A-Za-z0-9_-]+)$", token)
    if match:
        chunks[int(match.group(1))] = match.group(2)
        continue

    if token.startswith("pve_thin_client.preset_b64="):
        chunks[0] = token.split("=", 1)[1]

if not chunks:
    raise SystemExit(1)

payload = "".join(chunks[index] for index in sorted(chunks))
payload += "=" * (-len(payload) % 4)
data = base64.urlsafe_b64decode(payload.encode("ascii"))

if codec in ("", "base64url"):
    decoded = data
elif codec in ("gzip+base64url", "gz+base64url", "gzip"):
    decoded = gzip.decompress(data)
else:
    raise SystemExit(f"unsupported preset codec: {codec}")

target.write_bytes(decoded)
target.chmod(0o644)
source.write_text("cmdline\n", encoding="utf-8")
PY
  then
    PRESET_SOURCE="cmdline"
    log_msg "restored bundled preset from kernel cmdline to $CACHED_PRESET_FILE"
    return 0
  fi

  return 1
}

mount_discovered_live_medium() {
  local mounted=""
  local device=""
  local mount_dir=""

  mounted="$(mount_candidate_live_medium ro /tmp/pve-live-medium.XXXXXX live_medium_contains_preset_or_assets || true)"
  [[ -n "$mounted" ]] || return 1
  device="${mounted%%$'\t'*}"
  mount_dir="${mounted#*$'\t'}"
  TEMP_LIVE_MEDIUM_MOUNT="$mount_dir"
  log_msg "mounted live medium at $mount_dir from $device"
  printf '%s\n' "$mount_dir"
  return 0
}

mount_writable_live_medium_for_logs() {
  local mounted=""
  local device=""
  local mount_dir=""

  mounted="$(mount_candidate_live_medium rw /tmp/pve-live-logs.XXXXXX live_medium_contains_persist_root || true)"
  if [[ -n "$mounted" ]]; then
    device="${mounted%%$'\t'*}"
    mount_dir="${mounted#*$'\t'}"
    TEMP_LOG_PERSIST_MOUNT="$mount_dir"
    log_msg "mounted writable live medium for log persistence: $device -> $mount_dir"
    printf '%s\n' "$mount_dir"
    return 0
  fi

  log_msg "mount_writable_live_medium_for_logs: no writable live medium available"
  return 1
}

resolve_live_medium() {
  local target

  while IFS= read -r target; do
    [[ -n "$target" ]] || continue
    log_msg "candidate live mount: $target"
    if live_medium_contains_preset_or_assets "$target" 1; then
      log_msg "resolved live medium via existing mount: $target"
      printf '%s\n' "$target"
      return 0
    fi
  done < <(candidate_live_mounts | awk 'NF && !seen[$0]++')

  if mount_discovered_live_medium >/dev/null; then
    printf '%s\n' "$TEMP_LIVE_MEDIUM_MOUNT"
    return 0
  fi

  log_msg "unable to resolve live medium"
  return 1
}

resolve_preset_file() {
  local target

  restore_preset_from_cmdline || true

  if [[ -f "$CACHED_PRESET_FILE" ]]; then
    log_msg "resolved preset file via cached runtime state: $CACHED_PRESET_FILE"
    printf '%s\n' "$CACHED_PRESET_FILE"
    return 0
  fi

  while IFS= read -r target; do
    [[ -n "$target" ]] || continue
    log_msg "candidate live mount: $target"
    if target="$(candidate_preset_path "$target" 2>/dev/null || true)" && [[ -n "$target" ]]; then
      log_msg "resolved preset file via existing mount: $target"
      printf '%s\n' "$target"
      return 0
    fi
  done < <(candidate_live_mounts | awk 'NF && !seen[$0]++')

  if target="$(mount_discovered_live_medium 2>/dev/null || true)" && [[ -n "$target" ]]; then
    if target="$(candidate_preset_path "$target" 2>/dev/null || true)" && [[ -n "$target" ]]; then
      log_msg "resolved preset file via mounted device: $target"
      printf '%s\n' "$target"
      return 0
    fi
  fi

  log_msg "unable to resolve preset file"
  return 1
}

initialize_live_medium() {
  local live_asset_dir=""

  PRESET_FILE="$(resolve_preset_file || true)"
  if [[ -n "$PRESET_FILE" ]]; then
    if [[ "$PRESET_FILE" == "$CACHED_PRESET_FILE" ]]; then
      PRESET_SOURCE="$(cached_preset_source)"
      if [[ -n "$LIVE_MEDIUM" ]]; then
        live_asset_dir="$(candidate_live_asset_dir "$LIVE_MEDIUM" 1 2>/dev/null || true)"
      fi
    elif [[ "$PRESET_FILE" == */pve-thin-client/preset.env ]]; then
      LIVE_MEDIUM="$(dirname "$(dirname "$PRESET_FILE")")"
      live_asset_dir="$(candidate_live_asset_dir "$LIVE_MEDIUM" 1 2>/dev/null || true)"
    else
      PRESET_SOURCE="medium"
      live_asset_dir="$(dirname "$PRESET_FILE")"
      LIVE_MEDIUM="$live_asset_dir"
    fi
  fi

  if [[ -z "$LIVE_MEDIUM" ]]; then
    LIVE_MEDIUM="$(resolve_live_medium || true)"
  fi
  if [[ -z "$LIVE_MEDIUM" ]]; then
    LIVE_MEDIUM="$LIVE_MEDIUM_DEFAULT"
  fi

  if [[ -z "$live_asset_dir" ]]; then
    live_asset_dir="$(candidate_live_asset_dir "$LIVE_MEDIUM" 1 2>/dev/null || true)"
  fi
  if [[ -n "$live_asset_dir" ]]; then
    LIVE_ASSET_DIR="$live_asset_dir"
  else
    LIVE_ASSET_DIR="$LIVE_MEDIUM/pve-thin-client/live"
  fi
  if [[ -z "$PRESET_FILE" ]]; then
    PRESET_FILE="$(candidate_preset_path "$LIVE_MEDIUM" 2>/dev/null || true)"
  fi
  if [[ -z "$PRESET_FILE" && -f "$LIVE_MEDIUM/pve-thin-client/preset.env" ]]; then
    PRESET_FILE="$LIVE_MEDIUM/pve-thin-client/preset.env"
  fi
  if [[ -z "$PRESET_FILE" && -f "$LIVE_ASSET_DIR/preset.env" ]]; then
    PRESET_FILE="$LIVE_ASSET_DIR/preset.env"
  fi

  if [[ "$PRESET_SOURCE" == "unresolved" && -f "$PRESET_FILE" ]]; then
    PRESET_SOURCE="medium"
  fi

  log_msg "initialize_live_medium: LIVE_MEDIUM=$LIVE_MEDIUM"
  log_msg "initialize_live_medium: LIVE_ASSET_DIR=$LIVE_ASSET_DIR"
  log_msg "initialize_live_medium: PRESET_FILE=$PRESET_FILE"
  log_msg "initialize_live_medium: PRESET_SOURCE=$PRESET_SOURCE"
  persist_logs_to_medium
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mode)
        MODE="$2"
        shift 2
        ;;
      --target-disk)
        TARGET_DISK_OVERRIDE="$2"
        shift 2
        ;;
      --yes|--force)
        ASSUME_YES="1"
        shift
        ;;
      --auto-install)
        AUTO_INSTALL="1"
        shift
        ;;
      --list-targets-json)
        PRINT_TARGETS_JSON="1"
        shift
        ;;
      --print-preset-json)
        PRINT_PRESET_JSON="1"
        shift
        ;;
      --print-preset-summary)
        PRINT_PRESET_SUMMARY="1"
        shift
        ;;
      --print-debug-json)
        PRINT_DEBUG_JSON="1"
        shift
        ;;
      --print-ui-state-json)
        PRINT_UI_STATE_JSON="1"
        shift
        ;;
      --cache-bundled-preset)
        CACHE_PRESET_ONLY="1"
        shift
        ;;
      --list-beagle-vms-json)
        LIST_BEAGLE_VMS_JSON="1"
        shift
        ;;
      --cache-beagle-vm-preset)
        CACHE_BEAGLE_VM_PRESET="1"
        shift
        ;;
      --clear-cached-preset)
        CLEAR_CACHED_PRESET="1"
        shift
        ;;
      --beagle-api-host)
        BEAGLE_API_HOST="$2"
        shift 2
        ;;
      --beagle-api-scheme)
        BEAGLE_API_SCHEME="$2"
        shift 2
        ;;
      --beagle-api-port)
        BEAGLE_API_PORT="$2"
        shift 2
        ;;
      --beagle-api-verify-tls)
        BEAGLE_API_VERIFY_TLS="$2"
        shift 2
        ;;
      --beagle-api-username)
        BEAGLE_API_USERNAME="$2"
        shift 2
        ;;
      --beagle-api-password)
        BEAGLE_API_PASSWORD="$2"
        shift 2
        ;;
      --beagle-api-node)
        BEAGLE_API_NODE="$2"
        shift 2
        ;;
      --beagle-api-vmid)
        BEAGLE_API_VMID="$2"
        shift 2
        ;;
      *)
        echo "Unknown argument: $1" >&2
        exit 1
        ;;
    esac
  done
}

require_beagle_api_helper() {
  if [[ ! -x "$BEAGLE_API_HELPER" ]]; then
    echo "Missing Beagle API helper: $BEAGLE_API_HELPER" >&2
    exit 1
  fi
}

validate_beagle_api_args() {
  [[ -n "$BEAGLE_API_HOST" ]] || {
    echo "Missing --beagle-api-host" >&2
    exit 1
  }
  [[ -n "$BEAGLE_API_USERNAME" ]] || {
    echo "Missing --beagle-api-username" >&2
    exit 1
  }
  [[ -n "$BEAGLE_API_PASSWORD" ]] || {
    echo "Missing --beagle-api-password" >&2
    exit 1
  }
}

clear_cached_preset() {
  rm -f "$CACHED_PRESET_FILE" "$CACHED_PRESET_SOURCE_FILE"
  log_msg "cleared cached preset state"
}

list_beagle_vms_json() {
  require_beagle_api_helper
  validate_beagle_api_args

  "$BEAGLE_API_HELPER" \
    --host "$BEAGLE_API_HOST" \
    --scheme "$BEAGLE_API_SCHEME" \
    --port "$BEAGLE_API_PORT" \
    --verify-tls "$BEAGLE_API_VERIFY_TLS" \
    --username "$BEAGLE_API_USERNAME" \
    --password "$BEAGLE_API_PASSWORD" \
    list-vms-json
}

cache_beagle_vm_preset() {
  local tmp_preset=""
  local helper_args=()

  require_beagle_api_helper
  validate_beagle_api_args
  [[ -n "$BEAGLE_API_VMID" ]] || {
    echo "Missing --beagle-api-vmid" >&2
    exit 1
  }

  mkdir -p "$CACHED_STATE_DIR"
  tmp_preset="$(mktemp "$CACHED_STATE_DIR/beagle-preset.XXXXXX")"
  helper_args=(
    --host "$BEAGLE_API_HOST"
    --scheme "$BEAGLE_API_SCHEME"
    --port "$BEAGLE_API_PORT"
    --verify-tls "$BEAGLE_API_VERIFY_TLS"
    --username "$BEAGLE_API_USERNAME"
    --password "$BEAGLE_API_PASSWORD"
    build-preset-env
    --vmid "$BEAGLE_API_VMID"
  )
  if [[ -n "$BEAGLE_API_NODE" ]]; then
    helper_args+=(--node "$BEAGLE_API_NODE")
  fi
  "$BEAGLE_API_HELPER" \
    "${helper_args[@]}" >"$tmp_preset"

  install -m 0644 "$tmp_preset" "$CACHED_PRESET_FILE"
  printf 'beagle-api\n' >"$CACHED_PRESET_SOURCE_FILE"
  rm -f "$tmp_preset"
  PRESET_FILE="$CACHED_PRESET_FILE"
  PRESET_SOURCE="beagle-api"
  PRESET_ACTIVE="0"
  load_embedded_preset || true
  log_msg "cached beagle preset for vmid=$BEAGLE_API_VMID host=$BEAGLE_API_HOST source=$PRESET_SOURCE"
  persist_logs_to_medium
}

print_target_disks_json() {
  local live_disk
  live_disk="$(current_live_disk 2>/dev/null || true)"

  python3 - "$live_disk" <<'PY'
import json
import shlex
import subprocess
import sys

live_disk = sys.argv[1]
result = []
output = subprocess.check_output(
    ["lsblk", "-dn", "-P", "-o", "NAME,SIZE,MODEL,TYPE,RM,TRAN"], text=True
)

for line in output.splitlines():
    entry = {}
    for token in shlex.split(line):
      key, value = token.split("=", 1)
      entry[key] = value
    if entry.get("TYPE") != "disk":
        continue
    device = f"/dev/{entry['NAME']}"
    if device == live_disk:
        continue
    if any(device.startswith(prefix) for prefix in ("/dev/loop", "/dev/sr", "/dev/ram", "/dev/zram")):
        continue
    result.append(
        {
            "device": device,
            "size": entry.get("SIZE", "unknown"),
            "model": entry.get("MODEL", "disk"),
            "removable": entry.get("RM", "0"),
            "transport": entry.get("TRAN", ""),
        }
    )

print(json.dumps(result, indent=2))
PY
}

choose_target_disk() {
  local live_disk menu_items preferred_items fallback_items device label name size model type rm transport answer tty_path live_flag root_candidate
  local -a live_disks=()
  if [[ -n "$TARGET_DISK_OVERRIDE" ]]; then
    printf '%s\n' "$TARGET_DISK_OVERRIDE"
    return 0
  fi

  if mapfile -t live_disks < <(current_live_disks | awk 'NF && !seen[$0]++'); then
    :
  fi
  live_disk="${live_disks[0]:-}"
  menu_items=()
  preferred_items=()
  fallback_items=()
  tty_path="/dev/tty"

  if [[ ! -r "$tty_path" || ! -w "$tty_path" ]]; then
    tty_path=""
  fi

  while IFS=$'\x1f' read -r name size model type rm transport; do
    [[ "$type" == "disk" ]] || continue
    device="/dev/${name}"
    [[ "$device" == /dev/loop* || "$device" == /dev/sr* || "$device" == /dev/ram* || "$device" == /dev/zram* ]] && continue
    [[ "$device" == /dev/mmcblk*boot* || "$device" == /dev/mmcblk*rpmb* ]] && continue
    live_flag="0"
    if printf '%s\n' "${live_disks[@]}" | grep -Fxq "$device"; then
      live_flag="1"
    else
      for root_candidate in "${live_disks[@]}"; do
        if device_resolves_to_root_disk "$device" "$root_candidate"; then
          live_flag="1"
          break
        fi
      done
    fi
    label="${model:-disk} ${size:-unknown} rm=${rm:-0} ${transport:-}"
    log_msg "choose_target_disk: candidate device=$device size=${size:-unknown} model=${model:-disk} rm=${rm:-0} tran=${transport:-} live=$live_flag"
    if [[ "${rm:-0}" != "1" && "${transport:-}" != "usb" ]]; then
      # Never offer the currently booted live medium as install target.
      [[ "$live_flag" == "1" ]] && continue
      preferred_items+=("$device" "$label")
      continue
    fi
    [[ "$live_flag" == "1" ]] && continue
    fallback_items+=("$device" "$label")
  done < <(
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
  )

  if (( ${#preferred_items[@]} > 0 )); then
    menu_items=("${preferred_items[@]}")
    log_msg "choose_target_disk: using preferred internal-disk candidate set"
  else
    menu_items=("${fallback_items[@]}")
    log_msg "choose_target_disk: no preferred internal disks found, falling back to non-live removable candidates"
  fi

  if (( ${#menu_items[@]} == 0 )); then
    log_msg "choose_target_disk: no target disk candidates available"
    log_runtime_snapshot
    persist_logs_to_medium
    echo "No writable target disk found." >&2
    exit 1
  fi

  if command -v whiptail >/dev/null 2>&1 && ! installer_ui_is_text; then
    whiptail --title "Thinclient Installation" --menu \
      "Choose the target disk. It will be erased completely." 22 96 10 \
      "${menu_items[@]}" 3>&1 1>&2 2>&3
    return 0
  fi

  if [[ -z "$tty_path" ]]; then
    if (( ${#menu_items[@]} >= 2 )); then
      log_msg "choose_target_disk: non-interactive mode, auto-selecting ${menu_items[0]}"
      printf '%s\n' "${menu_items[0]}"
      return 0
    fi
    echo "Interactive disk selection requires a TTY." >&2
    exit 1
  fi

  local index=1
  printf '\n[Beagle OS Installation]\n' >"$tty_path"
  printf 'Choose the target disk. It will be erased completely.\n\n' >"$tty_path"
  while (( index <= ${#menu_items[@]} / 2 )); do
    printf '%s) %s %s\n' "$index" "${menu_items[$(( (index - 1) * 2 ))]}" "${menu_items[$(( (index - 1) * 2 + 1 ))]}" >"$tty_path"
    index=$((index + 1))
  done

  printf '\nType the number of the target disk and press ENTER: ' >"$tty_path"
  read -r answer <"$tty_path"
  [[ "$answer" =~ ^[0-9]+$ ]] || {
    echo "Invalid selection: $answer" >&2
    exit 1
  }
  (( answer >= 1 && answer <= ${#menu_items[@]} / 2 )) || {
    echo "Selection out of range: $answer" >&2
    exit 1
  }
  printf '%s\n' "${menu_items[$(( (answer - 1) * 2 ))]}"
}

confirm_wipe() {
  local target_disk="$1"
  local answer=""
  local path=""
  if [[ "$ASSUME_YES" == "1" ]]; then
    return 0
  fi

  if command -v whiptail >/dev/null 2>&1 && ! installer_ui_is_text; then
    whiptail --title "Thinclient Installation" --yesno \
      "The disk ${target_disk} will be fully erased and turned into a local thin-client boot disk." 14 88
    return $?
  fi

  path="$(resolve_tty_path 2>/dev/null || true)"
  if [[ -z "$path" ]]; then
    echo "Interactive wipe confirmation requires a TTY." >&2
    exit 1
  fi

  printf '\nThe disk %s will be fully erased.\n' "$target_disk" >"$path"
  printf 'Type YES to continue: ' >"$path"
  read -r answer <"$path"
  [[ "$answer" == "YES" ]]
}

load_profile() {
  local output
  output="$(
    MODE="$MODE" \
    CONNECTION_METHOD="$CONNECTION_METHOD" \
    PROFILE_NAME="$PROFILE_NAME" \
    RUNTIME_USER="$RUNTIME_USER" \
    HOSTNAME_VALUE="$HOSTNAME_VALUE" \
    AUTOSTART="$AUTOSTART" \
    NETWORK_MODE="$NETWORK_MODE" \
    NETWORK_INTERFACE="$NETWORK_INTERFACE" \
    NETWORK_STATIC_ADDRESS="$NETWORK_STATIC_ADDRESS" \
    NETWORK_STATIC_PREFIX="$NETWORK_STATIC_PREFIX" \
    NETWORK_GATEWAY="$NETWORK_GATEWAY" \
    NETWORK_DNS_SERVERS="$NETWORK_DNS_SERVERS" \
    SPICE_URL="$SPICE_URL" \
    NOVNC_URL="$NOVNC_URL" \
    DCV_URL="$DCV_URL" \
    BEAGLE_STREAM_CLIENT_HOST="$BEAGLE_STREAM_CLIENT_HOST" \
    BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST="$BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST" \
    BEAGLE_STREAM_CLIENT_LOCAL_HOST="$BEAGLE_STREAM_CLIENT_LOCAL_HOST" \
    BEAGLE_STREAM_CLIENT_PORT="$BEAGLE_STREAM_CLIENT_PORT" \
    BEAGLE_STREAM_CLIENT_APP="$BEAGLE_STREAM_CLIENT_APP" \
    REMOTE_VIEWER_BIN="$REMOTE_VIEWER_BIN" \
    BROWSER_BIN="$BROWSER_BIN" \
    BROWSER_FLAGS="$BROWSER_FLAGS" \
    DCV_VIEWER_BIN="$DCV_VIEWER_BIN" \
    BEAGLE_STREAM_CLIENT_BIN="$BEAGLE_STREAM_CLIENT_BIN" \
    BEAGLE_STREAM_CLIENT_RESOLUTION="$BEAGLE_STREAM_CLIENT_RESOLUTION" \
    BEAGLE_STREAM_CLIENT_FPS="$BEAGLE_STREAM_CLIENT_FPS" \
    BEAGLE_STREAM_CLIENT_BITRATE="$BEAGLE_STREAM_CLIENT_BITRATE" \
    BEAGLE_STREAM_CLIENT_VIDEO_CODEC="$BEAGLE_STREAM_CLIENT_VIDEO_CODEC" \
    BEAGLE_STREAM_CLIENT_VIDEO_DECODER="$BEAGLE_STREAM_CLIENT_VIDEO_DECODER" \
    BEAGLE_STREAM_CLIENT_AUDIO_CONFIG="$BEAGLE_STREAM_CLIENT_AUDIO_CONFIG" \
    BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE="$BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE" \
    BEAGLE_STREAM_CLIENT_QUIT_AFTER="$BEAGLE_STREAM_CLIENT_QUIT_AFTER" \
    BEAGLE_STREAM_SERVER_API_URL="$BEAGLE_STREAM_SERVER_API_URL" \
    BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL="$BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL" \
    BEAGLE_SCHEME="$BEAGLE_SCHEME" \
    BEAGLE_HOST="$BEAGLE_HOST" \
    BEAGLE_PORT="$BEAGLE_PORT" \
    BEAGLE_NODE="$BEAGLE_NODE" \
    BEAGLE_VMID="$BEAGLE_VMID" \
    BEAGLE_REALM="$BEAGLE_REALM" \
    BEAGLE_VERIFY_TLS="$BEAGLE_VERIFY_TLS" \
    CONNECTION_USERNAME="$CONNECTION_USERNAME" \
    CONNECTION_PASSWORD="$CONNECTION_PASSWORD" \
    CONNECTION_TOKEN="$CONNECTION_TOKEN" \
    BEAGLE_STREAM_SERVER_USERNAME="$BEAGLE_STREAM_SERVER_USERNAME" \
    BEAGLE_STREAM_SERVER_PASSWORD="$BEAGLE_STREAM_SERVER_PASSWORD" \
    "$ROOT_DIR/installer/setup-menu.sh"
  )"
  apply_shell_assignments "$output"
}

load_embedded_preset() {
  local attempt=1
  local max_attempts delay_seconds

  max_attempts="$PRESET_LOAD_RETRIES"
  delay_seconds="$PRESET_LOAD_RETRY_DELAY"
  [[ "$max_attempts" =~ ^[0-9]+$ ]] || max_attempts=6
  [[ "$delay_seconds" =~ ^([0-9]+([.][0-9]+)?)$ ]] || delay_seconds=1
  (( max_attempts > 0 )) || max_attempts=1

  while (( attempt <= max_attempts )); do
    if [[ -f "$PRESET_FILE" ]]; then
      log_msg "loading bundled preset from $PRESET_FILE (attempt $attempt)"
      # shellcheck disable=SC1090
      source "$PRESET_FILE"
      PRESET_ACTIVE="1"
      log_msg "preset active: profile=${PVE_THIN_CLIENT_PRESET_PROFILE_NAME:-} vmid=${PVE_THIN_CLIENT_PRESET_BEAGLE_VMID:-} host=${PVE_THIN_CLIENT_PRESET_BEAGLE_HOST:-}"
      persist_logs_to_medium
      return 0
    fi

    log_msg "preset file missing on attempt $attempt: $PRESET_FILE"
    if (( attempt < max_attempts )); then
      sleep "$delay_seconds"
      PRESET_FILE=""
      LIVE_MEDIUM=""
      initialize_live_medium
    fi
    attempt=$((attempt + 1))
  done

  log_msg "no bundled preset found after retries"
  return 1
}

cache_bundled_preset() {
  local manifest_file=""

  load_embedded_preset || true

  if [[ ! -f "$PRESET_FILE" ]]; then
    log_msg "cache_bundled_preset: no preset file available to cache"
    persist_logs_to_medium
    return 1
  fi

  if [[ "$PRESET_FILE" == "$CACHED_PRESET_FILE" ]]; then
    log_msg "cache_bundled_preset: preset is already cached at $CACHED_PRESET_FILE"
  else
    mkdir -p "$CACHED_STATE_DIR"
    install -m 0644 "$PRESET_FILE" "$CACHED_PRESET_FILE"
    printf 'medium\n' >"$CACHED_PRESET_SOURCE_FILE"
    log_msg "cache_bundled_preset: cached preset to $CACHED_PRESET_FILE from $PRESET_FILE"
  fi

  mkdir -p "$CACHED_STATE_DIR"

  if [[ -n "$LIVE_MEDIUM" ]]; then
    manifest_file="$(candidate_manifest_path "$LIVE_MEDIUM" 1 2>/dev/null || true)"
  fi
  if [[ -z "$manifest_file" && -f "$CACHED_MANIFEST_FILE" ]]; then
    manifest_file="$CACHED_MANIFEST_FILE"
  fi

  if [[ -n "$manifest_file" ]] && [[ -f "$manifest_file" ]]; then
    install -m 0644 "$manifest_file" "$CACHED_MANIFEST_FILE"
    log_msg "cache_bundled_preset: cached manifest to $CACHED_MANIFEST_FILE from $manifest_file"
  fi

  persist_logs_to_medium
  return 0
}

mode_is_available() {
  local mode="$1"

  case "$mode" in
    SPICE)
      [[ -n "${PVE_THIN_CLIENT_PRESET_SPICE_URL:-}" ]] || {
        [[ -n "${PVE_THIN_CLIENT_PRESET_BEAGLE_HOST:-}" ]] && \
        [[ -n "${PVE_THIN_CLIENT_PRESET_BEAGLE_NODE:-}" ]] && \
        [[ -n "${PVE_THIN_CLIENT_PRESET_BEAGLE_VMID:-}" ]] && \
        [[ -n "${PVE_THIN_CLIENT_PRESET_SPICE_USERNAME:-${PVE_THIN_CLIENT_PRESET_BEAGLE_USERNAME:-}}" ]] && \
        [[ -n "${PVE_THIN_CLIENT_PRESET_SPICE_PASSWORD:-${PVE_THIN_CLIENT_PRESET_BEAGLE_PASSWORD:-}}" ]]
      }
      ;;
    NOVNC)
      [[ -n "${PVE_THIN_CLIENT_PRESET_NOVNC_URL:-}" ]]
      ;;
    DCV)
      [[ -n "${PVE_THIN_CLIENT_PRESET_DCV_URL:-}" ]]
      ;;
    BEAGLE_STREAM_CLIENT)
      [[ -n "${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_HOST:-}" ]] && \
      [[ -n "${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_USERNAME:-}" ]] && \
      [[ -n "${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_PASSWORD:-}" ]]
      ;;
    *)
      return 1
      ;;
  esac
}

mode_label() {
  local mode="$1"
  case "$mode" in
    SPICE)
      if [[ -n "${PVE_THIN_CLIENT_PRESET_SPICE_URL:-}" ]]; then
        printf 'SPICE direct launcher\n'
      else
        printf 'SPICE via Beagle ticket\n'
      fi
      ;;
    NOVNC)
      printf 'noVNC browser session\n'
      ;;
    DCV)
      printf 'Amazon DCV session\n'
      ;;
    BEAGLE_STREAM_CLIENT)
      printf 'Beagle Stream Client + Beagle Stream Server low-latency stream\n'
      ;;
    *)
      printf '%s\n' "$mode"
      ;;
  esac
}

print_preset_summary() {
  if [[ "$PRESET_ACTIVE" != "1" ]]; then
    echo "No VM preset is currently cached or bundled."
    return 0
  fi

  local available=()
  local mode
  for mode in BEAGLE_STREAM_CLIENT SPICE NOVNC DCV; do
    if mode_is_available "$mode"; then
      available+=("$mode")
    fi
  done

  printf 'Active VM preset: %s\n' "${PVE_THIN_CLIENT_PRESET_VM_NAME:-${PVE_THIN_CLIENT_PRESET_PROFILE_NAME:-unnamed}}"
  printf 'VMID/Node: %s / %s\n' "${PVE_THIN_CLIENT_PRESET_BEAGLE_VMID:-n/a}" "${PVE_THIN_CLIENT_PRESET_BEAGLE_NODE:-n/a}"
  printf 'Beagle host: %s\n' "${PVE_THIN_CLIENT_PRESET_BEAGLE_HOST:-n/a}"
  if (( ${#available[@]} > 0 )); then
    printf 'Configured streaming modes: %s\n' "${available[*]}"
  else
    printf 'Configured streaming modes: none\n'
  fi
}

print_preset_json() {
  python3 "$PRESET_SUMMARY_HELPER" preset-summary-json \
    --preset-active "$PRESET_ACTIVE" \
    --vm-name "${PVE_THIN_CLIENT_PRESET_VM_NAME:-}" \
    --profile-name "${PVE_THIN_CLIENT_PRESET_PROFILE_NAME:-}" \
    --beagle-host "${PVE_THIN_CLIENT_PRESET_BEAGLE_HOST:-}" \
    --beagle-node "${PVE_THIN_CLIENT_PRESET_BEAGLE_NODE:-}" \
    --beagle-vmid "${PVE_THIN_CLIENT_PRESET_BEAGLE_VMID:-}" \
    --spice-url "${PVE_THIN_CLIENT_PRESET_SPICE_URL:-}" \
    --beagle-username "${PVE_THIN_CLIENT_PRESET_BEAGLE_USERNAME:-}" \
    --beagle-password "${PVE_THIN_CLIENT_PRESET_BEAGLE_PASSWORD:-}" \
    --spice-username "${PVE_THIN_CLIENT_PRESET_SPICE_USERNAME:-}" \
    --spice-password "${PVE_THIN_CLIENT_PRESET_SPICE_PASSWORD:-}" \
    --novnc-url "${PVE_THIN_CLIENT_PRESET_NOVNC_URL:-}" \
    --dcv-url "${PVE_THIN_CLIENT_PRESET_DCV_URL:-}" \
    --beagle-stream-client-host "${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_HOST:-}" \
    --default-mode "${PVE_THIN_CLIENT_PRESET_DEFAULT_MODE:-}" \
    --beagle-stream-client-app "${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_APP:-Desktop}"
}

print_debug_json() {
  python3 - "$PRESET_ACTIVE" "$LIVE_MEDIUM_DEFAULT" "$LIVE_MEDIUM" "$LIVE_ASSET_DIR" "$PRESET_FILE" "$LOG_FILE" "$LOG_DIR" "$PRESET_SOURCE" "$CACHED_PRESET_FILE" "$(cached_preset_source)" "$(current_live_disk 2>/dev/null || true)" "$LOG_SESSION_ID" <<'PY'
import json
import os
import sys

(
    preset_active,
    live_medium_default,
    live_medium,
    live_asset_dir,
    preset_file,
    log_file,
    log_dir,
    preset_source,
    cached_preset_file,
    cached_preset_source,
    live_disk,
    log_session_id,
) = sys.argv[1:13]

payload = {
    "preset_active": preset_active == "1",
    "live_medium_default": live_medium_default,
    "live_medium": live_medium,
    "live_asset_dir": live_asset_dir,
    "preset_file": preset_file,
    "preset_exists": bool(preset_file and os.path.isfile(preset_file)),
    "log_file": log_file,
    "log_exists": bool(log_file and os.path.isfile(log_file)),
    "log_dir": log_dir,
    "log_dir_exists": bool(log_dir and os.path.isdir(log_dir)),
    "preset_source": preset_source,
    "cached_preset_file": cached_preset_file,
    "cached_preset_exists": bool(cached_preset_file and os.path.isfile(cached_preset_file)),
    "cached_preset_source": cached_preset_source,
    "live_disk": live_disk,
    "log_session_id": log_session_id,
}
print(json.dumps(payload, indent=2))
PY
}

print_ui_state_json() {
  local live_disk
  live_disk="$(current_live_disk 2>/dev/null || true)"

  python3 "$PRESET_SUMMARY_HELPER" ui-state-json \
    --preset-active "$PRESET_ACTIVE" \
    --vm-name "${PVE_THIN_CLIENT_PRESET_VM_NAME:-}" \
    --profile-name "${PVE_THIN_CLIENT_PRESET_PROFILE_NAME:-}" \
    --beagle-host "${PVE_THIN_CLIENT_PRESET_BEAGLE_HOST:-}" \
    --beagle-node "${PVE_THIN_CLIENT_PRESET_BEAGLE_NODE:-}" \
    --beagle-vmid "${PVE_THIN_CLIENT_PRESET_BEAGLE_VMID:-}" \
    --spice-url "${PVE_THIN_CLIENT_PRESET_SPICE_URL:-}" \
    --beagle-username "${PVE_THIN_CLIENT_PRESET_BEAGLE_USERNAME:-}" \
    --beagle-password "${PVE_THIN_CLIENT_PRESET_BEAGLE_PASSWORD:-}" \
    --spice-username "${PVE_THIN_CLIENT_PRESET_SPICE_USERNAME:-}" \
    --spice-password "${PVE_THIN_CLIENT_PRESET_SPICE_PASSWORD:-}" \
    --novnc-url "${PVE_THIN_CLIENT_PRESET_NOVNC_URL:-}" \
    --dcv-url "${PVE_THIN_CLIENT_PRESET_DCV_URL:-}" \
    --beagle-stream-client-host "${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_HOST:-}" \
    --default-mode "${PVE_THIN_CLIENT_PRESET_DEFAULT_MODE:-}" \
    --beagle-stream-client-app "${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_APP:-Desktop}" \
    --live-medium-default "$LIVE_MEDIUM_DEFAULT" \
    --live-medium "$LIVE_MEDIUM" \
    --live-asset-dir "$LIVE_ASSET_DIR" \
    --preset-file "$PRESET_FILE" \
    --log-file "$LOG_FILE" \
    --log-dir "$LOG_DIR" \
    --preset-source "$PRESET_SOURCE" \
    --cached-preset-file "$CACHED_PRESET_FILE" \
    --cached-preset-source "$(cached_preset_source)" \
    --live-disk "$live_disk" \
    --log-session-id "$LOG_SESSION_ID"
}

choose_streaming_mode_from_preset() {
  local modes=()
  local menu_items=()
  local tty_path="/dev/tty"
  local mode answer index

  for mode in BEAGLE_STREAM_CLIENT SPICE NOVNC DCV; do
    if mode_is_available "$mode"; then
      modes+=("$mode")
      menu_items+=("$mode" "$(mode_label "$mode")")
    fi
  done

  if (( ${#modes[@]} == 0 )); then
    echo "The bundled VM preset does not contain a usable Beagle Stream Client, SPICE, noVNC or DCV target." >&2
    exit 1
  fi

  if (( ${#modes[@]} == 1 )); then
    printf '%s\n' "${modes[0]}"
    return 0
  fi

  if command -v whiptail >/dev/null 2>&1 && ! installer_ui_is_text; then
    whiptail --title "Thinclient Installation" --menu \
      "Choose the streaming mode for ${PVE_THIN_CLIENT_PRESET_VM_NAME:-this VM}." 20 88 8 \
      "${menu_items[@]}" 3>&1 1>&2 2>&3
    return 0
  fi

  if [[ ! -r "$tty_path" || ! -w "$tty_path" ]]; then
    echo "Interactive mode selection requires a TTY." >&2
    exit 1
  fi

  printf 'Available streaming modes for %s:\n' "${PVE_THIN_CLIENT_PRESET_VM_NAME:-this VM}" >"$tty_path"
  index=1
  while (( index <= ${#menu_items[@]} / 2 )); do
    printf '%s) %s %s\n' "$index" "${menu_items[$(( (index - 1) * 2 ))]}" "${menu_items[$(( (index - 1) * 2 + 1 ))]}" >"$tty_path"
    index=$((index + 1))
  done
  printf '\nType the number of the streaming mode and press ENTER: ' >"$tty_path"
  read -r answer <"$tty_path"
  [[ "$answer" =~ ^[0-9]+$ ]] || {
    echo "Invalid selection: $answer" >&2
    exit 1
  }
  (( answer >= 1 && answer <= ${#menu_items[@]} / 2 )) || {
    echo "Selection out of range: $answer" >&2
    exit 1
  }
  printf '%s\n' "${menu_items[$(( (answer - 1) * 2 ))]}"
}

available_mode_count() {
  local count=0
  local mode

  for mode in BEAGLE_STREAM_CLIENT SPICE NOVNC DCV; do
    if mode_is_available "$mode"; then
      count=$((count + 1))
    fi
  done

  printf '%s\n' "$count"
}

first_available_mode() {
  local mode

  for mode in BEAGLE_STREAM_CLIENT SPICE NOVNC DCV; do
    if mode_is_available "$mode"; then
      printf '%s\n' "$mode"
      return 0
    fi
  done

  return 1
}

apply_preset_defaults() {
  PROFILE_NAME="${PVE_THIN_CLIENT_PRESET_PROFILE_NAME:-default}"
  HOSTNAME_VALUE="${PVE_THIN_CLIENT_PRESET_HOSTNAME_VALUE:-beagle-os}"
  AUTOSTART="${PVE_THIN_CLIENT_PRESET_AUTOSTART:-1}"
  NETWORK_MODE="${PVE_THIN_CLIENT_PRESET_NETWORK_MODE:-dhcp}"
  NETWORK_INTERFACE="${PVE_THIN_CLIENT_PRESET_NETWORK_INTERFACE:-eth0}"
  NETWORK_STATIC_ADDRESS="${PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_ADDRESS:-}"
  NETWORK_STATIC_PREFIX="${PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_PREFIX:-24}"
  NETWORK_GATEWAY="${PVE_THIN_CLIENT_PRESET_NETWORK_GATEWAY:-}"
  NETWORK_DNS_SERVERS="${PVE_THIN_CLIENT_PRESET_NETWORK_DNS_SERVERS:-1.1.1.1 8.8.8.8}"
  BEAGLE_SCHEME="${PVE_THIN_CLIENT_PRESET_BEAGLE_SCHEME:-https}"
  BEAGLE_HOST="${PVE_THIN_CLIENT_PRESET_BEAGLE_HOST:-}"
  BEAGLE_PORT="${PVE_THIN_CLIENT_PRESET_BEAGLE_PORT:-8006}"
  BEAGLE_NODE="${PVE_THIN_CLIENT_PRESET_BEAGLE_NODE:-}"
  BEAGLE_VMID="${PVE_THIN_CLIENT_PRESET_BEAGLE_VMID:-}"
  BEAGLE_REALM="${PVE_THIN_CLIENT_PRESET_BEAGLE_REALM:-pam}"
  BEAGLE_VERIFY_TLS="${PVE_THIN_CLIENT_PRESET_BEAGLE_VERIFY_TLS:-1}"
  BEAGLE_MANAGER_URL="${PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_URL:-}"
  BEAGLE_MANAGER_PINNED_PUBKEY="${PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  BEAGLE_ENROLLMENT_URL="${PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_URL:-}"
  BEAGLE_ENROLLMENT_TOKEN="${PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_TOKEN:-}"
  BEAGLE_UPDATE_ENABLED="${PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_ENABLED:-1}"
  BEAGLE_UPDATE_CHANNEL="${PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_CHANNEL:-stable}"
  BEAGLE_UPDATE_BEHAVIOR="${PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_BEHAVIOR:-prompt}"
  BEAGLE_UPDATE_FEED_URL="${PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_FEED_URL:-}"
  BEAGLE_UPDATE_VERSION_PIN="${PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_VERSION_PIN:-}"
  BEAGLE_MANAGER_TOKEN=""
  BEAGLE_EGRESS_MODE="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_MODE:-full}"
  BEAGLE_EGRESS_TYPE="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_TYPE:-wireguard}"
  BEAGLE_EGRESS_INTERFACE="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_INTERFACE:-wg-beagle}"
  BEAGLE_EGRESS_DOMAINS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_DOMAINS:-}"
  BEAGLE_EGRESS_RESOLVERS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_RESOLVERS:-1.1.1.1 8.8.8.8}"
  BEAGLE_EGRESS_ALLOWED_IPS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_ALLOWED_IPS:-}"
  BEAGLE_EGRESS_WG_ADDRESS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ADDRESS:-}"
  BEAGLE_EGRESS_WG_DNS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_DNS:-}"
  BEAGLE_EGRESS_WG_PUBLIC_KEY="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PUBLIC_KEY:-}"
  BEAGLE_EGRESS_WG_ENDPOINT="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ENDPOINT:-}"
  BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE:-25}"
  BEAGLE_EGRESS_WG_PRIVATE_KEY="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRIVATE_KEY:-}"
  BEAGLE_EGRESS_WG_PRESHARED_KEY="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRESHARED_KEY:-}"
  IDENTITY_HOSTNAME="${PVE_THIN_CLIENT_PRESET_IDENTITY_HOSTNAME:-}"
  IDENTITY_TIMEZONE="${PVE_THIN_CLIENT_PRESET_IDENTITY_TIMEZONE:-}"
  IDENTITY_LOCALE="${PVE_THIN_CLIENT_PRESET_IDENTITY_LOCALE:-}"
  IDENTITY_KEYMAP="${PVE_THIN_CLIENT_PRESET_IDENTITY_KEYMAP:-}"
  IDENTITY_CHROME_PROFILE="${PVE_THIN_CLIENT_PRESET_IDENTITY_CHROME_PROFILE:-default}"
  BEAGLE_STREAM_CLIENT_BIN="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_BIN:-beagle-stream-client}"
  BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST:-}"
  BEAGLE_STREAM_CLIENT_LOCAL_HOST="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_LOCAL_HOST:-}"
  BEAGLE_STREAM_CLIENT_PORT="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_PORT:-}"
  BEAGLE_STREAM_CLIENT_RESOLUTION="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_RESOLUTION:-auto}"
  BEAGLE_STREAM_CLIENT_FPS="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_FPS:-60}"
  BEAGLE_STREAM_CLIENT_BITRATE="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_BITRATE:-32000}"
  BEAGLE_STREAM_CLIENT_VIDEO_CODEC="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_VIDEO_CODEC:-H.264}"
  BEAGLE_STREAM_CLIENT_VIDEO_DECODER="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_VIDEO_DECODER:-software}"
  BEAGLE_STREAM_CLIENT_AUDIO_CONFIG="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_AUDIO_CONFIG:-stereo}"
  BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE:-1}"
  BEAGLE_STREAM_CLIENT_QUIT_AFTER="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_QUIT_AFTER:-0}"
  BEAGLE_STREAM_SERVER_API_URL="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_API_URL:-}"
  BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL:-}"
  THINCLIENT_PASSWORD="${PVE_THIN_CLIENT_PRESET_THINCLIENT_PASSWORD:-}"
  BEAGLE_STREAM_SERVER_PINNED_PUBKEY="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_PINNED_PUBKEY:-}"
  BEAGLE_STREAM_SERVER_NAME="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_NAME:-}"
  BEAGLE_STREAM_SERVER_STREAM_PORT="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_STREAM_PORT:-}"
  BEAGLE_STREAM_SERVER_UNIQUEID="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_UNIQUEID:-}"
  BEAGLE_STREAM_SERVER_CERT_B64="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_CERT_B64:-}"
}

validate_beagle_stream_client_token_preset() {
  if [[ ( -z "${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_HOST:-}" && -z "${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST:-}" ) || -z "${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_USERNAME:-}" || -z "${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_PASSWORD:-}" ]]; then
    echo "Beagle Stream Client preset requires host plus Beagle Stream Server username/password for manager-token pairing." >&2
    return 1
  fi

  return 0
}

apply_preset_mode() {
  local selected_mode="$1"

  apply_preset_defaults
  MODE="$selected_mode"
  CONNECTION_METHOD="direct"
  SPICE_URL=""
  NOVNC_URL=""
  DCV_URL=""
  BEAGLE_STREAM_CLIENT_HOST=""
  BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST=""
  BEAGLE_STREAM_CLIENT_LOCAL_HOST=""
  BEAGLE_STREAM_CLIENT_PORT=""
  BEAGLE_STREAM_CLIENT_APP="Desktop"
  BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL=""
  CONNECTION_USERNAME=""
  CONNECTION_PASSWORD=""
  CONNECTION_TOKEN=""
  BEAGLE_STREAM_SERVER_USERNAME=""
  BEAGLE_STREAM_SERVER_PASSWORD=""

  case "$selected_mode" in
    BEAGLE_STREAM_CLIENT)
      BEAGLE_STREAM_CLIENT_HOST="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_HOST:-}"
      BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST:-}"
      BEAGLE_STREAM_CLIENT_LOCAL_HOST="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_LOCAL_HOST:-}"
      BEAGLE_STREAM_CLIENT_PORT="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_PORT:-}"
      BEAGLE_STREAM_CLIENT_APP="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_CLIENT_APP:-Desktop}"
      BEAGLE_STREAM_SERVER_API_URL="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_API_URL:-}"
      BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL:-}"
      BEAGLE_STREAM_SERVER_USERNAME="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_USERNAME:-}"
      BEAGLE_STREAM_SERVER_PASSWORD="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_PASSWORD:-}"
      validate_beagle_stream_client_token_preset || exit 1
      ;;
    SPICE)
      CONNECTION_USERNAME="${PVE_THIN_CLIENT_PRESET_SPICE_USERNAME:-${PVE_THIN_CLIENT_PRESET_BEAGLE_USERNAME:-}}"
      CONNECTION_PASSWORD="${PVE_THIN_CLIENT_PRESET_SPICE_PASSWORD:-${PVE_THIN_CLIENT_PRESET_BEAGLE_PASSWORD:-}}"
      CONNECTION_TOKEN="${PVE_THIN_CLIENT_PRESET_SPICE_TOKEN:-${PVE_THIN_CLIENT_PRESET_BEAGLE_TOKEN:-}}"
      if [[ -n "${PVE_THIN_CLIENT_PRESET_SPICE_URL:-}" ]]; then
        CONNECTION_METHOD="${PVE_THIN_CLIENT_PRESET_SPICE_METHOD:-direct}"
        SPICE_URL="${PVE_THIN_CLIENT_PRESET_SPICE_URL}"
      else
        CONNECTION_METHOD="beagle-ticket"
      fi
      ;;
    NOVNC)
      NOVNC_URL="${PVE_THIN_CLIENT_PRESET_NOVNC_URL:-}"
      CONNECTION_USERNAME="${PVE_THIN_CLIENT_PRESET_NOVNC_USERNAME:-${PVE_THIN_CLIENT_PRESET_BEAGLE_USERNAME:-}}"
      CONNECTION_PASSWORD="${PVE_THIN_CLIENT_PRESET_NOVNC_PASSWORD:-${PVE_THIN_CLIENT_PRESET_BEAGLE_PASSWORD:-}}"
      CONNECTION_TOKEN="${PVE_THIN_CLIENT_PRESET_NOVNC_TOKEN:-${PVE_THIN_CLIENT_PRESET_BEAGLE_TOKEN:-}}"
      ;;
    DCV)
      DCV_URL="${PVE_THIN_CLIENT_PRESET_DCV_URL:-}"
      CONNECTION_USERNAME="${PVE_THIN_CLIENT_PRESET_DCV_USERNAME:-}"
      CONNECTION_PASSWORD="${PVE_THIN_CLIENT_PRESET_DCV_PASSWORD:-}"
      CONNECTION_TOKEN="${PVE_THIN_CLIENT_PRESET_DCV_TOKEN:-}"
      ;;
    *)
      echo "Unsupported preset mode: $selected_mode" >&2
      exit 1
      ;;
  esac
}

load_install_profile() {
  if [[ "$PRESET_ACTIVE" == "1" ]]; then
    if [[ -n "$MODE" ]]; then
      mode_is_available "$MODE" || {
        echo "Requested mode '$MODE' is not available in the bundled preset." >&2
        exit 1
      }
    else
      MODE="${PVE_THIN_CLIENT_PRESET_DEFAULT_MODE:-}"
      if [[ -n "$MODE" ]]; then
        mode_is_available "$MODE" || MODE=""
      fi

      if [[ -z "$MODE" ]]; then
        if [[ "$AUTO_INSTALL" == "1" ]]; then
          MODE="$(first_available_mode || true)"
          [[ -n "$MODE" ]] || {
            echo "No usable streaming mode is available in the bundled preset." >&2
            exit 1
          }
        else
          MODE="$(choose_streaming_mode_from_preset)"
        fi
      fi
    fi
    apply_preset_mode "$MODE"
    return 0
  fi

  load_profile
}

prefix_to_netmask() {
  python3 - "$1" <<'PY'
import ipaddress
import sys

prefix = int(sys.argv[1])
network = ipaddress.ip_network(f"0.0.0.0/{prefix}")
print(network.netmask)
PY
}

boot_ip_arg() {
  if [[ "$NETWORK_MODE" == "dhcp" ]]; then
    printf 'ip=dhcp'
    return 0
  fi

  local netmask
  netmask="$(prefix_to_netmask "$NETWORK_STATIC_PREFIX")"
  printf 'ip=%s::%s:%s:%s:%s:none' \
    "$NETWORK_STATIC_ADDRESS" \
    "$NETWORK_GATEWAY" \
    "$netmask" \
    "$HOSTNAME_VALUE" \
    "$NETWORK_INTERFACE"
}

write_grub_cfg() {
  local root_uuid="$1"
  local irq_args_default=""
  local irq_args_safe="nomodeset irqpoll pci=nomsi noapic"
  local irq_args_legacy="nomodeset irqpoll noapic nolapic"

  cat > "$TARGET_MOUNT/boot/grub/grub.cfg" <<EOF
insmod part_gpt
insmod ext2
terminal_output console
set default=0
set timeout=4

menuentry 'Beagle OS Desktop' {
  search --no-floppy --fs-uuid --set=root $root_uuid
  linux /live/current/vmlinuz boot=live components username=thinclient hostname=$HOSTNAME_VALUE live-media=/dev/disk/by-uuid/$root_uuid live-media-path=/live/current live-media-timeout=10 ignore_uuid quiet splash loglevel=3 systemd.show_status=0 systemd.gpt_auto=0 vt.global_cursor_default=0 console=tty0 console=ttyS0,115200n8 plymouth.ignore-serial-consoles pve_thin_client.mode=runtime pve_thin_client.client_mode=desktop $irq_args_default
  initrd /live/current/initrd.img
}

menuentry 'Beagle OS Gaming' {
  search --no-floppy --fs-uuid --set=root $root_uuid
  linux /live/current/vmlinuz boot=live components username=thinclient hostname=$HOSTNAME_VALUE live-media=/dev/disk/by-uuid/$root_uuid live-media-path=/live/current live-media-timeout=10 ignore_uuid quiet splash loglevel=3 systemd.show_status=0 systemd.gpt_auto=0 vt.global_cursor_default=0 console=tty0 console=ttyS0,115200n8 plymouth.ignore-serial-consoles pve_thin_client.mode=runtime pve_thin_client.client_mode=gaming $irq_args_default
  initrd /live/current/initrd.img
}

menuentry 'Beagle OS Desktop (safe mode)' {
  search --no-floppy --fs-uuid --set=root $root_uuid
  linux /live/current/vmlinuz boot=live components username=thinclient hostname=$HOSTNAME_VALUE live-media=/dev/disk/by-uuid/$root_uuid live-media-path=/live/current live-media-timeout=10 ignore_uuid loglevel=7 systemd.show_status=1 systemd.gpt_auto=0 vt.global_cursor_default=0 console=tty0 console=ttyS0,115200n8 plymouth.enable=0 pve_thin_client.mode=runtime pve_thin_client.client_mode=desktop $irq_args_safe
  initrd /live/current/initrd.img
}

menuentry 'Beagle OS Desktop (legacy IRQ mode)' {
  search --no-floppy --fs-uuid --set=root $root_uuid
  linux /live/current/vmlinuz boot=live components username=thinclient hostname=$HOSTNAME_VALUE live-media=/dev/disk/by-uuid/$root_uuid live-media-path=/live/current live-media-timeout=10 ignore_uuid loglevel=7 systemd.show_status=1 systemd.gpt_auto=0 vt.global_cursor_default=0 console=tty0 console=ttyS0,115200n8 plymouth.enable=0 pve_thin_client.mode=runtime pve_thin_client.client_mode=desktop $irq_args_legacy
  initrd /live/current/initrd.img
}

menuentry 'Beagle OS (Slot A fallback)' {
  search --no-floppy --fs-uuid --set=root $root_uuid
  linux /live/a/vmlinuz boot=live components username=thinclient hostname=$HOSTNAME_VALUE live-media=/dev/disk/by-uuid/$root_uuid live-media-path=/live/a live-media-timeout=10 ignore_uuid loglevel=7 systemd.show_status=1 systemd.gpt_auto=0 vt.global_cursor_default=0 console=tty0 console=ttyS0,115200n8 plymouth.enable=0 pve_thin_client.mode=runtime pve_thin_client.client_mode=desktop $irq_args_safe
  initrd /live/a/initrd.img
}

menuentry 'Beagle OS (Slot B fallback)' {
  search --no-floppy --fs-uuid --set=root $root_uuid
  linux /live/b/vmlinuz boot=live components username=thinclient hostname=$HOSTNAME_VALUE live-media=/dev/disk/by-uuid/$root_uuid live-media-path=/live/b live-media-timeout=10 ignore_uuid loglevel=7 systemd.show_status=1 systemd.gpt_auto=0 vt.global_cursor_default=0 console=tty0 console=ttyS0,115200n8 plymouth.enable=0 pve_thin_client.mode=runtime pve_thin_client.client_mode=desktop $irq_args_safe
  initrd /live/b/initrd.img
}
EOF
}

write_efi_grub_stub() {
  local root_uuid="$1"
  local stub_dir="$EFI_MOUNT/EFI/BEAGLEOS"
  local fallback_dir="$EFI_MOUNT/EFI/BOOT"

  install -d -m 0755 "$stub_dir" "$fallback_dir"
  cat >"$stub_dir/grub.cfg" <<EOF
search --no-floppy --fs-uuid --set=root $root_uuid
set prefix=(\$root)/boot/grub
terminal_output console
configfile \$prefix/grub.cfg
EOF
  install -m 0644 "$stub_dir/grub.cfg" "$fallback_dir/grub.cfg"
}

copy_assets() {
  install -d -m 0755 "$TARGET_MOUNT/live/a" "$TARGET_MOUNT/live/b" "$TARGET_MOUNT/pve-thin-client" "$STATE_DIR"
  install -m 0644 "$INSTALL_LIVE_ASSET_DIR/vmlinuz" "$TARGET_MOUNT/live/a/vmlinuz"
  install -m 0644 "$INSTALL_LIVE_ASSET_DIR/initrd.img" "$TARGET_MOUNT/live/a/initrd.img"
  install -m 0644 "$INSTALL_LIVE_ASSET_DIR/filesystem.squashfs" "$TARGET_MOUNT/live/a/filesystem.squashfs"
  if [[ -f "$INSTALL_LIVE_ASSET_DIR/SHA256SUMS" ]]; then
    install -m 0644 "$INSTALL_LIVE_ASSET_DIR/SHA256SUMS" "$TARGET_MOUNT/live/a/SHA256SUMS"
  fi
  ln -sfn a "$TARGET_MOUNT/live/current"
  ln -sfn ../live "$TARGET_MOUNT/pve-thin-client/live"
  if [[ -f "$GRUB_BACKGROUND_SRC" ]]; then
    install -D -m 0644 "$GRUB_BACKGROUND_SRC" "$TARGET_MOUNT/boot/grub/background.jpg"
  fi
  MODE="$MODE" \
  CONNECTION_METHOD="$CONNECTION_METHOD" \
  PROFILE_NAME="$PROFILE_NAME" \
  RUNTIME_USER="$RUNTIME_USER" \
  HOSTNAME_VALUE="$HOSTNAME_VALUE" \
  AUTOSTART="$AUTOSTART" \
  NETWORK_MODE="$NETWORK_MODE" \
  NETWORK_INTERFACE="$NETWORK_INTERFACE" \
  NETWORK_STATIC_ADDRESS="$NETWORK_STATIC_ADDRESS" \
  NETWORK_STATIC_PREFIX="$NETWORK_STATIC_PREFIX" \
  NETWORK_GATEWAY="$NETWORK_GATEWAY" \
  NETWORK_DNS_SERVERS="$NETWORK_DNS_SERVERS" \
  SPICE_URL="$SPICE_URL" \
  NOVNC_URL="$NOVNC_URL" \
  DCV_URL="$DCV_URL" \
  BEAGLE_STREAM_CLIENT_HOST="$BEAGLE_STREAM_CLIENT_HOST" \
  BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST="$BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST" \
  BEAGLE_STREAM_CLIENT_LOCAL_HOST="$BEAGLE_STREAM_CLIENT_LOCAL_HOST" \
  BEAGLE_STREAM_CLIENT_PORT="$BEAGLE_STREAM_CLIENT_PORT" \
  BEAGLE_STREAM_CLIENT_APP="$BEAGLE_STREAM_CLIENT_APP" \
  REMOTE_VIEWER_BIN="$REMOTE_VIEWER_BIN" \
  BROWSER_BIN="$BROWSER_BIN" \
  BROWSER_FLAGS="$BROWSER_FLAGS" \
  DCV_VIEWER_BIN="$DCV_VIEWER_BIN" \
  BEAGLE_STREAM_CLIENT_BIN="$BEAGLE_STREAM_CLIENT_BIN" \
  BEAGLE_STREAM_CLIENT_RESOLUTION="$BEAGLE_STREAM_CLIENT_RESOLUTION" \
  BEAGLE_STREAM_CLIENT_FPS="$BEAGLE_STREAM_CLIENT_FPS" \
  BEAGLE_STREAM_CLIENT_BITRATE="$BEAGLE_STREAM_CLIENT_BITRATE" \
  BEAGLE_STREAM_CLIENT_VIDEO_CODEC="$BEAGLE_STREAM_CLIENT_VIDEO_CODEC" \
  BEAGLE_STREAM_CLIENT_VIDEO_DECODER="$BEAGLE_STREAM_CLIENT_VIDEO_DECODER" \
  BEAGLE_STREAM_CLIENT_AUDIO_CONFIG="$BEAGLE_STREAM_CLIENT_AUDIO_CONFIG" \
  BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE="$BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE" \
  BEAGLE_STREAM_CLIENT_QUIT_AFTER="$BEAGLE_STREAM_CLIENT_QUIT_AFTER" \
  BEAGLE_STREAM_SERVER_API_URL="$BEAGLE_STREAM_SERVER_API_URL" \
  BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL="$BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL" \
  BEAGLE_SCHEME="$BEAGLE_SCHEME" \
  BEAGLE_HOST="$BEAGLE_HOST" \
  BEAGLE_PORT="$BEAGLE_PORT" \
  BEAGLE_NODE="$BEAGLE_NODE" \
  BEAGLE_VMID="$BEAGLE_VMID" \
  BEAGLE_REALM="$BEAGLE_REALM" \
  BEAGLE_VERIFY_TLS="$BEAGLE_VERIFY_TLS" \
  BEAGLE_MANAGER_URL="$BEAGLE_MANAGER_URL" \
  BEAGLE_MANAGER_PINNED_PUBKEY="$BEAGLE_MANAGER_PINNED_PUBKEY" \
  BEAGLE_ENROLLMENT_URL="$BEAGLE_ENROLLMENT_URL" \
  BEAGLE_UPDATE_ENABLED="$BEAGLE_UPDATE_ENABLED" \
  BEAGLE_UPDATE_CHANNEL="$BEAGLE_UPDATE_CHANNEL" \
  BEAGLE_UPDATE_BEHAVIOR="$BEAGLE_UPDATE_BEHAVIOR" \
  BEAGLE_UPDATE_FEED_URL="$BEAGLE_UPDATE_FEED_URL" \
  BEAGLE_UPDATE_VERSION_PIN="$BEAGLE_UPDATE_VERSION_PIN" \
  BEAGLE_EGRESS_MODE="$BEAGLE_EGRESS_MODE" \
  BEAGLE_EGRESS_TYPE="$BEAGLE_EGRESS_TYPE" \
  BEAGLE_EGRESS_INTERFACE="$BEAGLE_EGRESS_INTERFACE" \
  BEAGLE_EGRESS_DOMAINS="$BEAGLE_EGRESS_DOMAINS" \
  BEAGLE_EGRESS_RESOLVERS="$BEAGLE_EGRESS_RESOLVERS" \
  BEAGLE_EGRESS_ALLOWED_IPS="$BEAGLE_EGRESS_ALLOWED_IPS" \
  BEAGLE_EGRESS_WG_ADDRESS="$BEAGLE_EGRESS_WG_ADDRESS" \
  BEAGLE_EGRESS_WG_DNS="$BEAGLE_EGRESS_WG_DNS" \
  BEAGLE_EGRESS_WG_PUBLIC_KEY="$BEAGLE_EGRESS_WG_PUBLIC_KEY" \
  BEAGLE_EGRESS_WG_ENDPOINT="$BEAGLE_EGRESS_WG_ENDPOINT" \
  BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE="$BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE" \
  IDENTITY_HOSTNAME="$IDENTITY_HOSTNAME" \
  IDENTITY_TIMEZONE="$IDENTITY_TIMEZONE" \
  IDENTITY_LOCALE="$IDENTITY_LOCALE" \
  IDENTITY_KEYMAP="$IDENTITY_KEYMAP" \
  IDENTITY_CHROME_PROFILE="$IDENTITY_CHROME_PROFILE" \
  CONNECTION_USERNAME="$CONNECTION_USERNAME" \
  CONNECTION_PASSWORD="$CONNECTION_PASSWORD" \
  CONNECTION_TOKEN="$CONNECTION_TOKEN" \
  BEAGLE_MANAGER_TOKEN="$BEAGLE_MANAGER_TOKEN" \
  BEAGLE_ENROLLMENT_TOKEN="$BEAGLE_ENROLLMENT_TOKEN" \
  BEAGLE_EGRESS_WG_PRIVATE_KEY="$BEAGLE_EGRESS_WG_PRIVATE_KEY" \
  BEAGLE_EGRESS_WG_PRESHARED_KEY="$BEAGLE_EGRESS_WG_PRESHARED_KEY" \
  BEAGLE_STREAM_SERVER_USERNAME="$BEAGLE_STREAM_SERVER_USERNAME" \
  BEAGLE_STREAM_SERVER_PASSWORD="$BEAGLE_STREAM_SERVER_PASSWORD" \
  BEAGLE_STREAM_SERVER_PINNED_PUBKEY="$BEAGLE_STREAM_SERVER_PINNED_PUBKEY" \
  BEAGLE_STREAM_SERVER_NAME="$BEAGLE_STREAM_SERVER_NAME" \
  BEAGLE_STREAM_SERVER_STREAM_PORT="$BEAGLE_STREAM_SERVER_STREAM_PORT" \
  BEAGLE_STREAM_SERVER_UNIQUEID="$BEAGLE_STREAM_SERVER_UNIQUEID" \
  BEAGLE_STREAM_SERVER_CERT_B64="$BEAGLE_STREAM_SERVER_CERT_B64" \
  RUNTIME_PASSWORD="$THINCLIENT_PASSWORD" \
  "$INSTALL_ROOT_DIR/installer/write-config.sh" "$STATE_DIR"

  if [[ ! -f "$STATE_DIR/local-auth.env" ]]; then
    cat >"$STATE_DIR/local-auth.env" <<EOF
PVE_THIN_CLIENT_RUNTIME_PASSWORD="$THINCLIENT_PASSWORD"
EOF
  fi

  [[ -f "$STATE_DIR/local-auth.env" ]] || {
    log_msg "failed to persist local-auth.env to $STATE_DIR"
    return 1
  }

  write_install_manifest
}

ensure_efivars_mounted() {
  [[ -d /sys/firmware/efi/efivars ]] || return 1

  if mountpoint -q /sys/firmware/efi/efivars; then
    return 0
  fi

  run_logged mount -t efivarfs efivarfs /sys/firmware/efi/efivars
}

resolve_partition_number() {
  local device="$1"
  local sysfs_part="/sys/class/block/${device##*/}/partition"
  local partnum=""

  partnum="$(lsblk -dnro PARTN "$device" 2>/dev/null | awk 'NF { print; exit }' || true)"
  if [[ -z "$partnum" && -r "$sysfs_part" ]]; then
    partnum="$(tr -d '[:space:]' < "$sysfs_part" 2>/dev/null || true)"
  fi

  printf '%s\n' "$partnum"
}

install_efi_boot_entry() {
  local target_disk="$1"
  local boot_part="$2"
  local partnum=""

  [[ -d /sys/firmware/efi ]] || return 0

  ensure_efivars_mounted

  partnum="$(resolve_partition_number "$boot_part")"
  [[ -n "$partnum" ]] || {
    log_msg "warning: unable to determine EFI partition number for $boot_part; skipping explicit efibootmgr entry creation"
    return 0
  }

  if efibootmgr -v 2>/dev/null | grep -Fq '\EFI\BEAGLEOS\grubx64.efi'; then
    return 0
  fi

  if run_logged efibootmgr \
    --create \
    --disk "$target_disk" \
    --part "$partnum" \
    --label "Beagle OS" \
    --loader '\EFI\BEAGLEOS\grubx64.efi'; then
    return 0
  fi

  log_msg "warning: efibootmgr could not create a persistent EFI boot entry; removable EFI fallback remains available"
  return 0
}

install_bootloader() {
  local target_disk="$1"
  local boot_part="$2"
  local root_uuid="$3"
  local bios_modules="biosdisk part_gpt part_msdos ext2 normal linux search search_fs_uuid configfile"
  local efi_modules="part_gpt part_msdos fat ext2 normal linux search search_fs_uuid configfile"
  local running_in_efi="0"

  [[ -d /sys/firmware/efi ]] && running_in_efi="1"

  if [[ "$running_in_efi" == "1" ]]; then
    if ! run_logged grub-install --target=i386-pc --modules="$bios_modules" --boot-directory="$TARGET_MOUNT/boot" "$target_disk"; then
      log_msg "warning: legacy BIOS grub-install failed on $target_disk; continuing with EFI-only bootloader installation"
    fi
  else
    run_logged grub-install --target=i386-pc --modules="$bios_modules" --boot-directory="$TARGET_MOUNT/boot" "$target_disk"
  fi

  run_logged grub-install \
    --target=x86_64-efi \
    --modules="$efi_modules" \
    --efi-directory="$EFI_MOUNT" \
    --boot-directory="$TARGET_MOUNT/boot" \
    --bootloader-id=BEAGLEOS \
    --no-nvram \
    --recheck
  run_logged grub-install \
    --target=x86_64-efi \
    --modules="$efi_modules" \
    --efi-directory="$EFI_MOUNT" \
    --boot-directory="$TARGET_MOUNT/boot" \
    --removable \
    --no-nvram \
    --recheck
  write_efi_grub_stub "$root_uuid"
  install_efi_boot_entry "$target_disk" "$boot_part"
}

main() {
  local target_disk bios_part boot_part root_part root_uuid

  setup_logging
  log_runtime_snapshot
  log_msg "starting local installer with args: $*"
  parse_args "$@"
  if [[ "$CLEAR_CACHED_PRESET" == "1" ]]; then
    clear_cached_preset
    return 0
  fi
  if [[ "$LIST_BEAGLE_VMS_JSON" == "1" ]]; then
    list_beagle_vms_json
    return 0
  fi
  if [[ "$CACHE_BEAGLE_VM_PRESET" == "1" ]]; then
    cache_beagle_vm_preset
    return 0
  fi
  initialize_live_medium
  if [[ "$CACHE_PRESET_ONLY" == "1" ]]; then
    cache_bundled_preset
    return 0
  fi
  load_embedded_preset || true
  if [[ "$PRINT_TARGETS_JSON" == "1" ]]; then
    print_target_disks_json
    return 0
  fi
  if [[ "$PRINT_PRESET_JSON" == "1" ]]; then
    print_preset_json
    return 0
  fi
  if [[ "$PRINT_PRESET_SUMMARY" == "1" ]]; then
    print_preset_summary
    return 0
  fi
  if [[ "$PRINT_DEBUG_JSON" == "1" ]]; then
    print_debug_json
    return 0
  fi
  if [[ "$PRINT_UI_STATE_JSON" == "1" ]]; then
    print_ui_state_json
    return 0
  fi

  require_root "$@"
  require_tools

  tty_note ""
  tty_note "Loading preset configuration..."
  load_install_profile
  tty_note "Detecting target disks..."
  target_disk="$(choose_target_disk)"
  [[ -n "$target_disk" ]] || exit 130
  confirm_wipe "$target_disk" || exit 130
  tty_note "Preparing installation assets..."
  prepare_install_assets

  if [[ ! -f "$INSTALL_LIVE_ASSET_DIR/filesystem.squashfs" ]]; then
    log_msg "missing installer assets under $INSTALL_LIVE_ASSET_DIR"
    echo "Install assets were not found under $INSTALL_LIVE_ASSET_DIR" >&2
    exit 1
  fi

  bios_part="$(partition_suffix "$target_disk" 1)"
  boot_part="$(partition_suffix "$target_disk" 2)"
  root_part="$(partition_suffix "$target_disk" 3)"

  run_logged_step "wiping target disk $target_disk" wipefs -a "$target_disk"
  run_logged parted -s "$target_disk" mklabel gpt
  run_logged parted -s "$target_disk" mkpart BIOSBOOT 1MiB 3MiB
  run_logged parted -s "$target_disk" set 1 bios_grub on
  run_logged parted -s "$target_disk" mkpart ESP fat32 3MiB 515MiB
  run_logged parted -s "$target_disk" set 2 esp on
  run_logged parted -s "$target_disk" set 2 boot on
  run_logged parted -s "$target_disk" mkpart primary ext4 515MiB 100%
  wait_for_target_partitions "$target_disk" "$bios_part" "$boot_part" "$root_part" || {
    echo "Target partitions did not become ready on $target_disk" >&2
    exit 1
  }

  [[ -b "$bios_part" ]] || {
    echo "BIOS boot partition could not be created on $target_disk" >&2
    exit 1
  }

  run_logged_step_with_retry "formatting EFI partition $boot_part" 5 1 mkfs.vfat -F 32 -n BEAGLEBOOT "$boot_part"
  run_logged_step_with_retry "formatting root partition $root_part" 5 1 mkfs.ext4 -F -L BEAGLEROOT "$root_part"

  run_logged install -d -m 0755 "$TARGET_MOUNT" "$EFI_MOUNT"
  run_logged mount "$root_part" "$TARGET_MOUNT"
  run_logged install -d -m 0755 "$EFI_MOUNT" "$TARGET_MOUNT/boot/grub"
  run_logged mount "$boot_part" "$EFI_MOUNT"

  run_logged_function "copying installer assets into target filesystem" copy_assets
  root_uuid="$(blkid -s UUID -o value "$root_part")"
  write_grub_cfg "$root_uuid"
  run_logged_function "installing bootloader onto $target_disk" install_bootloader "$target_disk" "$boot_part" "$root_uuid"
  run_logged sync

  if [[ "$AUTO_INSTALL" == "1" ]]; then
    return 0
  fi

  if command -v whiptail >/dev/null 2>&1; then
    whiptail --title "Beagle OS Installation" --msgbox \
      "Installation complete. Remove the USB stick and boot from the target disk." 12 72
  else
    echo "Installation complete. Remove the USB stick and boot from the target disk."
  fi
}

main "$@"
