#!/usr/bin/env bash

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

build_moonlight_manager_registration_payload() {
  local client_cert="${1:-}"
  local device_name="${2:-}"

  python3 - "$client_cert" "$device_name" <<'PY'
import json
import sys

print(json.dumps({
    "client_cert_pem": sys.argv[1],
    "device_name": sys.argv[2],
}))
PY
}

register_moonlight_client_via_manager() {
  local manager_url manager_token manager_pin manager_ca_cert device_name client_cert response_file payload_file http_status
  local curl_bin
  local -a curl_args tls_args

  manager_url="${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}"
  manager_token="${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}"
  manager_pin="${PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  manager_ca_cert="${PVE_THIN_CLIENT_BEAGLE_MANAGER_CA_CERT:-}"
  device_name="$(moonlight_client_device_name)"

  [[ -n "$manager_url" && -n "$manager_token" ]] || return 1
  client_cert="$(extract_moonlight_certificate_pem 2>/dev/null || true)"
  [[ -n "$client_cert" ]] || return 1

  response_file="$(mktemp)"
  payload_file="$(mktemp)"
  curl_bin="$(moonlight_curl_bin)"
  curl_args=("$curl_bin" -fsS --connect-timeout 6 --max-time 30 --output "$response_file" --write-out '%{http_code}' \
    -H "Authorization: Bearer ${manager_token}" \
    -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "${manager_url%/}/api/v1/endpoints/moonlight/register" "$manager_pin" "$manager_ca_cert")
  curl_args+=("${tls_args[@]}")

  build_moonlight_manager_registration_payload "$client_cert" "$device_name" >"$payload_file"

  http_status="$(
    "${curl_args[@]}" --data-binary "@${payload_file}" "${manager_url%/}/api/v1/endpoints/moonlight/register" || true
  )"
  if [[ "$http_status" != "201" ]]; then
    rm -f "$payload_file"
    rm -f "$response_file"
    return 1
  fi
  if ! sync_moonlight_host_from_manager_response "$response_file"; then
    rm -f "$payload_file"
    rm -f "$response_file"
    return 1
  fi
  rm -f "$payload_file"
  rm -f "$response_file"
  return 0
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
