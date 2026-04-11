#!/usr/bin/env bash
set -euo pipefail

DEFAULT_CONFIG_DIR="/etc/pve-thin-client"
LIVE_STATE_DIR_DEFAULT="/run/live/medium/pve-thin-client/state"
LIVE_PRESET_FILE_DEFAULT="/run/live/medium/pve-thin-client/preset.env"
BEAGLE_STATE_DIR_DEFAULT="/var/lib/beagle-os"
PRESET_STATE_DIR_DEFAULT="/run/beagle-os/preset-state"
BEAGLE_TRACE_FILE_DEFAULT="$BEAGLE_STATE_DIR_DEFAULT/runtime-trace.log"
BEAGLE_LAST_MARKER_FILE_DEFAULT="$BEAGLE_STATE_DIR_DEFAULT/last-marker.env"
RUNTIME_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE_OVERRIDES_PY="${MODE_OVERRIDES_PY:-$RUNTIME_SCRIPT_DIR/mode_overrides.py}"
CONFIG_DISCOVERY_PY="${CONFIG_DISCOVERY_PY:-$RUNTIME_SCRIPT_DIR/config_discovery.py}"
CONFIG_LOADER_SH="${CONFIG_LOADER_SH:-$RUNTIME_SCRIPT_DIR/config_loader.sh}"

# shellcheck disable=SC1090
source "$CONFIG_LOADER_SH"

beagle_state_dir() {
  printf '%s\n' "${BEAGLE_STATE_DIR:-$BEAGLE_STATE_DIR_DEFAULT}"
}

beagle_trace_file() {
  local state_dir
  state_dir="$(beagle_state_dir)"
  printf '%s\n' "${BEAGLE_TRACE_FILE:-$state_dir/runtime-trace.log}"
}

beagle_last_marker_file() {
  local state_dir
  state_dir="$(beagle_state_dir)"
  printf '%s\n' "${BEAGLE_LAST_MARKER_FILE:-$state_dir/last-marker.env}"
}

runtime_user_uid() {
  local user uid_entry

  user="$(runtime_user_name)"
  uid_entry="$(id -u "$user" 2>/dev/null || true)"
  if [[ -n "$uid_entry" ]]; then
    printf '%s\n' "$uid_entry"
    return 0
  fi

  printf '%s\n' "1000"
}

