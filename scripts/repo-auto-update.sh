#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETTINGS_FILE="${BEAGLE_SETTINGS_FILE:-${BEAGLE_MANAGER_DATA_DIR:-/var/lib/beagle/beagle-manager}/server-settings.json}"
STATUS_DIR="${BEAGLE_STATUS_DIR:-/var/lib/beagle}"
STATUS_FILE="$STATUS_DIR/repo-auto-update-status.json"
CACHE_DIR="${BEAGLE_REPO_AUTO_UPDATE_CACHE_DIR:-$STATUS_DIR/repo-auto-update-cache}"
WORKTREE_DIR="$CACHE_DIR/repo"
STAGING_DIR="$CACHE_DIR/staging"
INSTALL_DIR="${BEAGLE_INSTALL_DIR:-/opt/beagle}"
COMMIT_FILE="$INSTALL_DIR/.beagle-installed-commit"
DEFAULT_REPO_URL="${BEAGLE_REPO_AUTO_UPDATE_REPO_URL:-https://github.com/meinzeug/beagle-os.git}"
DEFAULT_BRANCH="${BEAGLE_REPO_AUTO_UPDATE_BRANCH:-main}"
DEFAULT_INTERVAL_MINUTES="${BEAGLE_REPO_AUTO_UPDATE_INTERVAL_MINUTES:-15}"

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
install -d -m 0755 "$STATUS_DIR" "$CACHE_DIR"

python3 - "$SETTINGS_FILE" "$STATUS_FILE" "$WORKTREE_DIR" "$STAGING_DIR" "$INSTALL_DIR" "$COMMIT_FILE" "$DEFAULT_REPO_URL" "$DEFAULT_BRANCH" "$DEFAULT_INTERVAL_MINUTES" <<'PY'
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

settings_path = Path(sys.argv[1])
status_path = Path(sys.argv[2])
worktree_dir = Path(sys.argv[3])
staging_dir = Path(sys.argv[4])
install_dir = Path(sys.argv[5])
commit_file = Path(sys.argv[6])
default_repo_url = sys.argv[7]
default_branch = sys.argv[8]
default_interval = int(sys.argv[9])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_status(payload: dict) -> None:
    status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        shutil.chown(status_path, group="beagle-manager")
    except Exception:
        pass
    try:
        status_path.chmod(0o640)
    except OSError:
        pass


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


settings = load_json(settings_path)
status = load_json(status_path)
config = {
    "enabled": bool(settings.get("repo_auto_update_enabled", False)),
    "repo_url": str(settings.get("repo_auto_update_repo_url") or default_repo_url).strip() or default_repo_url,
    "branch": str(settings.get("repo_auto_update_branch") or default_branch).strip() or default_branch,
    "interval_minutes": int(settings.get("repo_auto_update_interval_minutes", default_interval) or default_interval),
}

now = utcnow()
payload = {
    "enabled": config["enabled"],
    "repo_url": config["repo_url"],
    "branch": config["branch"],
    "interval_minutes": config["interval_minutes"],
    "checked_at": now.isoformat(),
    "state": "disabled",
    "reaction": "none",
    "message": "Repo-Auto-Update ist deaktiviert.",
    "current_commit": "",
    "remote_commit": "",
    "update_available": False,
    "last_update_at": str(status.get("last_update_at") or ""),
}

current_commit = ""
try:
    if commit_file.is_file():
        current_commit = commit_file.read_text(encoding="utf-8").strip()
except OSError:
    current_commit = ""
payload["current_commit"] = current_commit

if not config["enabled"]:
    write_status(payload)
    raise SystemExit(0)

last_checked = None
checked_at_raw = str(status.get("checked_at") or "").strip()
if checked_at_raw:
    try:
        last_checked = datetime.fromisoformat(checked_at_raw)
    except ValueError:
        last_checked = None
if last_checked and now - last_checked < timedelta(minutes=max(5, config["interval_minutes"])):
    payload.update(status)
    payload["checked_at"] = now.isoformat()
    payload["state"] = str(status.get("state") or "idle")
    payload["message"] = "Intervall noch nicht erreicht."
    payload["reaction"] = "interval_skip"
    write_status(payload)
    raise SystemExit(0)

worktree_dir.parent.mkdir(parents=True, exist_ok=True)
if not worktree_dir.is_dir():
    clone = run(["git", "clone", "--filter=blob:none", config["repo_url"], str(worktree_dir)], timeout=1800)
    if clone.returncode != 0:
        payload["state"] = "error"
        payload["reaction"] = "clone_failed"
        payload["message"] = (clone.stderr or clone.stdout or "git clone failed").strip()[:400]
        write_status(payload)
        raise SystemExit(1)

