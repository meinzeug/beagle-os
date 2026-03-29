#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_runtime_config
beagle_log_event "moonlight.start" "profile=${PVE_THIN_CLIENT_PROFILE_NAME:-default} host=${PVE_THIN_CLIENT_MOONLIGHT_HOST:-UNSET} app=${PVE_THIN_CLIENT_MOONLIGHT_APP:-Desktop}"

MOONLIGHT_LOG_DIR="${PVE_THIN_CLIENT_LOG_DIR:-${XDG_RUNTIME_DIR:-/tmp}/pve-thin-client}"
MOONLIGHT_LIST_LOG="$MOONLIGHT_LOG_DIR/moonlight-list.log"
MOONLIGHT_PAIR_LOG="$MOONLIGHT_LOG_DIR/moonlight-pair.log"

mkdir -p "$MOONLIGHT_LOG_DIR" 2>/dev/null || true

have_binary() {
  command -v "$1" >/dev/null 2>&1
}

detect_xauthority() {
  local auth_candidate=""

  auth_candidate="$(
    ps -eo args= 2>/dev/null | awk '
      /[X]org/ && /(^|[[:space:]]):0($|[[:space:]])/ {
        for (i = 1; i <= NF; i++) {
          if ($i == "-auth" && (i + 1) <= NF) {
            print $(i + 1)
            exit
          }
        }
      }
    '
  )"
  if [[ -n "$auth_candidate" && -r "$auth_candidate" ]]; then
    printf '%s\n' "$auth_candidate"
    return 0
  fi

  if [[ -n "${XAUTHORITY:-}" && -r "${XAUTHORITY}" ]]; then
    printf '%s\n' "${XAUTHORITY}"
    return 0
  fi

  auth_candidate="${HOME:-/home/thinclient}/.Xauthority"
  if [[ -r "$auth_candidate" ]]; then
    printf '%s\n' "$auth_candidate"
    return 0
  fi

  auth_candidate="$(find /tmp -maxdepth 1 -type f -name 'serverauth.*' 2>/dev/null | head -n 1 || true)"
  printf '%s\n' "${auth_candidate:-${HOME:-/home/thinclient}/.Xauthority}"
}

x_display_ready() {
  local auth_candidate="${1:-${XAUTHORITY:-}}"

  [[ -n "${DISPLAY:-}" ]] || return 1
  [[ -n "$auth_candidate" && -r "$auth_candidate" ]] || return 1
  command -v xset >/dev/null 2>&1 || return 0

  DISPLAY="$DISPLAY" XAUTHORITY="$auth_candidate" xset q >/dev/null 2>&1
}

