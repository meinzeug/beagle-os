from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_publish_public_update_artifacts_supports_prerelease_channel() -> None:
    script = (ROOT / "scripts" / "publish-public-update-artifacts.sh").read_text(encoding="utf-8")

    assert 'release_class_for_version()' in script
    assert 'beagle-downloads-prerelease-status.json' in script
    assert 'prereleases/$VERSION' in script
    assert 'release_class' in script
    assert 'artifact_base_url' in script


def test_publish_public_update_artifacts_keeps_stable_channel_separate() -> None:
    script = (ROOT / "scripts" / "publish-public-update-artifacts.sh").read_text(encoding="utf-8")

    assert 'beagle-downloads-status.json' in script
    assert 'PUBLIC_ARTIFACT_BASE_URL="$PUBLIC_BASE_URL"' in script
    assert 'STATUS_JSON_NAME="beagle-downloads-status.json"' in script