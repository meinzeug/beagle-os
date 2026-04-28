from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "repo-auto-update.sh"


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
