#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_PREPARE_FLOW_SH="${RUNTIME_PREPARE_FLOW_SH:-$SCRIPT_DIR/runtime_prepare_flow.sh}"
RUNTIME_CONFIG_PERSISTENCE_SH="${RUNTIME_CONFIG_PERSISTENCE_SH:-$SCRIPT_DIR/runtime_config_persistence.sh}"
APPLY_NETWORK_CONFIG_SH="${APPLY_NETWORK_CONFIG_SH:-$SCRIPT_DIR/apply-network-config.sh}"
RUNTIME_NETWORK_RUNTIME_SH="${RUNTIME_NETWORK_RUNTIME_SH:-$SCRIPT_DIR/runtime_network_runtime.sh}"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"
# shellcheck disable=SC1090
source "$RUNTIME_PREPARE_FLOW_SH"
# shellcheck disable=SC1090
source "$RUNTIME_CONFIG_PERSISTENCE_SH"
# shellcheck disable=SC1090
source "$RUNTIME_NETWORK_RUNTIME_SH"

TTY_PATH="${BEAGLE_NETWORK_TUI_TTY:-/dev/tty1}"
NETWORK_CHOICE_FILE="${BEAGLE_NETWORK_CHOICE_FILE:-/run/pve-thin-client/network-choice.env}"
DEFAULT_DNS_SERVERS="${PVE_THIN_CLIENT_DEFAULT_DNS_SERVERS:-1.1.1.1 9.9.9.9 8.8.8.8}"
BANNER_TIMEOUT_SECONDS="${BEAGLE_NETWORK_TUI_TIMEOUT_SECONDS:-3}"

have_tui_dialog() {
  [[ -n "$TTY_PATH" && -e "$TTY_PATH" ]] && command -v whiptail >/dev/null 2>&1
}

run_whiptail() {
  local tty_path="$TTY_PATH"
  whiptail "$@" --output-fd 3 \
    3>&1 1>"$tty_path" 2>"$tty_path" <"$tty_path"
}

dialog_msgbox() {
  local title="$1"
  local message="$2"
  if have_tui_dialog; then
    run_whiptail --title "$title" --msgbox "$message" 12 78 || true
  else
    printf '\n[%s]\n%s\nPress ENTER to continue. ' "$title" "$message" >"$TTY_PATH"
    read -r _ <"$TTY_PATH" || true
  fi
}

dialog_menu() {
  local title="$1"
  local message="$2"
  shift 2
  if have_tui_dialog; then
    run_whiptail --title "$title" --menu "$message" 20 86 10 "$@"
    return
  fi

  local answer="" key="" label="" index=1
  {
    printf '\n[%s]\n%s\n\n' "$title" "$message"
    while [[ "$#" -gt 0 ]]; do
      key="$1"; label="$2"; shift 2
      printf '%s) %s [%s]\n' "$index" "$label" "$key"
      index=$((index + 1))
    done
    printf 'Choice: '
  } >"$TTY_PATH"
  read -r answer <"$TTY_PATH" || return 1
  printf '%s\n' "$answer"
}

dialog_input() {
  local title="$1"
  local message="$2"
  local default_value="${3:-}"
  if have_tui_dialog; then
    run_whiptail --title "$title" --inputbox "$message" 12 78 "$default_value"
    return
  fi
  printf '\n[%s]\n%s\n> ' "$title" "$message" >"$TTY_PATH"
  read -r default_value <"$TTY_PATH" || return 1
  printf '%s\n' "$default_value"
}

dialog_password() {
  local title="$1"
  local message="$2"
  local value=""
  if have_tui_dialog; then
    run_whiptail --title "$title" --passwordbox "$message" 12 78
    return
  fi
  printf '\n[%s]\n%s\n> ' "$title" "$message" >"$TTY_PATH"
  read -r value <"$TTY_PATH" || return 1
  printf '%s\n' "$value"
}

