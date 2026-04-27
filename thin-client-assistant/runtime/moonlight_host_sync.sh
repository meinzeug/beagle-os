#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOONLIGHT_CLI_SH="${MOONLIGHT_CLI_SH:-$SCRIPT_DIR/moonlight_cli.sh}"
MOONLIGHT_HOST_REGISTRY_PY="${MOONLIGHT_HOST_REGISTRY_PY:-$SCRIPT_DIR/moonlight_host_registry.py}"
# shellcheck disable=SC1090
source "$MOONLIGHT_CLI_SH"

seed_moonlight_host_from_runtime_config() {
  local config_path uniqueid cert_b64 sunshine_name stream_port response_file

  uniqueid="${PVE_THIN_CLIENT_SUNSHINE_SERVER_UNIQUEID:-}"
  cert_b64="${PVE_THIN_CLIENT_SUNSHINE_SERVER_CERT_B64:-}"
  sunshine_name="${PVE_THIN_CLIENT_SUNSHINE_SERVER_NAME:-}"
  stream_port="${PVE_THIN_CLIENT_SUNSHINE_SERVER_STREAM_PORT:-$(moonlight_port)}"
  config_path="$(moonlight_client_config_path 2>/dev/null || true)"

  [[ -n "$config_path" && -r "$config_path" ]] || return 1
  [[ -n "$uniqueid" && -n "$cert_b64" ]] || return 1

  response_file="$(mktemp)"
  if ! python3 "$MOONLIGHT_HOST_REGISTRY_PY" seed-response \
    --output "$response_file" \
    --uniqueid "$uniqueid" \
    --cert-b64 "$cert_b64" \
    --sunshine-name "$sunshine_name" \
    --stream-port "$stream_port"
  then
    rm -f "$response_file"
    return 1
  fi

  if ! sync_moonlight_host_from_manager_response "$response_file"; then
    rm -f "$response_file"
    return 1
  fi

  rm -f "$response_file"
  return 0
}

moonlight_host_configured() {
  local config_path host connect_host port

  config_path="$(moonlight_client_config_path 2>/dev/null || true)"
  [[ -n "$config_path" && -r "$config_path" ]] || return 1

  host="$(moonlight_host)"
  connect_host="$(moonlight_connect_host)"
  port="$(moonlight_port)"

  python3 "$MOONLIGHT_HOST_REGISTRY_PY" is-configured \
    --config "$config_path" \
    --host "$host" \
    --connect-host "$connect_host" \
    --port "$port"
}

sync_moonlight_host_from_manager_response() {
  local response_file config_path host connect_host port

  response_file="${1:-}"
  [[ -n "$response_file" && -r "$response_file" ]] || return 1
  config_path="$(moonlight_client_config_path 2>/dev/null || true)"
  [[ -n "$config_path" && -w "$config_path" ]] || return 1
  host="$(moonlight_host)"
  connect_host="$(moonlight_connect_host)"
  port="$(moonlight_port)"

  python3 "$MOONLIGHT_HOST_REGISTRY_PY" sync-config \
    --config "$config_path" \
    --response "$response_file" \
    --host "$host" \
    --connect-host "$connect_host" \
    --port "$port"
}

retarget_moonlight_host_from_runtime_config() {
  local config_path host connect_host port

  config_path="$(moonlight_client_config_path 2>/dev/null || true)"
  [[ -n "$config_path" && -w "$config_path" ]] || return 1
  host="$(moonlight_host)"
  connect_host="$(moonlight_connect_host)"
  port="$(moonlight_port)"

  python3 "$MOONLIGHT_HOST_REGISTRY_PY" retarget-config \
    --config "$config_path" \
    --host "$host" \
    --connect-host "$connect_host" \
    --port "$port"
}

retarget_moonlight_host_from_session_broker_response() {
  local response_file="${1:-}"
  local host port current_node
  local -a broker_values

  [[ -n "$response_file" && -r "$response_file" ]] || return 1
  if ! mapfile -t broker_values < <(python3 - "$response_file" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
host = str(payload.get("stream_host") or "").strip()
port = str(payload.get("moonlight_port") or "").strip()
current_node = str(payload.get("current_node") or "").strip()
if not host:
    raise SystemExit(1)
print(host)
print(port)
print(current_node)
PY
  ); then
    return 1
  fi
  host="${broker_values[0]:-}"
  port="${broker_values[1]:-}"
  current_node="${broker_values[2]:-}"
  [[ -n "$host" ]] || return 1

  export PVE_THIN_CLIENT_MOONLIGHT_HOST="$host"
  if [[ -n "$port" ]]; then
    export PVE_THIN_CLIENT_MOONLIGHT_PORT="$port"
  fi
  if [[ -n "$current_node" ]]; then
    export PVE_THIN_CLIENT_SESSION_CURRENT_NODE="$current_node"
  fi
  retarget_moonlight_host_from_runtime_config
}

bootstrap_moonlight_client() {
  moonlight_host_configured && return 0
  extract_moonlight_certificate_pem >/dev/null 2>&1 && return 0
  bootstrap_moonlight_client_probe
}
