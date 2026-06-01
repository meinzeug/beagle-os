#!/usr/bin/env bash

SCRIPT_DIR="${RUNTIME_SCRIPT_DIR:-/usr/local/lib/pve-thin-client/runtime}"
BEAGLE_USB_RUNTIME_USBIPD_SH="${BEAGLE_USB_RUNTIME_USBIPD_SH:-$SCRIPT_DIR/beagle_usb_runtime_usbipd.sh}"
# shellcheck disable=SC1090
source "$BEAGLE_USB_RUNTIME_USBIPD_SH"

usbipd_bin() {
  if [[ -n "${BEAGLE_USBIPD_BIN:-}" ]]; then
    printf '%s\n' "$BEAGLE_USBIPD_BIN"
  elif command -v usbipd >/dev/null 2>&1; then
    command -v usbipd
  else
    printf '%s\n' "/usr/sbin/usbipd"
  fi
}

pkill_bin() {
  printf '%s\n' "${BEAGLE_PKILL_BIN:-pkill}"
}

modprobe_bin() {
  if [[ -n "${BEAGLE_MODPROBE_BIN:-}" ]]; then
    printf '%s\n' "$BEAGLE_MODPROBE_BIN"
  elif command -v modprobe >/dev/null 2>&1; then
    command -v modprobe
  else
    printf '%s\n' "/usr/sbin/modprobe"
  fi
}

systemctl_bin() {
  printf '%s\n' "${BEAGLE_SYSTEMCTL_BIN:-systemctl}"
}

ssh_bin() {
  printf '%s\n' "${BEAGLE_SSH_BIN:-ssh}"
}

sleep_bin() {
  printf '%s\n' "${BEAGLE_SLEEP_BIN:-sleep}"
}

python3_bin() {
  printf '%s\n' "${BEAGLE_PYTHON3_BIN:-python3}"
}

usb_tunnel_service_name() {
  printf '%s\n' "${BEAGLE_USB_TUNNEL_SERVICE:-beagle-usb-tunnel.service}"
}

usb_tunnel_state() {
  is_tunnel_running && printf 'up\n' || printf 'down\n'
}

audio_input_bridge_enabled() {
  [[ "${PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_BRIDGE_ENABLED:-1}" == "1" ]]
}

audio_input_local_port() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_LOCAL_PORT:-43200}"
}

audio_input_remote_port() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_PORT:-43200}"
}

usb_extra_reverse_forwards_raw() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_USB_EXTRA_REVERSE_FORWARDS:-}"
}

append_validated_reverse_forward() {
  local attach_host="$1"
  local remote_port="$2"
  local local_host="$3"
  local local_port="$4"
  local -n reverse_forwards_ref="$5"

  [[ "$remote_port" =~ ^[0-9]+$ ]] || return 1
  [[ "$local_port" =~ ^[0-9]+$ ]] || return 1
  (( remote_port >= 1 && remote_port <= 65535 )) || return 1
  (( local_port >= 1 && local_port <= 65535 )) || return 1
  [[ -n "$local_host" ]] || local_host="127.0.0.1"

  reverse_forwards_ref+=("-R" "${attach_host}:${remote_port}:${local_host}:${local_port}")
}

append_extra_reverse_forwards() {
  local attach_host="$1"
  local extra_specs raw spec label remote_port local_host local_port
  local -n reverse_forwards_ref="$2"

  extra_specs="$(usb_extra_reverse_forwards_raw)"
  [[ -n "$extra_specs" ]] || return 0

  while IFS= read -r raw; do
    spec="${raw//[[:space:]]/}"
    [[ -n "$spec" ]] || continue

    label=""
    remote_port=""
    local_host=""
    local_port=""
    IFS=':' read -r label remote_port local_host local_port _ <<<"$spec"
    if ! append_validated_reverse_forward "$attach_host" "$remote_port" "$local_host" "$local_port" reverse_forwards_ref; then
      echo "beagle-usb-tunnel: ignoring invalid extra reverse forward: ${raw}" >&2
      continue
    fi
    echo "beagle-usb-tunnel: enabled extra reverse forward ${label:-extra} ${attach_host}:${remote_port} -> ${local_host}:${local_port}" >&2
  done < <(printf '%s\n' "$extra_specs" | tr ',;' '\n')
}