network_choice_summary() {
  local type="${PVE_THIN_CLIENT_NETWORK_TYPE:-ethernet}"
  local iface="${PVE_THIN_CLIENT_NETWORK_INTERFACE:-auto}"
  local ssid="${PVE_THIN_CLIENT_WIFI_SSID:-}"
  if [[ "$type" == "wifi" ]]; then
    printf 'WLAN %s ueber %s' "${ssid:-<ohne SSID>}" "$iface"
  else
    printf 'Ethernet ueber %s' "$iface"
  fi
}

network_choice_is_present() {
  [[ "${PVE_THIN_CLIENT_NETWORK_CHOICE_CONFIRMED:-0}" == "1" ]] || return 1
  [[ -n "${PVE_THIN_CLIENT_NETWORK_INTERFACE:-}" ]] || return 1
  case "${PVE_THIN_CLIENT_NETWORK_TYPE:-ethernet}" in
    ethernet) return 0 ;;
    wifi) [[ -n "${PVE_THIN_CLIENT_WIFI_SSID:-}" ]] ;;
    *) return 1 ;;
  esac
}

show_reconfigure_banner() {
  local summary="$1"
  local key=""
  {
    printf '\033c'
    printf '\n'
    printf '#######################################################################\n'
    printf '#                                                                     #\n'
    printf '#                  BEAGLE OS LIVE NETZWERK                            #\n'
    printf '#                                                                     #\n'
    printf '#######################################################################\n'
    printf '\n'
    printf 'Gespeicherte Auswahl: %s\n' "$summary"
    printf '\n'
    printf 'Druecke N innerhalb von %s Sekunden, um Ethernet/WLAN neu auszuwaehlen.\n' "$BANNER_TIMEOUT_SECONDS"
    printf 'Ohne Eingabe startet Beagle OS mit der gespeicherten Auswahl.\n'
    printf '\n'
  } >"$TTY_PATH"

  if read -r -s -n 1 -t "$BANNER_TIMEOUT_SECONDS" key <"$TTY_PATH"; then
    case "$key" in
      n|N) return 0 ;;
    esac
  fi
  return 1
}

network_env_quote() {
  python3 - "$1" <<'PY'
import sys
value = sys.argv[1]
print("'" + value.replace("'", "'\"'\"'") + "'")
PY
}

