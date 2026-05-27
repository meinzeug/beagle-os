#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETTINGS_FILE="${BEAGLE_SETTINGS_FILE:-${BEAGLE_MANAGER_DATA_DIR:-/var/lib/beagle/beagle-manager}/server-settings.json}"
STATUS_DIR="${BEAGLE_STATUS_DIR:-/var/lib/beagle}"
STATUS_FILE="$STATUS_DIR/repo-auto-update-status.json"
REFRESH_STATUS_FILE="$STATUS_DIR/refresh.status.json"
FORCE_FILE="$STATUS_DIR/repo-auto-update-force"
CACHE_DIR="${BEAGLE_REPO_AUTO_UPDATE_CACHE_DIR:-$STATUS_DIR/repo-auto-update-cache}"
WORKTREE_DIR="$CACHE_DIR/repo"
STAGING_DIR="$CACHE_DIR/staging"
INSTALL_DIR="${BEAGLE_INSTALL_DIR:-/opt/beagle}"
COMMIT_FILE="$INSTALL_DIR/.beagle-installed-commit"
DEFAULT_REPO_URL="${BEAGLE_REPO_AUTO_UPDATE_REPO_URL:-https://github.com/meinzeug/beagle-os.git}"
DEFAULT_BRANCH="${BEAGLE_REPO_AUTO_UPDATE_BRANCH:-main}"
DEFAULT_CHANNEL="${BEAGLE_REPO_AUTO_UPDATE_CHANNEL:-stable}"
DEFAULT_INTERVAL_MINUTES="${BEAGLE_REPO_AUTO_UPDATE_INTERVAL_MINUTES:-1}"

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

python3 - "$SETTINGS_FILE" "$STATUS_FILE" "$FORCE_FILE" "$WORKTREE_DIR" "$STAGING_DIR" "$INSTALL_DIR" "$COMMIT_FILE" "$REFRESH_STATUS_FILE" "$DEFAULT_REPO_URL" "$DEFAULT_BRANCH" "$DEFAULT_CHANNEL" "$DEFAULT_INTERVAL_MINUTES" <<'PY'
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

settings_path = Path(sys.argv[1])
status_path = Path(sys.argv[2])
force_path = Path(sys.argv[3])
worktree_dir = Path(sys.argv[4])
staging_dir = Path(sys.argv[5])
install_dir = Path(sys.argv[6])
commit_file = Path(sys.argv[7])
refresh_status_file = Path(sys.argv[8])
default_repo_url = sys.argv[9]
default_branch = sys.argv[10]
default_channel = sys.argv[11]
default_interval = int(sys.argv[12])

_STABLE_TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


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


def repair_runtime_tree(root: Path) -> None:
    host_runtime = root / "beagle-host"
    legacy_alias = root / "beagle_host"

    if host_runtime.is_symlink():
        try:
            target = os.readlink(host_runtime)
        except OSError:
            target = ""
        if target in {"beagle-host", str(host_runtime)}:
            host_runtime.unlink(missing_ok=True)

    if host_runtime.exists() and not host_runtime.is_dir():
        if host_runtime.is_symlink():
            host_runtime.unlink(missing_ok=True)
        else:
            raise RuntimeError(f"runtime path is not a directory: {host_runtime}")

    host_runtime.mkdir(parents=True, exist_ok=True)

    if legacy_alias.exists() or legacy_alias.is_symlink():
        if legacy_alias.is_dir() and not legacy_alias.is_symlink():
            shutil.rmtree(legacy_alias)
        else:
            legacy_alias.unlink(missing_ok=True)
    legacy_alias.symlink_to("beagle-host")


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


_GIT_RETRY_HINTS = (
    "connection reset by peer",
    "recv failure",
    "early eof",
    "ssl_read",
    "gnutls_handshake",
    "the requested url returned error: 5",
    "could not resolve host",
    "operation timed out",
    "timed out",
    "rpc failed",
    "connection timed out",
    "unexpected disconnect",
    "remote end hung up unexpectedly",
)


