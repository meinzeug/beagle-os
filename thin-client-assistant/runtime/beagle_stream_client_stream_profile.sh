#!/usr/bin/env bash

beagle_stream_profile_override_env() {
  if [[ -n "${BEAGLE_STREAM_PROFILE_OVERRIDE_ENV:-}" ]]; then
    printf '%s\n' "$BEAGLE_STREAM_PROFILE_OVERRIDE_ENV"
    return 0
  fi
  if declare -F beagle_state_dir >/dev/null 2>&1; then
    printf '%s/stream-profile.env\n' "$(beagle_state_dir)"
    return 0
  fi
  printf '%s\n' "/var/lib/beagle-os/stream-profile.env"
}

BEAGLE_STREAM_PROFILE_OVERRIDE_ENV="$(beagle_stream_profile_override_env)"
if [[ -r "$BEAGLE_STREAM_PROFILE_OVERRIDE_ENV" ]]; then
  # shellcheck disable=SC1090
  source "$BEAGLE_STREAM_PROFILE_OVERRIDE_ENV"
fi

beagle_stream_client_video_decoder() {
  local configured
  configured="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VIDEO_DECODER:-software}"

  if [[ "$configured" == "auto" ]]; then
    if beagle_stream_hostless_enabled; then
      printf 'software\n'
      return 0
    fi

    # Hardware decode (VAAPI/VDPAU/Vulkan) requires /dev/dri/renderD128 (render node).
    # card0 is the KMS display node only; without renderD128 there is no working
    # hardware video decoder, so force software to avoid the blocking warning dialog.
    if [[ ! -e /dev/dri/renderD128 ]]; then
      printf 'software\n'
      return 0
    fi
    # renderD128 exists but is not accessible
    if [[ ! -r /dev/dri/renderD128 || ! -w /dev/dri/renderD128 ]]; then
      printf 'software\n'
      return 0
    fi
  fi

  printf '%s\n' "$configured"
}

beagle_stream_auto_profile_state_file() {
  if [[ -n "${BEAGLE_STREAM_AUTO_PROFILE_ENV:-}" ]]; then
    printf '%s\n' "$BEAGLE_STREAM_AUTO_PROFILE_ENV"
    return 0
  fi
  if declare -F beagle_state_dir >/dev/null 2>&1; then
    printf '%s/stream-auto-profile.env\n' "$(beagle_state_dir)"
    return 0
  fi
  printf '%s\n' "/var/lib/beagle-os/stream-auto-profile.env"
}

beagle_stream_route_device_for_host() {
  local target route
  target="${1:-}"
  [[ -n "$target" ]] || return 1
  route="$(ip route get "$target" 2>/dev/null | head -n 1 || true)"
  awk '{for (idx = 1; idx <= NF; idx++) if ($idx == "dev") {print $(idx + 1); exit}}' <<<"$route"
}

beagle_stream_route_link_mbps() {
  local target dev speed
  target="${1:-}"
  dev="$(beagle_stream_route_device_for_host "$target" 2>/dev/null || true)"
  [[ -n "$dev" && -r "/sys/class/net/$dev/speed" ]] || {
    printf '%s\n' "0"
    return 0
  }
  speed="$(cat "/sys/class/net/$dev/speed" 2>/dev/null || true)"
  [[ "$speed" =~ ^[0-9]+$ ]] || speed=0
  printf '%s\n' "$speed"
}

beagle_stream_ping_stats() {
  local target output transmitted received loss avg max ping_count ping_timeout ping_cap
  target="${1:-}"
  [[ -n "$target" ]] || return 1
  if ! command -v ping >/dev/null 2>&1; then
    return 1
  fi

  ping_count="${PVE_THIN_CLIENT_BEAGLE_STREAM_AUTO_QUALITY_PING_COUNT:-3}"
  ping_timeout="${PVE_THIN_CLIENT_BEAGLE_STREAM_AUTO_QUALITY_PING_TIMEOUT:-1}"
  ping_cap="${PVE_THIN_CLIENT_BEAGLE_STREAM_AUTO_QUALITY_PING_CAP:-4}"

  if command -v timeout >/dev/null 2>&1; then
    output="$(LC_ALL=C timeout --preserve-status "${ping_cap}" ping -n -c "${ping_count}" -W "${ping_timeout}" "$target" 2>/dev/null || true)"
  else
    output="$(LC_ALL=C ping -n -c "${ping_count}" -W "${ping_timeout}" "$target" 2>/dev/null || true)"
  fi
  transmitted="$(awk '/packets transmitted/ {print $1; exit}' <<<"$output")"
  received="$(awk '/packets transmitted/ {print $4; exit}' <<<"$output")"
  loss="$(awk -F', ' '/packet loss/ {for (idx = 1; idx <= NF; idx++) if ($idx ~ /packet loss/) {gsub(/% packet loss/, "", $idx); print int($idx); exit}}' <<<"$output")"
  avg="$(awk -F'=' '/rtt min\/avg\/max|round-trip min\/avg\/max/ {split($2, values, "/"); print int(values[2] + 0.5); exit}' <<<"$output")"
  max="$(awk -F'=' '/rtt min\/avg\/max|round-trip min\/avg\/max/ {split($2, values, "/"); print int(values[3] + 0.5); exit}' <<<"$output")"
  [[ "$transmitted" =~ ^[0-9]+$ ]] || transmitted=0
  [[ "$received" =~ ^[0-9]+$ ]] || received=0
  [[ "$loss" =~ ^[0-9]+$ ]] || loss=100
  [[ "$avg" =~ ^[0-9]+$ ]] || avg=999
  [[ "$max" =~ ^[0-9]+$ ]] || max=999
  printf '%s %s %s %s %s\n' "$transmitted" "$received" "$loss" "$avg" "$max"
}

