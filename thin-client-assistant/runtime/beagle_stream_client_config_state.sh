#!/usr/bin/env bash

SCRIPT_DIR="${RUNTIME_SCRIPT_DIR:-/usr/local/lib/pve-thin-client/runtime}"
BEAGLE_STREAM_CLIENT_HOST_SYNC_SH="${BEAGLE_STREAM_CLIENT_HOST_SYNC_SH:-$SCRIPT_DIR/beagle_stream_client_host_sync.sh}"

beagle_stream_client_default_config_path() {
  if [[ -n "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_CONFIG:-}" ]]; then
    printf '%s\n' "$PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_CONFIG"
    return 0
  fi
  printf '/home/%s/.config/Beagle OS/BeagleStream.conf\n' "${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}"
}

beagle_stream_client_config_path() {
  local candidate
  if [[ -n "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_CONFIG:-}" ]]; then
    [[ -r "$PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_CONFIG" ]] || return 1
    printf '%s\n' "$PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_CONFIG"
    return 0
  fi
  for candidate in \
    "${HOME:-/home/thinclient}/.config/Beagle OS/BeagleStream.conf" \
    "${HOME:-/home/thinclient}/.config/Beagle Stream Client Game Streaming Project/Beagle Stream Client.conf" \
    "${HOME:-/home/thinclient}/.config/Moonlight Game Streaming Project/Moonlight.conf" \
    "/home/${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}/.config/Beagle OS/BeagleStream.conf" \
    "/home/${PVE_THIN_CLIENT_RUNTIME_USER:-thinclient}/.config/Beagle Stream Client Game Streaming Project/Beagle Stream Client.conf" \
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

beagle_stream_client_uniqueid() {
  local config_path
  config_path="$(beagle_stream_client_config_path 2>/dev/null || true)"
  [[ -n "$config_path" && -r "$config_path" ]] || return 1
  python3 - "$config_path" <<'PY'
from pathlib import Path
import sys

for raw in Path(sys.argv[1]).read_text(encoding="utf-8", errors="ignore").splitlines():
    if raw.strip().startswith("uniqueid="):
        value = raw.split("=", 1)[1].strip()
        if value:
            print(value)
            raise SystemExit(0)
raise SystemExit(1)
PY
}

extract_beagle_stream_client_certificate_pem() {
  local config_path
  config_path="$(beagle_stream_client_config_path 2>/dev/null || true)"
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

ensure_beagle_stream_client_config() {
  local config_path config_dir tmp_dir cert_file key_file uniqueid device_name

  if extract_beagle_stream_client_certificate_pem >/dev/null 2>&1; then
    uniqueid="$(beagle_stream_client_uniqueid 2>/dev/null || true)"
    if [[ -n "$uniqueid" && -z "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_UNIQUEID:-}" ]]; then
      export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_UNIQUEID="$uniqueid"
    fi
    return 0
  fi

  command -v openssl >/dev/null 2>&1 || return 1
  command -v python3 >/dev/null 2>&1 || return 1

  config_path="$(beagle_stream_client_default_config_path)"
  [[ -n "$config_path" ]] || return 1
  config_dir="${config_path%/*}"
  [[ "$config_dir" != "$config_path" ]] || return 1
  mkdir -p "$config_dir" || return 1
  chmod 0700 "$config_dir" 2>/dev/null || true

  tmp_dir="$(mktemp -d)"
  cert_file="$tmp_dir/client.crt"
  key_file="$tmp_dir/client.key"
  uniqueid="$(openssl rand -hex 8 2>/dev/null | tr '[:lower:]' '[:upper:]' || true)"
  [[ -n "$uniqueid" ]] || uniqueid="0123456789ABCDEF"
  device_name="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_NAME:-${PVE_THIN_CLIENT_HOSTNAME:-beagle-stream-client}}"

  if ! openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 3650 \
    -subj "/CN=${device_name//\//-}" \
    -keyout "$key_file" \
    -out "$cert_file" >/dev/null 2>&1
  then
    rm -rf "$tmp_dir"
    return 1
  fi

  if ! python3 - "$config_path" "$cert_file" "$key_file" "$uniqueid" <<'PY'
from pathlib import Path
import sys

config_path = Path(sys.argv[1])
cert = Path(sys.argv[2]).read_text(encoding="utf-8")
key = Path(sys.argv[3]).read_text(encoding="utf-8")
uniqueid = sys.argv[4].strip() or "0123456789ABCDEF"


def qt_bytearray(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n")


def find_section(lines: list[str], name: str) -> tuple[int | None, int]:
    section_start = None
    section_end = len(lines)
    header = f"[{name}]"
    for idx, line in enumerate(lines):
        if line.strip() == header:
            section_start = idx
            for next_idx in range(idx + 1, len(lines)):
                if lines[next_idx].startswith("[") and lines[next_idx].endswith("]"):
                    section_end = next_idx
                    break
            break
    return section_start, section_end


lines = config_path.read_text(encoding="utf-8", errors="ignore").splitlines() if config_path.exists() else []
general_lines = [
    f'certificate="@ByteArray({qt_bytearray(cert)})"',
    f'key="@ByteArray({qt_bytearray(key)})"',
    f"uniqueid={uniqueid}",
]

section_start, section_end = find_section(lines, "General")
if section_start is None:
    replacement = ["[General]", *general_lines, ""]
    lines = replacement + lines
else:
    preserved = []
    for raw in lines[section_start + 1 : section_end]:
        key_name = raw.split("=", 1)[0].strip()
        if key_name in {"certificate", "key", "uniqueid"}:
            continue
        preserved.append(raw)
    lines = lines[: section_start + 1] + general_lines + preserved + lines[section_end:]

config_path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
PY
  then
    rm -rf "$tmp_dir"
    return 1
  fi

  chmod 0600 "$config_path" 2>/dev/null || true
  rm -rf "$tmp_dir"
  export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_CONFIG="$config_path"
  export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_UNIQUEID="$uniqueid"
  extract_beagle_stream_client_certificate_pem >/dev/null 2>&1
}

# shellcheck disable=SC1090
source "$BEAGLE_STREAM_CLIENT_HOST_SYNC_SH"
