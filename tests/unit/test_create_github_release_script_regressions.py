from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_create_release_script_detects_prerelease_class() -> None:
    script = (ROOT / "scripts" / "create-github-release.sh").read_text(encoding="utf-8")

    assert 'BEAGLE_RELEASE_CLASS="${BEAGLE_RELEASE_CLASS:-}"' in script
    assert "resolve_release_class()" in script
    assert "-(alpha|beta|rc)\\.[0-9]+$" in script


def test_create_release_script_sets_prerelease_flags() -> None:
    script = (ROOT / "scripts" / "create-github-release.sh").read_text(encoding="utf-8")

    assert "--prerelease --latest=false" in script
    assert "--latest" in script