beagle_stream_auto_quality_bucket() {
  local loss avg max link_mbps
  loss="${1:-100}"
  avg="${2:-999}"
  max="${3:-999}"
  link_mbps="${4:-0}"

  if [[ "$loss" -ge 15 || "$avg" -ge 100 || "$max" -ge 180 ]]; then
    printf '%s\n' "survival"
  elif [[ "$loss" -ge 5 || "$avg" -ge 70 || "$max" -ge 130 || ( "$link_mbps" -gt 0 && "$link_mbps" -lt 25 ) ]]; then
    printf '%s\n' "low"
  elif [[ "$loss" -ge 2 || "$avg" -ge 45 || "$max" -ge 90 || ( "$link_mbps" -gt 0 && "$link_mbps" -lt 60 ) ]]; then
    printf '%s\n' "medium"
  elif [[ "$loss" -ge 1 || "$avg" -ge 28 || "$max" -ge 60 || ( "$link_mbps" -gt 0 && "$link_mbps" -lt 120 ) ]]; then
    printf '%s\n' "high"
  else
    printf '%s\n' "ultra"
  fi
}

beagle_stream_auto_profile_for_bucket() {
  local bucket detected_resolution
  bucket="${1:-medium}"
  detected_resolution="$(local_display_resolution 2>/dev/null || true)"
  case "$bucket" in
    ultra)
      printf 'resolution=%s\nfps=60\nbitrate=45000\npacket_size=1392\nframe_pacing=0\nvsync=0\n' "${detected_resolution:-1920x1080}"
      ;;
    high)
      printf 'resolution=%s\nfps=60\nbitrate=32000\npacket_size=1360\nframe_pacing=0\nvsync=0\n' "${detected_resolution:-1920x1080}"
      ;;
    medium)
      printf 'resolution=1920x1080\nfps=45\nbitrate=22000\npacket_size=1280\nframe_pacing=1\nvsync=0\n'
      ;;
    low)
      printf 'resolution=1280x720\nfps=30\nbitrate=10000\npacket_size=1200\nframe_pacing=1\nvsync=0\n'
      ;;
    *)
      printf 'resolution=1280x720\nfps=30\nbitrate=6000\npacket_size=1100\nframe_pacing=1\nvsync=1\n'
      ;;
  esac
}

beagle_stream_detect_auto_profile() {
  local target stats transmitted received loss avg max link_mbps bucket state_file now state_dir
  target="${1:-}"
  [[ -n "$target" ]] || return 1

  stats="$(beagle_stream_ping_stats "$target" 2>/dev/null || true)"
  read -r transmitted received loss avg max <<<"${stats:-0 0 100 999 999}"
  link_mbps="$(beagle_stream_route_link_mbps "$target" 2>/dev/null || printf '0')"
  bucket="$(beagle_stream_auto_quality_bucket "$loss" "$avg" "$max" "$link_mbps")"
  now="$(date -Iseconds 2>/dev/null || date)"

  PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_BUCKET="$bucket"
  PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_TARGET="$target"
  PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_LINK_MBPS="$link_mbps"
  PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_PACKET_LOSS="$loss"
  PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_RTT_AVG_MS="$avg"
  PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_RTT_MAX_MS="$max"
  PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_CHECKED_AT="$now"

  state_file="$(beagle_stream_auto_profile_state_file)"
  state_dir="${state_file%/*}"
  mkdir -p "$state_dir" 2>/dev/null || true
  {
    printf 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_BUCKET=%q\n' "$bucket"
    printf 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_TARGET=%q\n' "$target"
    printf 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_LINK_MBPS=%q\n' "$link_mbps"
    printf 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_PACKET_LOSS=%q\n' "$loss"
    printf 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_RTT_AVG_MS=%q\n' "$avg"
    printf 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_RTT_MAX_MS=%q\n' "$max"
    printf 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_CHECKED_AT=%q\n' "$now"
  } >"$state_file" 2>/dev/null || true

  beagle_stream_auto_profile_for_bucket "$bucket"
}

