#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETTINGS_FILE="${BEAGLE_SETTINGS_FILE:-${BEAGLE_MANAGER_DATA_DIR:-/var/lib/beagle/beagle-manager}/server-settings.json}"
STATUS_DIR="${BEAGLE_STATUS_DIR:-/var/lib/beagle}"
STATUS_FILE="$STATUS_DIR/artifact-watchdog-status.json"
REFRESH_STATUS_FILE="$STATUS_DIR/refresh.status.json"
DIST_DIR="${BEAGLE_DIST_DIR:-$ROOT_DIR/dist}"
REFRESH_SERVICE_NAME="${BEAGLE_ARTIFACT_REFRESH_SERVICE:-beagle-artifacts-refresh.service}"

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

ensure_root "$@"
install -d -m 0755 "$STATUS_DIR"

python3 - "$SETTINGS_FILE" "$STATUS_FILE" "$REFRESH_STATUS_FILE" "$DIST_DIR" "$REFRESH_SERVICE_NAME" <<'PY'
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

settings_path = Path(sys.argv[1])
status_path = Path(sys.argv[2])
refresh_status_path = Path(sys.argv[3])
dist_dir = Path(sys.argv[4])
refresh_service_name = sys.argv[5]

required = [
    "beagle-downloads-status.json",
    "pve-thin-client-live-usb-latest.sh",
    "pve-thin-client-live-usb-latest.ps1",
    "pve-thin-client-usb-installer-latest.sh",
    "pve-thin-client-usb-installer-latest.ps1",
    "pve-thin-client-usb-payload-latest.tar.gz",
]
latest_public = [
    "pve-thin-client-usb-installer-latest.sh",
    "pve-thin-client-usb-installer-latest.ps1",
    "pve-thin-client-live-usb-latest.sh",
    "pve-thin-client-live-usb-latest.ps1",
    "pve-thin-client-usb-payload-latest.tar.gz",
]

def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}

settings = load_json(settings_path)
enabled = bool(settings.get("artifact_watchdog_enabled", True))
max_age_hours = int(settings.get("artifact_watchdog_max_age_hours", 6) or 6)
auto_repair = bool(settings.get("artifact_watchdog_auto_repair", True))
refresh_status = load_json(refresh_status_path)
status_json = load_json(dist_dir / "beagle-downloads-status.json")

now = datetime.now(timezone.utc)
version = ""
try:
    version = (dist_dir.parent / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    version = ""

versioned = []
if version:
    versioned = [
        f"pve-thin-client-usb-installer-v{version}.sh",
        f"pve-thin-client-usb-installer-v{version}.ps1",
        f"pve-thin-client-live-usb-v{version}.sh",
        f"pve-thin-client-live-usb-v{version}.ps1",
        f"pve-thin-client-usb-payload-v{version}.tar.gz",
    ]

missing_required = [name for name in required if not (dist_dir / name).is_file()]
missing_latest = [name for name in latest_public if not (dist_dir / name).is_file()]
missing_versioned = [name for name in versioned if not (dist_dir / name).is_file()]
findings: list[str] = []
if missing_required:
    findings.append("missing_required:" + ",".join(missing_required))
if missing_latest:
    findings.append("missing_latest:" + ",".join(missing_latest))
if missing_versioned:
    findings.append("missing_versioned:" + ",".join(missing_versioned))

artifact_age_seconds = None
status_mtime = None
try:
    if (dist_dir / "beagle-downloads-status.json").is_file():
        status_mtime = datetime.fromtimestamp((dist_dir / "beagle-downloads-status.json").stat().st_mtime, timezone.utc)
except OSError:
    status_mtime = None

refresh_updated_at = None
if refresh_status.get("updated_at"):
    try:
        refresh_updated_at = datetime.fromisoformat(str(refresh_status["updated_at"]))
    except ValueError:
        refresh_updated_at = None

candidate_times = [item for item in (status_mtime, refresh_updated_at) if item is not None]
if candidate_times:
    latest_time = max(candidate_times)
    artifact_age_seconds = int((now - latest_time).total_seconds())
    if artifact_age_seconds > max_age_hours * 3600:
        findings.append(f"out_of_date:{artifact_age_seconds}")

refresh_state = str(refresh_status.get("status") or "").strip().lower()
refresh_running = refresh_state in {"queued", "running"}
reaction = "none"
state = "disabled"
message = "Watchdog ist deaktiviert."

if enabled:
    if refresh_running:
        state = "repairing"
        reaction = "refresh_already_running"
        message = "Artifact-Refresh laeuft bereits."
    elif findings:
        state = "drift"
        message = "Artefakt-Drift erkannt."
        if auto_repair:
            result = subprocess.run(
                ["systemctl", "--no-block", "start", refresh_service_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                state = "repairing"
                reaction = "started_refresh"
                message = "Artifact-Refresh wegen Drift automatisch gestartet."
            else:
                reaction = "refresh_start_failed"
                message = "Artifact-Refresh konnte nicht automatisch gestartet werden."
                findings.append("auto_repair_error:" + (result.stderr or result.stdout).strip()[:200])
        else:
            reaction = "notify_only"
            message = "Artefakt-Drift erkannt, Auto-Repair ist deaktiviert."
    else:
        state = "healthy"
        message = "Alle Pflichtartefakte sind vorhanden und aktuell."

payload = {
    "enabled": enabled,
    "max_age_hours": max_age_hours,
    "auto_repair": auto_repair,
    "checked_at": now.isoformat(),
    "state": state,
    "reaction": reaction,
    "message": message,
    "findings": findings,
    "artifact_age_seconds": artifact_age_seconds,
    "refresh_status": refresh_state or "unknown",
    "version": version,
    "public_ready": not missing_latest and not missing_versioned,
}
status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

if getent group beagle-manager >/dev/null 2>&1; then
  chgrp beagle-manager "$STATUS_FILE" || true
fi
chmod 0640 "$STATUS_FILE" || true
