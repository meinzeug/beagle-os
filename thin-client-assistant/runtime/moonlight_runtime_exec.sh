#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOONLIGHT_RUNTIME_ENVIRONMENT_SH="${MOONLIGHT_RUNTIME_ENVIRONMENT_SH:-$SCRIPT_DIR/moonlight_runtime_environment.sh}"
MOONLIGHT_STREAM_PROFILE_SH="${MOONLIGHT_STREAM_PROFILE_SH:-$SCRIPT_DIR/moonlight_stream_profile.sh}"
# shellcheck disable=SC1090
source "$MOONLIGHT_RUNTIME_ENVIRONMENT_SH"
# shellcheck disable=SC1090
source "$MOONLIGHT_STREAM_PROFILE_SH"

moonlight_bin() {
  if [[ "${PVE_THIN_CLIENT_MOONLIGHT_BIN:-}" == "" ]] && beagle_stream_hostless_enabled; then
    printf '%s\n' "beagle-stream"
    return 0
  fi

  printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_BIN:-moonlight}"
}

moonlight_app() {
  render_template "${PVE_THIN_CLIENT_MOONLIGHT_APP:-Desktop}"
}

beagle_stream_enrollment_config() {
  printf '%s\n' "${BEAGLE_STREAM_ENROLLMENT_CONF:-/etc/beagle/enrollment.conf}"
}

beagle_stream_enrollment_value() {
  local key="$1"
  local file

  file="$(beagle_stream_enrollment_config)"
  [[ -r "$file" ]] || return 1

  awk -F= -v key="$key" '
    $1 == key {
      value = substr($0, index($0, "=") + 1)
      gsub(/^"/, "", value)
      gsub(/"$/, "", value)
      gsub(/^'\''/, "", value)
      gsub(/'\''$/, "", value)
      print value
      found = 1
      exit
    }
    END { if (!found) exit 1 }
  ' "$file"
}

beagle_stream_hostless_enabled() {
  local host control_plane token device_id pool_id

  host="$(moonlight_host 2>/dev/null || true)"
  [[ -z "$host" ]] || return 1

  control_plane="$(beagle_stream_enrollment_value control_plane 2>/dev/null || true)"
  token="$(beagle_stream_enrollment_value enrollment_token 2>/dev/null || true)"
  device_id="$(beagle_stream_enrollment_value device_id 2>/dev/null || true)"
  pool_id="$(beagle_stream_enrollment_value pool_id 2>/dev/null || true)"

  [[ -n "$control_plane" && -n "$token" && -n "$device_id" && -n "$pool_id" ]]
}

build_stream_args() {
  local resolution fps bitrate codec decoder audio_config app host connect_host port target
  local -n out_ref="$1"

  host="$(moonlight_host)"
  connect_host="$(moonlight_connect_host)"
  port="$(moonlight_port)"
  app="$(moonlight_app)"
  resolution="$(moonlight_resolution)"
  fps="${PVE_THIN_CLIENT_MOONLIGHT_FPS:-60}"
  bitrate="${PVE_THIN_CLIENT_MOONLIGHT_BITRATE:-20000}"
  codec="${PVE_THIN_CLIENT_MOONLIGHT_VIDEO_CODEC:-H.264}"
  decoder="$(moonlight_video_decoder)"
  audio_config="${PVE_THIN_CLIENT_MOONLIGHT_AUDIO_CONFIG:-stereo}"

  if beagle_stream_hostless_enabled; then
    out_ref=("$(moonlight_bin)" stream "$app")
  else
    target="$(format_moonlight_target "${connect_host:-$host}" "$port")"
    out_ref=("$(moonlight_bin)" stream "$target" "$app")
  fi

  case "$resolution" in
    720|1080|1440|4K)
      out_ref+=("--$resolution")
      ;;
    *x*)
      out_ref+=(--resolution "$resolution")
      ;;
  esac

  [[ -n "$fps" ]] && out_ref+=(--fps "$fps")
  [[ -n "$bitrate" ]] && out_ref+=(--bitrate "$bitrate")
  [[ -n "$codec" ]] && out_ref+=(--video-codec "$codec")
  [[ -n "$decoder" ]] && out_ref+=(--video-decoder "$decoder")
  [[ -n "$audio_config" ]] && out_ref+=(--audio-config "$audio_config")

  out_ref+=(--display-mode fullscreen --frame-pacing --keep-awake --no-hdr --no-yuv444)

  if [[ "${PVE_THIN_CLIENT_MOONLIGHT_ABSOLUTE_MOUSE:-1}" == "1" ]]; then
    out_ref+=(--absolute-mouse)
  fi
  if [[ "${PVE_THIN_CLIENT_MOONLIGHT_QUIT_AFTER:-0}" == "1" ]]; then
    out_ref+=(--quit-after)
  fi
}
