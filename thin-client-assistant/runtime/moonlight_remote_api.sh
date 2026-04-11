#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOONLIGHT_MANAGER_REGISTRATION_SH="${MOONLIGHT_MANAGER_REGISTRATION_SH:-$SCRIPT_DIR/moonlight_manager_registration.sh}"
# shellcheck disable=SC1090
source "$MOONLIGHT_MANAGER_REGISTRATION_SH"

moonlight_curl_bin() {
  printf '%s\n' "${BEAGLE_CURL_BIN:-curl}"
}

moonlight_hostname_value() {
  local hostname_bin="${BEAGLE_HOSTNAME_BIN:-hostname}"

  if [[ -n "${PVE_THIN_CLIENT_HOSTNAME:-}" ]]; then
    printf '%s\n' "${PVE_THIN_CLIENT_HOSTNAME}"
    return 0
  fi

  "$hostname_bin"
}

moonlight_client_device_name() {
  printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_CLIENT_NAME:-$(moonlight_hostname_value)}"
}

json_bool() {
  local payload="$1"
  python3 - "$payload" <<'PY'
import json
import sys

try:
    data = json.loads(sys.argv[1] or "{}")
except json.JSONDecodeError:
    raise SystemExit(1)

print("1" if bool(data.get("status")) else "0")
PY
}

submit_sunshine_pin() {
  local api_url username password pin name response
  local curl_bin
  local -a curl_args tls_args

  api_url="$(selected_sunshine_api_url)"
  username="${PVE_THIN_CLIENT_SUNSHINE_USERNAME:-}"
  password="${PVE_THIN_CLIENT_SUNSHINE_PASSWORD:-}"
  pin="${PVE_THIN_CLIENT_SUNSHINE_PIN:-}"
  name="$(moonlight_client_device_name)"

  [[ -n "$api_url" && -n "$username" && -n "$password" && -n "$pin" ]] || return 1

  curl_bin="$(moonlight_curl_bin)"
  curl_args=("$curl_bin" -fsS --connect-timeout 2 --max-time 4 --user "${username}:${password}" -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "$api_url" "${PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY:-}" "${PVE_THIN_CLIENT_SUNSHINE_CA_CERT:-}")
  curl_args+=("${tls_args[@]}")

  response="$(
    "${curl_args[@]}" \
      --data "{\"pin\":\"${pin}\",\"name\":\"${name}\"}" \
      "${api_url%/}/api/pin"
  )" || return 1

  [[ "$(json_bool "$response")" == "1" ]]
}