beagle_stream_state_dir() {
  local uid candidate

  uid="$(runtime_user_uid)"
  for candidate in \
    "${XDG_RUNTIME_DIR:-}" \
    "/run/user/$uid" \
    "$(beagle_state_dir)"
  do
    [[ -n "$candidate" ]] || continue
    case "$candidate" in
      /run/user/*)
        printf '%s/beagle-os\n' "$candidate"
        ;;
      *)
        printf '%s\n' "$candidate"
        ;;
    esac
    return 0
  done
}

beagle_stream_session_file() {
  printf '%s/streaming-session.env\n' "$(beagle_stream_state_dir)"
}

beagle_stream_suspended_units_file() {
  printf '%s/streaming-suspended-units.list\n' "$(beagle_stream_state_dir)"
}

beagle_stream_suspended_pids_file() {
  printf '%s/streaming-suspended-pids.list\n' "$(beagle_stream_state_dir)"
}

ensure_beagle_state_dir() {
  local state_dir candidate
  state_dir="$(beagle_state_dir)"

  for candidate in \
    "$state_dir" \
    "/run/beagle-os" \
    "${XDG_RUNTIME_DIR:-/run/user/$(id -u 2>/dev/null || echo 1000)}/beagle-os" \
    "/tmp/beagle-os"
  do
    [[ -n "$candidate" ]] || continue
    if mkdir -p "$candidate" >/dev/null 2>&1 && touch "$candidate/.write-test" >/dev/null 2>&1; then
      rm -f "$candidate/.write-test" >/dev/null 2>&1 || true
      export BEAGLE_STATE_DIR="$candidate"
      return 0
    fi
  done
}

ensure_beagle_stream_state_dir() {
  local dir
  dir="$(beagle_stream_state_dir)"
  [[ -n "$dir" ]] || return 1
  mkdir -p "$dir" >/dev/null 2>&1 || return 1
}

beagle_log_event() {
  local phase="${1:-event}"
  shift || true
  local message="${*:-}"
  local timestamp trace_file marker_file

  timestamp="$(date -Iseconds 2>/dev/null || date)"
  ensure_beagle_state_dir
  trace_file="$(beagle_trace_file)"
  marker_file="$(beagle_last_marker_file)"

  printf '[%s] phase=%s %s\n' "$timestamp" "$phase" "$message" >>"$trace_file" 2>/dev/null || true
  {
    printf 'timestamp=%q\n' "$timestamp"
    printf 'phase=%q\n' "$phase"
    printf 'message=%q\n' "$message"
  } >"$marker_file" 2>/dev/null || true

  if command -v logger >/dev/null 2>&1; then
    logger -t beagle-runtime "phase=$phase $message" >/dev/null 2>&1 || true
  fi
}

beagle_run_privileged() {
  if [[ "$(id -u)" == "0" ]]; then
    "$@"
    return $?
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo -n "$@"
    return $?
  fi

  return 1
}

beagle_unit_file_present() {
  local unit="${1:-}"
  [[ -n "$unit" ]] || return 1
  systemctl list-unit-files --full --no-legend "$unit" 2>/dev/null | awk '{print $1}' | grep -Fxq "$unit"
}

beagle_streaming_session_active() {
  local state_file

  state_file="$(beagle_stream_session_file)"
  if [[ -r "$state_file" ]] && grep -Eq '^active=1$' "$state_file"; then
    return 0
  fi

  pgrep -x GeForceNOW >/dev/null 2>&1 && return 0
  pgrep -f '/app/bin/GeForceNOW' >/dev/null 2>&1 && return 0
  return 1
}

beagle_mark_streaming_session() {
  local active="${1:-0}"
  local reason="${2:-}"
  local state_file temp_file timestamp

  ensure_beagle_stream_state_dir || return 0
  state_file="$(beagle_stream_session_file)"
  temp_file="${state_file}.$$"
  timestamp="$(date -Iseconds 2>/dev/null || date)"

  {
    printf 'active=%s\n' "$active"
    printf 'timestamp=%q\n' "$timestamp"
    printf 'reason=%q\n' "$reason"
    printf 'user=%q\n' "$(runtime_user_name)"
    printf 'pid=%q\n' "$$"
  } >"$temp_file" 2>/dev/null || return 0

  mv -f "$temp_file" "$state_file" >/dev/null 2>&1 || true
}

beagle_management_timer_units() {
  cat <<'EOF'
beagle-endpoint-report.timer
beagle-endpoint-dispatch.timer
beagle-runtime-heartbeat.timer
beagle-healthcheck.timer
beagle-update-scan.timer
beagle-kiosk-update-catalog.timer
EOF
}

beagle_management_service_units() {
  cat <<'EOF'
beagle-endpoint-report.service
beagle-endpoint-dispatch.service
beagle-runtime-heartbeat.service
beagle-healthcheck.service
beagle-update-scan.service
beagle-kiosk-update-catalog.service
EOF
}

beagle_suspend_management_activity() {
  local units_file unit active_state

  ensure_beagle_stream_state_dir || return 0
  units_file="$(beagle_stream_suspended_units_file)"
  : >"$units_file" 2>/dev/null || true
  beagle_mark_streaming_session 1 "gfn-stream"

  while IFS= read -r unit; do
    [[ -n "$unit" ]] || continue
    beagle_unit_file_present "$unit" || continue
    active_state="$(systemctl is-active "$unit" 2>/dev/null || true)"
    case "$active_state" in
      active|activating)
        printf '%s\n' "$unit" >>"$units_file" 2>/dev/null || true
        beagle_run_privileged systemctl stop --no-block "$unit" >/dev/null 2>&1 || true
        ;;
    esac
  done < <(beagle_management_timer_units)

  while IFS= read -r unit; do
    [[ -n "$unit" ]] || continue
    beagle_unit_file_present "$unit" || continue
    active_state="$(systemctl is-active "$unit" 2>/dev/null || true)"
    case "$active_state" in
      active|activating)
        beagle_run_privileged systemctl stop --no-block "$unit" >/dev/null 2>&1 || true
        ;;
    esac
  done < <(beagle_management_service_units)

  if [[ -f "$units_file" ]]; then
    sort -u -o "$units_file" "$units_file" >/dev/null 2>&1 || true
  fi
  beagle_log_event "streaming.management-suspended" "timers_stopped=1"
}

beagle_resume_management_activity() {
  local units_file unit

  units_file="$(beagle_stream_suspended_units_file)"
  if [[ -r "$units_file" ]]; then
    while IFS= read -r unit; do
      [[ -n "$unit" ]] || continue
      beagle_unit_file_present "$unit" || continue
      beagle_run_privileged systemctl start --no-block "$unit" >/dev/null 2>&1 || true
    done <"$units_file"
    rm -f "$units_file" >/dev/null 2>&1 || true
  fi

  beagle_mark_streaming_session 0 "gfn-stream-ended"
  beagle_log_event "streaming.management-resumed" "timers_started=1"
}

beagle_kiosk_runtime_patterns() {
  cat <<'EOF'
/opt/beagle-kiosk/launch.sh
/opt/beagle-kiosk/beagle-kiosk
appimage_extracted_.*/beagle-kiosk
--app-path=.*beagle-kiosk
EOF
}

