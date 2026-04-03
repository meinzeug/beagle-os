#!/usr/bin/env bash
set -euo pipefail

DEFAULT_CONFIG_DIR="/etc/pve-thin-client"
LIVE_STATE_DIR_DEFAULT="/run/live/medium/pve-thin-client/state"
LIVE_PRESET_FILE_DEFAULT="/run/live/medium/pve-thin-client/preset.env"
BEAGLE_STATE_DIR_DEFAULT="/var/lib/beagle-os"
PRESET_STATE_DIR_DEFAULT="/run/beagle-os/preset-state"
BEAGLE_TRACE_FILE_DEFAULT="$BEAGLE_STATE_DIR_DEFAULT/runtime-trace.log"
BEAGLE_LAST_MARKER_FILE_DEFAULT="$BEAGLE_STATE_DIR_DEFAULT/last-marker.env"

beagle_state_dir() {
  printf '%s\n' "${BEAGLE_STATE_DIR:-$BEAGLE_STATE_DIR_DEFAULT}"
}

beagle_trace_file() {
  local state_dir
  state_dir="$(beagle_state_dir)"
  printf '%s\n' "${BEAGLE_TRACE_FILE:-$state_dir/runtime-trace.log}"
}

beagle_last_marker_file() {
  local state_dir
  state_dir="$(beagle_state_dir)"
  printf '%s\n' "${BEAGLE_LAST_MARKER_FILE:-$state_dir/last-marker.env}"
}

ensure_beagle_state_dir() {
  local state_dir candidate
  state_dir="$(beagle_state_dir)"

  for candidate in \
    "$state_dir" \
    "/run/beagle-os" \
    "${XDG_RUNTIME_DIR:-/run/user/$(id -u 2>/dev/null || echo 1000)}/beagle-os" \
    "/tmp/beagle-os"
  do
    [[ -n "$candidate" ]] || continue
    if mkdir -p "$candidate" >/dev/null 2>&1 && touch "$candidate/.write-test" >/dev/null 2>&1; then
      rm -f "$candidate/.write-test" >/dev/null 2>&1 || true
      export BEAGLE_STATE_DIR="$candidate"
      return 0
    fi
  done
}

beagle_log_event() {
  local phase="${1:-event}"
  shift || true
  local message="${*:-}"
  local timestamp trace_file marker_file

  timestamp="$(date -Iseconds 2>/dev/null || date)"
  ensure_beagle_state_dir
  trace_file="$(beagle_trace_file)"
  marker_file="$(beagle_last_marker_file)"

  printf '[%s] phase=%s %s\n' "$timestamp" "$phase" "$message" >>"$trace_file" 2>/dev/null || true
  {
    printf 'timestamp=%q\n' "$timestamp"
    printf 'phase=%q\n' "$phase"
    printf 'message=%q\n' "$message"
  } >"$marker_file" 2>/dev/null || true

  if command -v logger >/dev/null 2>&1; then
    logger -t beagle-runtime "phase=$phase $message" >/dev/null 2>&1 || true
  fi
}

