from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "resolve-release-version.sh"


def _run_resolver(*, env_overrides: dict[str, str], github_output: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(env_overrides)
    return subprocess.run(
        ["bash", str(SCRIPT), "--github-output", str(github_output)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _read_github_output(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def test_accepts_stable_semver_and_emits_stable_class(tmp_path: Path) -> None:
    gh_output = tmp_path / "github_output.txt"
    result = _run_resolver(
        env_overrides={"BEAGLE_RELEASE_VERSION": "8.3.10"},
        github_output=gh_output,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "8.3.10"

    output = _read_github_output(gh_output)
    assert output["version"] == "8.3.10"
    assert output["tag"] == "v8.3.10"
    assert output["release_class"] == "stable"


def test_accepts_prerelease_semver_and_emits_prerelease_class(tmp_path: Path) -> None:
    gh_output = tmp_path / "github_output.txt"
    result = _run_resolver(
        env_overrides={"BEAGLE_RELEASE_VERSION": "v8.3.10-rc.1"},
        github_output=gh_output,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "8.3.10-rc.1"

    output = _read_github_output(gh_output)
    assert output["version"] == "8.3.10-rc.1"
    assert output["tag"] == "v8.3.10-rc.1"
    assert output["release_class"] == "prerelease"


def test_accepts_prerelease_tag_ref(tmp_path: Path) -> None:
    gh_output = tmp_path / "github_output.txt"
    result = _run_resolver(
        env_overrides={
            "BEAGLE_RELEASE_VERSION": "",
            "GITHUB_REF_TYPE": "tag",
            "GITHUB_REF_NAME": "v8.4.0-beta.2",
        },
        github_output=gh_output,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "8.4.0-beta.2"

    output = _read_github_output(gh_output)
    assert output["release_class"] == "prerelease"


def test_rejects_four_part_version(tmp_path: Path) -> None:
    gh_output = tmp_path / "github_output.txt"
    result = _run_resolver(
        env_overrides={"BEAGLE_RELEASE_VERSION": "8.3.9.1"},
        github_output=gh_output,
    )

    assert result.returncode != 0
    assert "Invalid SemVer version" in result.stderr