def _git_with_network_hardening(cmd: list[str]) -> list[str]:
    """Prepend git network-hardening flags before the git subcommand.

    Forces HTTP/1.1 (some middleboxes RST GitHub's HTTP/2+TLS1.3 frontends),
    raises post buffer for large refs, and adds lo-speed timeouts so a stalled
    socket fails fast and gets retried instead of hanging the whole service.
    """
    if not cmd or cmd[0] != "git":
        return cmd
    overrides = [
        "-c", "http.version=HTTP/1.1",
        "-c", "http.postBuffer=524288000",
        "-c", "http.lowSpeedLimit=1000",
        "-c", "http.lowSpeedTime=30",
    ]
    return ["git", *overrides, *cmd[1:]]


def run_git_network(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 1800,
    attempts: int = 4,
    backoff_seconds: float = 4.0,
) -> subprocess.CompletedProcess[str]:
    """Run a git network command with retries on transient TLS/TCP errors.

    Mitigates known intermittent "Recv failure: Connection reset by peer" /
    HTTP/2-frontend resets observed against github.com from some egress paths.
    """
    import time as _time

    hardened = _git_with_network_hardening(cmd)
    result: subprocess.CompletedProcess[str] | None = None
    last_signal = ""
    for attempt in range(1, max(1, attempts) + 1):
        try:
            result = subprocess.run(
                hardened,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            last_signal = f"timeout after {exc.timeout}s"
            if attempt >= attempts:
                return subprocess.CompletedProcess(hardened, 124, "", last_signal)
            _time.sleep(backoff_seconds * attempt)
            continue
        if result.returncode == 0:
            return result
        combined = f"{result.stdout}\n{result.stderr}".lower()
        if not any(hint in combined for hint in _GIT_RETRY_HINTS):
            return result
        last_signal = (result.stderr or result.stdout or "").strip()
        if attempt >= attempts:
            return result
        _time.sleep(backoff_seconds * attempt)
    # Should not reach here, but keep mypy happy.
    return result if result is not None else subprocess.CompletedProcess(hardened, 1, "", last_signal)


def same_commit(installed: str, remote: str) -> bool:
    left = str(installed or "").strip()
    right = str(remote or "").strip()
    if not left or not right:
        return False
    if left == right:
        return True
    # Older live hotfixes wrote short hashes to .beagle-installed-commit.
    if len(left) < len(right) and len(left) >= 7 and right.startswith(left):
        return True
    if len(right) < len(left) and len(right) >= 7 and left.startswith(right):
        return True
    return False


def resolve_installed_commit(commit_file: Path, status: dict, install_dir: Path) -> str:
    commit = ""
    try:
        if commit_file.is_file():
            commit = commit_file.read_text(encoding="utf-8").strip()
    except OSError:
        commit = ""
    if commit:
        return commit

    status_current_commit = str(status.get("current_commit") or "").strip()
    if status_current_commit:
        return status_current_commit

    status_state = str(status.get("state") or "").strip().lower()
    status_remote_commit = str(status.get("remote_commit") or "").strip()
    status_update_available = bool(status.get("update_available", False))
    if status_remote_commit and status_state == "healthy" and not status_update_available:
        return status_remote_commit

    git_dir = install_dir / ".git"
    if git_dir.exists():
        installed_commit_proc = run(["git", "rev-parse", "HEAD"], cwd=install_dir, timeout=60)
        if installed_commit_proc.returncode == 0:
            return (installed_commit_proc.stdout or "").strip()

    return ""


def read_version_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def normalize_update_channel(value: object, fallback: str = "stable") -> str:
    channel = str(value or "").strip().lower()
    if channel in {"stable", "rolling"}:
        return channel
    return "rolling" if str(fallback or "").strip().lower() == "rolling" else "stable"


def stable_tag_sort_key(tag_name: str) -> tuple[int, int, int]:
    match = _STABLE_TAG_RE.fullmatch(str(tag_name or "").strip())
    if not match:
        return (-1, -1, -1)
    return tuple(int(part) for part in match.groups())


def stable_tag_version(tag_name: str) -> str:
    tag = str(tag_name or "").strip()
    return tag[1:] if tag.startswith("v") else tag


def latest_stable_tag(repo_dir: Path) -> tuple[str, str]:
    tags = run(["git", "tag", "--list"], cwd=repo_dir, timeout=60)
    if tags.returncode != 0:
        return "", (tags.stderr or tags.stdout or "git tag --list failed").strip()[:400]
    candidates = [line.strip() for line in (tags.stdout or "").splitlines() if _STABLE_TAG_RE.fullmatch(line.strip())]
    if not candidates:
        return "", "no stable release tags found"
    candidates.sort(key=stable_tag_sort_key)
    return candidates[-1], ""


def read_running_build_commit(path: Path) -> str:
    data = load_json(path)
    if str(data.get("status") or "").strip().lower() not in {"queued", "running"}:
        return ""
    return str(data.get("build_commit") or "").strip()


def int_or_zero(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def list_commit_chain(repo_dir: Path, current: str, remote: str) -> tuple[bool, list[str], str]:
    current = str(current or "").strip()
    remote = str(remote or "").strip()
    if not remote:
        return False, [], "remote commit is empty"
    if current and same_commit(current, remote):
        return True, [], ""
    if not current:
        return True, [remote], ""
    if current:
        ancestor = run(["git", "merge-base", "--is-ancestor", current, remote], cwd=repo_dir, timeout=60)
        if ancestor.returncode != 0:
            detail = (ancestor.stderr or ancestor.stdout or "remote commit is not a descendant of installed commit").strip()
            return False, [], detail[:400]
        rev_range = f"{current}..{remote}"

    rev_list = run(["git", "rev-list", "--reverse", rev_range], cwd=repo_dir, timeout=120)
    if rev_list.returncode != 0:
        detail = (rev_list.stderr or rev_list.stdout or "git rev-list failed").strip()
        return False, [], detail[:400]
    commits = [line.strip() for line in (rev_list.stdout or "").splitlines() if line.strip()]
    if not commits and remote:
        commits = [remote]
    return True, commits, ""


def is_ancestor(repo_dir: Path, ancestor: str, descendant: str) -> bool:
    left = str(ancestor or "").strip()
    right = str(descendant or "").strip()
    if not left or not right:
        return False
    if same_commit(left, right):
        return True
    proc = run(["git", "merge-base", "--is-ancestor", left, right], cwd=repo_dir, timeout=60)
    return proc.returncode == 0


def remove_runtime_git_metadata(install_dir: Path) -> None:
    git_path = install_dir / ".git"
    if git_path.is_dir() and not git_path.is_symlink():
        shutil.rmtree(git_path)
        return
    try:
        git_path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def reset_runtime_git_checkout(install_dir: Path, repo_url: str, branch: str, commit: str) -> bool:
    git_path = install_dir / ".git"
    if not git_path.exists():
        return False

    inside = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=install_dir, timeout=60)
    if inside.returncode != 0:
        remove_runtime_git_metadata(install_dir)
        return False

    remote_set = run(["git", "remote", "set-url", "origin", repo_url], cwd=install_dir, timeout=120)
    if remote_set.returncode != 0:
        remote_add = run(["git", "remote", "add", "origin", repo_url], cwd=install_dir, timeout=120)
        if remote_add.returncode != 0:
            remove_runtime_git_metadata(install_dir)
            return False

    fetch_runtime = run_git_network(["git", "fetch", "--prune", "--tags", "origin", branch], cwd=install_dir, timeout=1800)
    if fetch_runtime.returncode != 0:
        remove_runtime_git_metadata(install_dir)
        return False

    reset = run(["git", "reset", "--hard", commit], cwd=install_dir, timeout=1800)
    if reset.returncode != 0:
        remove_runtime_git_metadata(install_dir)
        return False

    run(["git", "config", "--local", "beagle.runtime", "true"], cwd=install_dir, timeout=60)
    return True


def initialize_runtime_git_checkout(install_dir: Path, repo_url: str, branch: str, commit: str) -> bool:
    if (install_dir / ".git").exists():
        return reset_runtime_git_checkout(install_dir, repo_url, branch, commit)

    init = run(["git", "init"], cwd=install_dir, timeout=120)
    if init.returncode != 0:
        remove_runtime_git_metadata(install_dir)
        return False
    remote_add = run(["git", "remote", "add", "origin", repo_url], cwd=install_dir, timeout=120)
    if remote_add.returncode != 0:
        remove_runtime_git_metadata(install_dir)
        return False
    fetch_runtime = run_git_network(["git", "fetch", "--prune", "--tags", "origin", branch], cwd=install_dir, timeout=1800)
    if fetch_runtime.returncode != 0:
        remove_runtime_git_metadata(install_dir)
        return False
    reset = run(["git", "reset", "--hard", commit], cwd=install_dir, timeout=1800)
    if reset.returncode != 0:
        remove_runtime_git_metadata(install_dir)
        return False
    run(["git", "config", "--local", "beagle.runtime", "true"], cwd=install_dir, timeout=60)
    return True


settings = load_json(settings_path)
status = load_json(status_path)
legacy_default_channel = "rolling" if (
    "repo_auto_update_channel" not in settings
    and any(str(status.get(key) or "").strip() for key in ("checked_at", "current_commit", "remote_commit"))
) else default_channel
config = {
    "enabled": bool(settings.get("repo_auto_update_enabled", True)),
    "repo_url": str(settings.get("repo_auto_update_repo_url") or default_repo_url).strip() or default_repo_url,
    "branch": str(settings.get("repo_auto_update_branch") or default_branch).strip() or default_branch,
    "channel": normalize_update_channel(settings.get("repo_auto_update_channel"), legacy_default_channel),
    "interval_minutes": int(settings.get("repo_auto_update_interval_minutes", default_interval) or default_interval),
}

now = utcnow()
payload = {
    "enabled": config["enabled"],
    "repo_url": config["repo_url"],
    "branch": config["branch"],
    "channel": config["channel"],
    "interval_minutes": config["interval_minutes"],
    "checked_at": now.isoformat(),
    "state": "disabled",
    "reaction": "none",
    "message": "Repo-Auto-Update ist deaktiviert.",
    "installed_version": "",
    "remote_version": "",
    "current_commit": "",
    "remote_commit": "",
    "pending_commits": [],
    "pending_commit_count": 0,
    "applied_commits": status.get("applied_commits") if isinstance(status.get("applied_commits"), list) else [],
    "applied_commit_count": int_or_zero(status.get("applied_commit_count")),
    "update_available": False,
    "last_update_at": str(status.get("last_update_at") or ""),
}

current_commit = resolve_installed_commit(commit_file, status, install_dir)
payload["installed_version"] = read_version_file(install_dir / "VERSION")
payload["current_commit"] = current_commit
force_check = False
try:
    if force_path.is_file():
        force_check = True
        force_path.unlink()
except OSError:
    force_check = True

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
config_matches_status = (
    bool(status.get("enabled", False)) == config["enabled"]
    and str(status.get("repo_url") or "").strip() == config["repo_url"]
    and str(status.get("branch") or "").strip() == config["branch"]
    and normalize_update_channel(status.get("channel"), config["channel"]) == config["channel"]
    and int(status.get("interval_minutes") or 0) == config["interval_minutes"]
)
has_installed_commit = bool(current_commit)
status_state = str(status.get("state") or "").strip().lower()
status_current_commit = str(status.get("current_commit") or "").strip()
status_update_available = bool(status.get("update_available", False))
interval_recent = bool(
    last_checked
    and config_matches_status
    and not force_check
    and has_installed_commit
    and same_commit(status_current_commit, current_commit)
    and status_state not in {"error", "updating"}
    and not status_update_available
    and now - last_checked < timedelta(minutes=max(1, config["interval_minutes"]))
)

worktree_dir.parent.mkdir(parents=True, exist_ok=True)
if not worktree_dir.is_dir():
    clone = run_git_network(["git", "clone", "--filter=blob:none", config["repo_url"], str(worktree_dir)], timeout=1800)
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

cache_reset = run(["git", "reset", "--hard"], cwd=worktree_dir, timeout=180)
if cache_reset.returncode != 0:
    payload["state"] = "error"
    payload["reaction"] = "cache_reset_failed"
    payload["message"] = (cache_reset.stderr or cache_reset.stdout or "git cache reset failed").strip()[:400]
    write_status(payload)
    raise SystemExit(1)

fetch = run_git_network(["git", "fetch", "--prune", "origin", config["branch"]], cwd=worktree_dir, timeout=1800)
if fetch.returncode != 0:
    fallback_commit = current_commit or str(status.get("current_commit") or "").strip() or str(status.get("remote_commit") or "").strip()
    if fallback_commit:
        payload["state"] = "healthy"
        payload["reaction"] = "remote_check_deferred"
        payload["message"] = "Remote-Repo konnte gerade nicht geprueft werden; installierter Stand bleibt aktiv."
        payload["current_commit"] = fallback_commit
        payload["remote_commit"] = str(status.get("remote_commit") or fallback_commit).strip() or fallback_commit
        payload["remote_version"] = str(status.get("remote_version") or payload.get("installed_version") or "").strip()
        payload["target_commit"] = payload["remote_commit"]
        payload["target_version"] = payload["remote_version"]
        payload["channel_position"] = "remote_check_deferred"
        payload["update_available"] = False
        write_status(payload)
        raise SystemExit(0)
    payload["state"] = "error"
    payload["reaction"] = "fetch_failed"
    payload["message"] = (fetch.stderr or fetch.stdout or "git fetch failed").strip()[:400]
    write_status(payload)
    raise SystemExit(1)

tag_fetch = None
if config["channel"] == "stable":
    tag_fetch = run_git_network(["git", "fetch", "--tags", "--prune", "origin"], cwd=worktree_dir, timeout=1800)
elif not run(["git", "tag", "--list", "v*"], cwd=worktree_dir, timeout=60).stdout.strip():
    tag_fetch = run_git_network(["git", "fetch", "--tags", "--prune", "origin"], cwd=worktree_dir, timeout=180)

if tag_fetch is not None and tag_fetch.returncode != 0:
    payload["state"] = "error"
    payload["reaction"] = "tag_fetch_failed"
    payload["message"] = (tag_fetch.stderr or tag_fetch.stdout or "git tag fetch failed").strip()[:400]
    write_status(payload)
    raise SystemExit(1)

remote_ref = f"origin/{config['branch']}"
payload["rolling_ref"] = remote_ref
rolling_commit_proc = run(["git", "rev-parse", remote_ref], cwd=worktree_dir, timeout=60)
if rolling_commit_proc.returncode == 0:
    payload["rolling_commit"] = (rolling_commit_proc.stdout or "").strip()
rolling_version_proc = run(["git", "show", f"{remote_ref}:VERSION"], cwd=worktree_dir, timeout=60)
if rolling_version_proc.returncode == 0:
    payload["rolling_version"] = (rolling_version_proc.stdout or "").strip()

stable_tag, stable_tag_error = latest_stable_tag(worktree_dir)
if stable_tag:
    payload["stable_ref"] = stable_tag
    payload["stable_version"] = stable_tag_version(stable_tag)
    stable_commit_proc = run(["git", "rev-parse", stable_tag], cwd=worktree_dir, timeout=60)
    if stable_commit_proc.returncode == 0:
        payload["stable_commit"] = (stable_commit_proc.stdout or "").strip()

if config["channel"] == "stable":
    if not stable_tag:
        payload["state"] = "error"
        payload["reaction"] = "stable_tag_not_found"
        payload["message"] = stable_tag_error or "Kein stabiler Release-Tag gefunden."
        write_status(payload)
        raise SystemExit(1)
    remote_ref = stable_tag
    payload["remote_ref"] = stable_tag
    payload["remote_version"] = stable_tag_version(stable_tag)
else:
    payload["remote_ref"] = remote_ref

remote_commit_proc = run(["git", "rev-parse", remote_ref], cwd=worktree_dir, timeout=60)
if remote_commit_proc.returncode != 0:
    payload["state"] = "error"
    payload["reaction"] = "rev_parse_failed"
    payload["message"] = (remote_commit_proc.stderr or remote_commit_proc.stdout or "git rev-parse failed").strip()[:400]
    write_status(payload)
    raise SystemExit(1)

remote_commit = (remote_commit_proc.stdout or "").strip()
payload["remote_commit"] = remote_commit
payload["target_ref"] = remote_ref
payload["target_commit"] = remote_commit
payload["target_version"] = payload.get("remote_version") or ""
remote_version_proc = run(["git", "show", f"{remote_ref}:VERSION"], cwd=worktree_dir, timeout=60)
if remote_version_proc.returncode == 0 and config["channel"] != "stable":
    payload["remote_version"] = (remote_version_proc.stdout or "").strip()
    payload["target_version"] = payload["remote_version"]

chain_ok, pending_commits, chain_error = list_commit_chain(worktree_dir, current_commit, remote_commit)
rolling_rewrite_update = False
if not chain_ok:
    if config["channel"] == "stable":
        payload["state"] = "healthy"
        payload["reaction"] = "stable_channel_holds_newer_installed_commit"
        payload["stable_channel_holding"] = True
        payload["installed_ahead_of_target"] = is_ancestor(worktree_dir, remote_commit, current_commit)
        payload["channel_position"] = "ahead_of_stable" if payload["installed_ahead_of_target"] else "diverged_from_stable"
        payload["message"] = "Stable ist gewaehlt, aber der installierte Stand stammt aus Rolling und ist neuer als der letzte Stable-Release. Kein Downgrade wird ausgefuehrt; der Server wartet auf ein neues Stable-Tag."
        payload["update_available"] = False
        payload["pending_commits"] = []
        payload["pending_commit_count"] = 0
        write_status(payload)
        raise SystemExit(0)
    else:
        rolling_rewrite_update = True
        pending_commits = [remote_commit] if remote_commit else []
        payload["rolling_branch_rewrite"] = True
        payload["channel_position"] = "diverged_from_rolling"
payload["pending_commits"] = pending_commits
payload["pending_commit_count"] = len(pending_commits)
if not rolling_rewrite_update:
    payload["channel_position"] = "behind_target" if pending_commits else "at_target"

if current_commit and same_commit(current_commit, remote_commit):
    initialize_runtime_git_checkout(install_dir, config["repo_url"], config["branch"], remote_commit)
    payload["state"] = "healthy"
    payload["reaction"] = "interval_skip" if interval_recent else "no_update"
    payload["message"] = "Intervall noch nicht erreicht; Remote wurde trotzdem geprueft und ist unveraendert." if interval_recent else "Installierter Repo-Stand ist aktuell."
    payload["update_available"] = False
    payload["current_commit"] = remote_commit
    commit_file.write_text(remote_commit + "\n", encoding="utf-8")
    write_status(payload)
    raise SystemExit(0)

payload["state"] = "updating"
payload["reaction"] = "rolling_branch_rewrite_update" if rolling_rewrite_update else "start_update"
payload["message"] = "Rolling-Branch wurde neu geschrieben; Ziel-Commit wird direkt installiert." if rolling_rewrite_update else f"Neuer Repo-Stand erkannt, {len(pending_commits)} Commit(s) werden der Reihe nach uebernommen."
payload["update_available"] = True
write_status(payload)

stopped_stale_refresh_before_update = False
refresh_active_before_update = run(["systemctl", "is-active", "beagle-artifacts-refresh.service"], timeout=30)
running_build_commit_before_update = read_running_build_commit(refresh_status_file)
if refresh_active_before_update.returncode == 0 and (not running_build_commit_before_update or not same_commit(running_build_commit_before_update, remote_commit)):
    payload["reaction"] = "stopping_stale_artifact_refresh"
    payload["message"] = "Neuer Repo-Commit erkannt; laufender Artefakt-Build wird vor dem Repo-Install gestoppt."
    write_status(payload)
    stop_refresh = run(["systemctl", "stop", "beagle-artifacts-refresh.service"], timeout=90)
    run(["systemctl", "reset-failed", "beagle-artifacts-refresh.service"], timeout=30)
    if stop_refresh.returncode != 0:
        payload["state"] = "error"
        payload["reaction"] = "artifact_refresh_pre_update_stop_failed"
        payload["message"] = (stop_refresh.stderr or stop_refresh.stdout or "artifact refresh stop failed before repo update").strip()[-400:]
        write_status(payload)
        raise SystemExit(1)
    stopped_stale_refresh_before_update = True

try:
    repair_runtime_tree(install_dir)
except Exception as exc:
    payload["state"] = "error"
    payload["reaction"] = "repair_runtime_tree_failed"
    payload["message"] = str(exc).strip()[:400]
    write_status(payload)
    raise SystemExit(1)

runtime_git_updated = reset_runtime_git_checkout(install_dir, config["repo_url"], config["branch"], remote_commit)

if not runtime_git_updated:
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
            "--exclude", ".git",
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
    initialize_runtime_git_checkout(install_dir, config["repo_url"], config["branch"], remote_commit)

sync_web_ui = run(
    [sys.executable, str(install_dir / "scripts" / "sync-web-ui-version.py"), str(install_dir / "website" / "index.html"), str(payload["installed_version"] or payload["remote_version"] or "")],
    timeout=120,
)
if sync_web_ui.returncode != 0:
    payload["state"] = "error"
    payload["reaction"] = "sync_web_ui_version_failed"
    payload["message"] = (sync_web_ui.stderr or sync_web_ui.stdout or "sync-web-ui-version.py failed").strip()[:400]
    write_status(payload)
    raise SystemExit(1)
if payload["remote_version"]:
    payload["installed_version"] = payload["remote_version"]

install = None
for attempt in range(1, 4):
    install = run([str(install_dir / "scripts/install-beagle-host-services.sh")], cwd=install_dir, timeout=1800)
    combined_install_output = f"{install.stdout}\n{install.stderr}".lower()
    if install.returncode == 0:
        break
    if "cannot lock /etc/passwd" not in combined_install_output and "cannot lock /etc/group" not in combined_install_output:
        break
    payload["message"] = f"Host-Install wartet auf Account-Lock (Versuch {attempt}/3)."
    write_status(payload)
    import time
    time.sleep(3)

if install is None or install.returncode != 0:
    payload["state"] = "error"
    payload["reaction"] = "host_install_failed"
    payload["message"] = (install.stderr or install.stdout or "install-beagle-host-services.sh failed").strip()[-400:]
    write_status(payload)
    raise SystemExit(1)

refresh_active = run(["systemctl", "is-active", "beagle-artifacts-refresh.service"], timeout=30)
running_build_commit = read_running_build_commit(refresh_status_file)
refresh_command = ["systemctl", "--no-block", "start", "beagle-artifacts-refresh.service"]
refresh_action = "restart" if stopped_stale_refresh_before_update else "start"
if refresh_active.returncode == 0 and (not running_build_commit or not same_commit(running_build_commit, remote_commit)):
    refresh_action = "restart"
    stop_refresh = run(["systemctl", "stop", "beagle-artifacts-refresh.service"], timeout=90)
    run(["systemctl", "reset-failed", "beagle-artifacts-refresh.service"], timeout=30)
    if stop_refresh.returncode != 0:
        payload["state"] = "error"
        payload["reaction"] = "artifact_refresh_restart_failed"
        payload["message"] = (stop_refresh.stderr or stop_refresh.stdout or "artifact refresh stop failed before restart").strip()[-400:]
        write_status(payload)
        raise SystemExit(1)

refresh_started_async = run(refresh_command, timeout=60)
if refresh_started_async.returncode != 0:
    refresh = run([str(install_dir / "scripts/refresh-host-artifacts.sh")], cwd=install_dir, timeout=7200)
    if refresh.returncode != 0:
        payload["state"] = "error"
        payload["reaction"] = "artifact_refresh_failed"
        payload["message"] = (refresh.stderr or refresh.stdout or "refresh-host-artifacts.sh failed").strip()[-400:]
        write_status(payload)
        raise SystemExit(1)
    payload["reaction"] = "updated_with_inline_artifact_refresh"
    payload["message"] = "Repo-Update erfolgreich eingespielt. Artefakte wurden direkt aktualisiert."
else:
    payload["reaction"] = "updated_artifact_refresh_restarted" if refresh_action == "restart" else "updated_artifact_refresh_started"
    payload["message"] = "Repo-Update erfolgreich eingespielt. Laufender Artefakt-Build wurde fuer den neuen Commit neu gestartet." if refresh_action == "restart" else "Repo-Update erfolgreich eingespielt. Artefakt-Build laeuft separat weiter."

payload["state"] = "healthy"
payload["current_commit"] = remote_commit
payload["remote_commit"] = remote_commit
payload["applied_commits"] = pending_commits
payload["applied_commit_count"] = len(pending_commits)
payload["pending_commits"] = []
payload["pending_commit_count"] = 0
payload["update_available"] = False
payload["last_update_at"] = utcnow().isoformat()
commit_file.write_text(remote_commit + "\n", encoding="utf-8")
write_status(payload)
PY