beagle_stream_apply_auto_profile() {
  local target profile line key value state_file
  [[ "${BEAGLE_STREAM_AUTO_PROFILE_APPLIED:-0}" == "1" ]] && return 0
  BEAGLE_STREAM_AUTO_PROFILE_APPLIED=1

  [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY:-1}" == "1" ]] || return 0
  case "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PRESET:-auto}" in
    auto|adaptive|""|balanced|production|live_smooth) ;;
    *) return 0 ;;
  esac

  target="$(beagle_stream_client_connect_host 2>/dev/null || true)"
  [[ -n "$target" ]] || target="$(beagle_stream_client_host 2>/dev/null || true)"
  [[ -n "$target" ]] || return 0

  profile="$(beagle_stream_detect_auto_profile "$target" 2>/dev/null || true)"
  [[ -n "$profile" ]] || return 0
  state_file="$(beagle_stream_auto_profile_state_file)"
  if [[ -r "$state_file" ]]; then
    # shellcheck disable=SC1090
    source "$state_file"
  fi
  while IFS='=' read -r key value; do
    case "$key" in
      resolution)
        [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RESOLUTION:-auto}" == "auto" || -z "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RESOLUTION:-}" ]] && PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RESOLUTION="$value"
        ;;
      fps)
        [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS:-auto}" == "auto" || -z "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS:-}" ]] && PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS="$value"
        ;;
      bitrate)
        [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BITRATE:-auto}" == "auto" || -z "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BITRATE:-}" ]] && PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BITRATE="$value"
        ;;
      packet_size)
        [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PACKET_SIZE:-auto}" == "auto" || -z "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PACKET_SIZE:-}" ]] && PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PACKET_SIZE="$value"
        ;;
      frame_pacing)
        [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FRAME_PACING:-auto}" == "auto" || -z "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FRAME_PACING:-}" ]] && PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FRAME_PACING="$value"
        ;;
      vsync)
        [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VSYNC:-auto}" == "auto" || -z "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VSYNC:-}" ]] && PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VSYNC="$value"
        ;;
    esac
  done <<<"$profile"

  if declare -F beagle_log_event >/dev/null 2>&1; then
    beagle_log_event "beagle-stream-client.auto-quality" "target=${target} bucket=${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_BUCKET:-unknown} resolution=${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RESOLUTION:-auto} fps=${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS:-auto} bitrate=${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BITRATE:-auto}"
  fi
}

beagle_stream_ensure_auto_profile() {
  if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY:-1}" == "1" ]]; then
    beagle_stream_apply_auto_profile || true
  fi
}

record_decoder_choice() {
  local decoder="$1"
  beagle_log_event "beagle-stream-client.decoder" "decoder=${decoder} codec=${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VIDEO_CODEC:-auto}"
}

local_display_resolution() {
  if command -v xrandr >/dev/null 2>&1; then
    xrandr --query 2>/dev/null | awk '
      / connected primary / {
        for (i = 1; i <= NF; i++) {
          if ($i ~ /^[0-9]+x[0-9]+\+/) {
            split($i, parts, "+")
            print parts[1]
            exit
          }
        }
      }
      / connected / {
        for (i = 1; i <= NF; i++) {
          if ($i ~ /^[0-9]+x[0-9]+\+/) {
            split($i, parts, "+")
            print parts[1]
            exit
          }
        }
      }
      /^Screen [0-9]+:/ {
        if (match($0, /current [0-9]+ x [0-9]+/)) {
          value = substr($0, RSTART + 8, RLENGTH - 8)
          gsub(/ /, "", value)
          print value
          exit
        }
      }
    '
  fi
}

beagle_stream_client_resolution() {
  local configured detected
  beagle_stream_ensure_auto_profile
  configured="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RESOLUTION:-auto}"

  if [[ "$configured" == "auto" ]] && beagle_stream_hostless_enabled; then
    printf '%s\n' "1920x1080"
    return 0
  fi

  if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_RESOLUTION:-1}" == "1" ]]; then
    detected="$(local_display_resolution 2>/dev/null || true)"
    case "$configured" in
      ""|auto|native)
        if [[ -n "$detected" ]]; then
          printf '%s\n' "$detected"
          return 0
        fi
        ;;
      720|1080|1440|4K)
        if [[ -n "$detected" && "$detected" != "1024x768" ]]; then
          printf '%s\n' "$detected"
          return 0
        fi
        ;;
    esac
  fi

  printf '%s\n' "$configured"
}

beagle_stream_client_fps() {
  local configured
  beagle_stream_ensure_auto_profile
  configured="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS:-60}"

  printf '%s\n' "$configured"
}

beagle_stream_client_bitrate() {
  local configured
  beagle_stream_ensure_auto_profile
  configured="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BITRATE:-32000}"

  printf '%s\n' "$configured"
}

beagle_stream_client_packet_size() {
  local configured
  beagle_stream_ensure_auto_profile
  configured="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PACKET_SIZE:-}"

  if [[ "$configured" == "auto" ]]; then
    configured=""
  fi

  if [[ -n "$configured" ]]; then
    printf '%s\n' "$configured"
    return 0
  fi

  if beagle_stream_hostless_enabled; then
    # Leave packet size unset to use the client default transport behavior.
    printf '%s\n' ""
    return 0
  fi

  printf '%s\n' ""
}
