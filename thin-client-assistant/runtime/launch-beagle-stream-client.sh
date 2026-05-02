#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEAGLE_STREAM_CLIENT_TARGETING_SH="${BEAGLE_STREAM_CLIENT_TARGETING_SH:-$SCRIPT_DIR/beagle_stream_client_targeting.sh}"
BEAGLE_STREAM_CLIENT_PAIRING_SH="${BEAGLE_STREAM_CLIENT_PAIRING_SH:-$SCRIPT_DIR/beagle_stream_client_pairing.sh}"
BEAGLE_STREAM_CLIENT_RUNTIME_EXEC_SH="${BEAGLE_STREAM_CLIENT_RUNTIME_EXEC_SH:-$SCRIPT_DIR/beagle_stream_client_runtime_exec.sh}"
BEAGLE_STREAM_CLIENT_CLI_SH="${BEAGLE_STREAM_CLIENT_CLI_SH:-$SCRIPT_DIR/beagle_stream_client_cli.sh}"
BEAGLE_STREAM_CLIENT_HOST_SYNC_SH="${BEAGLE_STREAM_CLIENT_HOST_SYNC_SH:-$SCRIPT_DIR/beagle_stream_client_host_sync.sh}"
BEAGLE_STREAM_CLIENT_REMOTE_API_SH="${BEAGLE_STREAM_CLIENT_REMOTE_API_SH:-$SCRIPT_DIR/beagle_stream_client_remote_api.sh}"
BEAGLE_STREAM_CLIENT_MANAGER_REGISTRATION_SH="${BEAGLE_STREAM_CLIENT_MANAGER_REGISTRATION_SH:-$SCRIPT_DIR/beagle_stream_client_manager_registration.sh}"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_TARGETING_SH"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_CLI_SH"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_HOST_SYNC_SH"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_REMOTE_API_SH"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_MANAGER_REGISTRATION_SH"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_PAIRING_SH"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_RUNTIME_EXEC_SH"

load_runtime_config
beagle_log_event "beagle-stream-client.start" "profile=${PVE_THIN_CLIENT_PROFILE_NAME:-default} host=${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST:-UNSET} app=${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_APP:-Desktop}"

BEAGLE_STREAM_CLIENT_LOG_DIR="${PVE_THIN_CLIENT_LOG_DIR:-${XDG_RUNTIME_DIR:-/tmp}/pve-thin-client}"
BEAGLE_STREAM_CLIENT_LIST_LOG="$BEAGLE_STREAM_CLIENT_LOG_DIR/beagle-stream-client-list.log"
BEAGLE_STREAM_CLIENT_PAIR_LOG="$BEAGLE_STREAM_CLIENT_LOG_DIR/beagle-stream-client-pair.log"
BEAGLE_STREAM_CLIENT_STREAM_LOG="$BEAGLE_STREAM_CLIENT_LOG_DIR/beagle-stream-client-stream.log"

mkdir -p "$BEAGLE_STREAM_CLIENT_LOG_DIR" 2>/dev/null || true

have_binary() {
  command -v "$1" >/dev/null 2>&1
}

