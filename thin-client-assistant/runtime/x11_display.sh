#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
X11_DISPLAY_SELECTION_SH="${X11_DISPLAY_SELECTION_SH:-$SCRIPT_DIR/x11_display_selection.sh}"
# shellcheck disable=SC1090
source "$X11_DISPLAY_SELECTION_SH"

wait_for_x_display_selected() {
  local auth_candidate="${1:-${XAUTHORITY:-}}"
  local ready_phase="${2:-}"
  local unready_phase="${3:-}"
  local attempts attempt

  attempts="${PVE_THIN_CLIENT_X11_READY_RETRIES:-20}"

  if ! command -v xset >/dev/null 2>&1; then
    return 0
  fi

  for attempt in $(seq 1 "$attempts"); do
    if DISPLAY="$DISPLAY" XAUTHORITY="$auth_candidate" xset q >/dev/null 2>&1; then
      if [[ -n "$ready_phase" ]]; then
        beagle_log_event "$ready_phase" "display=${DISPLAY:-UNSET} xauthority=$auth_candidate attempt=${attempt}"
      fi
      return 0
    fi
    sleep 1
  done

  if [[ -n "$unready_phase" ]]; then
    beagle_log_event "$unready_phase" "display=${DISPLAY:-UNSET} xauthority=${auth_candidate:-UNSET}"
  fi
  return 1
}

wait_for_x_display() {
  local ready_phase="${1:-}"
  local unready_phase="${2:-}"
  local attempts attempt selected_auth

  attempts="${PVE_THIN_CLIENT_X11_READY_RETRIES:-20}"
  for attempt in $(seq 1 "$attempts"); do
    selected_auth="$(select_xauthority)"
    export XAUTHORITY="$selected_auth"
    if x_display_ready "$selected_auth"; then
      if [[ -n "$ready_phase" ]]; then
        beagle_log_event "$ready_phase" "display=${DISPLAY:-UNSET} xauthority=$selected_auth attempt=${attempt}"
      fi
      return 0
    fi
    sleep 1
  done

  if [[ -n "$unready_phase" ]]; then
    beagle_log_event "$unready_phase" "display=${DISPLAY:-UNSET} xauthority=${XAUTHORITY:-UNSET}"
  fi
  return 1
}
