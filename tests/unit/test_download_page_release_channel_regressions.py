from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_release_workflow_verifies_stable_and_prerelease_status_files() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    assert 'STATUS_FILE="beagle-downloads-status.json"' in workflow
    assert 'STATUS_FILE="beagle-downloads-prerelease-status.json"' in workflow
    assert 'EXPECTED_BASE_URL="https://beagle-os.com/beagle-updates/prereleases/${VERSION}"' in workflow


def test_publish_public_update_script_preserves_stable_when_prerelease_syncs() -> None:
    script = (ROOT / "scripts" / "publish-public-update-artifacts.sh").read_text(encoding="utf-8")

    assert '"$REMOTE_TARGET/prereleases/$VERSION/"' in script
    assert '"$PUBLISH_STAGE_ROOT/$STATUS_JSON_NAME"' in script
    assert 'Published prerelease artifacts to $REMOTE_TARGET/prereleases/$VERSION and updated $STATUS_JSON_NAME' in script