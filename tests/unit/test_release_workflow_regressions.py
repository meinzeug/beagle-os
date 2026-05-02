from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_release_workflow_syncs_release_metadata_before_persisting() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert 'run: python3 scripts/sync-release-version.py "$VERSION"' in workflow
    assert 'repo_version="$(git show HEAD:VERSION 2>/dev/null | tr -d ' in workflow
    assert "git add VERSION extension/manifest.json beagle-kiosk/package.json beagle-kiosk/package-lock.json website/index.html" in workflow
    assert "git fetch origin main" in workflow
    assert "git rebase origin/main" in workflow
    assert "BEAGLE_RELEASE_SYNC_TOKEN || secrets.COPILOT_ASSIGNMENT_TOKEN || github.token" in workflow
    assert 'git push origin "HEAD:refs/heads/main"' in workflow
    assert 'release_sha="$(git rev-parse HEAD)"' in workflow
    assert "Could not push release metadata to main" in workflow


def test_package_script_uses_shared_release_version_sync_helper() -> None:
    script = (ROOT / "scripts" / "package.sh").read_text(encoding="utf-8")

    assert 'python3 "$ROOT_DIR/scripts/sync-release-version.py" "$VERSION"' in script
