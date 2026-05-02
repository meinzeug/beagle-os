from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_release_workflow_syncs_release_metadata_before_persisting() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert 'run: python3 scripts/sync-release-version.py "$VERSION"' in workflow
    assert 'repo_version="$(git show HEAD:VERSION 2>/dev/null | tr -d ' in workflow
    assert "git add VERSION extension/manifest.json beagle-kiosk/package.json beagle-kiosk/package-lock.json website/index.html" in workflow


def test_package_script_uses_shared_release_version_sync_helper() -> None:
    script = (ROOT / "scripts" / "package.sh").read_text(encoding="utf-8")

    assert 'python3 "$ROOT_DIR/scripts/sync-release-version.py" "$VERSION"' in script