beagle_curl_tls_args() {
  local url="${1:-}"
  local pinned_pubkey="${2:-}"
  local ca_cert="${3:-}"
  local -a args=()

  if [[ "$url" == https://* ]]; then
    if [[ -n "$ca_cert" && -r "$ca_cert" ]]; then
      args+=(--cacert "$ca_cert")
      if [[ -n "$pinned_pubkey" ]]; then
        args+=(--pinnedpubkey "$pinned_pubkey")
      fi
    elif [[ -n "$pinned_pubkey" ]]; then
      args+=(-k --pinnedpubkey "$pinned_pubkey")
    fi
  fi

  printf '%s\n' "${args[@]}"
}

find_live_state_dir() {
  local dir
  local -a candidates=(
    "${LIVE_STATE_DIR:-$LIVE_STATE_DIR_DEFAULT}"
    "$LIVE_STATE_DIR_DEFAULT"
    "/lib/live/mount/medium/pve-thin-client/state"
  )

  for dir in "${candidates[@]}"; do
    if [[ -f "$dir/thinclient.conf" ]]; then
      printf '%s\n' "$dir"
      return 0
    fi
  done

  if command -v findmnt >/dev/null 2>&1; then
    while IFS= read -r dir; do
      [[ -n "$dir" ]] || continue
      dir="$dir/pve-thin-client/state"
      if [[ -f "$dir/thinclient.conf" ]]; then
        printf '%s\n' "$dir"
        return 0
      fi
    done < <(findmnt -rn -o TARGET 2>/dev/null || true)
  fi

  return 1
}

find_preset_file() {
  local file
  local -a candidates=(
    "${PVE_THIN_CLIENT_PRESET_FILE:-$LIVE_PRESET_FILE_DEFAULT}"
    "$LIVE_PRESET_FILE_DEFAULT"
    "/run/live/medium/pve-thin-client/live/preset.env"
    "/lib/live/mount/medium/pve-thin-client/preset.env"
    "/lib/live/mount/medium/pve-thin-client/live/preset.env"
  )

  for file in "${candidates[@]}"; do
    if [[ -f "$file" ]]; then
      printf '%s\n' "$file"
      return 0
    fi
  done

  return 1
}

restore_preset_from_cmdline() {
  local target_file="${1:-}"
  [[ -n "$target_file" ]] || return 1

  python3 - "$target_file" <<'PY'
import base64
import gzip
import re
import sys
from pathlib import Path

target = Path(sys.argv[1])
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

target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(decoded)
target.chmod(0o644)
PY
}

cmdline_var() {
  local key="${1:-}"
  local token

  [[ -n "$key" ]] || return 1

  for token in $(cat /proc/cmdline 2>/dev/null); do
    case "$token" in
      "${key}"=*)
        printf '%s\n' "${token#*=}"
        return 0
        ;;
    esac
  done

  return 1
}

apply_runtime_mode_overrides() {
  local requested_mode=""

  requested_mode="$(cmdline_var pve_thin_client.client_mode 2>/dev/null || true)"
  requested_mode="${requested_mode,,}"

  case "$requested_mode" in
    desktop|moonlight)
      PVE_THIN_CLIENT_MODE="MOONLIGHT"
      PVE_THIN_CLIENT_BOOT_PROFILE="desktop"
      ;;
    gaming|gfn|geforcenow|geforce-now)
      PVE_THIN_CLIENT_MODE="GFN"
      PVE_THIN_CLIENT_BOOT_PROFILE="gaming"
      ;;
  esac

  case "${PVE_THIN_CLIENT_MODE:-MOONLIGHT}" in
    GFN)
      PVE_THIN_CLIENT_BOOT_PROFILE="${PVE_THIN_CLIENT_BOOT_PROFILE:-gaming}"
      ;;
    *)
      PVE_THIN_CLIENT_BOOT_PROFILE="${PVE_THIN_CLIENT_BOOT_PROFILE:-desktop}"
      ;;
  esac
}

runtime_user_name() {
  printf '%s\n' "${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}"
}

runtime_group_name() {
  printf '%s\n' "${PVE_THIN_CLIENT_RUNTIME_GROUP:-$(runtime_user_name)}"
}

live_medium_dir() {
  local medium="${PVE_THIN_CLIENT_LIVE_MEDIUM_DIR:-/run/live/medium}"

  if [[ -d "$medium" ]]; then
    printf '%s\n' "$medium"
    return 0
  fi

  return 1
}

ensure_runtime_owned_dir() {
  local path="${1:-}"
  local mode="${2:-0700}"
  local owner group

  [[ -n "$path" ]] || return 1

  owner="$(runtime_user_name)"
  group="$(runtime_group_name)"

  if install -d -m "$mode" "$path" >/dev/null 2>&1 && touch "$path/.beagle-write-test" >/dev/null 2>&1; then
    rm -f "$path/.beagle-write-test" >/dev/null 2>&1 || true
    return 0
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n install -d -m "$mode" -o "$owner" -g "$group" "$path" >/dev/null 2>&1; then
    if touch "$path/.beagle-write-test" >/dev/null 2>&1; then
      rm -f "$path/.beagle-write-test" >/dev/null 2>&1 || true
      return 0
    fi
  fi

  return 1
}

