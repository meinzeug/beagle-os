#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALLER="$SCRIPT_DIR/pve-thin-client-local-installer.sh"
LIVE_MEDIUM="${LIVE_MEDIUM:-/run/live/medium}"
PRESET_FILE="${LIVE_MEDIUM}/pve-thin-client/preset.env"

ensure_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi

  if command -v sudo >/dev/null 2>&1; then
    exec sudo "$0" "$@"
  fi

  echo "This action requires root privileges and sudo is unavailable." >&2
  exit 1
}

menu_prompt() {
  local action_two_label="Open setup questionnaire only"

  if [[ -f "$PRESET_FILE" ]]; then
    action_two_label="Show bundled VM preset"
  fi

  if command -v whiptail >/dev/null 2>&1; then
    whiptail --title "PVE Thin Client Installer" --menu \
      "Select an action" 18 88 8 \
      "1" "Install thin client to local disk" \
      "2" "$action_two_label" \
      "3" "Open shell" \
      "4" "Reboot" \
      "5" "Power off" \
      3>&1 1>&2 2>&3
    return 0
  fi

  echo "1) Install thin client to local disk"
  echo "2) $action_two_label"
  echo "3) Open shell"
  echo "4) Reboot"
  echo "5) Power off"
  read -r -p "Choice: " answer
  printf '%s\n' "$answer"
}

while true; do
  choice="$(menu_prompt || true)"
  case "$choice" in
    1)
      ensure_root "$@"
      exec "$INSTALLER"
      ;;
    2)
      if [[ -f "$PRESET_FILE" ]]; then
        summary="$("$INSTALLER" --print-preset-summary)"
        if command -v whiptail >/dev/null 2>&1; then
          whiptail --title "Bundled VM Preset" --msgbox "$summary" 16 88
        else
          printf '%s\n' "$summary"
          read -r -p "Press ENTER to continue. " _
        fi
      else
        "$ROOT_DIR/installer/setup-menu.sh" >/tmp/pve-thin-client-profile.env
        cat /tmp/pve-thin-client-profile.env
        read -r -p "Saved questionnaire to /tmp/pve-thin-client-profile.env. Press ENTER to continue. " _
      fi
      ;;
    3)
      exec "${SHELL:-/bin/bash}"
      ;;
    4)
      ensure_root "$@"
      reboot
      ;;
    5)
      ensure_root "$@"
      poweroff
      ;;
  esac
done
