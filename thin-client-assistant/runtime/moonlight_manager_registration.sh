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

build_moonlight_stream_prepare_payload() {
  local resolution="${1:-}"
  local app="${2:-Desktop}"

  python3 - "$resolution" "$app" <<'PY'
import json
import sys

print(json.dumps({
    "resolution": sys.argv[1],
    "app": sys.argv[2],
}))
PY
}

build_moonlight_pair_token_payload() {
  local device_name="${1:-}"

  python3 - "$device_name" <<'PY'
import json
import sys

print(json.dumps({
    "device_name": sys.argv[1],
}))
PY
}

build_moonlight_pair_exchange_payload() {
  local pairing_token="${1:-}"

  python3 - "$pairing_token" <<'PY'
import json
import sys

print(json.dumps({
    "pairing_token": sys.argv[1],
}))
PY
}

parse_moonlight_pair_token_response() {
  local response_file="${1:-}"

  python3 - "$response_file" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
pairing = payload.get("pairing") if isinstance(payload, dict) else {}
if not isinstance(pairing, dict):
    pairing = {}
token = str(pairing.get("token") or "").strip()
pin = str(pairing.get("pin") or "").strip()
expires_at = str(pairing.get("expires_at") or "").strip()
if not token or not pin:
    raise SystemExit(1)
print(token)
print(pin)
print(expires_at)
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

prepare_moonlight_stream_via_manager() {
  local resolution="${1:-}"
  local app="${2:-Desktop}"
  local manager_url manager_token manager_pin manager_ca_cert response_file payload_file http_status
  local curl_bin
  local -a curl_args tls_args

  [[ -n "$resolution" ]] || return 1
  [[ "$resolution" =~ ^[0-9]{3,5}x[0-9]{3,5}$ ]] || return 1

  manager_url="${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}"
  manager_token="${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}"
  manager_pin="${PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  manager_ca_cert="${PVE_THIN_CLIENT_BEAGLE_MANAGER_CA_CERT:-}"
  [[ -n "$manager_url" && -n "$manager_token" ]] || return 1

  response_file="$(mktemp)"
  payload_file="$(mktemp)"
  curl_bin="$(moonlight_curl_bin)"
  curl_args=("$curl_bin" -fsS --connect-timeout 6 --max-time 30 --output "$response_file" --write-out '%{http_code}' \
    -H "Authorization: Bearer ${manager_token}" \
    -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "${manager_url%/}/api/v1/endpoints/moonlight/prepare-stream" "$manager_pin" "$manager_ca_cert")
  curl_args+=("${tls_args[@]}")

  build_moonlight_stream_prepare_payload "$resolution" "$app" >"$payload_file"
  http_status="$(${curl_args[@]} --data-binary "@${payload_file}" "${manager_url%/}/api/v1/endpoints/moonlight/prepare-stream" || true)"

  rm -f "$payload_file"
  rm -f "$response_file"
  [[ "$http_status" == "200" ]]
}

request_moonlight_pairing_token_via_manager() {
  local manager_url manager_token manager_pin manager_ca_cert response_file payload_file http_status
  local curl_bin device_name
  local -a curl_args tls_args parsed

  manager_url="${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}"
  manager_token="${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}"
  manager_pin="${PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  manager_ca_cert="${PVE_THIN_CLIENT_BEAGLE_MANAGER_CA_CERT:-}"
  [[ -n "$manager_url" && -n "$manager_token" ]] || return 1

  device_name="$(moonlight_client_device_name)"
  response_file="$(mktemp)"
  payload_file="$(mktemp)"
  curl_bin="$(moonlight_curl_bin)"
  curl_args=("$curl_bin" -fsS --connect-timeout 6 --max-time 20 --output "$response_file" --write-out '%{http_code}' \
    -H "Authorization: Bearer ${manager_token}" \
    -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "${manager_url%/}/api/v1/endpoints/moonlight/pair-token" "$manager_pin" "$manager_ca_cert")
  curl_args+=("${tls_args[@]}")

  build_moonlight_pair_token_payload "$device_name" >"$payload_file"
  http_status="$(${curl_args[@]} --data-binary "@${payload_file}" "${manager_url%/}/api/v1/endpoints/moonlight/pair-token" || true)"
  if [[ "$http_status" != "201" ]]; then
    rm -f "$payload_file" "$response_file"
    return 1
  fi

  if ! mapfile -t parsed < <(parse_moonlight_pair_token_response "$response_file"); then
    rm -f "$payload_file" "$response_file"
    return 1
  fi
  rm -f "$payload_file" "$response_file"

  [[ "${#parsed[@]}" -ge 2 ]] || return 1
  export PVE_THIN_CLIENT_MOONLIGHT_PAIRING_TOKEN="${parsed[0]}"
  export PVE_THIN_CLIENT_MOONLIGHT_PAIRING_PIN="${parsed[1]}"
  export PVE_THIN_CLIENT_MOONLIGHT_PAIRING_EXPIRES_AT="${parsed[2]:-}"
  return 0
}

exchange_moonlight_pairing_token_via_manager() {
  local pairing_token="${1:-}"
  local manager_url manager_token manager_pin manager_ca_cert response_file payload_file http_status
  local curl_bin
  local -a curl_args tls_args

  [[ -n "$pairing_token" ]] || return 1
  manager_url="${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}"
  manager_token="${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}"
  manager_pin="${PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  manager_ca_cert="${PVE_THIN_CLIENT_BEAGLE_MANAGER_CA_CERT:-}"
  [[ -n "$manager_url" && -n "$manager_token" ]] || return 1

  response_file="$(mktemp)"
  payload_file="$(mktemp)"
  curl_bin="$(moonlight_curl_bin)"
  curl_args=("$curl_bin" -fsS --connect-timeout 6 --max-time 20 --output "$response_file" --write-out '%{http_code}' \
    -H "Authorization: Bearer ${manager_token}" \
    -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "${manager_url%/}/api/v1/endpoints/moonlight/pair-exchange" "$manager_pin" "$manager_ca_cert")
  curl_args+=("${tls_args[@]}")

  build_moonlight_pair_exchange_payload "$pairing_token" >"$payload_file"
  http_status="$(${curl_args[@]} --data-binary "@${payload_file}" "${manager_url%/}/api/v1/endpoints/moonlight/pair-exchange" || true)"

  rm -f "$payload_file" "$response_file"
  [[ "$http_status" == "200" ]]
}