beagle_kiosk_runtime_running() {
  local runtime_user pattern

  runtime_user="$(runtime_user_name)"
  while IFS= read -r pattern; do
    [[ -n "$pattern" ]] || continue
    if pgrep -u "$runtime_user" -f "$pattern" >/dev/null 2>&1; then
      return 0
    fi
  done < <(beagle_kiosk_runtime_patterns)

  return 1
}

beagle_close_kiosk_window_for_stream() {
  local title timeout_cycles

  title="${PVE_THIN_CLIENT_GFN_KIOSK_WINDOW_TITLE:-Beagle OS Gaming}"
  timeout_cycles="${PVE_THIN_CLIENT_GFN_KIOSK_WINDOW_CLOSE_WAIT_CYCLES:-40}"

  command -v wmctrl >/dev/null 2>&1 || return 1
  DISPLAY="${DISPLAY:-:0}" wmctrl -c "$title" >/dev/null 2>&1 || return 1

  while (( timeout_cycles > 0 )); do
    if ! beagle_kiosk_runtime_running; then
      return 0
    fi
    sleep 0.25
    timeout_cycles=$((timeout_cycles - 1))
  done

  return 1
}

beagle_stop_kiosk_for_stream() {
  local runtime_user pattern wait_cycles

  runtime_user="$(runtime_user_name)"
  wait_cycles="${PVE_THIN_CLIENT_GFN_KIOSK_STOP_WAIT_CYCLES:-40}"

  beagle_log_event "streaming.kiosk-stop" "mode=requested user=${runtime_user}"

  if beagle_close_kiosk_window_for_stream; then
    beagle_log_event "streaming.kiosk-stop" "mode=graceful-close"
    return 0
  fi

  beagle_log_event "streaming.kiosk-stop" "mode=fallback-hardkill"

  while IFS= read -r pattern; do
    [[ -n "$pattern" ]] || continue
    pkill -TERM -u "$runtime_user" -f "$pattern" >/dev/null 2>&1 || true
  done < <(beagle_kiosk_runtime_patterns)

  while (( wait_cycles > 0 )); do
    if ! beagle_kiosk_runtime_running; then
      beagle_log_event "streaming.kiosk-stop" "mode=complete"
      return 0
    fi
    sleep 0.25
    wait_cycles=$((wait_cycles - 1))
  done

  while IFS= read -r pattern; do
    [[ -n "$pattern" ]] || continue
    pkill -KILL -u "$runtime_user" -f "$pattern" >/dev/null 2>&1 || true
  done < <(beagle_kiosk_runtime_patterns)

  beagle_log_event "streaming.kiosk-stop" "mode=forced"
}

