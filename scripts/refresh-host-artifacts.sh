#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${PVE_DCV_CONFIG_DIR:-/etc/beagle}"
HOST_ENV_FILE="${PVE_DCV_HOST_ENV_FILE:-$CONFIG_DIR/host.env}"
STATUS_DIR="${PVE_DCV_STATUS_DIR:-/var/lib/beagle}"
REFRESH_STATUS_FILE="$STATUS_DIR/refresh.status.json"
BEAGLE_HOST_PROVIDER="${BEAGLE_HOST_PROVIDER:-beagle}"
REFRESH_STATUS_GROUP="${BEAGLE_CONTROL_USER:-beagle-manager}"

START_TS="$(date +%s)"
STATUS_RESULT="running"
CURRENT_STEP="init"
CURRENT_PROGRESS=0
CURRENT_MESSAGE="Artifact-Refresh initialisiert ..."
ERROR_EXCERPT=""
CURRENT_DETAIL=""
CURRENT_HINT=""
CURRENT_ACTIVE_PROCESSES=""
STATUS_HEARTBEAT_PID=""

write_status_payload() {
  local status="$1"
  local end_ts duration version

  end_ts="$(date +%s)"
  duration="$(( end_ts - START_TS ))"
  version="$(tr -d ' \n\r' < "$ROOT_DIR/VERSION" 2>/dev/null || echo unknown)"

  install -d -m 0755 "$STATUS_DIR"
  python3 - "$REFRESH_STATUS_FILE" "$status" "$version" "$START_TS" "$end_ts" "$duration" "$CURRENT_STEP" "$CURRENT_PROGRESS" "$CURRENT_MESSAGE" "$ERROR_EXCERPT" "$CURRENT_DETAIL" "$CURRENT_HINT" "$CURRENT_ACTIVE_PROCESSES" <<'PY'
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
detail = sys.argv[11]
hint = sys.argv[12]
active_processes_raw = sys.argv[13]

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
if detail or hint or active_processes_raw:
    payload["build_activity"] = {
        "running": status == "running",
        "label": step,
        "detail": detail,
        "hint": hint,
        "elapsed_seconds": duration,
        "active_processes": [
            line.strip()[:220]
            for line in active_processes_raw.splitlines()
            if line.strip()
        ][:12],
    }
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
  CURRENT_DETAIL=""
  CURRENT_HINT=""
  CURRENT_ACTIVE_PROCESSES=""
  write_status_payload "running"
}

detect_refresh_activity() {
  local processes process_blob
  processes="$(pgrep -af 'repo-auto-update|refresh-host-artifacts|prepare-host-downloads|package.sh|build-thin-client-installer|build-server-installer|build-server-installimage|/usr/lib/live/build|lb build|apt-get|dpkg|update-initramfs|mkinitramfs|mksquashfs|xorriso|grub-mkrescue|npm run dist' 2>/dev/null | grep -v 'pgrep -af' | head -12 || true)"
  process_blob="$(printf '%s' "$processes" | tr '[:upper:]' '[:lower:]')"
  CURRENT_ACTIVE_PROCESSES="$processes"
  CURRENT_HINT="Die WebUI aktualisiert diesen Live-Status automatisch. Lange ISO-/SquashFS-Builds koennen 10 bis 30 Minuten dauern."

  if [[ "$process_blob" == *"mksquashfs"* ]]; then
    CURRENT_STEP="thin-client-squashfs"
    CURRENT_PROGRESS=68
    CURRENT_MESSAGE="Thin-Client-Root-Dateisystem wird komprimiert ..."
    CURRENT_DETAIL="SquashFS packt das komplette Live-System. Dieser Schritt ist CPU-/IO-intensiv und kann lange ohne sichtbaren Prozent-Sprung laufen."
  elif [[ "$process_blob" == *"xorriso"* || "$process_blob" == *"grub-mkrescue"* ]]; then
    CURRENT_STEP="thin-client-iso"
    CURRENT_PROGRESS=76
    CURRENT_MESSAGE="Thin-Client-ISO wird geschrieben ..."
    CURRENT_DETAIL="Bootloader, Kernel, Initramfs und Live-Dateisystem werden zur startfaehigen ISO zusammengebaut."
  elif [[ "$process_blob" == *"mkinitramfs"* || "$process_blob" == *"update-initramfs"* ]]; then
    CURRENT_STEP="thin-client-initramfs"
    CURRENT_PROGRESS=58
    CURRENT_MESSAGE="Boot-Image fuer den Thin Client wird vorbereitet ..."
    CURRENT_DETAIL="Kernel- und Initramfs-Dateien werden im Live-System erzeugt."
  elif [[ "$process_blob" == *"chroot_hooks"* ]]; then
    CURRENT_STEP="thin-client-config"
    CURRENT_PROGRESS=54
    CURRENT_MESSAGE="Beagle Live-System wird konfiguriert ..."
    CURRENT_DETAIL="Beagle-Hooks konfigurieren Runtime, Installer, Dienste und Bootverhalten im chroot."
  elif [[ "$process_blob" == *"chroot_install-packages"* || "$process_blob" == *"apt-get"* || "$process_blob" == *"dpkg"* ]]; then
    CURRENT_STEP="thin-client-packages"
    CURRENT_PROGRESS=42
    CURRENT_MESSAGE="Pakete und Treiber werden in das Live-System installiert ..."
    CURRENT_DETAIL="Debian-Pakete, Firmware, Grafik-/Audio-Komponenten, Moonlight-Abhaengigkeiten und Installer-Tools werden installiert."
  elif [[ "$process_blob" == *"binary_rootfs"* || "$process_blob" == *"/usr/lib/live/build/binary"* ]]; then
    CURRENT_STEP="thin-client-binary"
    CURRENT_PROGRESS=64
    CURRENT_MESSAGE="Bootfaehiges Live-Image wird zusammengesetzt ..."
    CURRENT_DETAIL="Live-build erzeugt die finalen Binary-Artefakte aus dem vorbereiteten Root-Dateisystem."
  elif [[ "$process_blob" == *"build-thin-client-installer"* || "$process_blob" == *"/usr/lib/live/build"* ]]; then
    CURRENT_STEP="thin-client-live-build"
    CURRENT_PROGRESS=35
    CURRENT_MESSAGE="Thin-Client-Live-Image wird gebaut ..."
    CURRENT_DETAIL="Das Beagle OS Thin-Client-Image wird inklusive Bootloader, Runtime und Installer erzeugt."
  elif [[ "$process_blob" == *"build-server-installimage"* ]]; then
    CURRENT_STEP="server-installimage"
    CURRENT_PROGRESS=84
    CURRENT_MESSAGE="Server-Installimage wird gebaut ..."
    CURRENT_DETAIL="Das Bare-Metal-Server-Installimage wird vorbereitet und paketiert."
  elif [[ "$process_blob" == *"build-server-installer"* ]]; then
    CURRENT_STEP="server-installer"
    CURRENT_PROGRESS=80
    CURRENT_MESSAGE="Server-Installer-ISO wird gebaut ..."
    CURRENT_DETAIL="Die Beagle Server-Installer-ISO wird erzeugt."
  elif [[ "$process_blob" == *"package.sh"* ]]; then
    CURRENT_STEP="package"
    CURRENT_PROGRESS=28
    CURRENT_MESSAGE="Release-Paketierung laeuft ..."
    CURRENT_DETAIL="Downloads, Checksummen und versionierte Artefakte werden zusammengefuehrt."
  fi
}