wired_interfaces() {
  local iface sys_class_net
  sys_class_net="${BEAGLE_SYS_CLASS_NET_DIR:-/sys/class/net}"
  for iface in "$sys_class_net"/*; do
    iface="$(basename "$iface")"
    [[ "$iface" == "lo" ]] && continue
    [[ -d "$sys_class_net/$iface/wireless" ]] && continue
    case "$iface" in
      docker*|virbr*|veth*|br-*|tun*|tap*|wg*|zt*|vmnet*|tailscale*) continue ;;
    esac
    printf '%s\n' "$iface"
  done
}

wifi_interfaces() {
  local iface sys_class_net
  sys_class_net="${BEAGLE_SYS_CLASS_NET_DIR:-/sys/class/net}"
  for iface in "$sys_class_net"/*; do
    iface="$(basename "$iface")"
    [[ "$iface" == "lo" ]] && continue
    [[ -d "$sys_class_net/$iface/wireless" ]] || continue
    printf '%s\n' "$iface"
  done
}

choose_interface() {
  local title="$1"
  local message="$2"
  shift 2
  local -a interfaces=("$@")
  local -a menu_items=()
  local iface choice
  if (( ${#interfaces[@]} == 0 )); then
    return 1
  fi
  if (( ${#interfaces[@]} == 1 )); then
    printf '%s\n' "${interfaces[0]}"
    return 0
  fi
  for iface in "${interfaces[@]}"; do
    menu_items+=("$iface" "MAC $(cat "${BEAGLE_SYS_CLASS_NET_DIR:-/sys/class/net}/$iface/address" 2>/dev/null || printf 'unknown')")
  done
  choice="$(dialog_menu "$title" "$message" "${menu_items[@]}")" || return 1
  if [[ "$choice" =~ ^[0-9]+$ ]]; then
    printf '%s\n' "${interfaces[$((choice - 1))]}"
  else
    printf '%s\n' "$choice"
  fi
}

scan_wifi_ssids() {
  local iface="$1"
  ip link set "$iface" up >/dev/null 2>&1 || true
  rfkill unblock wifi >/dev/null 2>&1 || true
  iw dev "$iface" scan 2>/dev/null | awk -F'SSID: ' '/SSID: / {print $2}' | sed '/^$/d' | awk '!seen[$0]++'
}

choose_wifi_ssid() {
  local iface="$1"
  local -a ssids=()
  local -a menu_items=()
  local ssid choice index=1
  mapfile -t ssids < <(scan_wifi_ssids "$iface" | sed -n '1,20p')
  if (( ${#ssids[@]} == 0 )); then
    dialog_input "WLAN SSID" "Keine WLANs gefunden. SSID manuell eingeben." ""
    return
  fi
  for ssid in "${ssids[@]}"; do
    menu_items+=("ssid-$index" "$ssid")
    index=$((index + 1))
  done
  menu_items+=("manual" "Verstecktes/anderes WLAN")
  choice="$(dialog_menu "WLAN auswaehlen" "Waehle das WLAN fuer Beagle OS Live." "${menu_items[@]}")" || return 1
  if [[ "$choice" =~ ^[0-9]+$ ]]; then
    choice="ssid-$choice"
  fi
  if [[ "$choice" == "manual" ]]; then
    dialog_input "WLAN SSID" "SSID eingeben." ""
    return
  fi
  index="${choice#ssid-}"
  [[ "$index" =~ ^[0-9]+$ ]] || return 1
  printf '%s\n' "${ssids[$((index - 1))]}"
}

write_network_choice() {
  local type="$1"
  local iface="$2"
  local ssid="${3:-}"
  local password="${4:-}"
  local target_dir network_file

  target_dir="${CONFIG_DIR:-$(runtime_system_config_dir)}"
  install -d -m 0755 "$target_dir" "$(dirname "$NETWORK_CHOICE_FILE")"
  network_file="$target_dir/network.env"
  {
    printf 'NETWORK_MODE=dhcp\n'
    printf 'INTERFACE=%s\n' "$(network_env_quote "$iface")"
    printf 'PVE_THIN_CLIENT_NETWORK_MODE=dhcp\n'
    printf 'PVE_THIN_CLIENT_NETWORK_INTERFACE=%s\n' "$(network_env_quote "$iface")"
    printf 'PVE_THIN_CLIENT_NETWORK_TYPE=%s\n' "$(network_env_quote "$type")"
    printf 'PVE_THIN_CLIENT_NETWORK_CHOICE_CONFIRMED=1\n'
    printf 'PVE_THIN_CLIENT_NETWORK_DNS_SERVERS=%s\n' "$(network_env_quote "$DEFAULT_DNS_SERVERS")"
    if [[ "$type" == "wifi" ]]; then
      printf 'PVE_THIN_CLIENT_WIFI_SSID=%s\n' "$(network_env_quote "$ssid")"
      printf 'PVE_THIN_CLIENT_WIFI_PSK=%s\n' "$(network_env_quote "$password")"
    fi
  } >"$network_file"
  chmod 0600 "$network_file"
  persist_runtime_config_to_live_state "$target_dir" || true
  {
    printf 'PVE_THIN_CLIENT_NETWORK_TYPE=%s\n' "$(network_env_quote "$type")"
    printf 'PVE_THIN_CLIENT_NETWORK_CHOICE_CONFIRMED=1\n'
    printf 'PVE_THIN_CLIENT_NETWORK_INTERFACE=%s\n' "$(network_env_quote "$iface")"
    printf 'PVE_THIN_CLIENT_WIFI_SSID=%s\n' "$(network_env_quote "$ssid")"
  } >"$NETWORK_CHOICE_FILE"
  chmod 0600 "$NETWORK_CHOICE_FILE"
}

configure_ethernet() {
  local -a ifaces=()
  local iface
  mapfile -t ifaces < <(wired_interfaces)
  iface="$(choose_interface "Ethernet" "Kabelgebundene Schnittstelle auswaehlen." "${ifaces[@]}")" || return 1
  write_network_choice "ethernet" "$iface"
}

configure_wifi() {
  local -a ifaces=()
  local iface ssid password
  command -v iw >/dev/null 2>&1 && command -v wpa_supplicant >/dev/null 2>&1 && command -v wpa_passphrase >/dev/null 2>&1 || {
    dialog_msgbox "WLAN nicht verfuegbar" "Dieses Live-System enthaelt nicht alle WLAN-Tools."
    return 1
  }
  mapfile -t ifaces < <(wifi_interfaces)
  iface="$(choose_interface "WLAN" "WLAN-Adapter auswaehlen." "${ifaces[@]}")" || return 1
  ssid="$(choose_wifi_ssid "$iface")" || return 1
  [[ -n "$ssid" ]] || return 1
  password="$(dialog_password "WLAN Passwort" "Passwort fuer ${ssid}. Leer lassen fuer offenes WLAN.")" || return 1
  write_network_choice "wifi" "$iface" "$ssid" "$password"
}

main() {
  local -a items=()
  local choice=""
  local summary=""
  local configured_iface=""
  local configured_ipv4=""

  load_runtime_config_with_retry || true
  sync_runtime_config_to_system || true
  load_runtime_config_with_retry || true

  if network_choice_is_present; then
    summary="$(network_choice_summary)"
    if ! show_reconfigure_banner "$summary"; then
      "$APPLY_NETWORK_CONFIG_SH" || true
      persist_runtime_config_to_live_state || true
      return 0
    fi
  fi

  if wired_interfaces | grep -q .; then
    items+=("ethernet" "Ethernet/Kabel")
  fi
  if wifi_interfaces | grep -q .; then
    items+=("wifi" "WLAN verbinden")
  fi
  if (( ${#items[@]} == 0 )); then
    dialog_msgbox "Kein Netzwerkgeraet" "Es wurde weder Ethernet noch WLAN erkannt. Desktop startet trotzdem."
    return 0
  fi

  while true; do
    choice="$(dialog_menu "Beagle OS Netzwerk" "Vor dem Desktop/Beagle Stream Client muss die Netzwerkverbindung gewaehlt werden." "${items[@]}")" || {
      dialog_msgbox "Netzwerk erforderlich" "Bitte Ethernet oder WLAN auswaehlen. Beagle OS Live startet danach Desktop und Beagle Stream Client."
      continue
    }
    [[ "$choice" =~ ^[0-9]+$ ]] && choice="${items[$(((choice - 1) * 2))]}"
    case "$choice" in
      ethernet) configure_ethernet && break ;;
      wifi) configure_wifi && break ;;
      *) return 1 ;;
    esac
  done

  "$APPLY_NETWORK_CONFIG_SH" || {
    dialog_msgbox "Netzwerkfehler" "Die Netzwerkverbindung konnte nicht aktiviert werden. Bitte erneut versuchen."
    return 1
  }
  persist_runtime_config_to_live_state || true
  configured_iface="$(pick_interface 2>/dev/null || true)"
  configured_ipv4="$(current_ipv4_address "$configured_iface" 2>/dev/null || true)"
  if [[ -n "$configured_ipv4" ]]; then
    dialog_msgbox "Netzwerk bereit" "Netzwerk wurde konfiguriert.\n\nSchnittstelle: ${configured_iface}\nDHCP IPv4: ${configured_ipv4}\n\nBeagle OS startet jetzt den Desktop."
  else
    dialog_msgbox "Netzwerk bereit" "Netzwerk wurde konfiguriert, aber es wurde noch keine IPv4-Adresse erkannt.\n\nSchnittstelle: ${configured_iface:-unbekannt}\n\nBeagle OS startet jetzt den Desktop."
  fi
}

main "$@"