start_audio_input_bridge() {
  local python_cmd log_dir log_file bridge_script

  audio_input_bridge_enabled || return 0
  python_cmd="$(python3_bin)"
  bridge_script="$SCRIPT_DIR/beagle_audio_input_bridge.py"
  [[ -r "$bridge_script" ]] || return 0
  if pgrep -f "beagle_audio_input_bridge.py" >/dev/null 2>&1; then
    return 0
  fi
  log_dir="${PVE_THIN_CLIENT_LOG_DIR:-/var/log/beagle}"
  mkdir -p "$log_dir" >/dev/null 2>&1 || true
  log_file="$log_dir/audio-input-bridge.log"
  nohup "$python_cmd" "$bridge_script" \
    --host 127.0.0.1 \
    --port "$(audio_input_local_port)" \
    >>"$log_file" 2>&1 </dev/null &
}

usb_list_json() {
  local payload

  ensure_usbipd >/dev/null 2>&1 || true
  payload="$(list_local_usb_json)"
  render_usb_list_json "$(usb_tunnel_state)" "$payload"
}

bind_usb_device() {
  local busid="$1"
  local usbip_cmd systemctl_cmd

  require_enabled
  usbip_cmd="$(usbip_bin)"
  systemctl_cmd="$(systemctl_bin)"
  ensure_usbipd
  _is_eligible_for_autobind "$busid" || {
    echo "refusing to bind local input/reserved USB device: $busid" >&2
    usb_list_json
    return 1
  }
  "$usbip_cmd" unbind -b "$busid" >/dev/null 2>&1 || true
  "$usbip_cmd" bind -b "$busid" >/dev/null 2>&1 || true
  bound_add "$busid"
  restart_usbipd
  "$systemctl_cmd" restart --no-block "$(usb_tunnel_service_name)" >/dev/null 2>&1 || true
  usb_list_json
}

unbind_usb_device() {
  local busid="$1"
  local usbip_cmd

  require_enabled
  usbip_cmd="$(usbip_bin)"
  "$usbip_cmd" unbind -b "$busid" >/dev/null 2>&1 || true
  bound_remove "$busid"
  restart_usbipd
  usb_list_json
}

usb_status_json() {
  render_usb_status_json "$(usb_tunnel_state)"
}

