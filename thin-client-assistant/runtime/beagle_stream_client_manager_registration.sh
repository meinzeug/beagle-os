#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEAGLE_STREAM_CLIENT_CONFIG_STATE_SH="${BEAGLE_STREAM_CLIENT_CONFIG_STATE_SH:-$SCRIPT_DIR/beagle_stream_client_config_state.sh}"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_CONFIG_STATE_SH"

build_beagle_stream_client_manager_registration_payload() {
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

build_beagle_stream_client_stream_prepare_payload() {
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

build_beagle_stream_client_pair_token_payload() {
  local device_name="${1:-}"

  python3 - "$device_name" <<'PY'
import json
import sys

print(json.dumps({
    "device_name": sys.argv[1],
}))
PY
}

build_beagle_stream_client_pair_exchange_payload() {
  local pairing_token="${1:-}"

  python3 - "$pairing_token" <<'PY'
import json
import sys

print(json.dumps({
    "pairing_token": sys.argv[1],
}))
PY
}

fetch_beagle_stream_client_current_session_via_manager() {
  local response_file="${1:-}"
  local manager_url manager_token manager_pin manager_ca_cert curl_bin session_id vmid url http_status
  local -a curl_args tls_args

  [[ -n "$response_file" ]] || return 1
  manager_url="${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}"
  manager_token="${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}"
  manager_pin="${PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  manager_ca_cert="${PVE_THIN_CLIENT_BEAGLE_MANAGER_CA_CERT:-}"
  session_id="${PVE_THIN_CLIENT_SESSION_ID:-}"
  vmid="${PVE_THIN_CLIENT_BEAGLE_VMID:-${PVE_THIN_CLIENT_PRESET_BEAGLE_VMID:-}}"
  [[ -n "$manager_url" && -n "$manager_token" ]] || return 1
  [[ -n "$session_id" || -n "$vmid" ]] || return 1

  url="${manager_url%/}/api/v1/session/current"
  if [[ -n "$session_id" ]]; then
    url="${url}?session_id=${session_id}"
  else
    url="${url}?vmid=${vmid}"
  fi

  curl_bin="$(beagle_stream_client_curl_bin)"
  curl_args=("$curl_bin" -fsS --connect-timeout 6 --max-time 20 --output "$response_file" --write-out '%{http_code}' \
    -H "Authorization: Bearer ${manager_token}")
  mapfile -t tls_args < <(beagle_curl_tls_args "$url" "$manager_pin" "$manager_ca_cert")
  curl_args+=("${tls_args[@]}")
  http_status="$("${curl_args[@]}" "$url" || true)"
  [[ "$http_status" == "200" ]]
}

parse_beagle_stream_client_pair_token_response() {
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
expires_at = str(pairing.get("expires_at") or "").strip()
if not token:
    raise SystemExit(1)
pairing_pin = ""
parts = token.split(".")
if len(parts) >= 2:
  try:
    import base64
    raw = parts[1] + "=" * (-len(parts[1]) % 4)
    claims = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8"))
    pairing_pin = str(claims.get("pairing_pin") or "").strip()
  except Exception:
    pairing_pin = ""
print(token)
print(expires_at)
print(pairing_pin)
PY
}

register_beagle_stream_client_via_manager() {
  local manager_url manager_token manager_pin manager_ca_cert device_name client_cert response_file payload_file http_status
  local curl_bin
  local -a curl_args tls_args

  manager_url="${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}"
  manager_token="${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}"
  manager_pin="${PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  manager_ca_cert="${PVE_THIN_CLIENT_BEAGLE_MANAGER_CA_CERT:-}"
  device_name="$(beagle_stream_client_device_name)"

  [[ -n "$manager_url" && -n "$manager_token" ]] || return 1
  client_cert="$(extract_beagle_stream_client_certificate_pem 2>/dev/null || true)"
  [[ -n "$client_cert" ]] || return 1

  response_file="$(mktemp)"
  payload_file="$(mktemp)"
  curl_bin="$(beagle_stream_client_curl_bin)"
  curl_args=("$curl_bin" -fsS --connect-timeout 6 --max-time 30 --output "$response_file" --write-out '%{http_code}' \
    -H "Authorization: Bearer ${manager_token}" \
    -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "${manager_url%/}/api/v1/endpoints/beagle-stream-client/register" "$manager_pin" "$manager_ca_cert")
  curl_args+=("${tls_args[@]}")

  build_beagle_stream_client_manager_registration_payload "$client_cert" "$device_name" >"$payload_file"

  http_status="$(
    "${curl_args[@]}" --data-binary "@${payload_file}" "${manager_url%/}/api/v1/endpoints/beagle-stream-client/register" || true
  )"
  if [[ "$http_status" != "201" ]]; then
    rm -f "$payload_file"
    rm -f "$response_file"
    return 1
  fi
  if ! sync_beagle_stream_client_host_from_manager_response "$response_file"; then
    rm -f "$payload_file"
    rm -f "$response_file"
    return 1
  fi
  rm -f "$payload_file"
  rm -f "$response_file"
  return 0
}

prepare_beagle_stream_client_stream_via_manager() {
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
  curl_bin="$(beagle_stream_client_curl_bin)"
  curl_args=("$curl_bin" -fsS --connect-timeout 6 --max-time 30 --output "$response_file" --write-out '%{http_code}' \
    -H "Authorization: Bearer ${manager_token}" \
    -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "${manager_url%/}/api/v1/endpoints/beagle-stream-client/prepare-stream" "$manager_pin" "$manager_ca_cert")
  curl_args+=("${tls_args[@]}")

  build_beagle_stream_client_stream_prepare_payload "$resolution" "$app" >"$payload_file"
  http_status="$("${curl_args[@]}" --data-binary "@${payload_file}" "${manager_url%/}/api/v1/endpoints/beagle-stream-client/prepare-stream" || true)"

  rm -f "$payload_file"
  rm -f "$response_file"
  [[ "$http_status" == "200" ]]
}

request_beagle_stream_client_pairing_token_via_manager() {
  local manager_url manager_token manager_pin manager_ca_cert response_file payload_file http_status
  local curl_bin device_name
  local -a curl_args tls_args parsed

  manager_url="${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}"
  manager_token="${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}"
  manager_pin="${PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  manager_ca_cert="${PVE_THIN_CLIENT_BEAGLE_MANAGER_CA_CERT:-}"
  [[ -n "$manager_url" && -n "$manager_token" ]] || return 1

  device_name="$(beagle_stream_client_device_name)"
  response_file="$(mktemp)"
  payload_file="$(mktemp)"
  curl_bin="$(beagle_stream_client_curl_bin)"
  curl_args=("$curl_bin" -fsS --connect-timeout 6 --max-time 20 --output "$response_file" --write-out '%{http_code}' \
    -H "Authorization: Bearer ${manager_token}" \
    -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "${manager_url%/}/api/v1/endpoints/beagle-stream-client/pair-token" "$manager_pin" "$manager_ca_cert")
  curl_args+=("${tls_args[@]}")

  build_beagle_stream_client_pair_token_payload "$device_name" >"$payload_file"
  http_status="$("${curl_args[@]}" --data-binary "@${payload_file}" "${manager_url%/}/api/v1/endpoints/beagle-stream-client/pair-token" || true)"
  if [[ "$http_status" != "201" ]]; then
    rm -f "$payload_file" "$response_file"
    return 1
  fi

  if ! mapfile -t parsed < <(parse_beagle_stream_client_pair_token_response "$response_file"); then
    rm -f "$payload_file" "$response_file"
    return 1
  fi
  rm -f "$payload_file" "$response_file"

  [[ "${#parsed[@]}" -ge 1 ]] || return 1
  export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_TOKEN="${parsed[0]}"
  export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_EXPIRES_AT="${parsed[1]:-}"
  export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_PIN="${parsed[2]:-}"
  return 0
}

exchange_beagle_stream_client_pairing_token_via_manager() {
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
  curl_bin="$(beagle_stream_client_curl_bin)"
  curl_args=("$curl_bin" -fsS --connect-timeout 6 --max-time 20 --output "$response_file" --write-out '%{http_code}' \
    -H "Authorization: Bearer ${manager_token}" \
    -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "${manager_url%/}/api/v1/endpoints/beagle-stream-client/pair-exchange" "$manager_pin" "$manager_ca_cert")
  curl_args+=("${tls_args[@]}")

  build_beagle_stream_client_pair_exchange_payload "$pairing_token" >"$payload_file"
  http_status="$("${curl_args[@]}" --data-binary "@${payload_file}" "${manager_url%/}/api/v1/endpoints/beagle-stream-client/pair-exchange" || true)"

  rm -f "$payload_file" "$response_file"
  [[ "$http_status" == "200" ]]
}
