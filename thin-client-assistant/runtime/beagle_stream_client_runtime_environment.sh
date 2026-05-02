#!/usr/bin/env bash

beagle_stream_client_audio_driver() {
  local runtime_dir pulse_socket

  if [[ -n "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUDIO_DRIVER:-}" ]]; then
    printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUDIO_DRIVER}"
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

configure_graphics_runtime() {
  export DISPLAY="${DISPLAY:-:0}"
  export HOME="${HOME:-/home/${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}}"
  export XAUTHORITY="$(select_xauthority)"
  export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
  export XDG_SESSION_TYPE="${XDG_SESSION_TYPE:-x11}"
  export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-x11}"
  unset WAYLAND_DISPLAY
  wait_for_x_display "beagle-stream-client.display-ready" "beagle-stream-client.display-unready"

  if [[ "$(beagle_stream_client_video_decoder)" == "software" ]]; then
    export QT_QUICK_BACKEND="${QT_QUICK_BACKEND:-software}"
    # Do NOT set LIBVA_DRIVER_NAME=none or VDPAU_DRIVER=noop — those values
    # cause dlopen failures for non-existent .so files (none_drv_video.so,
    # libvdpau_noop.so), which crash the FFmpeg software fallback chain.
    # With --video-decoder software, Beagle Stream Client handles hw-decoder skipping itself.
    unset LIBVA_DRIVER_NAME VDPAU_DRIVER 2>/dev/null || true
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
