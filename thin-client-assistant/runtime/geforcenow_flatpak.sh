#!/usr/bin/env bash

gfn_flatpak_bin() {
  printf '%s\n' "${BEAGLE_FLATPAK_BIN:-flatpak}"
}

resolve_gfn_install_scope() {
  case "${GFN_INSTALL_SCOPE}" in
    user|--user|"")
      printf '%s\n' "--user"
      ;;
    system|--system)
      printf '%s\n' "--system"
      ;;
    *)
      echo "Unsupported GeForce NOW install scope: ${GFN_INSTALL_SCOPE}" >&2
      exit 1
      ;;
  esac
}

run_gfn_cmd() {
  if [[ "${GFN_DRY_RUN:-0}" == "1" ]]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi

  "$@"
}

gfn_flatpak_is_installed() {
  local ref="$1"
  local flatpak_cmd

  flatpak_cmd="$(gfn_flatpak_bin)"
  "$flatpak_cmd" info "$GFN_INSTALL_SCOPE" "$ref" >/dev/null 2>&1
}

ensure_gfn_flatpak_available() {
  local flatpak_cmd

  flatpak_cmd="$(gfn_flatpak_bin)"
  if command -v "$flatpak_cmd" >/dev/null 2>&1; then
    return 0
  fi

  if [[ "${GFN_DRY_RUN:-0}" == "1" ]]; then
    echo "# flatpak is not installed on this machine; continuing because this is a dry-run"
    return 0
  fi

  echo "flatpak is not installed in this Beagle OS image." >&2
  return 1
}

ensure_gfn_install_scope_permissions() {
  if [[ "$GFN_INSTALL_SCOPE" == "--system" && "$(id -u)" != "0" ]]; then
    echo "System-wide GeForce NOW installation requires root." >&2
    return 1
  fi
}

ensure_gfn_flatpak_installation() {
  local flatpak_cmd

  flatpak_cmd="$(gfn_flatpak_bin)"
  ensure_gfn_flatpak_available || return 1
  run_gfn_cmd "$flatpak_cmd" remote-add "$GFN_INSTALL_SCOPE" --if-not-exists "$FLATHUB_REMOTE_NAME" "$FLATHUB_REMOTE_URL"
  run_gfn_cmd "$flatpak_cmd" remote-add "$GFN_INSTALL_SCOPE" --if-not-exists "$GFN_REMOTE_NAME" "$GFN_REMOTE_URL"
  if gfn_flatpak_is_installed "$GFN_RUNTIME_REF"; then
    beagle_log_event "gfn.install.cached-runtime" "ref=${GFN_RUNTIME_REF}"
  else
    run_gfn_cmd "$flatpak_cmd" install -y "$GFN_INSTALL_SCOPE" "$FLATHUB_REMOTE_NAME" "$GFN_RUNTIME_REF"
  fi
  if gfn_flatpak_is_installed "$GFN_APP_ID"; then
    beagle_log_event "gfn.install.cached-app" "app_id=${GFN_APP_ID}"
  else
    run_gfn_cmd "$flatpak_cmd" install -y "$GFN_INSTALL_SCOPE" "$GFN_REMOTE_NAME" "$GFN_APP_ID"
  fi
}
