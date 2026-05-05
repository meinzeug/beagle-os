#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEAGLE_STREAM_CLIENT_RUNTIME_ENVIRONMENT_SH="${BEAGLE_STREAM_CLIENT_RUNTIME_ENVIRONMENT_SH:-$SCRIPT_DIR/beagle_stream_client_runtime_environment.sh}"
BEAGLE_STREAM_CLIENT_STREAM_PROFILE_SH="${BEAGLE_STREAM_CLIENT_STREAM_PROFILE_SH:-$SCRIPT_DIR/beagle_stream_client_stream_profile.sh}"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_RUNTIME_ENVIRONMENT_SH"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_STREAM_PROFILE_SH"

beagle_stream_client_bin() {
  if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BIN:-}" == "" ]] && beagle_stream_hostless_enabled; then
    printf '%s\n' "beagle-stream"
    return 0
  fi

  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BIN:-beagle-stream-client}"
}

beagle_stream_client_app() {
  render_template "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_APP:-Desktop}"
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
  local host control_plane token device_id

  control_plane="$(beagle_stream_enrollment_value control_plane 2>/dev/null || true)"
  token="$(beagle_stream_enrollment_value enrollment_token 2>/dev/null || true)"
  device_id="$(beagle_stream_enrollment_value device_id 2>/dev/null || true)"

  # pool_id can be empty for dedicated VM targets (e.g. vm-100).
  [[ -n "$control_plane" && -n "$token" && -n "$device_id" ]] || return 1

  if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOSTLESS:-0}" == "1" ]]; then
    return 0
  fi

  if beagle_stream_broker_connection; then
    return 0
  fi

  host="$(beagle_stream_client_host 2>/dev/null || true)"
  [[ -z "$host" ]]
}

build_stream_args() {
  local resolution fps bitrate codec decoder audio_config app host connect_host port target
  local -n out_ref="$1"

  host="$(beagle_stream_client_host)"
  connect_host="$(beagle_stream_client_connect_host)"
  port="$(beagle_stream_client_port)"
  app="$(beagle_stream_client_app)"
  resolution="$(beagle_stream_client_resolution)"
  fps="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS:-60}"
  bitrate="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BITRATE:-20000}"
  codec="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VIDEO_CODEC:-H.264}"
  decoder="$(beagle_stream_client_video_decoder)"
  audio_config="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUDIO_CONFIG:-stereo}"

  if beagle_stream_hostless_enabled; then
    if [[ -n "${connect_host:-$host}" ]]; then
      target="$(format_beagle_stream_client_target "${connect_host:-$host}" "$port")"
      out_ref=("$(beagle_stream_client_bin)" stream "$target" "$app")
    else
      out_ref=("$(beagle_stream_client_bin)" stream "$app")
    fi
  else
    target="$(format_beagle_stream_client_target "${connect_host:-$host}" "$port")"
    out_ref=("$(beagle_stream_client_bin)" stream "$target" "$app")
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

  out_ref+=(--display-mode fullscreen --frame-pacing --keep-awake --capture-system-keys always --no-hdr --no-yuv444)

  if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_ABSOLUTE_MOUSE:-1}" == "1" ]]; then
    out_ref+=(--absolute-mouse)
  fi
  if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_QUIT_AFTER:-0}" == "1" ]]; then
    out_ref+=(--quit-after)
  fi
}