beagle_curl_tls_args() {
  local url="${1:-}"
  local pinned_pubkey="${2:-}"
  local ca_cert="${3:-}"
  local -a args=()

  if [[ "$url" == https://* ]]; then
    if [[ -n "$ca_cert" && -r "$ca_cert" ]]; then
      args+=(--cacert "$ca_cert")
      if [[ -n "$pinned_pubkey" ]]; then
        args+=(--pinnedpubkey "$pinned_pubkey")
      fi
    elif [[ -n "$pinned_pubkey" ]]; then
      args+=(-k --pinnedpubkey "$pinned_pubkey")
    fi
  fi

  printf '%s\n' "${args[@]}"
}

find_live_state_dir() {
  [[ -r "$CONFIG_DISCOVERY_PY" ]] || return 1
  python3 "$CONFIG_DISCOVERY_PY" find-live-state-dir \
    --live-state-dir "${LIVE_STATE_DIR:-}" \
    --live-state-dir-default "$LIVE_STATE_DIR_DEFAULT"
}

apply_runtime_mode_overrides() {
  local key value
  [[ -r "$MODE_OVERRIDES_PY" ]] || return 0

  while IFS=$'\t' read -r key value; do
    [[ "$key" =~ ^PVE_THIN_CLIENT_[A-Z0-9_]+$ ]] || continue
    printf -v "$key" '%s' "$value"
  done < <(
    python3 "$MODE_OVERRIDES_PY" \
      --current-mode "${PVE_THIN_CLIENT_MODE:-}" \
      --current-boot-profile "${PVE_THIN_CLIENT_BOOT_PROFILE:-}" \
      --current-client-mode "${PVE_THIN_CLIENT_CLIENT_MODE:-}"
  )
}

runtime_user_name() {
  printf '%s\n' "${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}"
}

runtime_group_name() {
  printf '%s\n' "${PVE_THIN_CLIENT_RUNTIME_GROUP:-$(runtime_user_name)}"
}

runtime_user_home() {
  local user home_entry

  user="$(runtime_user_name)"
  home_entry="$(getent passwd "$user" 2>/dev/null | awk -F: '{print $6}' | head -n 1 || true)"
  if [[ -n "$home_entry" ]]; then
    printf '%s\n' "$home_entry"
    return 0
  fi

  printf '/home/%s\n' "$user"
}

live_medium_dir() {
  local medium="${PVE_THIN_CLIENT_LIVE_MEDIUM_DIR:-/run/live/medium}"

  if [[ -d "$medium" ]]; then
    printf '%s\n' "$medium"
    return 0
  fi

  return 1
}

ensure_runtime_owned_dir() {
  local path="${1:-}"
  local mode="${2:-0700}"
  local owner group

  [[ -n "$path" ]] || return 1

  owner="$(runtime_user_name)"
  group="$(runtime_group_name)"

  if [[ "$(id -u)" == "0" ]]; then
    if install -d -m "$mode" -o "$owner" -g "$group" "$path" >/dev/null 2>&1 && touch "$path/.beagle-write-test" >/dev/null 2>&1; then
      rm -f "$path/.beagle-write-test" >/dev/null 2>&1 || true
      return 0
    fi
  fi

  if install -d -m "$mode" "$path" >/dev/null 2>&1 && touch "$path/.beagle-write-test" >/dev/null 2>&1; then
    rm -f "$path/.beagle-write-test" >/dev/null 2>&1 || true
    return 0
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n install -d -m "$mode" -o "$owner" -g "$group" "$path" >/dev/null 2>&1; then
    if touch "$path/.beagle-write-test" >/dev/null 2>&1; then
      rm -f "$path/.beagle-write-test" >/dev/null 2>&1 || true
      return 0
    fi
  fi

  return 1
}

ensure_runtime_owned_file() {
  local path="${1:-}"
  local mode="${2:-0644}"
  local owner group parent

  [[ -n "$path" ]] || return 1

  owner="$(runtime_user_name)"
  group="$(runtime_group_name)"
  parent="$(dirname "$path")"

  ensure_runtime_owned_dir "$parent" 0755 || return 1

  if [[ -e "$path" ]]; then
    if [[ "$(id -u)" == "0" ]]; then
      chown "$owner:$group" "$path" >/dev/null 2>&1 || true
      chmod "$mode" "$path" >/dev/null 2>&1 || true
      [[ -w "$path" ]] && return 0
    fi

    if [[ -w "$path" ]]; then
      chmod "$mode" "$path" >/dev/null 2>&1 || true
      return 0
    fi

    if command -v sudo >/dev/null 2>&1 && sudo -n chown "$owner:$group" "$path" >/dev/null 2>&1 && sudo -n chmod "$mode" "$path" >/dev/null 2>&1; then
      [[ -w "$path" ]] && return 0
    fi
  fi

  if touch "$path" >/dev/null 2>&1; then
    chmod "$mode" "$path" >/dev/null 2>&1 || true
    return 0
  fi

  if [[ "$(id -u)" == "0" ]]; then
    install -m "$mode" -o "$owner" -g "$group" /dev/null "$path" >/dev/null 2>&1
    [[ -w "$path" ]] && return 0
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n install -m "$mode" -o "$owner" -g "$group" /dev/null "$path" >/dev/null 2>&1; then
    [[ -w "$path" ]] && return 0
  fi

  return 1
}

ensure_runtime_owned_tree() {
  local path="${1:-}"
  local owner group

  [[ -n "$path" ]] || return 1
  [[ -e "$path" ]] || return 0

  owner="$(runtime_user_name)"
  group="$(runtime_group_name)"

  if [[ "$(id -u)" == "0" ]]; then
    chown -R "$owner:$group" "$path" >/dev/null 2>&1 || return 1
    return 0
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n chown -R "$owner:$group" "$path" >/dev/null 2>&1; then
    return 0
  fi

  return 1
}

prepare_geforcenow_environment() {
  local runtime_home="${1:-/home/$(runtime_user_name)}"
  local storage_root medium home_dir data_dir cache_dir config_dir tmp_dir

  storage_root="${PVE_THIN_CLIENT_GFN_STORAGE_ROOT:-}"
  if [[ -z "$storage_root" ]]; then
    medium="$(live_medium_dir 2>/dev/null || true)"
    if [[ -n "$medium" ]]; then
      storage_root="$medium/pve-thin-client/state/gfn"
    else
      storage_root="$(beagle_state_dir)/gfn"
    fi
  fi

  home_dir="$storage_root/home"
  data_dir="$home_dir/.local/share"
  cache_dir="$home_dir/.cache"
  config_dir="$home_dir/.config"
  tmp_dir="$storage_root/tmp"

  for dir in \
    "$storage_root" \
    "$home_dir" \
    "$home_dir/.local" \
    "$data_dir" \
    "$home_dir/.var/app" \
    "$cache_dir" \
    "$config_dir" \
    "$tmp_dir"
  do
    ensure_runtime_owned_dir "$dir" 0700 || return 1
  done

  ensure_runtime_owned_tree "$storage_root" || true

  export PVE_THIN_CLIENT_GFN_STORAGE_ROOT="$storage_root"
  export PVE_THIN_CLIENT_GFN_RUNTIME_HOME="$runtime_home"
  export HOME="$home_dir"
  export XDG_DATA_HOME="$data_dir"
  export XDG_CACHE_HOME="$cache_dir"
  export XDG_CONFIG_HOME="$config_dir"
  export FLATPAK_USER_DIR="$data_dir/flatpak"
  export FLATPAK_DOWNLOAD_TMPDIR="$tmp_dir"

  ensure_runtime_owned_dir "$FLATPAK_USER_DIR" 0700 || return 1
  ensure_runtime_owned_dir "$XDG_CACHE_HOME" 0700 || return 1
  ensure_runtime_owned_dir "$XDG_CONFIG_HOME" 0700 || return 1
  ensure_runtime_owned_dir "$HOME/.var/app" 0700 || return 1

  return 0
}

find_config_dir() {
  local installer_dir installer_script runtime_user preset_state_dir
  [[ -r "$CONFIG_DISCOVERY_PY" ]] || return 1
  installer_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../installer" && pwd)"
  installer_script="$installer_dir/write-config.sh"
  runtime_user="${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}"
  preset_state_dir="${PRESET_STATE_DIR:-$PRESET_STATE_DIR_DEFAULT}"

  python3 "$CONFIG_DISCOVERY_PY" find-config-dir \
    --config-dir "${CONFIG_DIR:-}" \
    --default-config-dir "$DEFAULT_CONFIG_DIR" \
    --live-state-dir "${LIVE_STATE_DIR:-}" \
    --live-state-dir-default "$LIVE_STATE_DIR_DEFAULT" \
    --preset-file "${PVE_THIN_CLIENT_PRESET_FILE:-}" \
    --live-preset-file-default "$LIVE_PRESET_FILE_DEFAULT" \
    --preset-state-dir "$preset_state_dir" \
    --runtime-user "$runtime_user" \
    --installer-script "$installer_script"
}

render_template() {
  local template="$1"
  local output="$template"

  output="${output//\{mode\}/${PVE_THIN_CLIENT_MODE:-}}"
  output="${output//\{username\}/${PVE_THIN_CLIENT_CONNECTION_USERNAME:-}}"
  output="${output//\{password\}/${PVE_THIN_CLIENT_CONNECTION_PASSWORD:-}}"
  output="${output//\{token\}/${PVE_THIN_CLIENT_CONNECTION_TOKEN:-}}"
  output="${output//\{host\}/${PVE_THIN_CLIENT_PROXMOX_HOST:-}}"
  output="${output//\{node\}/${PVE_THIN_CLIENT_PROXMOX_NODE:-}}"
  output="${output//\{vmid\}/${PVE_THIN_CLIENT_PROXMOX_VMID:-}}"
  output="${output//\{moonlight_host\}/${PVE_THIN_CLIENT_MOONLIGHT_HOST:-}}"
  output="${output//\{moonlight_local_host\}/${PVE_THIN_CLIENT_MOONLIGHT_LOCAL_HOST:-}}"
  output="${output//\{moonlight_port\}/${PVE_THIN_CLIENT_MOONLIGHT_PORT:-}}"
  output="${output//\{sunshine_api_url\}/${PVE_THIN_CLIENT_SUNSHINE_API_URL:-}}"

  printf '%s\n' "$output"
}

split_browser_flags() {
  local flags="${PVE_THIN_CLIENT_BROWSER_FLAGS:-}"
  if [[ -z "$flags" ]]; then
    return 0
  fi

  # shellcheck disable=SC2206
  BROWSER_FLAG_ARRAY=($flags)
}
