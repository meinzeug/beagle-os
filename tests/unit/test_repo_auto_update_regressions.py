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


def test_repo_auto_update_prefers_runtime_git_checkout_before_archive_rsync() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "def reset_runtime_git_checkout(install_dir: Path, repo_url: str, branch: str, commit: str) -> bool:" in script
    assert '["git", "reset", "--hard", commit]' in script
    assert 'runtime_git_updated = reset_runtime_git_checkout(install_dir, config["repo_url"], config["branch"], remote_commit)' in script
    assert "if not runtime_git_updated:" in script
    assert '"--exclude", ".git",' in script
    assert 'initialize_runtime_git_checkout(install_dir, config["repo_url"], config["branch"], remote_commit)' in script


def test_repo_auto_update_migrates_existing_hosts_to_git_checkout_when_current() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    current_block = script.split("if current_commit and same_commit(current_commit, remote_commit):", 1)[1]
    current_block = current_block.split('payload["state"] = "updating"', 1)[0]
    assert 'initialize_runtime_git_checkout(install_dir, config["repo_url"], config["branch"], remote_commit)' in current_block


def test_repo_auto_update_marks_repo_healthy_before_artifact_refresh_finishes() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert '["systemctl", "--no-block", "start", "beagle-artifacts-refresh.service"]' in script
    assert 'payload["reaction"] = "updated_artifact_refresh_restarted" if refresh_action == "restart" else "updated_artifact_refresh_started"' in script
    assert 'payload["message"] = "Repo-Update erfolgreich eingespielt. Laufender Artefakt-Build wurde fuer den neuen Commit neu gestartet." if refresh_action == "restart" else "Repo-Update erfolgreich eingespielt. Artefakt-Build laeuft separat weiter."' in script


def test_repo_auto_update_restarts_stale_artifact_refresh_for_new_commit() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'running_build_commit = read_running_build_commit(refresh_status_file)' in script
    assert 'if refresh_active.returncode == 0 and (not running_build_commit or not same_commit(running_build_commit, remote_commit)):' in script
    assert 'refresh_action = "restart"' in script
    assert '["systemctl", "stop", "beagle-artifacts-refresh.service"]' in script
    assert 'payload["reaction"] = "artifact_refresh_restart_failed"' in script
    assert 'payload["reaction"] = "updated_artifact_refresh_restarted" if refresh_action == "restart" else "updated_artifact_refresh_started"' in script


def test_repo_auto_update_checks_remote_before_interval_skip() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'interval_recent = bool(' in script
    assert 'cache_reset = run(["git", "reset", "--hard"], cwd=worktree_dir, timeout=180)' in script
    assert 'fetch = run_git_network(["git", "fetch", "--prune", "origin", config["branch"]], cwd=worktree_dir, timeout=1800)' in script
    assert 'fallback_commit = current_commit or str(status.get("current_commit") or "").strip() or str(status.get("remote_commit") or "").strip()' in script
    assert 'payload["reaction"] = "remote_check_deferred"' in script
    assert 'Remote-Repo konnte gerade nicht geprueft werden; installierter Stand bleibt aktiv.' in script
    current_block = script.split('if current_commit and same_commit(current_commit, remote_commit):', 1)[1]
    current_block = current_block.split('payload["state"] = "updating"', 1)[0]
    assert 'payload["reaction"] = "interval_skip" if interval_recent else "no_update"' in current_block
    assert 'Remote wurde trotzdem geprueft' in current_block


def test_repo_auto_update_stops_stale_artifact_build_before_installing_new_tree() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    preinstall_block = script.split('payload["state"] = "updating"', 1)[1]
    preinstall_block = preinstall_block.split('try:\n    repair_runtime_tree(install_dir)', 1)[0]
    assert 'stopped_stale_refresh_before_update = False' in preinstall_block
    assert 'running_build_commit_before_update = read_running_build_commit(refresh_status_file)' in preinstall_block
    assert 'if refresh_active_before_update.returncode == 0 and (not running_build_commit_before_update or not same_commit(running_build_commit_before_update, remote_commit)):' in preinstall_block
    assert 'payload["reaction"] = "stopping_stale_artifact_refresh"' in preinstall_block
    assert 'payload["reaction"] = "artifact_refresh_pre_update_stop_failed"' in preinstall_block
    assert 'stopped_stale_refresh_before_update = True' in preinstall_block