remote_set = run(["git", "remote", "set-url", "origin", config["repo_url"]], cwd=worktree_dir, timeout=120)
if remote_set.returncode != 0:
    payload["state"] = "error"
    payload["reaction"] = "remote_set_failed"
    payload["message"] = (remote_set.stderr or remote_set.stdout or "git remote set-url failed").strip()[:400]
    write_status(payload)
    raise SystemExit(1)

fetch = run(["git", "fetch", "--prune", "origin", config["branch"]], cwd=worktree_dir, timeout=1800)
if fetch.returncode != 0:
    payload["state"] = "error"
    payload["reaction"] = "fetch_failed"
    payload["message"] = (fetch.stderr or fetch.stdout or "git fetch failed").strip()[:400]
    write_status(payload)
    raise SystemExit(1)

remote_commit_proc = run(["git", "rev-parse", f"origin/{config['branch']}"], cwd=worktree_dir, timeout=60)
if remote_commit_proc.returncode != 0:
    payload["state"] = "error"
    payload["reaction"] = "rev_parse_failed"
    payload["message"] = (remote_commit_proc.stderr or remote_commit_proc.stdout or "git rev-parse failed").strip()[:400]
    write_status(payload)
    raise SystemExit(1)

remote_commit = (remote_commit_proc.stdout or "").strip()
payload["remote_commit"] = remote_commit

if current_commit and current_commit == remote_commit:
    payload["state"] = "healthy"
    payload["reaction"] = "no_update"
    payload["message"] = "Installierter Repo-Stand ist aktuell."
    payload["update_available"] = False
    write_status(payload)
    raise SystemExit(0)

payload["state"] = "updating"
payload["reaction"] = "start_update"
payload["message"] = "Neuer Repo-Stand erkannt, Update wird eingespielt."
payload["update_available"] = True
write_status(payload)

if staging_dir.exists():
    shutil.rmtree(staging_dir)
staging_dir.mkdir(parents=True, exist_ok=True)

archive_cmd = f"git -C {worktree_dir} archive {remote_commit} | tar -xf - -C {staging_dir}"
archive = subprocess.run(["bash", "-lc", archive_cmd], capture_output=True, text=True, timeout=1800, check=False)
if archive.returncode != 0:
    payload["state"] = "error"
    payload["reaction"] = "archive_failed"
    payload["message"] = (archive.stderr or archive.stdout or "git archive failed").strip()[:400]
    write_status(payload)
    raise SystemExit(1)

rsync = run(
    [
        "rsync",
        "-a",
        "--delete",
        "--exclude", ".git/",
        "--exclude", ".build/",
        "--exclude", "dist/",
        "--exclude", "__pycache__/",
        "--exclude", "*.pyc",
        f"{staging_dir}/",
        f"{install_dir}/",
    ],
    timeout=1800,
)
if rsync.returncode != 0:
    payload["state"] = "error"
    payload["reaction"] = "rsync_failed"
    payload["message"] = (rsync.stderr or rsync.stdout or "rsync failed").strip()[:400]
    write_status(payload)
    raise SystemExit(1)

commit_file.write_text(remote_commit + "\n", encoding="utf-8")

install = run([str(install_dir / "scripts/install-beagle-host-services.sh")], cwd=install_dir, timeout=1800)
if install.returncode != 0:
    payload["state"] = "error"
    payload["reaction"] = "host_install_failed"
    payload["message"] = (install.stderr or install.stdout or "install-beagle-host-services.sh failed").strip()[-400:]
    write_status(payload)
    raise SystemExit(1)

refresh = run([str(install_dir / "scripts/refresh-host-artifacts.sh")], cwd=install_dir, timeout=7200)
if refresh.returncode != 0:
    payload["state"] = "error"
    payload["reaction"] = "artifact_refresh_failed"
    payload["message"] = (refresh.stderr or refresh.stdout or "refresh-host-artifacts.sh failed").strip()[-400:]
    write_status(payload)
    raise SystemExit(1)

payload["state"] = "healthy"
payload["reaction"] = "updated"
payload["message"] = "Repo-Update erfolgreich eingespielt."
payload["current_commit"] = remote_commit
payload["remote_commit"] = remote_commit
payload["update_available"] = False
payload["last_update_at"] = utcnow().isoformat()
write_status(payload)
PY
