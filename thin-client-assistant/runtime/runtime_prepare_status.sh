#!/usr/bin/env bash

runtime_status_dir() {
  printf '%s\n' "${STATUS_DIR:-/var/lib/pve-thin-client}"
}

runtime_status_file() {
  local status_dir
  status_dir="$(runtime_status_dir)"
  printf '%s\n' "${STATUS_FILE:-$status_dir/runtime.status}"
}

runtime_required_binary() {
  local boot_mode="${1:-${BOOT_MODE:-}}"

  if [[ "$boot_mode" == "installer" ]]; then
    printf '%s\n' "installer-mode"
    return 0
  fi

  case "${PVE_THIN_CLIENT_MODE:-MOONLIGHT}" in
    MOONLIGHT)
      printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_BIN:-moonlight}"
      ;;
    KIOSK)
      printf '%s\n' "/usr/local/sbin/beagle-kiosk-launch"
      ;;
    GFN)
      printf '%s\n' "flatpak"
      ;;
    *)
      echo "Unsupported mode for Beagle OS: ${PVE_THIN_CLIENT_MODE:-UNSET}" >&2
      return 1
      ;;
  esac
}

runtime_binary_available() {
  local required_binary="${1:-}"
  local boot_mode="${2:-${BOOT_MODE:-}}"

  if [[ "$boot_mode" == "installer" ]]; then
    printf '%s\n' "1"
    return 0
  fi

  if [[ "$required_binary" == */* ]]; then
    if [[ -x "$required_binary" ]]; then
      printf '%s\n' "1"
    else
      printf '%s\n' "0"
    fi
    return 0
  fi

  if command -v "$required_binary" >/dev/null 2>&1; then
    printf '%s\n' "1"
  else
    printf '%s\n' "0"
  fi
}

write_prepare_runtime_status() {
  local boot_mode="${1:-${BOOT_MODE:-}}"
  local required_binary="${2:-}"
  local binary_available="${3:-}"
  local status_dir status_file python_bin

  status_dir="$(runtime_status_dir)"
  status_file="$(runtime_status_file)"
  python_bin="$(runtime_python_bin)"

  [[ -n "$required_binary" ]] || required_binary="$(runtime_required_binary "$boot_mode")"
  [[ -n "$binary_available" ]] || binary_available="$(runtime_binary_available "$required_binary" "$boot_mode")"

  mkdir -p "$status_dir"
  chmod 0755 "$status_dir"

  "$python_bin" "$STATUS_WRITER_PY" runtime-status \
    --path "$status_file" \
    --boot-mode "$boot_mode" \
    --mode "${PVE_THIN_CLIENT_MODE:-UNSET}" \
    --runtime-user "${PVE_THIN_CLIENT_RUNTIME_USER:-UNSET}" \
    --connection-method "${PVE_THIN_CLIENT_CONNECTION_METHOD:-UNSET}" \
    --profile-name "${PVE_THIN_CLIENT_PROFILE_NAME:-UNSET}" \
    --required-binary "$required_binary" \
    --moonlight-host "${PVE_THIN_CLIENT_MOONLIGHT_HOST:-UNSET}" \
    --moonlight-app "${PVE_THIN_CLIENT_MOONLIGHT_APP:-Desktop}" \
    --binary-available "$binary_available" >/dev/null

  chmod 0644 "$status_file"
}
