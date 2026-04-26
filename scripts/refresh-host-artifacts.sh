#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${PVE_DCV_CONFIG_DIR:-/etc/beagle}"
HOST_ENV_FILE="${PVE_DCV_HOST_ENV_FILE:-$CONFIG_DIR/host.env}"
STATUS_DIR="${PVE_DCV_STATUS_DIR:-/var/lib/beagle}"
REFRESH_STATUS_FILE="$STATUS_DIR/refresh.status.json"
BEAGLE_HOST_PROVIDER="${BEAGLE_HOST_PROVIDER:-proxmox}"
REFRESH_STATUS_GROUP="${BEAGLE_CONTROL_USER:-beagle-manager}"

START_TS="$(date +%s)"
STATUS_RESULT="running"
CURRENT_STEP="init"
CURRENT_PROGRESS=0
CURRENT_MESSAGE="Artifact-Refresh initialisiert ..."
ERROR_EXCERPT=""

write_status_payload() {
  local status="$1"
  local end_ts duration version

  end_ts="$(date +%s)"
  duration="$(( end_ts - START_TS ))"
  version="$(tr -d ' \n\r' < "$ROOT_DIR/VERSION" 2>/dev/null || echo unknown)"

  install -d -m 0755 "$STATUS_DIR"
  python3 - "$REFRESH_STATUS_FILE" "$status" "$version" "$START_TS" "$end_ts" "$duration" "$CURRENT_STEP" "$CURRENT_PROGRESS" "$CURRENT_MESSAGE" "$ERROR_EXCERPT" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
status = sys.argv[2]
version = sys.argv[3]
started = int(sys.argv[4])
ended = int(sys.argv[5])
duration = int(sys.argv[6])
step = sys.argv[7]
progress = int(sys.argv[8])
message = sys.argv[9]
error_excerpt = sys.argv[10]

payload = {
    "status": status,
    "version": version,
    "step": step,
    "progress": progress,
    "message": message,
    "last_result": status,
    "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat(),
    "updated_at": datetime.fromtimestamp(ended, timezone.utc).isoformat(),
    "duration_seconds": duration,
}
if status in {"ok", "failed"}:
    payload["finished_at"] = datetime.fromtimestamp(ended, timezone.utc).isoformat()
if error_excerpt:
    payload["error_excerpt"] = error_excerpt
path.write_text(json.dumps(payload, indent=2) + "\n")
PY
  if getent group "$REFRESH_STATUS_GROUP" >/dev/null 2>&1; then
    chgrp "$REFRESH_STATUS_GROUP" "$REFRESH_STATUS_FILE" || true
  fi
  chmod 0640 "$REFRESH_STATUS_FILE" || true
}

write_refresh_status() {
  write_status_payload "$STATUS_RESULT"
}

update_refresh_step() {
  CURRENT_STEP="$1"
  CURRENT_PROGRESS="$2"
  CURRENT_MESSAGE="$3"
  write_status_payload "running"
}

capture_refresh_error() {
  local failed_command
  failed_command="${BASH_COMMAND:-unknown command}"
  ERROR_EXCERPT="Command failed: ${failed_command:0:360}"
  CURRENT_MESSAGE="Fehler bei Schritt '$CURRENT_STEP'."
  STATUS_RESULT="failed"
}

ensure_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi

  if command -v sudo >/dev/null 2>&1; then
    exec sudo \
      PVE_DCV_CONFIG_DIR="$CONFIG_DIR" \
      PVE_DCV_HOST_ENV_FILE="$HOST_ENV_FILE" \
      BEAGLE_HOST_PROVIDER="$BEAGLE_HOST_PROVIDER" \
      "$0" "$@"
  fi

  echo "This command must run as root or use sudo." >&2
  exit 1
}

load_host_env() {
  if [[ -f "$HOST_ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$HOST_ENV_FILE"
  fi
}

trap capture_refresh_error ERR
trap write_refresh_status EXIT

ensure_root "$@"
load_host_env

update_refresh_step "preflight" 5 "Host-Umgebung und Download-Variablen werden vorbereitet ..."

export PVE_DCV_PROXY_SERVER_NAME="${PVE_DCV_PROXY_SERVER_NAME:-$(hostname -f 2>/dev/null || hostname)}"
export PVE_DCV_PROXY_LISTEN_PORT="${PVE_DCV_PROXY_LISTEN_PORT:-8443}"
export PVE_DCV_DOWNLOADS_PATH="${PVE_DCV_DOWNLOADS_PATH:-/beagle-downloads}"
export PVE_DCV_DOWNLOADS_BASE_URL="${PVE_DCV_DOWNLOADS_BASE_URL:-https://${PVE_DCV_PROXY_SERVER_NAME}:${PVE_DCV_PROXY_LISTEN_PORT}${PVE_DCV_DOWNLOADS_PATH}}"
export BEAGLE_HOST_PROVIDER="${BEAGLE_HOST_PROVIDER:-proxmox}"

update_refresh_step "prepare-host-downloads" 20 "Host-Downloads, Statusdateien und Installer-Launcher werden abgeglichen ..."
"$ROOT_DIR/scripts/prepare-host-downloads.sh"

update_refresh_step "finalize" 95 "Artefakte werden abgeschlossen und Statusdateien geschrieben ..."
STATUS_RESULT="ok"
CURRENT_PROGRESS=100
CURRENT_MESSAGE="Host-Artefakte erfolgreich aktualisiert."

echo "Refreshed hosted artifacts under $ROOT_DIR/dist"