main() {
  local bin host connect_host app resolved_app audio_driver port
  local hostless_beagle_stream=0
  local session_response_file=""
  local -a args=()

  bin="$(beagle_stream_client_bin)"
  host="$(beagle_stream_client_host)"
  connect_host="$(beagle_stream_client_connect_host)"
  port="$(beagle_stream_client_port)"
  app="$(beagle_stream_client_app)"

  if beagle_stream_hostless_enabled; then
    hostless_beagle_stream=1
  fi

  [[ -n "$host" || "$hostless_beagle_stream" == "1" ]] || {
    echo "Missing Beagle Stream Client host." >&2
    exit 1
  }

  have_binary "$bin" || {
    echo "Beagle Stream Client binary not found: $bin" >&2
    exit 1
  }

  if command -v /usr/local/bin/pve-thin-client-audio-init >/dev/null 2>&1; then
    /usr/local/bin/pve-thin-client-audio-init >/dev/null 2>&1 || true
    pkill -f '^bash /usr/local/bin/pve-thin-client-audio-init --watch' >/dev/null 2>&1 || true
    /usr/local/bin/pve-thin-client-audio-init --watch "${PVE_THIN_CLIENT_AUDIO_WATCH_LOOPS:-0}" >/dev/null 2>&1 &
  fi

  configure_audio_runtime
  audio_driver="$(beagle_stream_client_audio_driver)"
  if [[ -n "$audio_driver" && "$audio_driver" != "auto" ]]; then
    export SDL_AUDIODRIVER="$audio_driver"
  fi

  configure_graphics_runtime
  record_decoder_choice "$(beagle_stream_client_video_decoder)"

  if [[ "$hostless_beagle_stream" != "1" ]]; then
    session_response_file="$(mktemp)"
    if fetch_beagle_stream_client_current_session_via_manager "$session_response_file"; then
      if retarget_beagle_stream_client_host_from_session_broker_response "$session_response_file"; then
        host="$(beagle_stream_client_host)"
        connect_host="$(beagle_stream_client_connect_host)"
        port="$(beagle_stream_client_port)"
        beagle_log_event "beagle-stream-client.session-broker" "host=${host} connect_host=${connect_host:-$host} port=${port:-default} current_node=${PVE_THIN_CLIENT_SESSION_CURRENT_NODE:-unknown}"
      fi
    fi
    rm -f "$session_response_file"
  fi

  if [[ "$hostless_beagle_stream" != "1" ]]; then
    wait_for_stream_target || {
      beagle_log_event "beagle-stream-client.unreachable" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
      echo "Beagle Stream Client host '$host' is unreachable from this network." >&2
      exit 1
    }
  fi

  if command -v /usr/local/bin/pve-thin-client-display-init >/dev/null 2>&1; then
    /usr/local/bin/pve-thin-client-display-init >/dev/null 2>&1 || true
  fi

  if [[ "$hostless_beagle_stream" != "1" ]]; then
    if ensure_beagle_stream_client_local_host_route; then
      beagle_log_event "beagle-stream-client.local-route" "local_host=$(beagle_stream_client_local_host) via=${connect_host:-$host}"
    fi

    bootstrap_beagle_stream_client || true
    if ! beagle_stream_client_host_configured; then
      if seed_beagle_stream_client_host_from_runtime_config; then
        beagle_log_event "beagle-stream-client.seeded-config" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
      elif retarget_beagle_stream_client_host_from_runtime_config; then
        beagle_log_event "beagle-stream-client.retargeted-config" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
      fi
    fi

    if beagle_stream_client_host_configured; then
      beagle_log_event "beagle-stream-client.cached-config" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
    fi

    if beagle_stream_client_list; then
      beagle_log_event "beagle-stream-client.ready" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
    else
      ensure_paired || {
        beagle_log_event "beagle-stream-client.pairing-failed" "host=${host} port=${port:-default} pin=${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PIN:-unset}"
        echo "Beagle Stream Client pairing failed for host '$host'." >&2
        exit 1
      }
    fi
  else
    beagle_log_event "beagle-stream-client.beagle-stream-hostless" "app=${app} enrollment=$(beagle_stream_enrollment_config)"
  fi

  if [[ "$hostless_beagle_stream" != "1" ]]; then
    resolved_app="$(resolve_stream_app_name "$app" 2>/dev/null || printf '%s' "$app")"
    if [[ -n "$resolved_app" && "$resolved_app" != "$app" ]]; then
      beagle_log_event "beagle-stream-client.app-fallback" "requested=${app} resolved=${resolved_app}"
      PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_APP="$resolved_app"
      app="$resolved_app"
    fi
  fi

  local requested_resolution
  requested_resolution="$(beagle_stream_client_resolution)"
  if [[ "$hostless_beagle_stream" != "1" ]]; then
    if prepare_beagle_stream_client_stream_via_manager "$requested_resolution" "$app"; then
      beagle_log_event "beagle-stream-client.prepare-stream.ok" "resolution=${requested_resolution} app=${app}"
    else
      beagle_log_event "beagle-stream-client.prepare-stream.skip" "resolution=${requested_resolution} app=${app}"
    fi
  fi

  build_stream_args args
  if [[ "$hostless_beagle_stream" == "1" ]]; then
    echo "Starting BeagleStream brokered stream: app=$app resolution=$(beagle_stream_client_resolution) fps=${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS:-60}" >&2
  elif [[ -n "$connect_host" && "$connect_host" != "$host" ]]; then
    echo "Starting Beagle Stream Client stream: host=$host resolved_ipv4=$connect_host port=${port:-default} app=$app resolution=$(beagle_stream_client_resolution) fps=${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS:-60}" >&2
  else
    echo "Starting Beagle Stream Client stream: host=$host port=${port:-default} app=$app resolution=$(beagle_stream_client_resolution) fps=${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS:-60}" >&2
  fi
  if [[ "$hostless_beagle_stream" == "1" ]]; then
    beagle_log_event "beagle-stream-client.exec" "mode=beagle-stream-hostless app=${app} resolution=$(beagle_stream_client_resolution) fps=${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS:-60}"
  else
    beagle_log_event "beagle-stream-client.exec" "host=${host} connect_host=${connect_host:-$host} port=${port:-default} app=${app} resolution=$(beagle_stream_client_resolution) fps=${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS:-60}"
  fi
  {
    printf '=== %s ===\n' "$(date -Iseconds)"
    printf 'command: '
    printf '%q ' "${args[@]}"
    printf '\n'
  } >>"$BEAGLE_STREAM_CLIENT_STREAM_LOG"

  "${args[@]}" >>"$BEAGLE_STREAM_CLIENT_STREAM_LOG" 2>&1
  local stream_exit=$?
  if [[ "$hostless_beagle_stream" == "1" ]]; then
    beagle_log_event "beagle-stream-client.exit" "code=${stream_exit} mode=beagle-stream-hostless app=${app}"
  else
    beagle_log_event "beagle-stream-client.exit" "code=${stream_exit} host=${host} connect_host=${connect_host:-$host} port=${port:-default} app=${app}"
  fi
  if [[ "$stream_exit" -ne 0 ]]; then
    beagle_log_event "beagle-stream-client.error" "code=${stream_exit} log=${BEAGLE_STREAM_CLIENT_STREAM_LOG}"
  fi
  return "$stream_exit"
}

main "$@"
