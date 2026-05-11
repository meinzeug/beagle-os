#!/usr/bin/env bash
set -euo pipefail

BEAGLE_STREAM_CLIENT_LOCK_FILE="${XDG_RUNTIME_DIR:-/tmp}/beagle-stream-client-launch.lock"
exec 9>"$BEAGLE_STREAM_CLIENT_LOCK_FILE"
flock -n 9 || exit 0

SCRIPT_DIR="${RUNTIME_SCRIPT_DIR:-/usr/local/lib/pve-thin-client/runtime}"
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

wireguard_peer_restore_state_file() {
  printf '%s\n' "${BEAGLE_WG_PEER_RESTORE_STATE_FILE:-/run/beagle/wg-beagle-peer.env}"
}

wireguard_peer_state_value() {
  local key state_file
  key="$1"
  state_file="$2"
  awk -F= -v key="$key" '$1 == key {print substr($0, index($0, "=") + 1); exit}' "$state_file"
}

wireguard_conf_value() {
  local key conf_file
  key="$1"
  conf_file="$2"
  sudo awk -v key="$key" '
    /^\[Peer\]/{p=1; next}
    /^\[/{p=0}
    p && index($0, "=") {
      lhs=substr($0, 1, index($0, "=") - 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", lhs)
      if (lhs == key) {
        value=substr($0, index($0, "=") + 1)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
        print value
        exit
      }
    }
  ' "$conf_file"
}

# After a forced restart (ENet/control-channel disconnect), poll the Sunshine HTTP
# endpoint until it accepts connections or the timeout expires. This prevents
# "Connection refused (Error 1)" on restart attempt 2 caused by Sunshine briefly
# being unavailable while cleaning up the previous session or restarting.
wait_for_stream_server_ready() {
  local host port target max_wait elapsed
  host="${1:-}"
  port="${2:-}"
  max_wait="${3:-15}"
  if [[ -z "$host" ]]; then
    host="$(beagle_stream_client_connect_host 2>/dev/null || true)"
  fi
  if [[ -z "$port" ]]; then
    port="$(beagle_stream_client_port 2>/dev/null || true)"
  fi
  [[ -n "$host" && -n "$port" ]] || return 0
  target="http://${host}:${port}/serverinfo"
  elapsed=0
  while [[ "$elapsed" -lt "$max_wait" ]]; do
    if curl -fsS --connect-timeout 2 --max-time 3 "$target" >/dev/null 2>&1; then
      beagle_log_event "beagle-stream-client.server-ready" "host=${host} port=${port} wait=${elapsed}s"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  beagle_log_event "beagle-stream-client.server-ready-timeout" "host=${host} port=${port} wait=${elapsed}s"
  return 1
}

# Workaround: beagle-stream skips activatePeer() when wg-beagle interface exists,
# even if the peer was removed by a previous deactivatePeer() call.
# Ensure the peer is always configured before launching beagle-stream.
ensure_wg_interface() {
  local iface="wg-beagle"
  local wg_conf="/etc/wireguard/wg-beagle.conf"
  local allowed_ips endpoint endpoint_host
  local default_route default_gw default_dev route_count route

  sudo test -f "$wg_conf" 2>/dev/null || return 0
  if ip link show "$iface" &>/dev/null; then
    sudo ip link set up dev "$iface" >/dev/null 2>&1 || true
  else
    beagle_log_event "beagle-stream-client.wg-interface-up" "iface=${iface} conf=${wg_conf}"
    sudo systemctl start "wg-quick@${iface}.service" >/dev/null 2>&1 || \
      sudo wg-quick up "$iface" >/dev/null 2>&1 || true

    # Fallback for minimal live images where wg-quick fails due missing resolvconf.
    # Recreate enough of wg-quick behavior for this runtime path: interface,
    # address/mtu, endpoint exception route, and AllowedIPs routes.
    if ! ip link show "$iface" &>/dev/null; then
      local tmp_conf addr mtu
      tmp_conf="$(mktemp)"
      if sudo awk '
        BEGIN{in_iface=0;in_peer=0}
        /^\[Interface\]/{in_iface=1;in_peer=0;print;next}
        /^\[Peer\]/{in_peer=1;in_iface=0;print;next}
        /^\[/{in_iface=0;in_peer=0;print;next}
        {
          if (in_iface==1) {
            if ($0 ~ /^[[:space:]]*(Address|DNS|MTU|Table|PreUp|PostUp|PreDown|PostDown|SaveConfig)[[:space:]]*=/) next
            print; next
          }
          print
        }
      ' "$wg_conf" >"$tmp_conf" 2>/dev/null; then
        sudo ip link delete "$iface" >/dev/null 2>&1 || true
        if sudo ip link add "$iface" type wireguard >/dev/null 2>&1 && \
           sudo wg setconf "$iface" "$tmp_conf" >/dev/null 2>&1; then
          addr="$(sudo awk -F= '/^[[:space:]]*Address[[:space:]]*=/{gsub(/[[:space:]]/, "", $2); split($2, a, ","); print a[1]; exit}' "$wg_conf" 2>/dev/null || true)"
          mtu="$(sudo awk -F= '/^[[:space:]]*MTU[[:space:]]*=/{gsub(/[[:space:]]/, "", $2); print $2; exit}' "$wg_conf" 2>/dev/null || true)"
          [[ -n "$addr" ]] && sudo ip address add "$addr" dev "$iface" >/dev/null 2>&1 || true
          [[ -n "$mtu" ]] || mtu="1420"
          sudo ip link set mtu "$mtu" up dev "$iface" >/dev/null 2>&1 || true
          beagle_log_event "beagle-stream-client.wg-interface-fallback" "iface=${iface} mtu=${mtu}"
        fi
      fi
      rm -f "$tmp_conf" >/dev/null 2>&1 || true
    fi
  fi

  allowed_ips="$(sudo awk -F= '/^[[:space:]]*AllowedIPs[[:space:]]*=/{gsub(/[[:space:]]/, "", $2); print $2; exit}' "$wg_conf" 2>/dev/null || true)"
  endpoint="$(sudo awk -F= '/^[[:space:]]*Endpoint[[:space:]]*=/{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit}' "$wg_conf" 2>/dev/null || true)"
  endpoint_host="${endpoint%%:*}"
  endpoint_host="${endpoint_host#[}"
  endpoint_host="${endpoint_host%]}"
  default_route="$(ip route show default 2>/dev/null | head -n1 || true)"
  default_gw="$(awk '/default/{for (i=1;i<=NF;i++) if ($i=="via") {print $(i+1); exit}}' <<<"$default_route")"
  default_dev="$(awk '/default/{for (i=1;i<=NF;i++) if ($i=="dev") {print $(i+1); exit}}' <<<"$default_route")"
  if [[ -n "$endpoint_host" && -n "$default_dev" ]]; then
    if [[ -n "$default_gw" ]]; then
      sudo ip route replace "$endpoint_host" via "$default_gw" dev "$default_dev" >/dev/null 2>&1 || true
    else
      sudo ip route replace "$endpoint_host" dev "$default_dev" >/dev/null 2>&1 || true
    fi
  fi

  route_count=0
  IFS=',' read -r -a routes <<<"$allowed_ips"
  for route in "${routes[@]}"; do
    [[ -n "$route" ]] || continue
    sudo ip route replace "$route" dev "$iface" >/dev/null 2>&1 || true
    route_count=$((route_count + 1))
  done
  beagle_log_event "beagle-stream-client.wg-routes-fallback" "iface=${iface} routes=${route_count} endpoint=${endpoint_host:-none}"

  if ! ip link show "$iface" &>/dev/null; then
    beagle_log_event "beagle-stream-client.wg-interface-missing" "iface=${iface}"
  fi
}

ensure_wg_peer() {
  local iface="wg-beagle"
  local wg_conf="/etc/wireguard/wg-beagle.conf"
  local peer_state
  peer_state="$(wireguard_peer_restore_state_file)"
  # The root-owned wg-quick config contains the private key. The root prepare
  # step publishes only public peer restore values for this sandboxed launcher.
  [[ -r "$peer_state" ]] || sudo test -f "$wg_conf" 2>/dev/null || return 0
  ensure_wg_interface
  ip link show "$iface" &>/dev/null || return 0
  # If no peers are configured, restore peer from the persisted conf file.
  # NOTE: wg addconf fails on wg-quick configs (Address/DNS fields are not
  # recognized by the low-level wg tool), so we parse and call wg set directly.
  if ! wg show "$iface" peers 2>/dev/null | grep -q .; then
    beagle_log_event "beagle-stream-client.wg-peer-restore" "iface=${iface} conf=${wg_conf}"
    local pubkey endpoint allowed_ips keepalive
    if [[ -r "$peer_state" ]]; then
      pubkey="$(wireguard_peer_state_value WG_PEER_PUBLIC_KEY "$peer_state")"
      endpoint="$(wireguard_peer_state_value WG_PEER_ENDPOINT "$peer_state")"
      allowed_ips="$(wireguard_peer_state_value WG_PEER_ALLOWED_IPS "$peer_state")"
      keepalive="$(wireguard_peer_state_value WG_PEER_KEEPALIVE "$peer_state")"
    else
      pubkey="$(wireguard_conf_value PublicKey "$wg_conf")"
      endpoint="$(wireguard_conf_value Endpoint "$wg_conf")"
      allowed_ips="$(wireguard_conf_value AllowedIPs "$wg_conf" | tr -d '[:space:]')"
      keepalive="$(wireguard_conf_value PersistentKeepalive "$wg_conf")"
    fi
    [[ -n "$pubkey" ]] || return 0
    local -a wg_args=("$iface" peer "$pubkey")
    [[ -n "$endpoint" ]]    && wg_args+=(endpoint "$endpoint")
    [[ -n "$allowed_ips" ]] && wg_args+=(allowed-ips "$allowed_ips")
    [[ -n "$keepalive" ]]   && wg_args+=(persistent-keepalive "$keepalive")
    wg set "${wg_args[@]}" 2>/dev/null || sudo wg set "${wg_args[@]}" 2>/dev/null || true
  fi
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

  ensure_wg_peer

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

  if [[ "$hostless_beagle_stream" == "1" && -z "${SDL_RENDER_DRIVER:-}" ]]; then
    export SDL_RENDER_DRIVER="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RENDER_DRIVER:-opengl}"
    beagle_log_event "beagle-stream-client.renderer" "driver=${SDL_RENDER_DRIVER} mode=hostless"
  fi

  if [[ "$hostless_beagle_stream" == "1" || "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISABLE_VULKAN:-1}" == "1" ]]; then
    if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISABLE_VULKAN:-1}" == "1" && -z "${SDL_RENDER_DRIVER:-}" ]]; then
      export SDL_RENDER_DRIVER="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RENDER_DRIVER:-opengl}"
      beagle_log_event "beagle-stream-client.renderer" "driver=${SDL_RENDER_DRIVER} mode=disable-vulkan"
    fi
    export PREFER_VULKAN="${PREFER_VULKAN:-0}"
    export VULKAN_IS_SLOW="${VULKAN_IS_SLOW:-1}"
    export PLVK_ALLOW_SOFTWARE="${PLVK_ALLOW_SOFTWARE:-0}"
  fi

  if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISABLE_VULKAN:-1}" == "1" ]]; then
    export VK_ICD_FILENAMES="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VK_ICD_FILENAMES:-/dev/null}"
    if [[ "$hostless_beagle_stream" == "1" ]]; then
      beagle_log_event "beagle-stream-client.vulkan" "disabled=1 icd=${VK_ICD_FILENAMES} mode=hostless"
    else
      beagle_log_event "beagle-stream-client.vulkan" "disabled=1 icd=${VK_ICD_FILENAMES} mode=direct"
    fi
  fi

  if [[ "$hostless_beagle_stream" != "1" ]]; then
    # In direct mode the endpoint is operator-controlled and must not be overwritten
    # by manager session broker responses that may prefer public routing.
    if beagle_stream_broker_connection; then
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
    else
      beagle_log_event "beagle-stream-client.session-broker" "mode=direct-skip host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
    fi
  elif beagle_stream_broker_connection; then
    session_response_file="$(mktemp)"
    if fetch_beagle_stream_client_current_session_via_manager "$session_response_file"; then
      if retarget_beagle_stream_client_host_from_session_broker_response "$session_response_file"; then
        host="$(beagle_stream_client_host)"
        connect_host="$(beagle_stream_client_connect_host)"
        port="$(beagle_stream_client_port)"
        beagle_log_event "beagle-stream-client.session-broker" "mode=hostless host=${host} connect_host=${connect_host:-$host} port=${port:-default} current_node=${PVE_THIN_CLIENT_SESSION_CURRENT_NODE:-unknown}"
      fi
    fi
    rm -f "$session_response_file"
    if [[ -z "${host:-}" ]]; then
      host="$(beagle_stream_client_local_host 2>/dev/null || true)"
      if [[ -n "$host" ]]; then
        export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BROKER_HOST="$host"
        connect_host="$(beagle_stream_client_connect_host)"
        port="$(beagle_stream_client_port)"
        beagle_log_event "beagle-stream-client.session-broker" "mode=hostless-fallback host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
      fi
    fi
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

    if register_beagle_stream_client_via_manager; then
      beagle_log_event "beagle-stream-client.register-refresh" "host=${host} port=${port:-default}"
    fi

    if beagle_stream_client_stream_ready; then
      beagle_log_event "beagle-stream-client.ready" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
    else
      ensure_paired || {
        beagle_log_event "beagle-stream-client.pairing-failed" "host=${host} port=${port:-default} auth=manager-token"
        echo "Beagle Stream Client pairing failed for host '$host'." >&2
        exit 1
      }
    fi
  else
    if [[ -n "${host:-}" ]]; then
      wait_for_stream_target || {
        beagle_log_event "beagle-stream-client.unreachable" "mode=hostless host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
        echo "Beagle Stream Client broker target '$host' is unreachable from this network." >&2
        exit 1
      }
      bootstrap_beagle_stream_client || true
      if register_beagle_stream_client_via_manager; then
        beagle_log_event "beagle-stream-client.register-refresh" "mode=hostless host=${host} port=${port:-default}"
      fi

      if beagle_stream_client_stream_ready; then
        beagle_log_event "beagle-stream-client.ready" "mode=hostless host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
      else
        ensure_paired || {
          beagle_log_event "beagle-stream-client.pairing-failed" "mode=hostless host=${host} port=${port:-default} auth=manager-token"
          echo "Beagle Stream Client pairing failed for broker target '$host'." >&2
          exit 1
        }
      fi
    fi
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
  elif [[ -n "${host:-}" ]]; then
    if prepare_beagle_stream_client_stream_via_manager "$requested_resolution" "$app"; then
      beagle_log_event "beagle-stream-client.prepare-stream.ok" "mode=hostless resolution=${requested_resolution} app=${app}"
    else
      beagle_log_event "beagle-stream-client.prepare-stream.skip" "mode=hostless resolution=${requested_resolution} app=${app}"
    fi
  fi

  build_stream_args args
  if [[ "$hostless_beagle_stream" == "1" ]]; then
    echo "Starting BeagleStream brokered stream: host=${host:-broker} connect_host=${connect_host:-${host:-broker}} port=${port:-default} app=$app resolution=$(beagle_stream_client_resolution) fps=$(beagle_stream_client_fps)" >&2
  elif [[ -n "$connect_host" && "$connect_host" != "$host" ]]; then
    echo "Starting Beagle Stream Client stream: host=$host resolved_ipv4=$connect_host port=${port:-default} app=$app resolution=$(beagle_stream_client_resolution) fps=$(beagle_stream_client_fps)" >&2
  else
    echo "Starting Beagle Stream Client stream: host=$host port=${port:-default} app=$app resolution=$(beagle_stream_client_resolution) fps=$(beagle_stream_client_fps)" >&2
  fi
  if [[ "$hostless_beagle_stream" == "1" ]]; then
    beagle_log_event "beagle-stream-client.exec" "mode=beagle-stream-hostless host=${host:-broker} connect_host=${connect_host:-${host:-broker}} port=${port:-default} app=${app} resolution=$(beagle_stream_client_resolution) fps=$(beagle_stream_client_fps)"
  else
    beagle_log_event "beagle-stream-client.exec" "host=${host} connect_host=${connect_host:-$host} port=${port:-default} app=${app} resolution=$(beagle_stream_client_resolution) fps=$(beagle_stream_client_fps)"
  fi
  {
    printf '=== %s ===\n' "$(date -Iseconds)"
    printf 'command: '
    printf '%q ' "${args[@]}"
    printf '\n'
  } >>"$BEAGLE_STREAM_CLIENT_STREAM_LOG"

  # GTK hint overlays can crash on minimal live images with broken icon caches.
  # Keep this disabled by default and allow explicit opt-in via env.
  if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_HINT_ENABLED:-0}" == "1" ]] && command -v /usr/local/bin/beagle-stream-hint >/dev/null 2>&1; then
    /usr/local/bin/beagle-stream-hint >/dev/null 2>&1 &
  fi

  local stream_exit=0 stream_attempt=1 max_attempts retry_delay stream_pid stream_start_line stream_forced_restart
  local app_lookup_port_fallback_used=0
  local connect_host_fallback_used=0
  max_attempts="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_MAX_RESTARTS:-3}"
  retry_delay="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RESTART_DELAY:-3}"
  # Background watchdog: restores wg peer if binary's deactivatePeer() removes it mid-session.
  wg_peer_watchdog() {
    while sleep 8; do
      ensure_wg_peer 2>/dev/null || true
    done
  }
  local wg_watchdog_pid=""
  wg_peer_watchdog &
  wg_watchdog_pid=$!
  while :; do
    build_stream_args args
    if [[ "$stream_attempt" -gt 1 ]]; then
      beagle_log_event "beagle-stream-client.restart" "attempt=${stream_attempt}/${max_attempts} app=${app}"
      printf '=== restart attempt %s/%s %s ===\n' "$stream_attempt" "$max_attempts" "$(date -Iseconds)" >>"$BEAGLE_STREAM_CLIENT_STREAM_LOG"
    fi
    # Restore wg peer before every attempt (binary's deactivatePeer() may have removed it).
    ensure_wg_peer
    stream_start_line="$(wc -l <"$BEAGLE_STREAM_CLIENT_STREAM_LOG" 2>/dev/null || printf '0')"
    stream_forced_restart=0
    "${args[@]}" >>"$BEAGLE_STREAM_CLIENT_STREAM_LOG" 2>&1 &
    stream_pid=$!
    while kill -0 "$stream_pid" >/dev/null 2>&1; do
      if tail -n +"$((stream_start_line + 1))" "$BEAGLE_STREAM_CLIENT_STREAM_LOG" 2>/dev/null | grep -Eq 'Qt Critical: Connection terminated|Connection terminated|Error code: -1'; then
        beagle_log_event "beagle-stream-client.connection-terminated" "attempt=${stream_attempt}/${max_attempts} pid=${stream_pid}"
        kill -TERM "$stream_pid" >/dev/null 2>&1 || true
        sleep 1
        kill -KILL "$stream_pid" >/dev/null 2>&1 || true
        stream_forced_restart=1
        break
      fi
      sleep 2
    done
    if [[ "$stream_forced_restart" -eq 1 ]]; then
      wait "$stream_pid" >/dev/null 2>&1 || true
      stream_exit=124
    elif wait "$stream_pid"; then
      stream_exit=0
    else
      stream_exit=$?
    fi

    if [[ "$stream_exit" -ne 0 && "$stream_attempt" -lt "$max_attempts" && "$app_lookup_port_fallback_used" -eq 0 ]]; then
      if tail -n +"$((stream_start_line + 1))" "$BEAGLE_STREAM_CLIENT_STREAM_LOG" 2>/dev/null | grep -Eqi 'Server certificate mismatch|"applist" request failed|Failed to find application|Failed to load application'; then
        if [[ "$port" =~ ^[0-9]+$ ]]; then
          local fallback_port
          fallback_port="$((port + 1))"
          if [[ "$fallback_port" -gt 0 ]]; then
            export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PORT="$fallback_port"
            port="$fallback_port"
            retarget_beagle_stream_client_host_from_runtime_config || true
            beagle_log_event "beagle-stream-client.port-fallback" "from=$((fallback_port - 1)) to=${fallback_port} reason=applist-or-cert-mismatch"
            app_lookup_port_fallback_used=1
          fi
        fi
      fi
    fi

    if [[ "$stream_exit" -eq 0 || "$stream_attempt" -ge "$max_attempts" ]]; then
      break
    fi
    # After a forced restart (ENet disconnect), wait for Sunshine to finish session
    # cleanup before retrying — avoids "Connection refused (Error 1)" on attempt 2+.
    if [[ "$stream_forced_restart" -eq 1 ]]; then
      ensure_wg_peer
      wait_for_stream_server_ready "${connect_host:-$host}" "$port" 15 || true
    fi
    sleep "$retry_delay"
    stream_attempt=$((stream_attempt + 1))
  done
  [[ -n "$wg_watchdog_pid" ]] && kill "$wg_watchdog_pid" 2>/dev/null || true
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
