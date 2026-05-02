#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATUS_DIR="${BEAGLE_STATUS_DIR:-/var/lib/beagle}"
STATUS_FILE="$STATUS_DIR/system-updates-status.json"
STATUS_GROUP="${BEAGLE_CONTROL_USER:-beagle-manager}"

START_TS="$(date +%s)"
STATUS_RESULT="running"
STATUS_MESSAGE="Systemupdates werden vorbereitet ..."
ERROR_EXCERPT=""
OUTPUT_EXCERPT=""

ensure_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi
  if command -v sudo >/dev/null 2>&1; then
    exec sudo "$0" "$@"
  fi
  echo "This command must run as root or use sudo." >&2
  exit 1
}

write_status() {
  local status="$1"
  local finished_ts
  finished_ts="$(date +%s)"
  install -d -m 0755 "$STATUS_DIR"
  python3 - "$STATUS_FILE" "$status" "$START_TS" "$finished_ts" "$STATUS_MESSAGE" "$ERROR_EXCERPT" "$OUTPUT_EXCERPT" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
status = sys.argv[2]
started = int(sys.argv[3])
finished = int(sys.argv[4])
message = sys.argv[5]
error_excerpt = sys.argv[6]
output_excerpt = sys.argv[7]

payload = {
    "status": status,
    "message": message,
    "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat(),
    "updated_at": datetime.fromtimestamp(finished, timezone.utc).isoformat(),
    "duration_seconds": max(0, finished - started),
}
if status in {"ok", "failed"}:
    payload["finished_at"] = datetime.fromtimestamp(finished, timezone.utc).isoformat()
if error_excerpt:
    payload["error_excerpt"] = error_excerpt
if output_excerpt:
    payload["output_excerpt"] = output_excerpt
payload["reboot_required"] = Path("/run/reboot-required").exists()
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
  if getent group "$STATUS_GROUP" >/dev/null 2>&1; then
    chgrp "$STATUS_GROUP" "$STATUS_FILE" || true
  fi
  chmod 0640 "$STATUS_FILE" || true
}

capture_failure() {
  local command="${BASH_COMMAND:-unknown command}"
  STATUS_RESULT="failed"
  STATUS_MESSAGE="Systemupdates konnten nicht installiert werden."
  ERROR_EXCERPT="Command failed: ${command:0:400}"
}

trap 'capture_failure' ERR
trap 'write_status "$STATUS_RESULT"' EXIT

ensure_root "$@"
write_status "running"

STATUS_MESSAGE="APT-Paketlisten werden aktualisiert ..."
write_status "running"
apt_update_output="$(apt-get update -qq 2>&1)"
OUTPUT_EXCERPT="${apt_update_output: -1200}"

STATUS_MESSAGE="Verfuegbare Systemupdates werden installiert ..."
write_status "running"
upgrade_output="$(
  DEBIAN_FRONTEND=noninteractive \
    apt-get upgrade --with-new-pkgs -y -qq -o Dpkg::Options::=--force-confold 2>&1
)"
OUTPUT_EXCERPT="${upgrade_output: -2000}"

STATUS_RESULT="ok"
STATUS_MESSAGE="Systemupdates erfolgreich installiert."
