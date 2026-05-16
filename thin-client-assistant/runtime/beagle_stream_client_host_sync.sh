#!/usr/bin/env bash

 : "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST:=}"
 : "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_CONNECT_HOST:=}"
 : "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LOCAL_HOST:=}"

SCRIPT_DIR="${RUNTIME_SCRIPT_DIR:-/usr/local/lib/pve-thin-client/runtime}"
BEAGLE_STREAM_CLIENT_CLI_SH="${BEAGLE_STREAM_CLIENT_CLI_SH:-$SCRIPT_DIR/beagle_stream_client_cli.sh}"
BEAGLE_STREAM_CLIENT_HOST_REGISTRY_PY="${BEAGLE_STREAM_CLIENT_HOST_REGISTRY_PY:-$SCRIPT_DIR/beagle_stream_client_host_registry.py}"
# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_CLI_SH"

seed_beagle_stream_client_host_from_runtime_config() {
    : "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST:=}"
    : "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_CONNECT_HOST:=}"
    : "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LOCAL_HOST:=}"
  local config_path uniqueid cert_b64 beagle_stream_server_name stream_port response_file

  uniqueid="${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_UNIQUEID:-}"
  cert_b64="${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_CERT_B64:-}"
  beagle_stream_server_name="${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_NAME:-}"
  stream_port="${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_STREAM_PORT:-$(beagle_stream_client_port)}"
  config_path="$(beagle_stream_client_config_path 2>/dev/null || true)"

  # Fallback: Wenn HOST leer, aber LOCAL_HOST gesetzt ist, dann setze HOST auf LOCAL_HOST
  if [[ -z "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST:-}" && -n "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LOCAL_HOST:-}" ]]; then
    export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LOCAL_HOST:-}"
  fi
  if [[ -z "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_CONNECT_HOST:-}" && -n "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LOCAL_HOST:-}" ]]; then
    export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_CONNECT_HOST="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LOCAL_HOST:-}"
  fi

  [[ -n "$config_path" && -r "$config_path" ]] || return 1
  [[ -n "$uniqueid" && -n "$cert_b64" ]] || return 1

  response_file="$(mktemp)"
  if ! python3 "$BEAGLE_STREAM_CLIENT_HOST_REGISTRY_PY" seed-response \
    --output "$response_file" \
    --uniqueid "$uniqueid" \
    --cert-b64 "$cert_b64" \
    --beagle-stream-server-name "$beagle_stream_server_name" \
    --stream-port "$stream_port"
  then
    rm -f "$response_file"
    return 1
  fi

  if ! sync_beagle_stream_client_host_from_manager_response "$response_file"; then
    rm -f "$response_file"
    return 1
  fi

  rm -f "$response_file"
  return 0
}

beagle_stream_client_host_configured() {
  local config_path host connect_host port expected_uniqueid expected_cert_b64
  local -a args

  config_path="$(beagle_stream_client_config_path 2>/dev/null || true)"
  [[ -n "$config_path" && -r "$config_path" ]] || return 1

  host="$(beagle_stream_client_host)"
  connect_host="$(beagle_stream_client_connect_host)"
  port="$(beagle_stream_client_port)"
  expected_uniqueid="${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_UNIQUEID:-}"
  expected_cert_b64="${PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_CERT_B64:-}"

  args=(python3 "$BEAGLE_STREAM_CLIENT_HOST_REGISTRY_PY" is-configured \
    --config "$config_path" \
    --host "$host" \
    --connect-host "$connect_host" \
    --port "$port")

  if [[ -n "$expected_uniqueid" ]]; then
    args+=(--expected-uniqueid "$expected_uniqueid")
  fi
  if [[ -n "$expected_cert_b64" ]]; then
    args+=(--expected-cert-b64 "$expected_cert_b64")
  fi

  "${args[@]}"
}

sync_beagle_stream_client_host_from_manager_response() {
  local response_file config_path host connect_host port

  response_file="${1:-}"
  [[ -n "$response_file" && -r "$response_file" ]] || return 1
  config_path="$(beagle_stream_client_config_path 2>/dev/null || true)"
  [[ -n "$config_path" && -w "$config_path" ]] || return 1
  host="$(beagle_stream_client_host)"
  connect_host="$(beagle_stream_client_connect_host)"
  port="$(beagle_stream_client_port)"

  python3 "$BEAGLE_STREAM_CLIENT_HOST_REGISTRY_PY" sync-config \
    --config "$config_path" \
    --response "$response_file" \
    --host "$host" \
    --connect-host "$connect_host" \
    --port "$port"
}

retarget_beagle_stream_client_host_from_runtime_config() {
  local config_path host connect_host port

  config_path="$(beagle_stream_client_config_path 2>/dev/null || true)"
  [[ -n "$config_path" && -w "$config_path" ]] || return 1
  host="$(beagle_stream_client_host)"
  connect_host="$(beagle_stream_client_connect_host)"
  port="$(beagle_stream_client_port)"

  python3 "$BEAGLE_STREAM_CLIENT_HOST_REGISTRY_PY" retarget-config \
    --config "$config_path" \
    --host "$host" \
    --connect-host "$connect_host" \
    --port "$port"
}

