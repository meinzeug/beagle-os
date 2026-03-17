#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_runtime_config

have_binary() {
  command -v "$1" >/dev/null 2>&1
}

moonlight_bin() {
  printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_BIN:-moonlight}"
}

moonlight_host() {
  render_template "${PVE_THIN_CLIENT_MOONLIGHT_HOST:-}"
}

moonlight_app() {
  render_template "${PVE_THIN_CLIENT_MOONLIGHT_APP:-Desktop}"
}

sunshine_api_url() {
  local configured host
  configured="$(render_template "${PVE_THIN_CLIENT_SUNSHINE_API_URL:-}" 2>/dev/null || true)"
  if [[ -n "$configured" ]]; then
    printf '%s\n' "$configured"
    return 0
  fi

  host="$(moonlight_host)"
  if [[ -n "$host" ]]; then
    printf 'https://%s:47990\n' "$host"
  fi
}

json_bool() {
  local payload="$1"
  python3 - "$payload" <<'PY'
import json
import sys

try:
    data = json.loads(sys.argv[1] or "{}")
except json.JSONDecodeError:
    raise SystemExit(1)

print("1" if bool(data.get("status")) else "0")
PY
}

moonlight_list() {
  local bin host
  bin="$(moonlight_bin)"
  host="$(moonlight_host)"
  "$bin" list "$host" >/tmp/pve-thin-client-moonlight-list.log 2>&1
}

submit_sunshine_pin() {
  local api_url username password pin name response

  api_url="$(sunshine_api_url)"
  username="${PVE_THIN_CLIENT_SUNSHINE_USERNAME:-}"
  password="${PVE_THIN_CLIENT_SUNSHINE_PASSWORD:-}"
  pin="${PVE_THIN_CLIENT_SUNSHINE_PIN:-}"
  name="${PVE_THIN_CLIENT_MOONLIGHT_CLIENT_NAME:-${PVE_THIN_CLIENT_HOSTNAME:-$(hostname)}}"

  [[ -n "$api_url" && -n "$username" && -n "$password" && -n "$pin" ]] || return 1

  response="$(
    curl -kfsS \
      --user "${username}:${password}" \
      -H 'Content-Type: application/json' \
      --data "{\"pin\":\"${pin}\",\"name\":\"${name}\"}" \
      "${api_url%/}/api/pin"
  )" || return 1

  [[ "$(json_bool "$response")" == "1" ]]
}

ensure_paired() {
  local bin host pin pair_pid paired_ok attempt pair_status

  bin="$(moonlight_bin)"
  host="$(moonlight_host)"
  pin="${PVE_THIN_CLIENT_SUNSHINE_PIN:-}"

  moonlight_list && return 0

  [[ -n "$pin" ]] || return 1

  "$bin" pair "$host" --pin "$pin" >/tmp/pve-thin-client-moonlight-pair.log 2>&1 &
  pair_pid=$!
  paired_ok="0"

  for attempt in $(seq 1 20); do
    sleep 1
    if submit_sunshine_pin; then
      paired_ok="1"
      break
    fi
  done

  pair_status=0
  wait "$pair_pid" || pair_status=$?

  [[ "$pair_status" == "0" ]] || return "$pair_status"
  [[ "$paired_ok" == "1" ]] || return 1
  moonlight_list
}

build_stream_args() {
  local resolution fps bitrate codec decoder audio_config app host
  local -n out_ref="$1"

  host="$(moonlight_host)"
  app="$(moonlight_app)"
  resolution="${PVE_THIN_CLIENT_MOONLIGHT_RESOLUTION:-1080}"
  fps="${PVE_THIN_CLIENT_MOONLIGHT_FPS:-60}"
  bitrate="${PVE_THIN_CLIENT_MOONLIGHT_BITRATE:-20000}"
  codec="${PVE_THIN_CLIENT_MOONLIGHT_VIDEO_CODEC:-H.264}"
  decoder="${PVE_THIN_CLIENT_MOONLIGHT_VIDEO_DECODER:-auto}"
  audio_config="${PVE_THIN_CLIENT_MOONLIGHT_AUDIO_CONFIG:-stereo}"

  out_ref=("$(moonlight_bin)" stream "$host" "$app")

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

main() {
  local bin host app
  local -a args=()

  bin="$(moonlight_bin)"
  host="$(moonlight_host)"
  app="$(moonlight_app)"

  [[ -n "$host" ]] || {
    echo "Missing Moonlight host." >&2
    exit 1
  }

  have_binary "$bin" || {
    echo "Moonlight binary not found: $bin" >&2
    exit 1
  }

  if ! moonlight_list; then
    ensure_paired || {
      echo "Moonlight pairing failed for host '$host'." >&2
      exit 1
    }
  fi

  build_stream_args args
  echo "Starting Moonlight stream: host=$host app=$app resolution=${PVE_THIN_CLIENT_MOONLIGHT_RESOLUTION:-1080} fps=${PVE_THIN_CLIENT_MOONLIGHT_FPS:-60}" >&2
  exec "${args[@]}"
}

main "$@"
