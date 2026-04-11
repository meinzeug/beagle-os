#!/usr/bin/env bash

moonlight_bin() {
  printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_BIN:-moonlight}"
}

moonlight_app() {
  render_template "${PVE_THIN_CLIENT_MOONLIGHT_APP:-Desktop}"
}

moonlight_audio_driver() {
  local runtime_dir pulse_socket

  if [[ -n "${PVE_THIN_CLIENT_MOONLIGHT_AUDIO_DRIVER:-}" ]]; then
    printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_AUDIO_DRIVER}"
    return 0
  fi

  runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  pulse_socket="${runtime_dir}/pulse/native"
  if [[ -S "$pulse_socket" ]]; then
    printf '%s\n' "pulseaudio"
    return 0
  fi

  printf '%s\n' "alsa"
}

moonlight_video_decoder() {
  local configured
  configured="${PVE_THIN_CLIENT_MOONLIGHT_VIDEO_DECODER:-auto}"

  if [[ "$configured" == "auto" ]] && [[ ! -e /dev/dri/renderD128 ]] && [[ ! -e /dev/dri/card0 ]]; then
    printf 'software\n'
    return 0
  fi

  if [[ "$configured" == "auto" ]] && [[ -e /dev/dri/renderD128 ]] && [[ ! -r /dev/dri/renderD128 || ! -w /dev/dri/renderD128 ]]; then
    printf 'software\n'
    return 0
  fi

  if [[ "$configured" == "auto" ]] && [[ ! -e /dev/dri/renderD128 ]] && [[ -e /dev/dri/card0 ]] && [[ ! -r /dev/dri/card0 || ! -w /dev/dri/card0 ]]; then
    printf 'software\n'
    return 0
  fi

  printf '%s\n' "$configured"
}

record_decoder_choice() {
  local decoder="$1"
  beagle_log_event "moonlight.decoder" "decoder=${decoder} codec=${PVE_THIN_CLIENT_MOONLIGHT_VIDEO_CODEC:-auto}"
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

moonlight_resolution() {
  local configured detected
  configured="${PVE_THIN_CLIENT_MOONLIGHT_RESOLUTION:-auto}"

  if [[ "${PVE_THIN_CLIENT_MOONLIGHT_AUTO_RESOLUTION:-1}" == "1" ]]; then
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

build_stream_args() {
  local resolution fps bitrate codec decoder audio_config app host connect_host port target
  local -n out_ref="$1"

  host="$(moonlight_host)"
  connect_host="$(moonlight_connect_host)"
  port="$(moonlight_port)"
  target="$(format_moonlight_target "${connect_host:-$host}" "$port")"
  app="$(moonlight_app)"
  resolution="$(moonlight_resolution)"
  fps="${PVE_THIN_CLIENT_MOONLIGHT_FPS:-60}"
  bitrate="${PVE_THIN_CLIENT_MOONLIGHT_BITRATE:-20000}"
  codec="${PVE_THIN_CLIENT_MOONLIGHT_VIDEO_CODEC:-H.264}"
  decoder="$(moonlight_video_decoder)"
  audio_config="${PVE_THIN_CLIENT_MOONLIGHT_AUDIO_CONFIG:-stereo}"

  out_ref=("$(moonlight_bin)" stream "$target" "$app")

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

configure_graphics_runtime() {
  export DISPLAY="${DISPLAY:-:0}"
  export HOME="${HOME:-/home/${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}}"
  export XAUTHORITY="$(select_xauthority)"
  export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
  export XDG_SESSION_TYPE="${XDG_SESSION_TYPE:-x11}"
  export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-x11}"
  unset WAYLAND_DISPLAY
  wait_for_x_display "moonlight.display-ready" "moonlight.display-unready"

  if [[ "$(moonlight_video_decoder)" == "software" ]]; then
    export QT_QUICK_BACKEND="${QT_QUICK_BACKEND:-software}"
    export LIBVA_DRIVER_NAME="${LIBVA_DRIVER_NAME:-none}"
    export VDPAU_DRIVER="${VDPAU_DRIVER:-noop}"
  fi
}

configure_audio_runtime() {
  local runtime_dir pulse_socket

  export HOME="${HOME:-/home/${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}}"
  runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
  export XDG_RUNTIME_DIR="$runtime_dir"
  mkdir -p "$runtime_dir" >/dev/null 2>&1 || true

  pulse_socket="${runtime_dir}/pulse/native"
  if [[ -S "$pulse_socket" ]]; then
    export PULSE_SERVER="${PULSE_SERVER:-unix:${pulse_socket}}"
  fi
}
