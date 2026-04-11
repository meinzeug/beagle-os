#!/usr/bin/env bash

detect_xauthority() {
  local auth_candidate=""

  auth_candidate="$(
    ps -eo args= 2>/dev/null | awk '
      /[X]org/ && /(^|[[:space:]]):0($|[[:space:]])/ {
        for (i = 1; i <= NF; i++) {
          if ($i == "-auth" && (i + 1) <= NF) {
            print $(i + 1)
            exit
          }
        }
      }
    '
  )"
  if [[ -n "$auth_candidate" && -r "$auth_candidate" ]]; then
    printf '%s\n' "$auth_candidate"
    return 0
  fi

  if [[ -n "${XAUTHORITY:-}" && -r "${XAUTHORITY}" ]]; then
    printf '%s\n' "${XAUTHORITY}"
    return 0
  fi

  auth_candidate="${HOME:-/home/thinclient}/.Xauthority"
  if [[ -r "$auth_candidate" ]]; then
    printf '%s\n' "$auth_candidate"
    return 0
  fi

  auth_candidate="$(find /tmp -maxdepth 1 -type f -name 'serverauth.*' 2>/dev/null | head -n 1 || true)"
  printf '%s\n' "${auth_candidate:-${HOME:-/home/thinclient}/.Xauthority}"
}

x_display_ready() {
  local auth_candidate="${1:-${XAUTHORITY:-}}"

  [[ -n "${DISPLAY:-}" ]] || return 1
  [[ -n "$auth_candidate" && -r "$auth_candidate" ]] || return 1
  command -v xset >/dev/null 2>&1 || return 0

  DISPLAY="$DISPLAY" XAUTHORITY="$auth_candidate" xset q >/dev/null 2>&1
}

select_xauthority() {
  local home_candidate detected_candidate candidate
  local -a candidates=()
  declare -A seen=()

  home_candidate="${HOME:-/home/${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}}/.Xauthority"
  detected_candidate="$(detect_xauthority 2>/dev/null || true)"

  for candidate in \
    "${XAUTHORITY:-}" \
    "$home_candidate" \
    "$detected_candidate"
  do
    [[ -n "$candidate" && -r "$candidate" ]] || continue
    [[ -n "${seen[$candidate]:-}" ]] && continue
    candidates+=("$candidate")
    seen["$candidate"]=1
  done

  while IFS= read -r candidate; do
    [[ -n "$candidate" && -r "$candidate" ]] || continue
    [[ -n "${seen[$candidate]:-}" ]] && continue
    candidates+=("$candidate")
    seen["$candidate"]=1
  done < <(find /tmp -maxdepth 1 -type f -name 'serverauth.*' 2>/dev/null | sort || true)

  if ((${#candidates[@]} == 0)); then
    printf '%s\n' "$home_candidate"
    return 0
  fi

  for candidate in "${candidates[@]}"; do
    if x_display_ready "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  printf '%s\n' "${candidates[0]}"
}

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