refresh_status_heartbeat() {
  while true; do
    detect_refresh_activity
    write_status_payload "running"
    sleep 10
  done
}

start_refresh_heartbeat() {
  refresh_status_heartbeat &
  STATUS_HEARTBEAT_PID="$!"
}

stop_refresh_heartbeat() {
  if [[ -n "$STATUS_HEARTBEAT_PID" ]] && kill -0 "$STATUS_HEARTBEAT_PID" >/dev/null 2>&1; then
    kill "$STATUS_HEARTBEAT_PID" >/dev/null 2>&1 || true
    wait "$STATUS_HEARTBEAT_PID" >/dev/null 2>&1 || true
  fi
  STATUS_HEARTBEAT_PID=""
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

trap 'capture_refresh_error; stop_refresh_heartbeat' ERR
trap 'stop_refresh_heartbeat; write_refresh_status' EXIT

ensure_root "$@"
load_host_env

update_refresh_step "preflight" 5 "Host-Umgebung und Download-Variablen werden vorbereitet ..."

export PVE_DCV_PROXY_SERVER_NAME="${PVE_DCV_PROXY_SERVER_NAME:-$(hostname -f 2>/dev/null || hostname)}"
export PVE_DCV_PROXY_LISTEN_PORT="${PVE_DCV_PROXY_LISTEN_PORT:-443}"
export PVE_DCV_DOWNLOADS_PATH="${PVE_DCV_DOWNLOADS_PATH:-/beagle-downloads}"
export PVE_DCV_DOWNLOADS_BASE_URL="$(
  if [[ "${PVE_DCV_PROXY_LISTEN_PORT:-443}" == "443" ]]; then
    printf 'https://%s%s\n' "${PVE_DCV_PROXY_SERVER_NAME}" "${PVE_DCV_DOWNLOADS_PATH}"
  else
    printf 'https://%s:%s%s\n' "${PVE_DCV_PROXY_SERVER_NAME}" "${PVE_DCV_PROXY_LISTEN_PORT}" "${PVE_DCV_DOWNLOADS_PATH}"
  fi
)"
export BEAGLE_HOST_PROVIDER="${BEAGLE_HOST_PROVIDER:-beagle}"

update_refresh_step "prepare-host-downloads" 20 "Host-Downloads, Statusdateien und Installer-Launcher werden abgeglichen ..."
start_refresh_heartbeat
"$ROOT_DIR/scripts/prepare-host-downloads.sh"
stop_refresh_heartbeat

update_refresh_step "finalize" 95 "Artefakte werden abgeschlossen und Statusdateien geschrieben ..."
STATUS_RESULT="ok"
CURRENT_PROGRESS=100
CURRENT_MESSAGE="Host-Artefakte erfolgreich aktualisiert."

echo "Refreshed hosted artifacts under $ROOT_DIR/dist"
