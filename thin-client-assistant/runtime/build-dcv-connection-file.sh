#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_runtime_config

URL="$(render_template "${PVE_THIN_CLIENT_DCV_URL:-}")"
if [[ -z "$URL" ]]; then
  echo "Missing DCV URL." >&2
  exit 1
fi

OUTPUT_FILE="${1:-$(mktemp --suffix=.dcv)}"
python3 - "$URL" "$OUTPUT_FILE" "${PVE_THIN_CLIENT_CONNECTION_USERNAME:-}" "${PVE_THIN_CLIENT_CONNECTION_PASSWORD:-}" "${PVE_THIN_CLIENT_CONNECTION_TOKEN:-}" <<'PY'
import sys
from pathlib import Path
from urllib.parse import urlparse

url = sys.argv[1]
output = Path(sys.argv[2])
username = sys.argv[3]
password = sys.argv[4]
token = sys.argv[5]

parsed = urlparse(url if "://" in url else f"dcv://{url}")
host = parsed.hostname or ""
port = parsed.port or 8443
path = parsed.path or "/"

lines = [
    "[version]",
    "format=1.0",
    "[connect]",
    f"host={host}",
    f"port={port}",
]

if path and path != "/":
    lines.append(f"weburlpath={path}")
if username:
    lines.append(f"user={username}")
if password:
    lines.append(f"password={password}")
if token:
    lines.append(f"authtoken={token}")

output.write_text("\n".join(lines) + "\n")
print(output)
PY