select_xauthority() {
  local home_candidate detected_candidate candidate
  local -a candidates=()
  declare -A seen=()

  home_candidate="${HOME:-/home/${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}}/.Xauthority"
  detected_candidate="$(detect_xauthority 2>/dev/null || true)"

  for candidate in \
    "${XAUTHORITY:-}" \
    "$home_candidate" \
    "$detected_candidate"
  do
    [[ -n "$candidate" && -r "$candidate" ]] || continue
    [[ -n "${seen[$candidate]:-}" ]] && continue
    candidates+=("$candidate")
    seen["$candidate"]=1
  done

  while IFS= read -r candidate; do
    [[ -n "$candidate" && -r "$candidate" ]] || continue
    [[ -n "${seen[$candidate]:-}" ]] && continue
    candidates+=("$candidate")
    seen["$candidate"]=1
  done < <(find /tmp -maxdepth 1 -type f -name 'serverauth.*' 2>/dev/null | sort || true)

  if ((${#candidates[@]} == 0)); then
    printf '%s\n' "$home_candidate"
    return 0
  fi

  for candidate in "${candidates[@]}"; do
    if x_display_ready "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  printf '%s\n' "${candidates[0]}"
}

wait_for_x_display() {
  local attempts attempt selected_auth

  attempts="${PVE_THIN_CLIENT_X11_READY_RETRIES:-20}"
  for attempt in $(seq 1 "$attempts"); do
    selected_auth="$(select_xauthority)"
    export XAUTHORITY="$selected_auth"
    if x_display_ready "$selected_auth"; then
      beagle_log_event "moonlight.display-ready" "display=${DISPLAY:-UNSET} xauthority=$selected_auth attempt=${attempt}"
      return 0
    fi
    sleep 1
  done

  beagle_log_event "moonlight.display-unready" "display=${DISPLAY:-UNSET} xauthority=${XAUTHORITY:-UNSET}"
  return 1
}

moonlight_bin() {
  printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_BIN:-moonlight}"
}

prefer_ipv4() {
  [[ "${PVE_THIN_CLIENT_MOONLIGHT_PREFER_IPV4:-1}" == "1" ]]
}

is_ip_literal() {
  python3 - "$1" <<'PY'
import ipaddress
import sys

try:
    ipaddress.ip_address(sys.argv[1].strip("[]"))
except ValueError:
    raise SystemExit(1)
PY
}

moonlight_host() {
  render_template "${PVE_THIN_CLIENT_MOONLIGHT_HOST:-}"
}

moonlight_gateway_fallback_host() {
  local gateway host
  gateway="${PVE_THIN_CLIENT_NETWORK_GATEWAY:-}"
  host="$(moonlight_host)"

  [[ -n "$gateway" ]] || return 1
  [[ "$gateway" != "$host" ]] || return 1
  printf '%s\n' "$gateway"
}

moonlight_port() {
  render_template "${PVE_THIN_CLIENT_MOONLIGHT_PORT:-}"
}

format_moonlight_target() {
  local host="$1"
  local port="$2"

  [[ -n "$host" ]] || return 1
  if [[ -z "$port" ]]; then
    printf '%s\n' "$host"
    return 0
  fi

  if [[ "$host" == \[*\] ]]; then
    printf '%s:%s\n' "$host" "$port"
    return 0
  fi

  if [[ "$host" == *:* ]]; then
    printf '[%s]:%s\n' "$host" "$port"
    return 0
  fi

  printf '%s:%s\n' "$host" "$port"
}

resolve_ipv4_host() {
  python3 - "$1" <<'PY'
import socket
import sys

host = sys.argv[1]
seen = set()
for entry in socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM):
    address = entry[4][0]
    if address not in seen:
        seen.add(address)
        print(address)
        raise SystemExit(0)

raise SystemExit(1)
PY
}

moonlight_primary_connect_host() {
  local host resolved
  host="$(moonlight_host)"
  [[ -n "$host" ]] || return 0
  if prefer_ipv4 && ! is_ip_literal "$host"; then
    resolved="$(resolve_ipv4_host "$host" 2>/dev/null || true)"
    if [[ -n "$resolved" ]]; then
      printf '%s\n' "$resolved"
      return 0
    fi
  fi
  printf '%s\n' "$host"
}

rewrite_url_host() {
  python3 - "$1" "$2" <<'PY'
from urllib.parse import urlsplit, urlunsplit
import sys

url = (sys.argv[1] or "").strip()
host = (sys.argv[2] or "").strip()
if not url or not host:
    raise SystemExit(1)

parts = urlsplit(url)
if not parts.scheme or not parts.netloc:
    raise SystemExit(1)

userinfo = ""
if "@" in parts.netloc:
    userinfo, _, _ = parts.netloc.rpartition("@")
    userinfo = f"{userinfo}@"

hostname = parts.hostname or ""
port = f":{parts.port}" if parts.port else ""
netloc = f"{userinfo}{host}{port}"
print(urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment)))
PY
}

moonlight_app() {
  render_template "${PVE_THIN_CLIENT_MOONLIGHT_APP:-Desktop}"
}

moonlight_audio_driver() {
  printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_AUDIO_DRIVER:-alsa}"
}

moonlight_video_decoder() {
  local configured
  configured="${PVE_THIN_CLIENT_MOONLIGHT_VIDEO_DECODER:-auto}"

  if [[ "$configured" == "auto" ]] && [[ ! -e /dev/dri/renderD128 ]] && [[ ! -e /dev/dri/card0 ]]; then
    printf 'software\n'
    return 0
  fi

  if [[ "$configured" == "auto" ]] && [[ -e /dev/dri/renderD128 ]] && [[ ! -r /dev/dri/renderD128 || ! -w /dev/dri/renderD128 ]]; then
    printf 'software\n'
    return 0
  fi

  if [[ "$configured" == "auto" ]] && [[ ! -e /dev/dri/renderD128 ]] && [[ -e /dev/dri/card0 ]] && [[ ! -r /dev/dri/card0 || ! -w /dev/dri/card0 ]]; then
    printf 'software\n'
    return 0
  fi

  printf '%s\n' "$configured"
}

