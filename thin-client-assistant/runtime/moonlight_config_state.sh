#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOONLIGHT_HOST_SYNC_SH="${MOONLIGHT_HOST_SYNC_SH:-$SCRIPT_DIR/moonlight_host_sync.sh}"

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

# shellcheck disable=SC1090
source "$MOONLIGHT_HOST_SYNC_SH"
