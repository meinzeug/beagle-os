#!/usr/bin/env bash

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
  if ! python3 - "$response_file" "$uniqueid" "$cert_b64" "$sunshine_name" "$stream_port" <<'PY'
from pathlib import Path
import base64
import json
import sys

response_path = Path(sys.argv[1])
uniqueid = (sys.argv[2] or "").strip()
cert_b64 = (sys.argv[3] or "").strip()
sunshine_name = (sys.argv[4] or "").strip()
stream_port = (sys.argv[5] or "").strip()

try:
    server_cert_pem = base64.b64decode(cert_b64.encode("ascii"), validate=True).decode("utf-8")
except Exception:
    raise SystemExit(1)

if not uniqueid or "BEGIN CERTIFICATE" not in server_cert_pem:
    raise SystemExit(1)

payload = {
    "sunshine_server": {
        "uniqueid": uniqueid,
        "server_cert_pem": server_cert_pem,
        "sunshine_name": sunshine_name,
        "stream_port": stream_port,
    }
}
response_path.write_text(json.dumps(payload), encoding="utf-8")
PY
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

  python3 - "$config_path" "$host" "$connect_host" "$port" <<'PY'
from pathlib import Path
import sys

config_path = Path(sys.argv[1])
host = (sys.argv[2] or "").strip()
connect_host = (sys.argv[3] or "").strip()
port = (sys.argv[4] or "").strip()

text = config_path.read_text(encoding="utf-8", errors="ignore")
lines = text.splitlines()
section_start = None
section_end = len(lines)
for idx, line in enumerate(lines):
    if line.strip() == "[hosts]":
        section_start = idx
        for next_idx in range(idx + 1, len(lines)):
            if lines[next_idx].startswith("[") and lines[next_idx].endswith("]"):
                section_end = next_idx
                break
        break

if section_start is None:
    raise SystemExit(1)

entries = {}
for raw in lines[section_start + 1:section_end]:
    if "=" not in raw:
        continue
    key, value = raw.split("=", 1)
    entries[key.strip()] = value.strip()

size = int(entries.get("size", "0") or "0")
expected_hosts = {value for value in (host, connect_host) if value}
expected_ports = {value for value in (port, "47984", "50100") if value}

for idx in range(1, size + 1):
    uuid_value = entries.get(f"{idx}\\uuid", "").strip()
    cert_value = entries.get(f"{idx}\\srvcert", "").strip()
    if not uuid_value or "BEGIN CERTIFICATE" not in cert_value:
        continue

    manual_host = entries.get(f"{idx}\\manualaddress", "").strip()
    local_host = entries.get(f"{idx}\\localaddress", "").strip()
    manual_port = entries.get(f"{idx}\\manualport", "").strip()
    local_port = entries.get(f"{idx}\\localport", "").strip()

    if expected_hosts and manual_host not in expected_hosts and local_host not in expected_hosts:
        continue

    if expected_ports and manual_port and manual_port not in expected_ports and local_port and local_port not in expected_ports:
        continue

    raise SystemExit(0)

raise SystemExit(1)
PY
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

  python3 - "$config_path" "$response_file" "$host" "$connect_host" "$port" <<'PY'
from pathlib import Path
import json
import sys

config_path = Path(sys.argv[1])
response_path = Path(sys.argv[2])
host = (sys.argv[3] or "").strip()
connect_host = (sys.argv[4] or "").strip()
port = (sys.argv[5] or "").strip()

payload = json.loads(response_path.read_text(encoding="utf-8"))
server = payload.get("sunshine_server") if isinstance(payload, dict) else None
if not isinstance(server, dict):
    raise SystemExit(1)

uniqueid = str(server.get("uniqueid", "") or "").strip()
server_cert_pem = str(server.get("server_cert_pem", "") or "")
sunshine_name = str(server.get("sunshine_name", "") or "").strip() or host or connect_host
stream_port = str(server.get("stream_port", "") or "").strip()
manual_host = connect_host or host
manual_port = port or stream_port or "47984"

if not uniqueid or "BEGIN CERTIFICATE" not in server_cert_pem or not manual_host:
    raise SystemExit(1)

text = config_path.read_text(encoding="utf-8", errors="ignore")
lines = text.splitlines()
section_start = None
section_end = len(lines)
for idx, line in enumerate(lines):
    if line.strip() == "[hosts]":
        section_start = idx
        for next_idx in range(idx + 1, len(lines)):
            if lines[next_idx].startswith("[") and lines[next_idx].endswith("]"):
                section_end = next_idx
                break
        break

if section_start is None:
    if lines and lines[-1] != "":
        lines.append("")
    section_start = len(lines)
    section_end = section_start + 1
    lines.append("[hosts]")

host_lines = lines[section_start + 1:section_end]
entries = {}
for raw in host_lines:
    if "=" not in raw:
        continue
    key, value = raw.split("=", 1)
    entries[key] = value

existing_local_address = entries.get("1\\localaddress", "").strip()
existing_local_port = entries.get("1\\localport", "").strip()
existing_mac = entries.get("1\\mac", "@ByteArray()").strip() or "@ByteArray()"
existing_nvidiasw = entries.get("1\\nvidiasw", "false").strip() or "false"
existing_remote_address = entries.get("1\\remoteaddress", "").strip()
existing_remote_port = entries.get("1\\remoteport", "0").strip() or "0"
existing_ipv6_address = entries.get("1\\ipv6address", "").strip()
existing_ipv6_port = entries.get("1\\ipv6port", "0").strip() or "0"

escaped_cert = server_cert_pem.replace("\\", "\\\\").replace("\n", "\\n")
updated_host_lines = [
    "1\\customname=false",
    f"1\\hostname={sunshine_name}",
    f"1\\ipv6address={existing_ipv6_address}",
    f"1\\ipv6port={existing_ipv6_port}",
    f"1\\localaddress={existing_local_address}",
    f"1\\localport={existing_local_port or manual_port}",
    f"1\\mac={existing_mac}",
    f"1\\manualaddress={manual_host}",
    f"1\\manualport={manual_port}",
    f"1\\nvidiasw={existing_nvidiasw}",
    f"1\\remoteaddress={existing_remote_address}",
    f"1\\remoteport={existing_remote_port}",
    f"1\\srvcert=@ByteArray({escaped_cert})",
    f"1\\uuid={uniqueid}",
    "size=1",
]

lines = lines[:section_start + 1] + updated_host_lines + lines[section_end:]
config_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
PY
}

bootstrap_moonlight_client() {
  local bin host port timeout_value target

  moonlight_host_configured && return 0
  extract_moonlight_certificate_pem >/dev/null 2>&1 && return 0

  bin="$(moonlight_bin)"
  host="$(moonlight_connect_host)"
  port="$(moonlight_port)"
  timeout_value="$(moonlight_bootstrap_timeout)"
  target="$(format_moonlight_target "$host" "$port")"

  [[ -n "$target" ]] || return 1

  if command -v timeout >/dev/null 2>&1; then
    timeout --preserve-status "$timeout_value" "$bin" list "$target" >/dev/null 2>&1 || true
    return 0
  fi

  "$bin" list "$target" >/dev/null 2>&1 || true
}