record_decoder_choice() {
  local decoder="$1"
  beagle_log_event "moonlight.decoder" "decoder=${decoder} codec=${PVE_THIN_CLIENT_MOONLIGHT_VIDEO_CODEC:-auto}"
}

local_display_resolution() {
  if command -v xrandr >/dev/null 2>&1; then
    xrandr --query 2>/dev/null | awk '
      / connected primary / {
        for (i = 1; i <= NF; i++) {
          if ($i ~ /^[0-9]+x[0-9]+\+/) {
            split($i, parts, "+")
            print parts[1]
            exit
          }
        }
      }
      / connected / {
        for (i = 1; i <= NF; i++) {
          if ($i ~ /^[0-9]+x[0-9]+\+/) {
            split($i, parts, "+")
            print parts[1]
            exit
          }
        }
      }
      /^Screen [0-9]+:/ {
        if (match($0, /current [0-9]+ x [0-9]+/)) {
          value = substr($0, RSTART + 8, RLENGTH - 8)
          gsub(/ /, "", value)
          print value
          exit
        }
      }
    '
  fi
}

moonlight_resolution() {
  local configured detected
  configured="${PVE_THIN_CLIENT_MOONLIGHT_RESOLUTION:-auto}"

  if [[ "${PVE_THIN_CLIENT_MOONLIGHT_AUTO_RESOLUTION:-1}" == "1" ]]; then
    detected="$(local_display_resolution 2>/dev/null || true)"
    case "$configured" in
      ""|auto|native)
        if [[ -n "$detected" ]]; then
          printf '%s\n' "$detected"
          return 0
        fi
        ;;
      720|1080|1440|4K)
        if [[ -n "$detected" && "$detected" != "1024x768" ]]; then
          printf '%s\n' "$detected"
          return 0
        fi
        ;;
    esac
  fi

  printf '%s\n' "$configured"
}

moonlight_list_timeout() {
  printf '%s\n' "${PVE_THIN_CLIENT_MOONLIGHT_LIST_TIMEOUT:-12}"
}

sunshine_api_url() {
  local configured host
  configured="$(render_template "${PVE_THIN_CLIENT_SUNSHINE_API_URL:-}" 2>/dev/null || true)"
  if [[ -n "$configured" ]]; then
    printf '%s\n' "$configured"
    return 0
  fi

  host="$(moonlight_host)"
  if [[ -n "$host" ]]; then
    printf 'https://%s:47990\n' "$host"
  fi
}

