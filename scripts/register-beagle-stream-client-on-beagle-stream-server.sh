#!/usr/bin/env bash
set -euo pipefail

BEAGLE_STREAM_SERVER_STATE="${BEAGLE_STREAM_SERVER_STATE:-$HOME/.config/beagle-stream-server/beagle_stream_server_state.json}"
CLIENT_CONFIG="${CLIENT_CONFIG:-}"
DEVICE_NAME="${DEVICE_NAME:-beagle-os-client}"
RESTART_BEAGLE_STREAM_SERVER="${RESTART_BEAGLE_STREAM_SERVER:-1}"

usage() {
  cat <<EOF
Usage: $0 --client-config /path/to/Beagle Stream Client.conf [--beagle-stream-server-state /path/to/beagle_stream_server_state.json] [--device-name NAME] [--no-restart]

Registers the Beagle Stream Client client certificate from a Beagle endpoint on a Beagle Stream Server host
so the endpoint can stream without an interactive pairing workflow.
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --client-config) CLIENT_CONFIG="$2"; shift 2 ;;
      --beagle-stream-server-state) BEAGLE_STREAM_SERVER_STATE="$2"; shift 2 ;;
      --device-name) DEVICE_NAME="$2"; shift 2 ;;
      --no-restart) RESTART_BEAGLE_STREAM_SERVER="0"; shift ;;
      -h|--help) usage; exit 0 ;;
      *)
        echo "Unknown argument: $1" >&2
        usage
        exit 1
        ;;
    esac
  done
}

restart_beagle_stream_server() {
  if [[ "$RESTART_BEAGLE_STREAM_SERVER" != "1" ]]; then
    return 0
  fi

  if systemctl --user list-unit-files beagle-stream-server.service >/dev/null 2>&1; then
    systemctl --user restart beagle-stream-server.service >/dev/null 2>&1 || true
    return 0
  fi

  pkill -x beagle-stream-server >/dev/null 2>&1 || true
  nohup beagle-stream-server >/dev/null 2>&1 </dev/null &
  sleep 2
}

main() {
  parse_args "$@"

  [[ -n "$CLIENT_CONFIG" ]] || {
    echo "--client-config is required" >&2
    exit 1
  }
  [[ -r "$CLIENT_CONFIG" ]] || {
    echo "Beagle Stream Client client config is not readable: $CLIENT_CONFIG" >&2
    exit 1
  }
  [[ -f "$BEAGLE_STREAM_SERVER_STATE" ]] || {
    echo "Beagle Stream Server state file not found: $BEAGLE_STREAM_SERVER_STATE" >&2
    exit 1
  }

  python3 - "$CLIENT_CONFIG" "$BEAGLE_STREAM_SERVER_STATE" "$DEVICE_NAME" <<'PY'
import json
import sys
import uuid
from pathlib import Path

client_config = Path(sys.argv[1])
beagle_stream_server_state = Path(sys.argv[2])
device_name = sys.argv[3]

text = client_config.read_text()
marker = 'certificate="@ByteArray('
start = text.find(marker)
if start < 0:
    raise SystemExit("Beagle Stream Client certificate not found in client config.")

start += len(marker)
end = text.find(')"\nkey=', start)
if end < 0:
    raise SystemExit("Unable to parse Beagle Stream Client certificate payload.")

cert = bytes(text[start:end], "utf-8").decode("unicode_escape")

state = json.loads(beagle_stream_server_state.read_text())
root = state.setdefault("root", {})
named_devices = root.setdefault("named_devices", [])

for entry in named_devices:
    if entry.get("cert") == cert:
        entry["name"] = device_name
        beagle_stream_server_state.write_text(json.dumps(state, indent=4) + "\n")
        print("updated-existing")
        raise SystemExit(0)

named_devices.append(
    {
        "name": device_name,
        "cert": cert,
        "uuid": str(uuid.uuid4()).upper(),
    }
)

beagle_stream_server_state.write_text(json.dumps(state, indent=4) + "\n")
print("registered-new")
PY

  restart_beagle_stream_server
}

main "$@"