prepare_geforcenow_environment() {
  local runtime_home="${1:-/home/$(runtime_user_name)}"
  local storage_root medium home_dir data_dir cache_dir config_dir tmp_dir

  storage_root="${PVE_THIN_CLIENT_GFN_STORAGE_ROOT:-}"
  if [[ -z "$storage_root" ]]; then
    medium="$(live_medium_dir 2>/dev/null || true)"
    if [[ -n "$medium" ]]; then
      storage_root="$medium/pve-thin-client/state/gfn"
    else
      storage_root="$(beagle_state_dir)/gfn"
    fi
  fi

  home_dir="$storage_root/home"
  data_dir="$home_dir/.local/share"
  cache_dir="$home_dir/.cache"
  config_dir="$home_dir/.config"
  tmp_dir="$storage_root/tmp"

  for dir in \
    "$storage_root" \
    "$home_dir" \
    "$home_dir/.local" \
    "$data_dir" \
    "$home_dir/.var/app" \
    "$cache_dir" \
    "$config_dir" \
    "$tmp_dir"
  do
    ensure_runtime_owned_dir "$dir" 0700 || return 1
  done

  export PVE_THIN_CLIENT_GFN_STORAGE_ROOT="$storage_root"
  export PVE_THIN_CLIENT_GFN_RUNTIME_HOME="$runtime_home"
  export HOME="$home_dir"
  export XDG_DATA_HOME="$data_dir"
  export XDG_CACHE_HOME="$cache_dir"
  export XDG_CONFIG_HOME="$config_dir"
  export FLATPAK_USER_DIR="$data_dir/flatpak"
  export FLATPAK_DOWNLOAD_TMPDIR="$tmp_dir"

  ensure_runtime_owned_dir "$FLATPAK_USER_DIR" 0700 || return 1
  ensure_runtime_owned_dir "$XDG_CACHE_HOME" 0700 || return 1
  ensure_runtime_owned_dir "$XDG_CONFIG_HOME" 0700 || return 1
  ensure_runtime_owned_dir "$HOME/.var/app" 0700 || return 1

  return 0
}

