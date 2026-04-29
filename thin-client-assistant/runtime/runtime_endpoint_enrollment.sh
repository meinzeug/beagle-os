#!/usr/bin/env bash

runtime_python_bin() {
  printf '%s\n' "${BEAGLE_PYTHON_BIN:-python3}"
}

runtime_curl_bin() {
  printf '%s\n' "${BEAGLE_CURL_BIN:-curl}"
}

runtime_hostname_bin() {
  printf '%s\n' "${BEAGLE_HOSTNAME_BIN:-hostname}"
}

runtime_credentials_file() {
  printf '%s\n' "${CREDENTIALS_FILE:-${CONFIG_DIR:-${PVE_THIN_CLIENT_SYSTEM_CONFIG_DIR:-/etc/pve-thin-client}}/credentials.env}"
}

runtime_thinclient_config_file() {
  printf '%s\n' "${CONFIG_FILE:-${CONFIG_DIR:-${PVE_THIN_CLIENT_SYSTEM_CONFIG_DIR:-/etc/pve-thin-client}}/thinclient.conf}"
}

runtime_wireguard_enrollment_script() {
  printf '%s\n' "${RUNTIME_WIREGUARD_ENROLLMENT_SH:-$SCRIPT_DIR/enrollment_wireguard.sh}"
}

runtime_enrollment_url() {
  printf '%s\n' "${PVE_THIN_CLIENT_BEAGLE_ENROLLMENT_URL:-${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}/api/v1/endpoints/enroll}"
}

runtime_endpoint_hostname() {
  local hostname_bin

  if [[ -n "${PVE_THIN_CLIENT_HOSTNAME:-}" ]]; then
    printf '%s\n' "${PVE_THIN_CLIENT_HOSTNAME}"
    return 0
  fi

  hostname_bin="$(runtime_hostname_bin)"
  "$hostname_bin"
}

runtime_endpoint_id() {
  local hostname_value
  hostname_value="$(runtime_endpoint_hostname)"
  printf '%s-%s\n' "$hostname_value" "${PVE_THIN_CLIENT_BEAGLE_VMID:-0}"
}

reload_runtime_enrollment_config() {
  local config_file credentials_file

  config_file="$(runtime_thinclient_config_file)"
  credentials_file="$(runtime_credentials_file)"

  # shellcheck disable=SC1090
  source "$config_file"
  # shellcheck disable=SC1090
  source "$credentials_file"
}

enroll_endpoint_if_needed() {
  local credentials_file response_file enroll_url enrollment_token endpoint_id hostname_value http_status manager_pin manager_ca_cert
  local python_bin curl_bin
  local -a curl_args tls_args

  credentials_file="$(runtime_credentials_file)"
  [[ -f "$credentials_file" ]] || return 0

  enrollment_token="${PVE_THIN_CLIENT_BEAGLE_ENROLLMENT_TOKEN:-}"
  [[ -n "$enrollment_token" ]] || return 0
  [[ -z "${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}" ]] || return 0

  enroll_url="$(runtime_enrollment_url)"
  [[ -n "$enroll_url" ]] || return 1

  endpoint_id="$(runtime_endpoint_id)"
  hostname_value="$(runtime_endpoint_hostname)"
  manager_pin="${PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  manager_ca_cert="${PVE_THIN_CLIENT_BEAGLE_MANAGER_CA_CERT:-}"
  response_file="$(mktemp)"
  python_bin="$(runtime_python_bin)"
  curl_bin="$(runtime_curl_bin)"

  curl_args=("$curl_bin" -fsS --connect-timeout 8 --max-time 20 --output "$response_file" --write-out '%{http_code}' -H 'Content-Type: application/json')
  mapfile -t tls_args < <(beagle_curl_tls_args "$enroll_url" "$manager_pin" "$manager_ca_cert")
  curl_args+=("${tls_args[@]}")
  http_status="$(
    "${curl_args[@]}" \
      --data "{\"enrollment_token\":\"${enrollment_token}\",\"endpoint_id\":\"${endpoint_id}\",\"hostname\":\"${hostname_value}\"}" \
      "${enroll_url%/}" || true
  )"
  if [[ "$http_status" != "201" ]]; then
    rm -f "$response_file"
    return 1
  fi

  "$python_bin" "$APPLY_ENROLLMENT_CONFIG_PY" \
    "$response_file" \
    "$(runtime_thinclient_config_file)" \
    "$credentials_file"
  rm -f "$response_file"

  reload_runtime_enrollment_config
}

enroll_wireguard_if_needed() {
  local manager_url manager_token mode egress_type interface_name endpoint_id script_path

  mode="${PVE_THIN_CLIENT_BEAGLE_EGRESS_MODE:-full}"
  egress_type="${PVE_THIN_CLIENT_BEAGLE_EGRESS_TYPE:-}"
  [[ "$mode" != "direct" ]] || return 0
  [[ "$egress_type" == "wireguard" ]] || return 0

  manager_url="${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}"
  manager_token="${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}"
  [[ -n "$manager_url" && -n "$manager_token" ]] || return 1

  script_path="$(runtime_wireguard_enrollment_script)"
  [[ -x "$script_path" ]] || return 1

  interface_name="${PVE_THIN_CLIENT_BEAGLE_EGRESS_INTERFACE:-wg-beagle}"
  endpoint_id="${PVE_THIN_CLIENT_BEAGLE_DEVICE_ID:-$(runtime_endpoint_id)}"
  BEAGLE_CONTROL_PLANE="$manager_url" \
  BEAGLE_DEVICE_ID="$endpoint_id" \
  BEAGLE_MANAGER_TOKEN="$manager_token" \
  WG_IFACE="$interface_name" \
  "$script_path"
}
