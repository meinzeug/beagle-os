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
from urllib.parse import parse_qs, urlparse
import os

url = sys.argv[1]
output = Path(sys.argv[2])
username = sys.argv[3]
password = sys.argv[4]
token = sys.argv[5]

parsed = urlparse(url if "://" in url else f"dcv://{url}")
host = parsed.hostname or ""
port = parsed.port or 8443
path = os.environ.get("PVE_THIN_CLIENT_DCV_WEB_URL_PATH", "").strip() or (parsed.path or "/")
query = parse_qs(parsed.query, keep_blank_values=False)
session_id = os.environ.get("PVE_THIN_CLIENT_DCV_SESSION_ID", "").strip() or parsed.fragment.strip()
auth_token = token or (query.get("authToken", [""])[0].strip())
transport = os.environ.get("PVE_THIN_CLIENT_DCV_TRANSPORT", "").strip().lower() or (query.get("transport", [""])[0].strip().lower())
proxy_type = os.environ.get("PVE_THIN_CLIENT_DCV_PROXY_TYPE", "").strip().upper() or "SYSTEM"
proxy_host = os.environ.get("PVE_THIN_CLIENT_DCV_PROXY_HOST", "").strip()
proxy_port = os.environ.get("PVE_THIN_CLIENT_DCV_PROXY_PORT", "").strip()

if not host:
    raise SystemExit("Unable to determine the DCV host from the configured URL.")

if auth_token and not session_id:
    raise SystemExit("DCV auth tokens require a session ID (#sessionId or PVE_THIN_CLIENT_DCV_SESSION_ID).")

if transport and transport not in {"websocket", "quic"}:
    raise SystemExit(f"Unsupported DCV transport: {transport}")

if proxy_type not in {"HTTPS", "HTTP", "SOCKS5", "SOCKS", "SYSTEM", "NONE", "DIRECT"}:
    raise SystemExit(f"Unsupported DCV proxy type: {proxy_type}")

lines = [
    "[version]",
    "format=1.0",
    "[connect]",
    f"host={host}",
    f"port={port}",
    f"proxytype={proxy_type}",
]

if path and path != "/":
    lines.append(f"weburlpath={path}")
if session_id:
    lines.append(f"sessionid={session_id}")
if username:
    lines.append(f"user={username}")
if password:
    lines.append(f"password={password}")
if auth_token:
    lines.append(f"authtoken={auth_token}")
if transport:
    lines.append(f"transport={transport}")
if proxy_host:
    lines.append(f"proxyhost={proxy_host}")
if proxy_port:
    lines.append(f"proxyport={proxy_port}")

output.write_text("\n".join(lines) + "\n")
output.chmod(0o600)
print(output)
PY
