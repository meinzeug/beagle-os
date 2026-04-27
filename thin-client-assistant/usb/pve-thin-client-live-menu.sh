#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALLER="${PVE_THIN_CLIENT_INSTALLER_BIN:-$SCRIPT_DIR/pve-thin-client-local-installer.sh}"
BEAGLE_API_HELPER="${PVE_THIN_CLIENT_BEAGLE_API_HELPER:-$SCRIPT_DIR/pve-thin-client-beagle-api.py}"
LIVE_MEDIUM_HELPERS="$SCRIPT_DIR/live_medium_helpers.sh"
LIVE_MEDIUM_DEFAULT="${LIVE_MEDIUM:-/run/live/medium}"
TEMP_LIVE_MEDIUM_MOUNT=""
BOOT_STAMP="$(date -u +%Y%m%dT%H%M%SZ 2>/dev/null || date +%Y%m%dT%H%M%SZ)"
LOG_SESSION_ID="${PVE_THIN_CLIENT_LOG_SESSION_ID:-${BOOT_STAMP}-installer-menu}"
LOG_ROOT="${PVE_THIN_CLIENT_LOG_ROOT:-/tmp/pve-thin-client-logs}"
LOG_DIR="${PVE_THIN_CLIENT_LOG_DIR:-$LOG_ROOT/$LOG_SESSION_ID}"
LOG_FILE="$LOG_DIR/live-menu.log"
LOG_PERSIST_DIR=""
TEMP_LOG_PERSIST_MOUNT=""
LOG_SYNC_IN_PROGRESS=0
LOGIN_STATE_FILE="/run/pve-thin-client/beagle-login.env"
NETWORK_STATE_FILE="/run/pve-thin-client/installer-network.env"
RUNTIME_NETWORK_DIR="/run/systemd/network"
RUNTIME_NETWORK_FILE="$RUNTIME_NETWORK_DIR/10-pve-thin-client-installer.network"
WPA_RUNTIME_DIR="/run/pve-thin-client"
WPA_CONFIG_FILE="$WPA_RUNTIME_DIR/wpa_supplicant-installer.conf"
WPA_PID_FILE="$WPA_RUNTIME_DIR/wpa_supplicant-installer.pid"
AUTO_INSTALL_LOCK_FILE="$WPA_RUNTIME_DIR/installer-auto.lock"
DEFAULT_DNS_SERVERS=("1.1.1.1" "9.9.9.9" "8.8.8.8")
DEFAULT_API_SCHEME="https"
DEFAULT_API_PORT="8006"
DEFAULT_API_VERIFY_TLS="1"
NETWORK_SETUP_COMPLETE=0
BUNDLED_PRESET_MODE=0
AUTO_INSTALL_ACTIVE=0
AUTO_INSTALL_LOCK_HELD=0
AUTO_INSTALL_LOCK_FD=""
AUTO_INSTALL_LOCK_SKIPPED=0
LAST_INSTALL_EXIT_CODE=0

# shellcheck disable=SC1090
source "$LIVE_MEDIUM_HELPERS"

have_passwordless_sudo() {
  [[ "${EUID}" -eq 0 ]] || (command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1)
}

privileged_run() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
    return
  fi

  if have_passwordless_sudo; then
    sudo -n "$@"
    return
  fi

  return 1
}

