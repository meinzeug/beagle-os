#!/usr/bin/env bash

log_gfn_launch_target() {
  local target="${1:-}"
  [[ -n "$target" ]] || return 0
  case "$target" in
    geforcenow:*|com.nvidia.geforcenow:*|nvidia-gfn:*|http://localhost:2259*)
      beagle_log_event "gfn.callback" "target=${target%%\?*}"
      ;;
  esac
}

is_gfn_callback_target() {
  local target="${1:-}"
  case "$target" in
    geforcenow:*|com.nvidia.geforcenow:*|nvidia-gfn:*|http://localhost:2259*)
      return 0
      ;;
  esac
  return 1
}

stop_gfn_kiosk_after_delay() {
  local delay_seconds="${1:-0}"

  if [[ "$delay_seconds" =~ ^[0-9]+$ ]] && (( delay_seconds > 0 )); then
    sleep "$delay_seconds"
  fi

  beagle_stop_kiosk_for_stream || true
}

start_gfn_stream_optimization() {
  local target="${1:-}"

  [[ "${GFN_STREAM_OPTIMIZE:-1}" == "1" ]] || return 0
  is_gfn_callback_target "$target" && return 0

  beagle_suspend_management_activity || true
  stop_gfn_kiosk_after_delay "${GFN_STREAM_PAUSE_DELAY_SECONDS:-12}" >/dev/null 2>&1 &
  STREAM_KIOSK_STOP_PID="$!"
  STREAM_OPTIMIZATION_ACTIVE="1"
  beagle_log_event "gfn.stream-optimization" "mode=active kiosk-stop-delay=${GFN_STREAM_PAUSE_DELAY_SECONDS:-12}"
}

stop_gfn_stream_optimization() {
  [[ "${STREAM_OPTIMIZATION_ACTIVE:-0}" == "1" ]] || return 0

  if [[ -n "${STREAM_KIOSK_STOP_PID:-}" ]]; then
    kill "$STREAM_KIOSK_STOP_PID" >/dev/null 2>&1 || true
    wait "$STREAM_KIOSK_STOP_PID" 2>/dev/null || true
    STREAM_KIOSK_STOP_PID=""
  fi

  beagle_resume_management_activity || true
  STREAM_OPTIMIZATION_ACTIVE="0"
  beagle_log_event "gfn.stream-optimization" "mode=inactive"
}
