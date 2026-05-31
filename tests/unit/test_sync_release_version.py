from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "sync-release-version.py"


def _write_fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "extension").mkdir(parents=True)
    (repo / "beagle-kiosk").mkdir(parents=True)
    (repo / "website").mkdir(parents=True)
    (repo / "VERSION").write_text("8.0.0\n", encoding="utf-8")
    (repo / "extension" / "manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": 3,
                "name": "Beagle OS Integration",
                "version": "8.0.0",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (repo / "beagle-kiosk" / "package.json").write_text(
        json.dumps({"name": "beagle-kiosk", "version": "8.0.0"}) + "\n",
        encoding="utf-8",
    )
    (repo / "beagle-kiosk" / "package-lock.json").write_text(
        json.dumps(
            {
                "name": "beagle-kiosk",
                "version": "8.0.0",
                "packages": {"": {"version": "8.0.0"}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (repo / "website" / "index.html").write_text(
        '<link rel="stylesheet" href="/styles.css?v=8.0.0">\n<script src="/main.js?v=8.0.0"></script>\n',
        encoding="utf-8",
    )
    return repo


def _run_sync(repo: Path, version: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["BEAGLE_ROOT_DIR"] = str(repo)
    return subprocess.run(
        [sys.executable, str(SCRIPT), version],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_sync_release_version_updates_stable_version_files(tmp_path: Path) -> None:
    repo = _write_fixture_repo(tmp_path)
    result = _run_sync(repo, "8.3.10")

    assert result.returncode == 0, result.stderr
    assert (repo / "VERSION").read_text(encoding="utf-8").strip() == "8.3.10"

    manifest = json.loads((repo / "extension" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "8.3.10"
    assert manifest["version_name"] == "8.3.10"

    pkg = json.loads((repo / "beagle-kiosk" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((repo / "beagle-kiosk" / "package-lock.json").read_text(encoding="utf-8"))
    assert pkg["version"] == "8.3.10"
    assert lock["version"] == "8.3.10"
    assert lock["packages"][""]["version"] == "8.3.10"

    web = (repo / "website" / "index.html").read_text(encoding="utf-8")
    assert "/styles.css?v=8.3.10" in web
    assert "/main.js?v=8.3.10" in web


def test_sync_release_version_accepts_prerelease_and_keeps_numeric_extension_version(tmp_path: Path) -> None:
    repo = _write_fixture_repo(tmp_path)
    result = _run_sync(repo, "8.3.10-rc.2")

    assert result.returncode == 0, result.stderr
    assert (repo / "VERSION").read_text(encoding="utf-8").strip() == "8.3.10-rc.2"

    manifest = json.loads((repo / "extension" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "8.3.10"
    assert manifest["version_name"] == "8.3.10-rc.2"

    pkg = json.loads((repo / "beagle-kiosk" / "package.json").read_text(encoding="utf-8"))
    assert pkg["version"] == "8.3.10-rc.2"


def test_sync_release_version_rejects_invalid_four_part_version(tmp_path: Path) -> None:
    repo = _write_fixture_repo(tmp_path)
    result = _run_sync(repo, "8.3.9.1")

    assert result.returncode != 0
    assert "invalid version" in result.stderr