generate_config_dir_from_preset() {
  local preset_file="${1:-}"
  local state_dir="${2:-${PRESET_STATE_DIR:-$PRESET_STATE_DIR_DEFAULT}}"
  local installer_dir installer_script

  [[ -f "$preset_file" ]] || return 1

  installer_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../installer" && pwd)"
  installer_script="$installer_dir/write-config.sh"
  [[ -x "$installer_script" ]] || return 1

  # shellcheck disable=SC1090
  source "$preset_file"

  install -d -m 0755 "$state_dir"

  MODE="${PVE_THIN_CLIENT_PRESET_DEFAULT_MODE:-MOONLIGHT}" \
  RUNTIME_USER="${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}" \
  AUTOSTART="${PVE_THIN_CLIENT_PRESET_AUTOSTART:-1}" \
  PROFILE_NAME="${PVE_THIN_CLIENT_PRESET_PROFILE_NAME:-default}" \
  HOSTNAME_VALUE="${PVE_THIN_CLIENT_PRESET_HOSTNAME_VALUE:-beagle-os}" \
  CONNECTION_METHOD="direct" \
  MOONLIGHT_HOST="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_HOST:-}" \
  MOONLIGHT_LOCAL_HOST="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_LOCAL_HOST:-}" \
  MOONLIGHT_PORT="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_PORT:-}" \
  MOONLIGHT_APP="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_APP:-Desktop}" \
  MOONLIGHT_BIN="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_BIN:-moonlight}" \
  MOONLIGHT_RESOLUTION="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_RESOLUTION:-auto}" \
  MOONLIGHT_FPS="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_FPS:-60}" \
  MOONLIGHT_BITRATE="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_BITRATE:-20000}" \
  MOONLIGHT_VIDEO_CODEC="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_VIDEO_CODEC:-H.264}" \
  MOONLIGHT_VIDEO_DECODER="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_VIDEO_DECODER:-auto}" \
  MOONLIGHT_AUDIO_CONFIG="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_AUDIO_CONFIG:-stereo}" \
  MOONLIGHT_ABSOLUTE_MOUSE="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_ABSOLUTE_MOUSE:-1}" \
  MOONLIGHT_QUIT_AFTER="${PVE_THIN_CLIENT_PRESET_MOONLIGHT_QUIT_AFTER:-0}" \
  SUNSHINE_API_URL="${PVE_THIN_CLIENT_PRESET_SUNSHINE_API_URL:-}" \
  PROXMOX_SCHEME="${PVE_THIN_CLIENT_PRESET_PROXMOX_SCHEME:-https}" \
  PROXMOX_HOST="${PVE_THIN_CLIENT_PRESET_PROXMOX_HOST:-}" \
  PROXMOX_PORT="${PVE_THIN_CLIENT_PRESET_PROXMOX_PORT:-8006}" \
  PROXMOX_NODE="${PVE_THIN_CLIENT_PRESET_PROXMOX_NODE:-}" \
  PROXMOX_VMID="${PVE_THIN_CLIENT_PRESET_PROXMOX_VMID:-}" \
  PROXMOX_REALM="${PVE_THIN_CLIENT_PRESET_PROXMOX_REALM:-pam}" \
  PROXMOX_VERIFY_TLS="${PVE_THIN_CLIENT_PRESET_PROXMOX_VERIFY_TLS:-1}" \
  BEAGLE_MANAGER_URL="${PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_URL:-}" \
  BEAGLE_MANAGER_PINNED_PUBKEY="${PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_PINNED_PUBKEY:-}" \
  BEAGLE_ENROLLMENT_URL="${PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_URL:-}" \
  BEAGLE_UPDATE_ENABLED="${PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_ENABLED:-1}" \
  BEAGLE_UPDATE_CHANNEL="${PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_CHANNEL:-stable}" \
  BEAGLE_UPDATE_BEHAVIOR="${PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_BEHAVIOR:-prompt}" \
  BEAGLE_UPDATE_FEED_URL="${PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_FEED_URL:-}" \
  BEAGLE_UPDATE_VERSION_PIN="${PVE_THIN_CLIENT_PRESET_BEAGLE_UPDATE_VERSION_PIN:-}" \
  BEAGLE_EGRESS_MODE="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_MODE:-direct}" \
  BEAGLE_EGRESS_TYPE="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_TYPE:-}" \
  BEAGLE_EGRESS_INTERFACE="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_INTERFACE:-beagle-egress}" \
  BEAGLE_EGRESS_DOMAINS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_DOMAINS:-}" \
  BEAGLE_EGRESS_RESOLVERS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_RESOLVERS:-1.1.1.1 8.8.8.8}" \
  BEAGLE_EGRESS_ALLOWED_IPS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_ALLOWED_IPS:-}" \
  BEAGLE_EGRESS_WG_ADDRESS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ADDRESS:-}" \
  BEAGLE_EGRESS_WG_DNS="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_DNS:-}" \
  BEAGLE_EGRESS_WG_PUBLIC_KEY="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PUBLIC_KEY:-}" \
  BEAGLE_EGRESS_WG_ENDPOINT="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_ENDPOINT:-}" \
  BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PERSISTENT_KEEPALIVE:-25}" \
  IDENTITY_HOSTNAME="${PVE_THIN_CLIENT_PRESET_IDENTITY_HOSTNAME:-}" \
  IDENTITY_TIMEZONE="${PVE_THIN_CLIENT_PRESET_IDENTITY_TIMEZONE:-}" \
  IDENTITY_LOCALE="${PVE_THIN_CLIENT_PRESET_IDENTITY_LOCALE:-}" \
  IDENTITY_KEYMAP="${PVE_THIN_CLIENT_PRESET_IDENTITY_KEYMAP:-}" \
  IDENTITY_CHROME_PROFILE="${PVE_THIN_CLIENT_PRESET_IDENTITY_CHROME_PROFILE:-default}" \
  BEAGLE_USB_ENABLED="${PVE_THIN_CLIENT_PRESET_BEAGLE_USB_ENABLED:-1}" \
  BEAGLE_USB_TUNNEL_HOST="${PVE_THIN_CLIENT_PRESET_BEAGLE_USB_TUNNEL_HOST:-}" \
  BEAGLE_USB_TUNNEL_USER="${PVE_THIN_CLIENT_PRESET_BEAGLE_USB_TUNNEL_USER:-thinovernet}" \
  BEAGLE_USB_TUNNEL_PORT="${PVE_THIN_CLIENT_PRESET_BEAGLE_USB_TUNNEL_PORT:-}" \
  BEAGLE_USB_ATTACH_HOST="${PVE_THIN_CLIENT_PRESET_BEAGLE_USB_ATTACH_HOST:-10.10.10.1}" \
  NETWORK_MODE="${PVE_THIN_CLIENT_PRESET_NETWORK_MODE:-dhcp}" \
  NETWORK_INTERFACE="${PVE_THIN_CLIENT_PRESET_NETWORK_INTERFACE:-eth0}" \
  NETWORK_STATIC_ADDRESS="${PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_ADDRESS:-}" \
  NETWORK_STATIC_PREFIX="${PVE_THIN_CLIENT_PRESET_NETWORK_STATIC_PREFIX:-24}" \
  NETWORK_GATEWAY="${PVE_THIN_CLIENT_PRESET_NETWORK_GATEWAY:-}" \
  NETWORK_DNS_SERVERS="${PVE_THIN_CLIENT_PRESET_NETWORK_DNS_SERVERS:-1.1.1.1 8.8.8.8}" \
  CONNECTION_USERNAME="${PVE_THIN_CLIENT_PRESET_PROXMOX_USERNAME:-}" \
  CONNECTION_PASSWORD="${PVE_THIN_CLIENT_PRESET_PROXMOX_PASSWORD:-}" \
  CONNECTION_TOKEN="${PVE_THIN_CLIENT_PRESET_PROXMOX_TOKEN:-}" \
  BEAGLE_MANAGER_TOKEN="" \
  BEAGLE_ENROLLMENT_TOKEN="${PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_TOKEN:-}" \
  BEAGLE_EGRESS_WG_PRIVATE_KEY="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRIVATE_KEY:-}" \
  BEAGLE_EGRESS_WG_PRESHARED_KEY="${PVE_THIN_CLIENT_PRESET_BEAGLE_EGRESS_WG_PRESHARED_KEY:-}" \
  SUNSHINE_USERNAME="${PVE_THIN_CLIENT_PRESET_SUNSHINE_USERNAME:-}" \
  SUNSHINE_PASSWORD="${PVE_THIN_CLIENT_PRESET_SUNSHINE_PASSWORD:-}" \
  SUNSHINE_PIN="${PVE_THIN_CLIENT_PRESET_SUNSHINE_PIN:-}" \
  SUNSHINE_PINNED_PUBKEY="${PVE_THIN_CLIENT_PRESET_SUNSHINE_PINNED_PUBKEY:-}" \
  SUNSHINE_SERVER_NAME="${PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_NAME:-}" \
  SUNSHINE_SERVER_STREAM_PORT="${PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_STREAM_PORT:-}" \
  SUNSHINE_SERVER_UNIQUEID="${PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_UNIQUEID:-}" \
  SUNSHINE_SERVER_CERT_B64="${PVE_THIN_CLIENT_PRESET_SUNSHINE_SERVER_CERT_B64:-}" \
  RUNTIME_PASSWORD="${PVE_THIN_CLIENT_PRESET_THINCLIENT_PASSWORD:-}" \
    "$installer_script" "$state_dir"

  printf '%s\n' "$state_dir"
}