run_usb_tunnel_daemon() {
  local ssh_cmd camera_pid=""
  local tunnel_user tunnel_host tunnel_attach_host tunnel_port
  local rc
  local ssh_output=""
  local -a reverse_forwards=()

  require_enabled
  [[ -n "$(usb_host)" && -n "$(usb_port)" && -n "$(usb_user)" ]] || exit 0
  [[ -r "$(usb_key_file)" && -r "$(usb_known_hosts_file)" ]] || exit 0
  tunnel_user="$(usb_user)"
  tunnel_host="$(usb_host)"
  tunnel_attach_host="$(usb_attach_host)"
  tunnel_port="$(usb_port)"
  ssh_cmd="$(ssh_bin)"
  # Auto-bind all eligible USB devices before syncing manually-bound list.
  auto_bind_eligible_devices || true
  sync_bound_devices
  start_audio_input_bridge || true
  reverse_forwards+=("-R" "${tunnel_attach_host}:${tunnel_port}:127.0.0.1:3240")
  if audio_input_bridge_enabled; then
    reverse_forwards+=("-R" "$(usb_attach_host):$(audio_input_remote_port):127.0.0.1:$(audio_input_local_port)")
  fi
  append_extra_reverse_forwards "$tunnel_attach_host" reverse_forwards

  # Keep camera forwarding optional so a busy remote camera port does not break
  # USB passthrough for microphones or other attached USB peripherals.
  if [[ "${PVE_THIN_CLIENT_BEAGLE_USB_CAMERA_TUNNEL_ENABLED:-1}" == "1" ]]; then
    local camera_remote_port="${PVE_THIN_CLIENT_BEAGLE_CAMERA_STREAM_PORT:-8091}"
    local camera_local_port="${PVE_THIN_CLIENT_BEAGLE_CAMERA_LOCAL_STREAM_PORT:-8091}"
    "$ssh_cmd" -N \
      -o BatchMode=yes \
      -o ExitOnForwardFailure=no \
      -o ServerAliveInterval=20 \
      -o ServerAliveCountMax=3 \
      -o StrictHostKeyChecking=yes \
      -o UserKnownHostsFile="$(usb_known_hosts_file)" \
      -i "$(usb_key_file)" \
      -R "${tunnel_attach_host}:${camera_remote_port}:127.0.0.1:${camera_local_port}" \
      "${tunnel_user}@${tunnel_host}" >/dev/null 2>&1 &
    camera_pid="$!"
    trap '[[ -n "${camera_pid:-}" ]] && kill "${camera_pid}" >/dev/null 2>&1 || true' EXIT INT TERM
  fi

  reap_stale_tunnel_clients() {
    # Stale ssh tunnel clients can survive abrupt restarts and keep remote
    # reverse ports occupied. Reap matching local tunnel clients first.
    local pgrep_cmd
    local pid=""
    local -a stale_tunnel_pids=()
    local -a _audio_pids=()
    pgrep_cmd="$(pgrep_bin)"
    mapfile -t stale_tunnel_pids < <("$pgrep_cmd" -f "ssh .*${tunnel_user}@${tunnel_host}.*-R ${tunnel_attach_host}:${tunnel_port}:127.0.0.1:3240" 2>/dev/null || true)
    mapfile -t _audio_pids < <("$pgrep_cmd" -f "ssh .*${tunnel_user}@${tunnel_host}.*-R ${tunnel_attach_host}:${tunnel_audio_port}:127.0.0.1:${tunnel_audio_port}" 2>/dev/null || true)
    stale_tunnel_pids+=("${_audio_pids[@]}")
    if [[ "${#stale_tunnel_pids[@]}" -eq 0 ]]; then
      return 0
    fi
    for pid in "${stale_tunnel_pids[@]}"; do
      [[ "$pid" == "$$" ]] && continue
      [[ -n "${camera_pid:-}" && "$pid" == "${camera_pid}" ]] && continue
      kill "$pid" >/dev/null 2>&1 || true
    done
    "$(sleep_bin)" 1
    for pid in "${stale_tunnel_pids[@]}"; do
      [[ "$pid" == "$$" ]] && continue
      [[ -n "${camera_pid:-}" && "$pid" == "${camera_pid}" ]] && continue
      kill -0 "$pid" >/dev/null 2>&1 || continue
      kill -9 "$pid" >/dev/null 2>&1 || true
    done
  }

  while true; do
    reap_stale_tunnel_clients
    set +e
    ssh_output="$("$ssh_cmd" -N \
      -o BatchMode=yes \
      -o ExitOnForwardFailure=yes \
      -o ServerAliveInterval=20 \
      -o ServerAliveCountMax=3 \
      -o StrictHostKeyChecking=yes \
      -o UserKnownHostsFile="$(usb_known_hosts_file)" \
      -i "$(usb_key_file)" \
      "${reverse_forwards[@]}" \
      "${tunnel_user}@${tunnel_host}" 2>&1)"
    rc=$?
    set -e
    if [[ "$rc" -eq 0 ]]; then
      break
    fi
    if [[ -n "$ssh_output" ]]; then
      printf '%s\n' "$ssh_output" >&2
    fi
    if printf '%s\n' "$ssh_output" | grep -q "remote port forwarding failed for listen port"; then
      echo "beagle-usb-tunnel: remote reverse port occupied; waiting for host stale-session reaper" >&2
    fi
    echo "beagle-usb-tunnel: ssh exited with rc=${rc}; retrying" >&2
    "$(sleep_bin)" 3
  done
}
