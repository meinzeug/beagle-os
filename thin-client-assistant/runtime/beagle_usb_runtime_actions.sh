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
  local -a reverse_forwards=()

  require_enabled
  [[ -n "$(usb_host)" && -n "$(usb_port)" && -n "$(usb_user)" ]] || exit 0
  [[ -r "$(usb_key_file)" && -r "$(usb_known_hosts_file)" ]] || exit 0
  ssh_cmd="$(ssh_bin)"
  # Auto-bind all eligible USB devices before syncing manually-bound list.
  auto_bind_eligible_devices || true
  sync_bound_devices
  start_audio_input_bridge || true
  reverse_forwards+=("-R" "$(usb_attach_host):$(usb_port):127.0.0.1:3240")
  if audio_input_bridge_enabled; then
    reverse_forwards+=("-R" "$(usb_attach_host):$(audio_input_remote_port):127.0.0.1:$(audio_input_local_port)")
  fi

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
      -R "$(usb_attach_host):${camera_remote_port}:127.0.0.1:${camera_local_port}" \
      "$(usb_user)@$(usb_host)" >/dev/null 2>&1 &
    camera_pid="$!"
    trap '[[ -n "$camera_pid" ]] && kill "$camera_pid" >/dev/null 2>&1 || true' EXIT INT TERM
  fi

  exec "$ssh_cmd" -N \
    -o BatchMode=yes \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=20 \
    -o ServerAliveCountMax=3 \
    -o StrictHostKeyChecking=yes \
    -o UserKnownHostsFile="$(usb_known_hosts_file)" \
    -i "$(usb_key_file)" \
    "${reverse_forwards[@]}" \
    "$(usb_user)@$(usb_host)"
}