find_config_dir() {
  if [[ -f "${CONFIG_DIR:-$DEFAULT_CONFIG_DIR}/thinclient.conf" ]]; then
    printf '%s\n' "${CONFIG_DIR:-$DEFAULT_CONFIG_DIR}"
    return 0
  fi

  if LIVE_STATE_DIR="$(find_live_state_dir)"; then
    printf '%s\n' "$LIVE_STATE_DIR"
    return 0
  fi

  if preset_file="$(find_preset_file 2>/dev/null || true)" && [[ -n "$preset_file" ]]; then
    if generated_dir="$(generate_config_dir_from_preset "$preset_file" 2>/dev/null || true)" && [[ -f "$generated_dir/thinclient.conf" ]]; then
      printf '%s\n' "$generated_dir"
      return 0
    fi
  fi

  if preset_cache_dir="$(beagle_state_dir 2>/dev/null || printf '%s\n' "$PRESET_STATE_DIR_DEFAULT")"; then
    preset_cache_file="$preset_cache_dir/cmdline-preset.env"
    if restore_preset_from_cmdline "$preset_cache_file" 2>/dev/null; then
      if generated_dir="$(generate_config_dir_from_preset "$preset_cache_file" 2>/dev/null || true)" && [[ -f "$generated_dir/thinclient.conf" ]]; then
        printf '%s\n' "$generated_dir"
        return 0
      fi
    fi
  fi

  return 1
}

