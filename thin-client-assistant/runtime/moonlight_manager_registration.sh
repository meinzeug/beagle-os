#!/usr/bin/env bash

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
