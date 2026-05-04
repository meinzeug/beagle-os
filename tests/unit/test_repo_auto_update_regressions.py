from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "repo-auto-update.sh"
CHECK_HOST_SCRIPT = ROOT / "scripts" / "check-beagle-host.sh"


def test_repo_auto_update_repairs_runtime_tree_before_rsync_and_install() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "def repair_runtime_tree(root: Path) -> None:" in script
    assert 'host_runtime = root / "beagle-host"' in script
    assert 'legacy_alias = root / "beagle_host"' in script
    assert 'legacy_alias.symlink_to("beagle-host")' in script
    assert "repair_runtime_tree(install_dir)" in script
    assert '"reaction"] = "repair_runtime_tree_failed"' in script


def test_repo_auto_update_accepts_short_installed_commit_hash() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "def same_commit(installed: str, remote: str) -> bool:" in script
    assert "right.startswith(left)" in script
    assert "same_commit(current_commit, remote_commit)" in script


def test_repo_auto_update_recovers_missing_commit_stamp_from_status_or_git() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "def resolve_installed_commit(commit_file: Path, status: dict, install_dir: Path) -> str:" in script
    assert 'status_current_commit = str(status.get("current_commit") or "").strip()' in script
    assert 'status_remote_commit = str(status.get("remote_commit") or "").strip()' in script
    assert 'if git_dir.exists():' in script
    assert 'current_commit = resolve_installed_commit(commit_file, status, install_dir)' in script


def test_repo_auto_update_marks_repo_healthy_before_artifact_refresh_finishes() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert '["systemctl", "--no-block", "start", "beagle-artifacts-refresh.service"]' in script
    assert 'payload["reaction"] = "updated_artifact_refresh_started"' in script
    assert 'payload["message"] = "Repo-Update erfolgreich eingespielt. Artefakt-Build laeuft separat weiter."' in script


def test_repo_auto_update_tracks_installed_and_remote_versions() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'def read_version_file(path: Path) -> str:' in script
    assert 'payload["installed_version"] = read_version_file(install_dir / "VERSION")' in script
    assert 'remote_version_proc = run(["git", "show", f"origin/{config[\'branch\']}:VERSION"], cwd=worktree_dir, timeout=60)' in script
    assert 'payload["remote_version"] = (remote_version_proc.stdout or "").strip()' in script
    assert '"sync-web-ui-version.py"' in script
    assert 'payload["reaction"] = "sync_web_ui_version_failed"' in script


def test_host_check_validates_diamond_d0_repo_update_status() -> None:
    script = CHECK_HOST_SCRIPT.read_text(encoding="utf-8")

    assert 'REPO_AUTO_UPDATE_STATUS_FILE="${BEAGLE_REPO_AUTO_UPDATE_STATUS_FILE:-${PVE_DCV_STATUS_DIR:-/var/lib/beagle}/repo-auto-update-status.json}"' in script
    assert "check_repo_auto_update_status()" in script
    assert '"repo state is {status.get(\'state\')!r}, expected healthy"' in script
    assert '"installed_version mismatch"' in script
    assert '"remote_version mismatch"' in script
    assert '"current_commit != remote_commit"' in script
    assert 'check_file "$REPO_AUTO_UPDATE_STATUS_FILE"' in script