load_runtime_config() {
  local dir
  dir="$(find_config_dir)" || {
    echo "Unable to locate thin-client config." >&2
    return 1
  }

  CONFIG_DIR="$dir"
  CONFIG_FILE="$dir/thinclient.conf"
  NETWORK_FILE="$dir/network.env"
  CREDENTIALS_FILE="$dir/credentials.env"
  LOCAL_AUTH_FILE="$dir/local-auth.env"

  if [[ ! -r "$CONFIG_FILE" ]]; then
    echo "Thin-client config is not readable: $CONFIG_FILE" >&2
    return 1
  fi

  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
  if [[ -r "$NETWORK_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$NETWORK_FILE"
  elif [[ -e "$NETWORK_FILE" ]]; then
    echo "Skipping unreadable network file: $NETWORK_FILE" >&2
  fi
  if [[ -r "$CREDENTIALS_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CREDENTIALS_FILE"
  elif [[ -e "$CREDENTIALS_FILE" ]]; then
    echo "Skipping unreadable credentials file: $CREDENTIALS_FILE" >&2
  fi

  apply_runtime_mode_overrides
}

render_template() {
  local template="$1"
  local output="$template"

  output="${output//\{mode\}/${PVE_THIN_CLIENT_MODE:-}}"
  output="${output//\{username\}/${PVE_THIN_CLIENT_CONNECTION_USERNAME:-}}"
  output="${output//\{password\}/${PVE_THIN_CLIENT_CONNECTION_PASSWORD:-}}"
  output="${output//\{token\}/${PVE_THIN_CLIENT_CONNECTION_TOKEN:-}}"
  output="${output//\{host\}/${PVE_THIN_CLIENT_PROXMOX_HOST:-}}"
  output="${output//\{node\}/${PVE_THIN_CLIENT_PROXMOX_NODE:-}}"
  output="${output//\{vmid\}/${PVE_THIN_CLIENT_PROXMOX_VMID:-}}"
  output="${output//\{moonlight_host\}/${PVE_THIN_CLIENT_MOONLIGHT_HOST:-}}"
  output="${output//\{moonlight_local_host\}/${PVE_THIN_CLIENT_MOONLIGHT_LOCAL_HOST:-}}"
  output="${output//\{moonlight_port\}/${PVE_THIN_CLIENT_MOONLIGHT_PORT:-}}"
  output="${output//\{sunshine_api_url\}/${PVE_THIN_CLIENT_SUNSHINE_API_URL:-}}"

  printf '%s\n' "$output"
}

split_browser_flags() {
  local flags="${PVE_THIN_CLIENT_BROWSER_FLAGS:-}"
  if [[ -z "$flags" ]]; then
    return 0
  fi

  # shellcheck disable=SC2206
  BROWSER_FLAG_ARRAY=($flags)
}