cleanup() {
  if [[ "$AUTO_INSTALL_LOCK_HELD" == "1" && -n "$AUTO_INSTALL_LOCK_FD" ]]; then
    eval "exec ${AUTO_INSTALL_LOCK_FD}>&-"
  fi
  if [[ -n "$TEMP_LOG_PERSIST_MOUNT" ]]; then
    if [[ "${EUID}" -eq 0 ]]; then
      umount "$TEMP_LOG_PERSIST_MOUNT" >/dev/null 2>&1 || true
    else
      sudo -n umount "$TEMP_LOG_PERSIST_MOUNT" >/dev/null 2>&1 || true
    fi
    rmdir "$TEMP_LOG_PERSIST_MOUNT" >/dev/null 2>&1 || true
  fi
  if [[ -n "$TEMP_LIVE_MEDIUM_MOUNT" ]]; then
    if [[ "${EUID}" -eq 0 ]]; then
      umount "$TEMP_LIVE_MEDIUM_MOUNT" >/dev/null 2>&1 || true
    else
      sudo -n umount "$TEMP_LIVE_MEDIUM_MOUNT" >/dev/null 2>&1 || true
    fi
    rmdir "$TEMP_LIVE_MEDIUM_MOUNT" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

setup_logging() {
  mkdir -p "$LOG_DIR"
  touch "$LOG_FILE"
  chmod 0644 "$LOG_FILE" >/dev/null 2>&1 || true
  mkdir -p "$(dirname "$LOGIN_STATE_FILE")"
  {
    printf 'LOG_SESSION_ID=%s\n' "$LOG_SESSION_ID"
    printf 'LOG_DIR=%s\n' "$LOG_DIR"
    printf 'DATE=%s\n' "$(date -Is 2>/dev/null || date)"
  } >"$LOG_DIR/session.env" 2>/dev/null || true
}

running_from_live_environment() {
  if [[ -d /run/live/medium || -d /lib/live/mount/medium ]]; then
    return 0
  fi

  if [[ -r /proc/cmdline ]]; then
    grep -Eq '(^| )boot=live( |$)|(^| )pve_thin_client\.mode=installer( |$)' /proc/cmdline 2>/dev/null
    return $?
  fi

  return 1
}

installer_ui_is_text() {
  if [[ "${PVE_THIN_CLIENT_INSTALLER_UI:-}" == "text" ]]; then
    return 0
  fi

  if [[ -r /proc/cmdline ]]; then
    grep -Eq '(^| )pve_thin_client\.installer_ui=text( |$)' /proc/cmdline 2>/dev/null
    return $?
  fi

  return 1
}

sanitize_log_session_id() {
  local raw="${LOG_SESSION_ID:-$(basename "$LOG_DIR")}"
  raw="${raw//[^A-Za-z0-9._-]/_}"
  [[ -n "$raw" ]] || raw="installer"
  printf '%s\n' "$raw"
}

mount_writable_live_medium_for_logs() {
  local mounted=""
  local mount_dir=""

  mounted="$(mount_candidate_live_medium rw /tmp/pve-live-logs.XXXXXX live_medium_contains_persist_root || true)"
  [[ -n "$mounted" ]] || return 1
  mount_dir="${mounted#*$'\t'}"
  TEMP_LOG_PERSIST_MOUNT="$mount_dir"
  printf '%s\n' "$mount_dir"

  return 0
}

persist_logs_to_medium() {
  local persist_root=""
  local session_dir=""
  local persist_parent=""

  if ! running_from_live_environment; then
    return 0
  fi

  if [[ -d "$LIVE_MEDIUM_DEFAULT/pve-thin-client" ]]; then
    if [[ -w "$LIVE_MEDIUM_DEFAULT/pve-thin-client" ]]; then
      persist_root="$LIVE_MEDIUM_DEFAULT"
    elif mountpoint -q "$LIVE_MEDIUM_DEFAULT"; then
      privileged_run mount -o remount,rw "$LIVE_MEDIUM_DEFAULT" >/dev/null 2>&1 || \
        privileged_run mount -o remount,rw "$(findmnt -n -o SOURCE "$LIVE_MEDIUM_DEFAULT" 2>/dev/null || true)" "$LIVE_MEDIUM_DEFAULT" >/dev/null 2>&1 || true
      if [[ -w "$LIVE_MEDIUM_DEFAULT/pve-thin-client" ]]; then
        persist_root="$LIVE_MEDIUM_DEFAULT"
      fi
    fi
  else
    persist_root="$(mount_writable_live_medium_for_logs || true)"
  fi

  [[ -n "$persist_root" ]] || return 0

  session_dir="$(sanitize_log_session_id)"
  persist_parent="$persist_root/pve-thin-client/logs"
  mkdir -p "$persist_parent/$session_dir" >/dev/null 2>&1 || return 0
  LOG_PERSIST_DIR="$persist_parent/$session_dir"
  cp -a "$LOG_DIR/." "$LOG_PERSIST_DIR/" 2>/dev/null || true
  printf '%s\n' "$session_dir" >"$persist_parent/LATEST.txt" 2>/dev/null || true
}

sync_logs_to_medium() {
  [[ "$LOG_SYNC_IN_PROGRESS" == "1" ]] && return 0
  LOG_SYNC_IN_PROGRESS=1
  persist_logs_to_medium >/dev/null 2>&1 || true
  LOG_SYNC_IN_PROGRESS=0
}

log_msg() {
  setup_logging
  printf '[%s] %s\n' "$(date -Is 2>/dev/null || date)" "$*" >>"$LOG_FILE"
}

acquire_auto_install_lock() {
  mkdir -p "$WPA_RUNTIME_DIR"
  exec {AUTO_INSTALL_LOCK_FD}>"$AUTO_INSTALL_LOCK_FILE"
  if flock -n "$AUTO_INSTALL_LOCK_FD"; then
    AUTO_INSTALL_LOCK_HELD=1
    return 0
  fi
  AUTO_INSTALL_LOCK_HELD=0
  return 1
}

log_network_snapshot() {
  local label="${1:-network}"
  setup_logging
  {
    echo "=== $label ==="
    date -Is 2>/dev/null || date
    echo
    echo "=== ip -br link ==="
    ip -br link 2>/dev/null || true
    echo
    echo "=== ip -br addr ==="
    ip -br addr 2>/dev/null || true
    echo
    echo "=== ip route ==="
    ip route 2>/dev/null || true
    echo
    echo "=== /etc/resolv.conf ==="
    cat /etc/resolv.conf 2>/dev/null || true
    echo
    echo "=== networkctl ==="
    networkctl --no-pager --all 2>/dev/null || true
    echo
  } >>"$LOG_DIR/network-status.log" 2>&1 || true
}

detect_tty_path() {
  local tty_path="/dev/tty"
  if [[ -r "$tty_path" && -w "$tty_path" ]]; then
    printf '%s\n' "$tty_path"
  fi
}

TTY_PATH="$(detect_tty_path || true)"

have_tui_dialog() {
  [[ -n "$TTY_PATH" ]] && command -v whiptail >/dev/null 2>&1 && ! installer_ui_is_text
}

run_whiptail() {
  whiptail "$@" --output-fd 3 \
    3>&1 \
    1>"$TTY_PATH" \
    2>"$TTY_PATH" \
    <"$TTY_PATH"
}

dialog_msgbox() {
  local title="$1"
  local text="$2"
  if have_tui_dialog; then
    run_whiptail --title "$title" --msgbox "$text" 18 90
    return 0
  fi

  printf '\n[%s]\n%s\n' "$title" "$text"
  if [[ -n "$TTY_PATH" ]]; then
    printf 'Press ENTER to continue. ' >"$TTY_PATH"
    read -r _ <"$TTY_PATH"
  fi
}

dialog_input() {
  local title="$1"
  local text="$2"
  local default_value="${3:-}"
  local answer=""

  if have_tui_dialog; then
    run_whiptail --title "$title" --inputbox "$text" 12 90 "$default_value"
    return 0
  fi

  [[ -n "$TTY_PATH" ]] || return 1
  printf '\n[%s]\n%s\n> ' "$title" "$text" >"$TTY_PATH"
  read -r answer <"$TTY_PATH" || return 1
  if [[ -z "$answer" ]]; then
    answer="$default_value"
  fi
  printf '%s\n' "$answer"
}

dialog_password() {
  local title="$1"
  local text="$2"
  local answer=""

  if have_tui_dialog; then
    run_whiptail --title "$title" --passwordbox "$text" 12 90
    return 0
  fi

  [[ -n "$TTY_PATH" ]] || return 1
  printf '\n[%s]\n%s\n> ' "$title" "$text" >"$TTY_PATH"
  read -rs answer <"$TTY_PATH" || return 1
  printf '\n' >"$TTY_PATH"
  printf '%s\n' "$answer"
}

dialog_menu() {
  local title="$1"
  local text="$2"
  shift 2
  local -a items=("$@")
  local count=0
  local index=1
  local answer=""

  count=$(( ${#items[@]} / 2 ))
  if have_tui_dialog; then
    run_whiptail --title "$title" --menu "$text" 22 100 "$count" "${items[@]}"
    return 0
  fi

  [[ -n "$TTY_PATH" ]] || return 1
  printf '\n[%s]\n%s\n' "$title" "$text" >"$TTY_PATH"
  while (( index <= count )); do
    printf '%s) %s %s\n' \
      "$index" \
      "${items[$(( (index - 1) * 2 ))]}" \
      "${items[$(( (index - 1) * 2 + 1 ))]}" >"$TTY_PATH"
    index=$((index + 1))
  done
  printf 'Choice: ' >"$TTY_PATH"
  read -r answer <"$TTY_PATH" || return 1
  [[ "$answer" =~ ^[0-9]+$ ]] || return 1
  (( answer >= 1 && answer <= count )) || return 1
  printf '%s\n' "${items[$(( (answer - 1) * 2 ))]}"
}

is_ip_literal() {
  local value="${1:-}"
  [[ "$value" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ || "$value" =~ : ]]
}

resolve_ipv4_address() {
  local host="${1:-}"
  [[ -n "$host" ]] || return 1
  python3 - "$host" <<'PY'
import socket
import sys

host = sys.argv[1].strip()
if not host:
    raise SystemExit(1)

seen = set()
try:
    infos = socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
except OSError:
    raise SystemExit(1)

for info in infos:
    address = info[4][0]
    if address not in seen:
        seen.add(address)
        print(address)
        raise SystemExit(0)

raise SystemExit(1)
PY
}

wired_interfaces() {
  local iface
  for iface in /sys/class/net/*; do
    iface="$(basename "$iface")"
    [[ "$iface" == "lo" ]] && continue
    [[ -d "/sys/class/net/$iface/wireless" ]] && continue
    case "$iface" in
      docker*|virbr*|veth*|br-*|tun*|tap*|wg*|zt*|vmnet*|tailscale*) continue ;;
    esac
    printf '%s\n' "$iface"
  done
}

wifi_interfaces() {
  local iface
  for iface in /sys/class/net/*; do
    iface="$(basename "$iface")"
    [[ "$iface" == "lo" ]] && continue
    [[ -d "/sys/class/net/$iface/wireless" ]] || continue
    printf '%s\n' "$iface"
  done
}

choose_interface() {
  local title="$1"
  local text="$2"
  shift 2
  local -a interfaces=("$@")
  local -a menu_items=()
  local iface=""

  if (( ${#interfaces[@]} == 0 )); then
    return 1
  fi

  if (( ${#interfaces[@]} == 1 )); then
    printf '%s\n' "${interfaces[0]}"
    return 0
  fi

  for iface in "${interfaces[@]}"; do
    menu_items+=("$iface" "MAC $(cat "/sys/class/net/$iface/address" 2>/dev/null || printf 'unknown')")
  done

  dialog_menu "$title" "$text" "${menu_items[@]}"
}

write_runtime_network_file() {
  local iface="$1"
  local dns_block=""
  local dns_server=""
  install -d -m 0755 "$RUNTIME_NETWORK_DIR"
  install -d -m 0700 "$WPA_RUNTIME_DIR"
  for dns_server in "${DEFAULT_DNS_SERVERS[@]}"; do
    dns_block="${dns_block}DNS=${dns_server}"$'\n'
  done
  cat >"$RUNTIME_NETWORK_FILE" <<EOF
[Match]
Name=$iface

[Network]
DHCP=yes
${dns_block}Domains=~.

[DHCPv4]
UseDNS=yes
EOF
}

restart_network_stack() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl restart systemd-networkd.service >/dev/null 2>&1 || true
    systemctl restart systemd-resolved.service >/dev/null 2>&1 || true
  fi
}

write_runtime_resolv_conf() {
  local iface="${1:-}"
  local dns_server=""

  install -d -m 0700 "$WPA_RUNTIME_DIR"
  {
    printf '# Generated by Thinclient Installer\n'
    for dns_server in "${DEFAULT_DNS_SERVERS[@]}"; do
      printf 'nameserver %s\n' "$dns_server"
    done
    printf 'options timeout:2 attempts:2 rotate\n'
  } >"$WPA_RUNTIME_DIR/resolv.conf"

  if [[ "${EUID}" -eq 0 ]]; then
    cp "$WPA_RUNTIME_DIR/resolv.conf" /etc/resolv.conf >/dev/null 2>&1 || true
  elif have_passwordless_sudo; then
    sudo -n cp "$WPA_RUNTIME_DIR/resolv.conf" /etc/resolv.conf >/dev/null 2>&1 || true
  fi

  if [[ -n "$iface" ]] && command -v resolvectl >/dev/null 2>&1; then
    resolvectl dns "$iface" "${DEFAULT_DNS_SERVERS[@]}" >/dev/null 2>&1 || true
    resolvectl domain "$iface" "~." >/dev/null 2>&1 || true
    resolvectl flush-caches >/dev/null 2>&1 || true
  fi
}

save_network_state() {
  local mode="$1"
  local iface="$2"
  local ssid="${3:-}"
  mkdir -p "$(dirname "$NETWORK_STATE_FILE")"
  cat >"$NETWORK_STATE_FILE" <<EOF
PVE_INSTALLER_NETWORK_MODE=$mode
PVE_INSTALLER_NETWORK_INTERFACE=$iface
PVE_INSTALLER_WIFI_SSID=$ssid
EOF
}

wait_for_interface_network() {
  local iface="$1"
  local timeout="${2:-25}"
  local elapsed=0

  while (( elapsed < timeout )); do
    if ip -4 addr show dev "$iface" scope global 2>/dev/null | grep -q 'inet ' && ip route show default 2>/dev/null | grep -q .; then
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done

  return 1
}

wait_for_dns_resolution() {
  local host="$1"
  local timeout="${2:-15}"
  local elapsed=0

  is_ip_literal "$host" && return 0

  while (( elapsed < timeout )); do
    if resolve_ipv4_address "$host" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done

  return 1
}

stop_wifi_stack() {
  if [[ -f "$WPA_PID_FILE" ]]; then
    kill "$(cat "$WPA_PID_FILE" 2>/dev/null || printf '')" >/dev/null 2>&1 || true
    rm -f "$WPA_PID_FILE"
  fi

  if command -v wpa_cli >/dev/null 2>&1; then
    wpa_cli terminate >/dev/null 2>&1 || true
  fi
}

build_wpa_supplicant_config() {
  local ssid="$1"
  local password="$2"

  install -d -m 0700 "$WPA_RUNTIME_DIR"
  if [[ -n "$password" ]]; then
    wpa_passphrase "$ssid" "$password" >"$WPA_CONFIG_FILE"
  else
    python3 - "$WPA_CONFIG_FILE" "$ssid" <<'PY'
import json
import sys
from pathlib import Path

target = Path(sys.argv[1])
ssid = sys.argv[2]
quoted = json.dumps(ssid)
target.write_text(
    "ctrl_interface=/run/wpa_supplicant\n"
    "update_config=0\n"
    "network={\n"
    f"    ssid={quoted}\n"
    "    key_mgmt=NONE\n"
    "    scan_ssid=1\n"
    "}\n",
    encoding="utf-8",
)
PY
  fi
  chmod 0600 "$WPA_CONFIG_FILE" >/dev/null 2>&1 || true
}

scan_wifi_ssids() {
  local iface="$1"
  ip link set "$iface" up >/dev/null 2>&1 || true
  if command -v rfkill >/dev/null 2>&1; then
    rfkill unblock wifi >/dev/null 2>&1 || true
  fi
  iw dev "$iface" scan 2>/dev/null | awk -F'SSID: ' '/SSID: / {print $2}' | sed '/^$/d' | awk '!seen[$0]++'
}

choose_wifi_ssid() {
  local iface="$1"
  local -a ssids=()
  local -a menu_items=()
  local ssid=""
  local choice=""
  local index=1

  mapfile -t ssids < <(scan_wifi_ssids "$iface" | sed -n '1,20p')
  if (( ${#ssids[@]} == 0 )); then
    dialog_input "WLAN SSID" "No WLANs were discovered automatically. Enter the SSID manually." ""
    return 0
  fi

  for ssid in "${ssids[@]}"; do
    menu_items+=("ssid-$index" "$ssid")
    index=$((index + 1))
  done
  menu_items+=("manual" "Hidden or other WLAN")

  choice="$(dialog_menu "Choose WLAN" "Select the Wi-Fi network for internet access." "${menu_items[@]}")" || return 1
  if [[ "$choice" == "manual" ]]; then
    dialog_input "WLAN SSID" "Enter the WLAN SSID." ""
    return 0
  fi

  index="${choice#ssid-}"
  [[ "$index" =~ ^[0-9]+$ ]] || return 1
  printf '%s\n' "${ssids[$((index - 1))]}"
}

prepare_ethernet_network() {
  local -a ifaces=()
  local iface=""

  mapfile -t ifaces < <(wired_interfaces)
  if (( ${#ifaces[@]} == 0 )); then
    dialog_msgbox "No Ethernet Found" "No wired network interface was detected on this machine."
    return 1
  fi

  iface="$(choose_interface "Ethernet" "Select the wired interface to use." "${ifaces[@]}")" || return 1
  log_msg "selected ethernet interface: $iface"
  ip link set "$iface" up >/dev/null 2>&1 || true
  stop_wifi_stack
  write_runtime_network_file "$iface"
  restart_network_stack
  write_runtime_resolv_conf "$iface"
  log_network_snapshot "ethernet-before-wait"
  if ! wait_for_interface_network "$iface" 25; then
    log_network_snapshot "ethernet-timeout"
    dialog_msgbox "Ethernet Not Ready" "No DHCP lease or default route appeared on $iface. Check the cable and switch port, then try again."
    return 1
  fi

  write_runtime_resolv_conf "$iface"
  save_network_state "ethernet" "$iface"
  NETWORK_SETUP_COMPLETE=1
  log_network_snapshot "ethernet-ready"
  return 0
}

prepare_wifi_network() {
  local -a ifaces=()
  local iface=""
  local ssid=""
  local password=""

  if ! command -v iw >/dev/null 2>&1 || ! command -v wpa_supplicant >/dev/null 2>&1 || ! command -v wpa_passphrase >/dev/null 2>&1; then
    dialog_msgbox "WLAN Unsupported" "This installer image does not contain the Wi-Fi tools it needs. Rebuild the image with WLAN support."
    return 1
  fi

  mapfile -t ifaces < <(wifi_interfaces)
  if (( ${#ifaces[@]} == 0 )); then
    dialog_msgbox "No WLAN Found" "No wireless interface was detected on this machine."
    return 1
  fi

  iface="$(choose_interface "WLAN" "Select the wireless interface to use." "${ifaces[@]}")" || return 1
  log_msg "selected wifi interface: $iface"
  ssid="$(choose_wifi_ssid "$iface")" || return 1
  [[ -n "$ssid" ]] || {
    dialog_msgbox "Missing WLAN SSID" "A WLAN name is required."
    return 1
  }
  password="$(dialog_password "WLAN Password" "Enter the WLAN password for ${ssid}. Leave blank for an open network.")" || return 1

  if command -v rfkill >/dev/null 2>&1; then
    rfkill unblock wifi >/dev/null 2>&1 || true
  fi
  ip link set "$iface" up >/dev/null 2>&1 || true
  stop_wifi_stack
  build_wpa_supplicant_config "$ssid" "$password"
  if ! wpa_supplicant -B -P "$WPA_PID_FILE" -i "$iface" -c "$WPA_CONFIG_FILE" >/dev/null 2>&1; then
    dialog_msgbox "WLAN Failed" "wpa_supplicant could not start for ${iface}. Check the adapter and try again."
    return 1
  fi

  write_runtime_network_file "$iface"
  restart_network_stack
  write_runtime_resolv_conf "$iface"
  log_network_snapshot "wifi-before-wait"
  if ! wait_for_interface_network "$iface" 35; then
    log_network_snapshot "wifi-timeout"
    dialog_msgbox "WLAN Not Ready" "No DHCP lease or default route appeared on ${iface}. Check the password and signal quality, then try again."
    return 1
  fi

  write_runtime_resolv_conf "$iface"
  save_network_state "wifi" "$iface" "$ssid"
  NETWORK_SETUP_COMPLETE=1
  log_network_snapshot "wifi-ready"
  return 0
}

configure_network_access() {
  local -a items=()
  local choice=""

  if [[ "$NETWORK_SETUP_COMPLETE" == "1" ]]; then
    return 0
  fi

  if wired_interfaces | grep -q .; then
    items+=("ethernet" "Cable (Ethernet)")
  fi
  if wifi_interfaces | grep -q .; then
    items+=("wifi" "WLAN")
  fi

  if (( ${#items[@]} == 0 )); then
    dialog_msgbox "No Network Hardware" "No wired or wireless network interface was detected."
    return 1
  fi

  choice="$(dialog_menu "Internet Connection" "Choose how this installer should reach the internet and Beagle." "${items[@]}")" || return 1
  case "$choice" in
    ethernet)
      prepare_ethernet_network
      ;;
    wifi)
      prepare_wifi_network
      ;;
    *)
      return 1
      ;;
  esac
}

effective_api_host() {
  local host="$1"
  local host_ip="$2"

  if [[ -z "$host" ]]; then
    printf '%s\n' "$host_ip"
    return 0
  fi

  if is_ip_literal "$host"; then
    printf '%s\n' "$host"
    return 0
  fi

  if wait_for_dns_resolution "$host" 8; then
    printf '%s\n' "$host"
    return 0
  fi

  if [[ -n "$host_ip" ]]; then
    log_msg "DNS lookup failed for $host, falling back to $host_ip"
    printf '%s\n' "$host_ip"
    return 0
  fi

  return 1
}

mount_discovered_live_medium() {
  local mounted=""
  local mount_dir=""

  mounted="$(mount_candidate_live_medium ro /tmp/pve-live-medium.XXXXXX live_medium_contains_manifest_or_assets || true)"
  [[ -n "$mounted" ]] || return 1
  mount_dir="${mounted#*$'\t'}"
  TEMP_LIVE_MEDIUM_MOUNT="$mount_dir"
  printf '%s\n' "$mount_dir"
  return 0
}

resolve_manifest_file() {
  local target=""

  while IFS= read -r target; do
    if target="$(candidate_manifest_path "$target" 2>/dev/null || true)" && [[ -n "$target" ]]; then
      printf '%s\n' "$target"
      return 0
    fi
  done < <(candidate_live_mounts | awk 'NF && !seen[$0]++')

  if target="$(mount_discovered_live_medium 2>/dev/null || true)" && [[ -n "$target" ]]; then
    if target="$(candidate_manifest_path "$target" 2>/dev/null || true)" && [[ -n "$target" ]]; then
      printf '%s\n' "$target"
      return 0
    fi
  fi

  return 1
}

default_api_settings_json() {
  local manifest_file=""
  manifest_file="$(resolve_manifest_file || true)"
  python3 - "$manifest_file" "$LOGIN_STATE_FILE" "$DEFAULT_API_SCHEME" "$DEFAULT_API_PORT" "$DEFAULT_API_VERIFY_TLS" <<'PY'
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

manifest_file, login_state_file, default_scheme, default_port, default_verify_tls = sys.argv[1:6]
payload = {
    "scheme": default_scheme,
    "host": "",
    "host_ip": "",
    "port": default_port,
    "verify_tls": default_verify_tls,
    "username": "",
}

if manifest_file and Path(manifest_file).is_file():
    try:
        manifest = json.loads(Path(manifest_file).read_text(encoding="utf-8"))
        payload["scheme"] = str(manifest.get("beagle_api_scheme", payload["scheme"]) or payload["scheme"])
        payload["host"] = str(manifest.get("beagle_api_host", payload["host"]) or payload["host"])
        payload["host_ip"] = str(manifest.get("beagle_api_host_ip", payload["host_ip"]) or payload["host_ip"])
        payload["port"] = str(manifest.get("beagle_api_port", payload["port"]) or payload["port"])
        payload["verify_tls"] = str(manifest.get("beagle_api_verify_tls", payload["verify_tls"]) or payload["verify_tls"])
        source = manifest.get("payload_source", "")
        if source and not payload["host"]:
            parsed = urlparse(source)
            if parsed.scheme:
                payload["scheme"] = parsed.scheme
            if parsed.hostname:
                payload["host"] = parsed.hostname
    except Exception:
        pass

if login_state_file and Path(login_state_file).is_file():
    state = {}
    for raw_line in Path(login_state_file).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        state[key] = value
    payload["scheme"] = state.get("PVE_LOGIN_SCHEME", payload["scheme"])
    payload["host"] = state.get("PVE_LOGIN_HOST", payload["host"])
    payload["host_ip"] = state.get("PVE_LOGIN_HOST_IP", payload["host_ip"])
    payload["port"] = state.get("PVE_LOGIN_PORT", payload["port"])
    payload["verify_tls"] = state.get("PVE_LOGIN_VERIFY_TLS", payload["verify_tls"])
    payload["username"] = state.get("PVE_LOGIN_USERNAME", payload["username"])

print(json.dumps(payload))
PY
}

save_login_defaults() {
  local scheme="$1"
  local host="$2"
  local host_ip="$3"
  local port="$4"
  local verify_tls="$5"
  local username="$6"

  mkdir -p "$(dirname "$LOGIN_STATE_FILE")"
  cat >"$LOGIN_STATE_FILE" <<EOF
PVE_LOGIN_SCHEME=$scheme
PVE_LOGIN_HOST=$host
PVE_LOGIN_HOST_IP=$host_ip
PVE_LOGIN_PORT=$port
PVE_LOGIN_VERIFY_TLS=$verify_tls
PVE_LOGIN_USERNAME=$username
EOF
}

run_installer_command() {
  env \
    PVE_THIN_CLIENT_LOG_DIR="$LOG_DIR" \
    PVE_THIN_CLIENT_LOG_SESSION_ID="${PVE_THIN_CLIENT_LOG_SESSION_ID:-$(basename "$LOG_DIR")}" \
    "$INSTALLER" "$@"
}

run_installer_as_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    run_installer_command "$@"
    return $?
  fi

  if have_passwordless_sudo; then
    sudo -n env \
      PVE_THIN_CLIENT_LOG_DIR="$LOG_DIR" \
      PVE_THIN_CLIENT_LOG_SESSION_ID="${PVE_THIN_CLIENT_LOG_SESSION_ID:-$(basename "$LOG_DIR")}" \
      "$INSTALLER" "$@"
    return $?
  fi

  dialog_msgbox "Missing Privileges" "Passwordless sudo is required for disk installation in the live environment."
  return 1
}

list_beagle_vms_json_direct() {
  env \
    PVE_THIN_CLIENT_LOG_DIR="$LOG_DIR" \
    PVE_THIN_CLIENT_LOG_SESSION_ID="${PVE_THIN_CLIENT_LOG_SESSION_ID:-$(basename "$LOG_DIR")}" \
    "$BEAGLE_API_HELPER" \
      --host "$1" \
      --scheme "$2" \
      --port "$3" \
      --verify-tls "$4" \
      --username "$5" \
      --password "$6" \
      list-vms-json
}

show_current_preset_summary() {
  local summary=""
  if [[ "${EUID}" -eq 0 ]] || have_passwordless_sudo; then
    summary="$(run_installer_as_root --print-preset-summary 2>/dev/null || true)"
  else
    summary="$(run_installer_command --print-preset-summary 2>/dev/null || true)"
  fi
  [[ -n "$summary" ]] || summary="No VM preset is currently cached or bundled."
  dialog_msgbox "Current Preset" "$summary"
}

has_bundled_preset() {
  local payload=""
  if [[ "${EUID}" -eq 0 ]] || have_passwordless_sudo; then
    payload="$(run_installer_as_root --print-preset-json 2>/dev/null || true)"
  else
    payload="$(run_installer_command --print-preset-json 2>/dev/null || true)"
  fi
  [[ -n "$payload" ]] || return 1

  python3 - "$payload" <<'PY'
import json
import sys

try:
    payload = json.loads(sys.argv[1])
except Exception:
    raise SystemExit(1)

raise SystemExit(0 if payload.get("preset_active") else 1)
PY
}

resolve_auto_target_disk() {
  local debug_json=""
  local targets_json=""

  debug_json="$(run_installer_as_root --print-debug-json 2>/dev/null || true)"
  targets_json="$(run_installer_as_root --list-targets-json 2>/dev/null || true)"

  [[ -n "$targets_json" ]] || return 1

  python3 - "$debug_json" "$targets_json" <<'PY'
import json
import re
import sys

try:
    debug = json.loads(sys.argv[1]) if sys.argv[1] else {}
except Exception:
    debug = {}

try:
    targets = json.loads(sys.argv[2]) if sys.argv[2] else []
except Exception:
    targets = []

live_disk = str(debug.get("live_disk") or "").strip()
if live_disk and not live_disk.startswith("/dev/"):
    live_disk = f"/dev/{live_disk}"

valid = []
for item in targets:
    device = str(item.get("device") or "").strip()
    if not device.startswith("/dev/"):
        continue
    if re.match(r"^/dev/(loop|sr|ram|zram|nbd)", device):
        continue
    if live_disk and device == live_disk:
        continue
    size = str(item.get("size") or "").strip().upper()
    if size in {"", "0", "0B"}:
        continue
    model = str(item.get("model") or "").strip()
    rm = str(item.get("removable") or "0").strip()
    tran = str(item.get("transport") or "").strip().lower()
    score = 0
    if rm != "1" and tran != "usb":
        score += 20
    if model:
        score += 2
    valid.append((score, device))

if not valid:
    raise SystemExit(1)

valid.sort(reverse=True)
print(valid[0][1])
PY
}

install_from_bundled_preset() {
  AUTO_INSTALL_LOCK_SKIPPED=0
  LAST_INSTALL_EXIT_CODE=0

  if ! has_bundled_preset; then
    LAST_INSTALL_EXIT_CODE=1
    return 1
  fi

  if ! have_passwordless_sudo; then
    dialog_msgbox "Missing Privileges" "Passwordless sudo is required for preset-based disk installation."
    LAST_INSTALL_EXIT_CODE=1
    return 1
  fi

  if ! acquire_auto_install_lock; then
    log_msg "bundled preset detected, but another auto install instance already holds the lock"
    log_msg "auto install runner is passive because another session already owns the lock"
    AUTO_INSTALL_LOCK_SKIPPED=1
    LAST_INSTALL_EXIT_CODE=1
    return 1
  fi

  log_msg "bundled preset detected, starting non-interactive preset-based install"
  AUTO_INSTALL_ACTIVE=1
  run_installer_as_root --cache-bundled-preset >/dev/null 2>&1 || true

  local target_disk=""
  target_disk="$(resolve_auto_target_disk || true)"
  if [[ -z "$target_disk" ]]; then
    log_msg "failed to resolve auto target disk for bundled preset install"
    LAST_INSTALL_EXIT_CODE=1
    sync_logs_to_medium
    return 1
  fi
  log_msg "resolved bundled preset install target disk: $target_disk"

  set +e
  run_installer_as_root --target-disk "$target_disk" --yes --auto-install
  LAST_INSTALL_EXIT_CODE=$?
  set -e
  sync_logs_to_medium
  return "$LAST_INSTALL_EXIT_CODE"
}

reboot_after_successful_install() {
  dialog_msgbox "Installation Complete" "Installation is complete. Remove the USB stick now. Press OK or ENTER to reboot."
  if [[ "${EUID}" -eq 0 ]]; then
    exec reboot
  fi
  if have_passwordless_sudo; then
    exec sudo -n reboot
  fi
}

choose_vm_from_json() {
  local vm_json="$1"
  local -a menu_items=()
  local selection=""

  if ! mapfile -t menu_items < <(python3 -c '
import json
import sys

payload = json.loads(sys.argv[1])
for vm in payload.get("vms", []):
    tag = f"{vm['vmid']}@{vm['node']}"
    label = f"{vm['name']} (node {vm['node']}, status {vm['status']})"
    print(tag)
    print(label)
  ' "$vm_json"
  ); then
    dialog_msgbox "Invalid Beagle Response" "The installer received an invalid VM list from the Beagle API helper."
    return 2
  fi

  if (( ${#menu_items[@]} == 0 )); then
    return 3
  fi

  selection="$(dialog_menu "Choose VM" "Select the VM that should be installed onto this thin client." "${menu_items[@]}")" || return 1
  printf '%s\n' "$selection"
}

prompt_manual_vm_selection() {
  local default_node="${1:-srv}"
  local node=""
  local vmid=""

  node="$(dialog_input "Beagle Node" "Enter the Beagle node name for the VM." "$default_node")" || return 1
  vmid="$(dialog_input "Beagle VMID" "Enter the VMID that should be installed onto this thin client." "100")" || return 1
  if [[ ! "$vmid" =~ ^[0-9]+$ ]]; then
    dialog_msgbox "Invalid VMID" "The VMID must be numeric."
    return 1
  fi
  printf '%s@%s\n' "$vmid" "$node"
}

install_from_beagle_vm() {
  local defaults_json=""
  local host=""
  local host_ip=""
  local effective_host=""
  local username=""
  local password=""
  local scheme="$DEFAULT_API_SCHEME"
  local port="$DEFAULT_API_PORT"
  local verify_tls="$DEFAULT_API_VERIFY_TLS"
  local vm_json=""
  local choice=""
  local vmid=""
  local node=""
  local err_file=""
  local summary=""
  local choice_rc=0

  defaults_json="$(default_api_settings_json)"
  host="$(printf '%s' "$defaults_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("host",""))')"
  host_ip="$(printf '%s' "$defaults_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("host_ip",""))')"
  username="$(printf '%s' "$defaults_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("username",""))')"
  scheme="$(printf '%s' "$defaults_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("scheme","https"))')"
  port="$(printf '%s' "$defaults_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("port","8006"))')"
  verify_tls="$(printf '%s' "$defaults_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("verify_tls","0"))')"

  configure_network_access || return 1

  if [[ -z "$host" ]]; then
    host="$(dialog_input "Beagle Host" "Enter the Beagle host name or IP address." "$host")" || return 1
  fi
  if [[ -z "$host_ip" ]] && ! is_ip_literal "$host"; then
    host_ip="$(resolve_ipv4_address "$host" 2>/dev/null || true)"
  fi
  username="$(dialog_input "Beagle Login" "Log in to ${host} as user@realm." "$username")" || return 1
  password="$(dialog_password "Beagle Password" "Enter the Beagle password for ${username} on ${host}.")" || return 1
  effective_host="$(effective_api_host "$host" "$host_ip" || true)"
  if [[ -z "$effective_host" ]]; then
    log_network_snapshot "dns-resolution-failed"
    dialog_msgbox "Beagle Host Unreachable" "The installer has network connectivity, but DNS cannot resolve ${host}. Reconfigure the network or use an IP-based host entry."
    NETWORK_SETUP_COMPLETE=0
    return 1
  fi

  save_login_defaults "$scheme" "$host" "$host_ip" "$port" "$verify_tls" "$username"
  err_file="$(mktemp)"
  if ! vm_json="$(list_beagle_vms_json_direct \
      "$effective_host" \
      "$scheme" \
      "$port" \
      "$verify_tls" \
      "$username" \
      "$password" 2>"$err_file")"; then
    dialog_msgbox "Beagle Login Failed" "$(sed -n '1,30p' "$err_file" 2>/dev/null || printf 'Unable to contact Beagle API.')"
    rm -f "$err_file"
    return 1
  fi
  rm -f "$err_file"

  set +e
  choice="$(choose_vm_from_json "$vm_json")"
  choice_rc=$?
  set -e
  if (( choice_rc != 0 )); then
    if (( choice_rc == 2 || choice_rc == 3 )); then
      dialog_msgbox "Manual VM Selection" "Automatic VM listing failed or returned no visible QEMU VMs. Enter the target node and VMID directly."
      choice="$(prompt_manual_vm_selection "srv")" || return 1
    else
      return 1
    fi
  fi
  vmid="${choice%@*}"
  node="${choice#*@}"
  [[ -n "$vmid" && -n "$node" ]] || {
    dialog_msgbox "Invalid Selection" "The VM selection could not be parsed."
    return 1
  }

  run_installer_as_root --clear-cached-preset >/dev/null
  err_file="$(mktemp)"
  if ! run_installer_as_root \
      --cache-beagle-vm-preset \
      --beagle-api-host "$effective_host" \
      --beagle-api-scheme "$scheme" \
      --beagle-api-port "$port" \
      --beagle-api-verify-tls "$verify_tls" \
      --beagle-api-username "$username" \
      --beagle-api-password "$password" \
      --beagle-api-node "$node" \
      --beagle-api-vmid "$vmid" > /dev/null 2>"$err_file"; then
    dialog_msgbox "Preset Build Failed" "$(sed -n '1,30p' "$err_file" 2>/dev/null || printf 'Unable to build VM preset from Beagle.')"
    rm -f "$err_file"
    return 1
  fi
  rm -f "$err_file"

  summary="$(run_installer_command --print-preset-summary 2>/dev/null || true)"
  if [[ -n "$summary" ]]; then
    dialog_msgbox "VM Preset Loaded" "$summary"
  fi

  run_installer_as_root
}

install_manual_profile() {
  run_installer_as_root --clear-cached-preset >/dev/null
  run_installer_as_root
}

main_menu() {
  local answer=""
  local action_label="Retry preset detection + install"
  if have_tui_dialog; then
    local menu_text="Bundled VM preset detected. The profile is preloaded, but you must choose the target disk before installation starts."
    if [[ "$BUNDLED_PRESET_MODE" != "1" ]]; then
      menu_text="No bundled VM preset found. Re-plug USB stick or recreate it with a VM-specific installer package."
    else
      action_label="Start preset installation"
    fi
    run_whiptail \
      --title "Beagle OS Installer" \
      --menu "$menu_text" 20 90 8 \
      "1" "$action_label" \
      "2" "Set up network" \
      "3" "Show current preset" \
      "4" "Open shell" \
      "5" "Reboot" \
      "6" "Power off"
    return 0
  fi

  [[ -n "$TTY_PATH" ]] || return 1
  {
    printf '\n[Beagle OS Installer]\n'
    if [[ "$BUNDLED_PRESET_MODE" == "1" ]]; then
      printf 'Bundled VM preset detected. The profile is preloaded, but you must choose the target disk before installation starts.\n'
      action_label="Start preset installation"
    else
      printf 'No bundled VM preset found. Recreate the USB stick with a VM-specific installer package.\n'
    fi
    printf '1) %s\n' "$action_label"
    printf '2) Set up network\n'
    printf '3) Show current preset\n'
    printf '4) Open shell\n'
    printf '5) Reboot\n'
    printf '6) Power off\n'
    printf 'Choice: '
  } >"$TTY_PATH"
  read -r answer <"$TTY_PATH" || return 1
  printf '%s\n' "$answer"
}

setup_logging
log_msg "starting live menu"

if has_bundled_preset; then
  BUNDLED_PRESET_MODE=1
  log_msg "bundled preset detected; waiting for operator confirmation before installation"
fi

while true; do
  choice="$(main_menu || true)"
  log_msg "main menu selection: ${choice:-<empty>}"
  case "$choice" in
    1)
      if has_bundled_preset; then
        BUNDLED_PRESET_MODE=1
        if install_from_bundled_preset; then
          reboot_after_successful_install
        elif [[ "$LAST_INSTALL_EXIT_CODE" == "130" ]]; then
          log_msg "preset-based installation was cancelled by the operator"
        elif [[ "$AUTO_INSTALL_LOCK_SKIPPED" != "1" ]]; then
          detail=""
          detail="$(tail -n 20 "$LOG_DIR/local-installer.log" 2>/dev/null | tr -d '\r' || true)"
          [[ -n "$detail" ]] || detail="Preset-based installation failed. Check logs on the USB stick under pve-thin-client/logs."
          dialog_msgbox "Preset Install Failed" "$detail"
        fi
      else
        BUNDLED_PRESET_MODE=0
        dialog_msgbox "No Bundled Preset Found" "No bundled VM preset is available on this USB stick. Recreate the stick from the VM-specific installer package."
      fi
      ;;
    2)
      configure_network_access || true
      ;;
    3)
      show_current_preset_summary
      ;;
    4)
      exec "${SHELL:-/bin/bash}"
    ;;
    5)
      if [[ "${EUID}" -eq 0 ]]; then
        exec reboot
      fi
      if have_passwordless_sudo; then
        exec sudo -n reboot
      fi
      dialog_msgbox "Missing Privileges" "Passwordless sudo is required to reboot from the installer menu."
      ;;
    6)
      if [[ "${EUID}" -eq 0 ]]; then
        exec poweroff
      fi
      if have_passwordless_sudo; then
        exec sudo -n poweroff
      fi
      dialog_msgbox "Missing Privileges" "Passwordless sudo is required to power off from the installer menu."
      ;;
  esac
done