probe_stream_target() {
  local api_url host port connect_host effective_api_url
  local -a curl_opts
  local username password

  api_url="$1"
  host="$2"
  port="$(moonlight_port)"
  connect_host="${3:-$(moonlight_primary_connect_host)}"
  effective_api_url="$api_url"
  curl_opts=(-fsS -o /dev/null --connect-timeout 2 --max-time 4)
  username="${PVE_THIN_CLIENT_SUNSHINE_USERNAME:-}"
  password="${PVE_THIN_CLIENT_SUNSHINE_PASSWORD:-}"
  if prefer_ipv4 && [[ -n "$connect_host" ]] && [[ "$connect_host" != "$host" ]]; then
    curl_opts+=(-4)
    if [[ -n "$api_url" ]]; then
      effective_api_url="$(rewrite_url_host "$api_url" "$connect_host" 2>/dev/null || printf '%s\n' "$api_url")"
    fi
  fi
  if [[ -n "$username" && -n "$password" ]]; then
    curl_opts+=(--user "${username}:${password}")
  fi
  if [[ -n "$effective_api_url" ]]; then
    if [[ "$effective_api_url" == https://* ]]; then
      if [[ -n "${PVE_THIN_CLIENT_SUNSHINE_CA_CERT:-}" && -r "${PVE_THIN_CLIENT_SUNSHINE_CA_CERT}" ]]; then
        curl_opts+=(--cacert "${PVE_THIN_CLIENT_SUNSHINE_CA_CERT}")
        if [[ -n "${PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY:-}" ]]; then
          curl_opts+=(--pinnedpubkey "${PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY}")
        fi
      elif [[ -n "${PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY:-}" ]]; then
        curl_opts+=(-k --pinnedpubkey "${PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY}")
      elif [[ "${PVE_THIN_CLIENT_ALLOW_INSECURE_TLS:-0}" == "1" ]]; then
        curl_opts+=(-k)
      else
        effective_api_url=""
      fi
    fi
    if [[ -n "$effective_api_url" ]]; then
      curl "${curl_opts[@]}" "${effective_api_url%/}/api/apps" && return 0
    fi
  fi

  [[ -n "$host" ]] || return 1

  if [[ -n "$port" ]]; then
    python3 - "$host" "$port" "$connect_host" <<'PY' && return 0
import socket
import sys

candidates = [value for value in sys.argv[1:] if value]
port = int(candidates[1]) if len(candidates) > 1 else 0
hosts = [candidates[0]]
if len(candidates) > 2 and candidates[2] not in hosts:
    hosts.insert(0, candidates[2])

for host in hosts:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        continue
    for family, socktype, proto, _, sockaddr in infos:
        try:
            with socket.socket(family, socktype, proto) as sock:
                sock.settimeout(2.5)
                sock.connect(sockaddr)
            raise SystemExit(0)
        except OSError:
            continue

raise SystemExit(1)
PY
  fi

  return 1
}

effective_sunshine_api_url() {
  local api_url host connect_host rewritten

  api_url="$1"
  host="$2"
  connect_host="${3:-}"

  [[ -n "$api_url" ]] || return 1
  [[ -n "$host" ]] || {
    printf '%s\n' "$api_url"
    return 0
  }

  if prefer_ipv4 && [[ -n "$connect_host" ]] && [[ "$connect_host" != "$host" ]]; then
    rewritten="$(rewrite_url_host "$api_url" "$connect_host" 2>/dev/null || true)"
    if [[ -n "$rewritten" ]]; then
      printf '%s\n' "$rewritten"
      return 0
    fi
  fi

  printf '%s\n' "$api_url"
}

selected_sunshine_api_url() {
  local api_url host connect_host effective_api_url fallback_host rewritten

  api_url="$(sunshine_api_url)"
  host="$(moonlight_host)"
  connect_host="$(moonlight_primary_connect_host)"
  effective_api_url="$(effective_sunshine_api_url "$api_url" "$host" "$connect_host" 2>/dev/null || printf '%s\n' "$api_url")"
  if probe_stream_target "$api_url" "$host" "$connect_host"; then
    printf '%s\n' "$effective_api_url"
    return 0
  fi

  fallback_host="$(moonlight_gateway_fallback_host 2>/dev/null || true)"
  if [[ -n "$fallback_host" && -n "$api_url" ]]; then
    rewritten="$(rewrite_url_host "$api_url" "$fallback_host" 2>/dev/null || true)"
    if [[ -n "$rewritten" ]]; then
      printf '%s\n' "$rewritten"
      return 0
    fi
  fi

  printf '%s\n' "$api_url"
}

moonlight_client_config_path() {
  local candidate
  for candidate in \
    "${PVE_THIN_CLIENT_MOONLIGHT_CONFIG:-}" \
    "${HOME:-/home/thinclient}/.config/Moonlight Game Streaming Project/Moonlight.conf" \
    "/home/${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}/.config/Moonlight Game Streaming Project/Moonlight.conf"
  do
    [[ -n "$candidate" ]] || continue
    if [[ -r "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
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

extract_moonlight_certificate_pem() {
  local config_path
  config_path="$(moonlight_client_config_path 2>/dev/null || true)"
  [[ -n "$config_path" && -r "$config_path" ]] || return 1
  python3 - "$config_path" <<'PY'
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="ignore")
marker = 'certificate="@ByteArray('
start = text.find(marker)
if start < 0:
    raise SystemExit(1)
start += len(marker)
end = text.find(')"', start)
if end < 0:
    raise SystemExit(1)
payload = bytes(text[start:end], "utf-8").decode("unicode_escape")
print(payload)
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

register_moonlight_client_via_manager() {
  local manager_url manager_token manager_pin device_name client_cert response_file payload_file http_status
  local -a curl_args

  manager_url="${PVE_THIN_CLIENT_BEAGLE_MANAGER_URL:-}"
  manager_token="${PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-}"
  manager_pin="${PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY:-}"
  device_name="${PVE_THIN_CLIENT_MOONLIGHT_CLIENT_NAME:-${PVE_THIN_CLIENT_HOSTNAME:-$(hostname)}}"

  [[ -n "$manager_url" && -n "$manager_token" ]] || return 1
  client_cert="$(extract_moonlight_certificate_pem 2>/dev/null || true)"
  [[ -n "$client_cert" ]] || return 1

  response_file="$(mktemp)"
  payload_file="$(mktemp)"
  curl_args=(curl -fsS --connect-timeout 6 --max-time 30 --output "$response_file" --write-out '%{http_code}' \
    -H "Authorization: Bearer ${manager_token}" \
    -H 'Content-Type: application/json')
  if [[ "$manager_url" == https://* ]]; then
    if [[ -n "$manager_pin" ]]; then
      curl_args+=(--pinnedpubkey "$manager_pin")
    elif [[ "${PVE_THIN_CLIENT_ALLOW_INSECURE_TLS:-0}" == "1" ]]; then
      curl_args+=(-k)
    else
      rm -f "$payload_file"
      rm -f "$response_file"
      return 1
    fi
  fi

  python3 - "$client_cert" "$device_name" >"$payload_file" <<'PY'
import json
import sys

print(json.dumps({
    "client_cert_pem": sys.argv[1],
    "device_name": sys.argv[2],
}))
PY

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

moonlight_connect_host() {
  local host fallback_host api_url

  host="$(moonlight_primary_connect_host)"
  api_url="$(sunshine_api_url)"
  if probe_stream_target "$api_url" "$(moonlight_host)" "$host"; then
    printf '%s\n' "$host"
    return 0
  fi

  fallback_host="$(moonlight_gateway_fallback_host 2>/dev/null || true)"
  if [[ -n "$fallback_host" ]]; then
    printf '%s\n' "$fallback_host"
    return 0
  fi

  printf '%s\n' "$host"
}

moonlight_target_reachable() {
  local host connect_host api_url

  host="$(moonlight_host)"
  connect_host="$(moonlight_connect_host)"
  api_url="$(selected_sunshine_api_url)"
  probe_stream_target "$api_url" "$host" "$connect_host"
}

wait_for_stream_target() {
  local attempts delay attempt host connect_host port

  attempts="${PVE_THIN_CLIENT_STREAM_WAIT_RETRIES:-15}"
  delay="${PVE_THIN_CLIENT_STREAM_WAIT_DELAY:-2}"
  host="$(moonlight_host)"
  connect_host="$(moonlight_connect_host)"
  port="$(moonlight_port)"

  for attempt in $(seq 1 "$attempts"); do
    if moonlight_target_reachable; then
      beagle_log_event "moonlight.reachable" "host=${host} connect_host=${connect_host:-$host} port=${port:-default} attempt=${attempt}"
      return 0
    fi
    beagle_log_event "moonlight.waiting" "host=${host} connect_host=${connect_host:-$host} port=${port:-default} attempt=${attempt}/${attempts}"
    [[ "$attempt" -lt "$attempts" ]] || break
    sleep "$delay"
  done

  return 1
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

moonlight_list() {
  local bin host port timeout_value target
  bin="$(moonlight_bin)"
  host="$(moonlight_connect_host)"
  port="$(moonlight_port)"
  timeout_value="$(moonlight_list_timeout)"
  target="$(format_moonlight_target "$host" "$port")"

  if command -v timeout >/dev/null 2>&1; then
    timeout --preserve-status "$timeout_value" "$bin" list "$target" >"$MOONLIGHT_LIST_LOG" 2>&1
    return $?
  fi

  "$bin" list "$target" >"$MOONLIGHT_LIST_LOG" 2>&1
}

submit_sunshine_pin() {
  local api_url username password pin name response
  local -a curl_args

  api_url="$(selected_sunshine_api_url)"
  username="${PVE_THIN_CLIENT_SUNSHINE_USERNAME:-}"
  password="${PVE_THIN_CLIENT_SUNSHINE_PASSWORD:-}"
  pin="${PVE_THIN_CLIENT_SUNSHINE_PIN:-}"
  name="${PVE_THIN_CLIENT_MOONLIGHT_CLIENT_NAME:-${PVE_THIN_CLIENT_HOSTNAME:-$(hostname)}}"

  [[ -n "$api_url" && -n "$username" && -n "$password" && -n "$pin" ]] || return 1

  curl_args=(curl -fsS --connect-timeout 2 --max-time 4 --user "${username}:${password}" -H 'Content-Type: application/json')
  if [[ "$api_url" == https://* ]]; then
    if [[ -n "${PVE_THIN_CLIENT_SUNSHINE_CA_CERT:-}" && -r "${PVE_THIN_CLIENT_SUNSHINE_CA_CERT}" ]]; then
      curl_args+=(--cacert "${PVE_THIN_CLIENT_SUNSHINE_CA_CERT}")
      if [[ -n "${PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY:-}" ]]; then
        curl_args+=(--pinnedpubkey "${PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY}")
      fi
    elif [[ -n "${PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY:-}" ]]; then
      curl_args+=(-k --pinnedpubkey "${PVE_THIN_CLIENT_SUNSHINE_PINNED_PUBKEY}")
    elif [[ "${PVE_THIN_CLIENT_ALLOW_INSECURE_TLS:-0}" == "1" ]]; then
      curl_args+=(-k)
    else
      return 1
    fi
  fi

  response="$(
    "${curl_args[@]}" \
      --data "{\"pin\":\"${pin}\",\"name\":\"${name}\"}" \
      "${api_url%/}/api/pin"
  )" || return 1

  [[ "$(json_bool "$response")" == "1" ]]
}

ensure_paired() {
  local bin host port pin pair_pid paired_ok attempt pair_status target

  bin="$(moonlight_bin)"
  host="$(moonlight_connect_host)"
  port="$(moonlight_port)"
  pin="${PVE_THIN_CLIENT_SUNSHINE_PIN:-}"
  target="$(format_moonlight_target "$host" "$port")"

  moonlight_list && return 0

  if register_moonlight_client_via_manager; then
    beagle_log_event "moonlight.registered" "host=${host} port=${port:-default}"
    for attempt in $(seq 1 8); do
      sleep 1
      if moonlight_list; then
        return 0
      fi
    done
  fi

  [[ -n "$pin" ]] || return 1

  if command -v timeout >/dev/null 2>&1; then
    timeout --preserve-status "$(moonlight_list_timeout)" "$bin" pair "$target" --pin "$pin" >"$MOONLIGHT_PAIR_LOG" 2>&1 &
  else
    "$bin" pair "$target" --pin "$pin" >"$MOONLIGHT_PAIR_LOG" 2>&1 &
  fi
  pair_pid=$!
  paired_ok="0"

  for attempt in $(seq 1 20); do
    sleep 1
    if submit_sunshine_pin; then
      paired_ok="1"
      break
    fi
  done

  pair_status=0
  wait "$pair_pid" || pair_status=$?

  [[ "$pair_status" == "0" ]] || return "$pair_status"
  [[ "$paired_ok" == "1" ]] || return 1
  moonlight_list
}

build_stream_args() {
  local resolution fps bitrate codec decoder audio_config app host connect_host port target
  local -n out_ref="$1"

  host="$(moonlight_host)"
  connect_host="$(moonlight_connect_host)"
  port="$(moonlight_port)"
  target="$(format_moonlight_target "${connect_host:-$host}" "$port")"
  app="$(moonlight_app)"
  resolution="$(moonlight_resolution)"
  fps="${PVE_THIN_CLIENT_MOONLIGHT_FPS:-60}"
  bitrate="${PVE_THIN_CLIENT_MOONLIGHT_BITRATE:-20000}"
  codec="${PVE_THIN_CLIENT_MOONLIGHT_VIDEO_CODEC:-H.264}"
  decoder="$(moonlight_video_decoder)"
  audio_config="${PVE_THIN_CLIENT_MOONLIGHT_AUDIO_CONFIG:-stereo}"

  out_ref=("$(moonlight_bin)" stream "$target" "$app")

  case "$resolution" in
    720|1080|1440|4K)
      out_ref+=("--$resolution")
      ;;
    *x*)
      out_ref+=(--resolution "$resolution")
      ;;
  esac

  [[ -n "$fps" ]] && out_ref+=(--fps "$fps")
  [[ -n "$bitrate" ]] && out_ref+=(--bitrate "$bitrate")
  [[ -n "$codec" ]] && out_ref+=(--video-codec "$codec")
  [[ -n "$decoder" ]] && out_ref+=(--video-decoder "$decoder")
  [[ -n "$audio_config" ]] && out_ref+=(--audio-config "$audio_config")

  out_ref+=(--display-mode fullscreen --frame-pacing --keep-awake --no-hdr --no-yuv444)

  if [[ "${PVE_THIN_CLIENT_MOONLIGHT_ABSOLUTE_MOUSE:-1}" == "1" ]]; then
    out_ref+=(--absolute-mouse)
  fi
  if [[ "${PVE_THIN_CLIENT_MOONLIGHT_QUIT_AFTER:-0}" == "1" ]]; then
    out_ref+=(--quit-after)
  fi
}

configure_graphics_runtime() {
  export DISPLAY="${DISPLAY:-:0}"
  export HOME="${HOME:-/home/${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}}"
  export XAUTHORITY="$(select_xauthority)"
  export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
  export XDG_SESSION_TYPE="${XDG_SESSION_TYPE:-x11}"
  export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-x11}"
  unset WAYLAND_DISPLAY
  wait_for_x_display

  if [[ "$(moonlight_video_decoder)" == "software" ]]; then
    export QT_QUICK_BACKEND="${QT_QUICK_BACKEND:-software}"
    export LIBVA_DRIVER_NAME="${LIBVA_DRIVER_NAME:-none}"
    export VDPAU_DRIVER="${VDPAU_DRIVER:-noop}"
  fi
}

main() {
  local bin host connect_host app audio_driver port
  local -a args=()

  bin="$(moonlight_bin)"
  host="$(moonlight_host)"
  connect_host="$(moonlight_connect_host)"
  port="$(moonlight_port)"
  app="$(moonlight_app)"

  [[ -n "$host" ]] || {
    echo "Missing Moonlight host." >&2
    exit 1
  }

  have_binary "$bin" || {
    echo "Moonlight binary not found: $bin" >&2
    exit 1
  }

  audio_driver="$(moonlight_audio_driver)"
  if [[ -n "$audio_driver" && "$audio_driver" != "auto" ]]; then
    export SDL_AUDIODRIVER="$audio_driver"
  fi

  configure_graphics_runtime
  record_decoder_choice "$(moonlight_video_decoder)"

  wait_for_stream_target || {
    beagle_log_event "moonlight.unreachable" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
    echo "Moonlight host '$host' is unreachable from this network." >&2
    exit 1
  }

  if command -v /usr/local/bin/pve-thin-client-display-init >/dev/null 2>&1; then
    /usr/local/bin/pve-thin-client-display-init >/dev/null 2>&1 || true
  fi

  if command -v /usr/local/bin/pve-thin-client-audio-init >/dev/null 2>&1; then
    /usr/local/bin/pve-thin-client-audio-init >/dev/null 2>&1 || true
    pkill -f '^bash /usr/local/bin/pve-thin-client-audio-init --watch' >/dev/null 2>&1 || true
    /usr/local/bin/pve-thin-client-audio-init --watch "${PVE_THIN_CLIENT_AUDIO_WATCH_LOOPS:-0}" >/dev/null 2>&1 &
  fi

  if moonlight_host_configured; then
    beagle_log_event "moonlight.cached-config" "host=${host} connect_host=${connect_host:-$host} port=${port:-default}"
  elif ! moonlight_list; then
    ensure_paired || {
      beagle_log_event "moonlight.pairing-failed" "host=${host} port=${port:-default} pin=${PVE_THIN_CLIENT_SUNSHINE_PIN:-unset}"
      echo "Moonlight pairing failed for host '$host'." >&2
      exit 1
    }
  fi

  build_stream_args args
  if [[ -n "$connect_host" && "$connect_host" != "$host" ]]; then
    echo "Starting Moonlight stream: host=$host resolved_ipv4=$connect_host port=${port:-default} app=$app resolution=$(moonlight_resolution) fps=${PVE_THIN_CLIENT_MOONLIGHT_FPS:-60}" >&2
  else
    echo "Starting Moonlight stream: host=$host port=${port:-default} app=$app resolution=$(moonlight_resolution) fps=${PVE_THIN_CLIENT_MOONLIGHT_FPS:-60}" >&2
  fi
  beagle_log_event "moonlight.exec" "host=${host} connect_host=${connect_host:-$host} port=${port:-default} app=${app} resolution=$(moonlight_resolution) fps=${PVE_THIN_CLIENT_MOONLIGHT_FPS:-60}"
  exec "${args[@]}"
}

main "$@"