def test_repo_auto_update_verifies_and_records_full_commit_chain() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "def list_commit_chain(repo_dir: Path, current: str, remote: str) -> tuple[bool, list[str], str]:" in script
    assert '["git", "merge-base", "--is-ancestor", current, remote]' in script
    assert '["git", "rev-list", "--reverse", rev_range]' in script
    assert 'chain_ok, pending_commits, chain_error = list_commit_chain(worktree_dir, current_commit, remote_commit)' in script
    assert 'rolling_rewrite_update = True' in script
    assert 'payload["reaction"] = "rolling_branch_rewrite_update" if rolling_rewrite_update else "start_update"' in script
    assert 'payload["rolling_branch_rewrite"] = True' in script
    assert 'payload["pending_commits"] = pending_commits' in script
    assert 'payload["applied_commits"] = pending_commits' in script
    assert 'payload["applied_commit_count"] = len(pending_commits)' in script


def test_repo_auto_update_tracks_installed_and_remote_versions() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'def read_version_file(path: Path) -> str:' in script
    assert 'payload["installed_version"] = read_version_file(install_dir / "VERSION")' in script
    assert 'remote_version_proc = run(["git", "show", f"{remote_ref}:VERSION"], cwd=worktree_dir, timeout=60)' in script
    assert 'payload["remote_version"] = (remote_version_proc.stdout or "").strip()' in script
    assert '"sync-web-ui-version.py"' in script
    assert 'payload["reaction"] = "sync_web_ui_version_failed"' in script


def test_repo_auto_update_supports_stable_tag_channel() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'DEFAULT_CHANNEL="${BEAGLE_REPO_AUTO_UPDATE_CHANNEL:-stable}"' in script
    assert 'def latest_stable_tag(repo_dir: Path) -> tuple[str, str]:' in script
    assert '"channel": normalize_update_channel(settings.get("repo_auto_update_channel"), legacy_default_channel)' in script
    assert 'if config["channel"] == "stable":' in script
    assert 'tag_fetch = run_git_network(["git", "fetch", "--tags", "--force", "--prune", "origin"], cwd=worktree_dir, timeout=1800)' in script
    assert 'elif not run(["git", "tag", "--list", "v*"], cwd=worktree_dir, timeout=60).stdout.strip():' in script
    assert 'if config["channel"] == "stable":' in script
    assert 'remote_ref = stable_tag' in script
    assert 'payload["remote_version"] = stable_tag_version(stable_tag)' in script
    assert 'payload["stable_channel_holding"] = True' in script
    assert 'payload["reaction"] = "stable_channel_holds_newer_installed_commit"' in script
    assert 'Kein Downgrade wird ausgefuehrt' in script


def test_repo_auto_update_force_fetches_tags_to_survive_moved_release_tags() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    # A re-pointed release tag (for example a re-cut v8.3.14) otherwise makes
    # `git fetch --tags` abort with "would clobber existing tag", which
    # permanently bricks the auto-updater on every deployed server. Every
    # tag-aware fetch must use --force so moved tags are accepted.
    import re

    tag_fetches = re.findall(r'run_git_network\(\["git", "fetch"[^\]]*"--tags"[^\]]*\]', script)
    assert tag_fetches, "expected at least one tag-aware git fetch"
    for fetch in tag_fetches:
        assert '"--force"' in fetch, f"tag fetch missing --force: {fetch}"


def test_host_check_validates_diamond_d0_repo_update_status() -> None:
    script = CHECK_HOST_SCRIPT.read_text(encoding="utf-8")

    assert 'REPO_AUTO_UPDATE_STATUS_FILE="${BEAGLE_REPO_AUTO_UPDATE_STATUS_FILE:-${PVE_DCV_STATUS_DIR:-/var/lib/beagle}/repo-auto-update-status.json}"' in script
    assert "check_repo_auto_update_status()" in script
    assert '"repo state is {status.get(\'state\')!r}, expected healthy"' in script
    assert '"installed_version mismatch"' in script
    assert '"remote_version mismatch"' in script
    assert '"current_commit != remote_commit"' in script
    assert 'stable_holding = bool(status.get("stable_channel_holding", False))' in script
    assert 'if not stable_holding and str(status.get("remote_version") or "").strip() != version:' in script
    assert 'if not stable_holding and not same_commit(str(status.get("current_commit") or ""), str(status.get("remote_commit") or "")):' in script
    assert 'check_file "$REPO_AUTO_UPDATE_STATUS_FILE"' in script


def test_host_check_validates_d1_installimage_bootstrap_completion() -> None:
    script = CHECK_HOST_SCRIPT.read_text(encoding="utf-8")

    assert "check_installimage_bootstrap()" in script
    assert "beagle-installimage-bootstrap.service" in script
    assert "installimage bootstrap completed" in script
    assert "installimage bootstrap done marker missing" in script
    assert "installimage bootstrap service failed" in script
    assert "BEAGLE_INSTALLIMAGE_BOOTSTRAP_DONE_FILE" in script

