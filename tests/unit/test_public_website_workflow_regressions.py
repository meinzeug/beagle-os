from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_public_website_workflow_resolves_release_class() -> None:
    workflow = (ROOT / ".github" / "workflows" / "public-website.yml").read_text(encoding="utf-8")

    assert "id: version" in workflow
    assert "--write VERSION --github-output \"$GITHUB_OUTPUT\"" in workflow
    assert "^v[0-9]+\\.[0-9]+\\.[0-9]+(-(alpha|beta|rc)\\.[0-9]+)?$" in workflow


def test_public_website_workflow_skips_deploy_for_prerelease() -> None:
    workflow = (ROOT / ".github" / "workflows" / "public-website.yml").read_text(encoding="utf-8")

    assert "Skip prerelease website deployment" in workflow
    assert "steps.version.outputs.release_class == 'prerelease'" in workflow
    assert "steps.version.outputs.release_class != 'prerelease'" in workflow