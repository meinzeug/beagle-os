#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOONLIGHT_TARGETING_SH="${MOONLIGHT_TARGETING_SH:-$SCRIPT_DIR/moonlight_targeting.sh}"
MOONLIGHT_PAIRING_SH="${MOONLIGHT_PAIRING_SH:-$SCRIPT_DIR/moonlight_pairing.sh}"
MOONLIGHT_RUNTIME_EXEC_SH="${MOONLIGHT_RUNTIME_EXEC_SH:-$SCRIPT_DIR/moonlight_runtime_exec.sh}"
MOONLIGHT_CLI_SH="${MOONLIGHT_CLI_SH:-$SCRIPT_DIR/moonlight_cli.sh}"
MOONLIGHT_HOST_SYNC_SH="${MOONLIGHT_HOST_SYNC_SH:-$SCRIPT_DIR/moonlight_host_sync.sh}"
MOONLIGHT_REMOTE_API_SH="${MOONLIGHT_REMOTE_API_SH:-$SCRIPT_DIR/moonlight_remote_api.sh}"
MOONLIGHT_MANAGER_REGISTRATION_SH="${MOONLIGHT_MANAGER_REGISTRATION_SH:-$SCRIPT_DIR/moonlight_manager_registration.sh}"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
# shellcheck disable=SC1090
source "$MOONLIGHT_TARGETING_SH"
# shellcheck disable=SC1090
source "$MOONLIGHT_CLI_SH"
# shellcheck disable=SC1090
source "$MOONLIGHT_HOST_SYNC_SH"
# shellcheck disable=SC1090
source "$MOONLIGHT_REMOTE_API_SH"
# shellcheck disable=SC1090
source "$MOONLIGHT_MANAGER_REGISTRATION_SH"
# shellcheck disable=SC1090
source "$MOONLIGHT_PAIRING_SH"
# shellcheck disable=SC1090
source "$MOONLIGHT_RUNTIME_EXEC_SH"

load_runtime_config
beagle_log_event "moonlight.start" "profile=${PVE_THIN_CLIENT_PROFILE_NAME:-default} host=${PVE_THIN_CLIENT_MOONLIGHT_HOST:-UNSET} app=${PVE_THIN_CLIENT_MOONLIGHT_APP:-Desktop}"

MOONLIGHT_LOG_DIR="${PVE_THIN_CLIENT_LOG_DIR:-${XDG_RUNTIME_DIR:-/tmp}/pve-thin-client}"
MOONLIGHT_LIST_LOG="$MOONLIGHT_LOG_DIR/moonlight-list.log"
MOONLIGHT_PAIR_LOG="$MOONLIGHT_LOG_DIR/moonlight-pair.log"
MOONLIGHT_STREAM_LOG="$MOONLIGHT_LOG_DIR/moonlight-stream.log"

mkdir -p "$MOONLIGHT_LOG_DIR" 2>/dev/null || true

have_binary() {
  command -v "$1" >/dev/null 2>&1
}

main() {
  local bin host connect_host app resolved_app audio_driver port
  local -a args=()

  bin="$(moonlight_bin)"
  host="$(moonlight_host)"
  connect_host="$(moonlight_connect_host)"
  port="$(moonlight_port)"
  app="$(moonlight_app)"

  [[ -n "$host" ]] || {
    echo "Missing Moonlight host." >&2
    exit 1
  }

  have_binary "$bin" || {
    echo "Moonlight binary not found: $bin" >&2
    exit 1
  }

  if command -v /usr/local/bin/pve-thin-client-audio-init >/dev/null 2>&1; then
    /usr/local/bin/pve-thin-client-audio-init >/dev/null 2>&1 || true
    pkill -f '^bash /usr/local/bin/pve-thin-client-audio-init --watch' >/dev/null 2>&1 || true
    /usr/local/bin/pve-thin-client-audio-init --watch "${PVE_THIN_CLIENT_AUDIO_WATCH_LOOPS:-0}" >/dev/null 2>&1 &
  fi

  configure_audio_runtime
  audio_driver="$(moonlight_audio_driver)"
  if [[ -n "$audio_driver" && "$audio_driver" != "auto" ]]; then
    export SDL_AUDIODRIVER="$audio_driver"
  fi

  configure_graphics_runtime
  record_decoder_choice "$(moonlight_video_decoder)"

  wait_for_stream_target || {
    beagle_log_event "moonlight.unreachable" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
    echo "Moonlight host '$host' is unreachable from this network." >&2
    exit 1
  }

  if command -v /usr/local/bin/pve-thin-client-display-init >/dev/null 2>&1; then
    /usr/local/bin/pve-thin-client-display-init >/dev/null 2>&1 || true
  fi

  if ensure_moonlight_local_host_route; then
    beagle_log_event "moonlight.local-route" "local_host=$(moonlight_local_host) via=${connect_host:-$host}"
  fi

  bootstrap_moonlight_client || true
  if ! moonlight_host_configured; then
    if seed_moonlight_host_from_runtime_config; then
      beagle_log_event "moonlight.seeded-config" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
    elif retarget_moonlight_host_from_runtime_config; then
      beagle_log_event "moonlight.retargeted-config" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
    fi
  fi

  if moonlight_host_configured; then
    beagle_log_event "moonlight.cached-config" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
  fi

  if moonlight_list; then
    beagle_log_event "moonlight.ready" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
  else
    ensure_paired || {
      beagle_log_event "moonlight.pairing-failed" "host=${host} port=${port:-default} pin=${PVE_THIN_CLIENT_SUNSHINE_PIN:-unset}"
      echo "Moonlight pairing failed for host '$host'." >&2
      exit 1
    }
  fi

  resolved_app="$(resolve_stream_app_name "$app" 2>/dev/null || printf '%s' "$app")"
  if [[ -n "$resolved_app" && "$resolved_app" != "$app" ]]; then
    beagle_log_event "moonlight.app-fallback" "requested=${app} resolved=${resolved_app}"
    PVE_THIN_CLIENT_MOONLIGHT_APP="$resolved_app"
    app="$resolved_app"
  fi

  build_stream_args args
  if [[ -n "$connect_host" && "$connect_host" != "$host" ]]; then
    echo "Starting Moonlight stream: host=$host resolved_ipv4=$connect_host port=${port:-default} app=$app resolution=$(moonlight_resolution) fps=${PVE_THIN_CLIENT_MOONLIGHT_FPS:-60}" >&2
  else
    echo "Starting Moonlight stream: host=$host port=${port:-default} app=$app resolution=$(moonlight_resolution) fps=${PVE_THIN_CLIENT_MOONLIGHT_FPS:-60}" >&2
  fi
  beagle_log_event "moonlight.exec" "host=${host} connect_host=${connect_host:-$host} port=${port:-default} app=${app} resolution=$(moonlight_resolution) fps=${PVE_THIN_CLIENT_MOONLIGHT_FPS:-60}"
  {
    printf '=== %s ===\n' "$(date -Iseconds)"
    printf 'command: '
    printf '%q ' "${args[@]}"
    printf '\n'
  } >>"$MOONLIGHT_STREAM_LOG"

  "${args[@]}" >>"$MOONLIGHT_STREAM_LOG" 2>&1
  local stream_exit=$?
  beagle_log_event "moonlight.exit" "code=${stream_exit} host=${host} connect_host=${connect_host:-$host} port=${port:-default} app=${app}"
  if [[ "$stream_exit" -ne 0 ]]; then
    beagle_log_event "moonlight.error" "code=${stream_exit} log=${MOONLIGHT_STREAM_LOG}"
  fi
  return "$stream_exit"
}

main "$@"