sync_beagle_stream_client_host_from_serverinfo_probe() {
  local config_path host connect_host port response_file serverinfo cert_pem
  local curl_bin cert_port
  local -a parsed cert_ports

  config_path="$(beagle_stream_client_config_path 2>/dev/null || true)"
  [[ -n "$config_path" && -w "$config_path" ]] || return 1

  host="$(beagle_stream_client_host)"
  connect_host="$(beagle_stream_client_connect_host)"
  port="$(beagle_stream_client_port)"
  [[ -n "$connect_host" && "$port" =~ ^[0-9]+$ ]] || return 1

  curl_bin="$(beagle_stream_client_curl_bin)"
  serverinfo="$("$curl_bin" -fsS --connect-timeout 2 --max-time 4 "http://${connect_host}:${port}/serverinfo" 2>/dev/null || true)"
  [[ -n "$serverinfo" ]] || return 1
  command -v openssl >/dev/null 2>&1 || return 1

  if ! mapfile -t parsed < <(python3 - "$serverinfo" <<'PY'
import sys
import xml.etree.ElementTree as ET

payload = sys.argv[1] or ""

try:
    root = ET.fromstring(payload)
except ET.ParseError:
    raise SystemExit(1)


def text(name):
    value = root.findtext(name) or ""
    return value.strip()


uniqueid = text("uniqueid")
hostname = text("hostname")
https_port = text("HttpsPort")

if not uniqueid:
    raise SystemExit(1)

print(uniqueid)
print(hostname)
print(https_port if https_port.isdigit() else "")
PY
  ); then
    return 1
  fi

  cert_ports=()
  if [[ "${parsed[2]:-}" =~ ^[0-9]+$ ]]; then
    cert_ports+=("${parsed[2]}")
  fi
  cert_ports+=("$((port + 1))" "50001" "47990")

  for cert_port in "${cert_ports[@]}"; do
    [[ -n "$cert_port" ]] || continue
    if command -v timeout >/dev/null 2>&1; then
      cert_pem="$(
        printf Q | timeout 3 openssl s_client -connect "${connect_host}:${cert_port}" -servername "$connect_host" -showcerts 2>/dev/null |
          awk '/-----BEGIN CERTIFICATE-----/{flag=1} flag{print} /-----END CERTIFICATE-----/{exit}'
      )"
    else
      cert_pem="$(
        printf Q | openssl s_client -connect "${connect_host}:${cert_port}" -servername "$connect_host" -showcerts 2>/dev/null |
          awk '/-----BEGIN CERTIFICATE-----/{flag=1} flag{print} /-----END CERTIFICATE-----/{exit}'
      )"
    fi
    if [[ "$cert_pem" == *"BEGIN CERTIFICATE"* ]]; then
      break
    fi
    cert_pem=""
  done
  [[ -n "$cert_pem" ]] || return 1

  response_file="$(mktemp)"
  if ! python3 - "$response_file" "${parsed[0]}" "$cert_pem" "${parsed[1]:-${host:-$connect_host}}" "$port" <<'PY'
import json
import sys
from pathlib import Path

output, uniqueid, cert_pem, server_name, stream_port = sys.argv[1:6]
if not uniqueid.strip() or "BEGIN CERTIFICATE" not in cert_pem:
    raise SystemExit(1)

Path(output).write_text(
    json.dumps(
        {
            "beagle_stream_server": {
                "uniqueid": uniqueid.strip(),
                "server_cert_pem": cert_pem,
                "beagle_stream_server_name": server_name.strip(),
                "stream_port": stream_port.strip(),
            }
        }
    ),
    encoding="utf-8",
)
PY
  then
    rm -f "$response_file"
    return 1
  fi

  if ! sync_beagle_stream_client_host_from_manager_response "$response_file"; then
    rm -f "$response_file"
    return 1
  fi
  rm -f "$response_file"
  return 0
}

retarget_beagle_stream_client_host_from_session_broker_response() {
  local response_file="${1:-}"
  local host local_host port current_node
  local -a broker_values

  [[ -n "$response_file" && -r "$response_file" ]] || return 1
  if ! mapfile -t broker_values < <(python3 - "$response_file" <<'PY'
import json
import ipaddress
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

def value(*keys):
  for key in keys:
    raw = str(payload.get(key) or "").strip()
    if raw:
      return raw
  return ""

def is_private_ip(raw):
  try:
    ip = ipaddress.ip_address(raw.strip("[]"))
  except ValueError:
    return False
  return ip.is_private

host = str(payload.get("stream_host") or "").strip()
local_host = value("beagle_stream_client_local_host", "stream_local_host", "guest_ip")
if not local_host and is_private_ip(host):
  local_host = host
port = str(payload.get("beagle_stream_client_port") or "").strip()
current_node = str(payload.get("current_node") or "").strip()
if not host:
    raise SystemExit(1)
print(host)
print(local_host)
print(port)
print(current_node)
PY
  ); then
    return 1
  fi
  host="${broker_values[0]:-}"
  local_host="${broker_values[1]:-}"
  port="${broker_values[2]:-}"
  current_node="${broker_values[3]:-}"
  [[ -n "$host" ]] || return 1

  export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST="$host"
  export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BROKER_HOST="$host"
  if [[ -n "$local_host" ]]; then
    export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LOCAL_HOST="$local_host"
  fi
  if [[ -n "$port" ]]; then
    export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PORT="$port"
  fi
  if [[ -n "$current_node" ]]; then
    export PVE_THIN_CLIENT_SESSION_CURRENT_NODE="$current_node"
  fi
  retarget_beagle_stream_client_host_from_runtime_config
}

bootstrap_beagle_stream_client() {
  beagle_stream_client_host_configured && return 0
  sync_beagle_stream_client_host_from_serverinfo_probe && return 0
  bootstrap_beagle_stream_client_probe
}
