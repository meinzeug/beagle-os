#!/usr/bin/env bash

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
