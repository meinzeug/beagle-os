from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / "scripts" / "build-server-installimage.sh"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
BUILD_ISO_WORKFLOW = ROOT / ".github" / "workflows" / "build-iso.yml"


def test_installimage_build_retries_transient_apt_fetch_failures() -> None:
    script = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert 'APT_RETRY_ATTEMPTS="${BEAGLE_APT_RETRY_ATTEMPTS:-5}"' in script
    assert "apt_retry()" in script
    assert "apt_retry_chroot()" in script
    assert "-o Acquire::Retries=5" in script
    assert "-o Acquire::https::Timeout=60" in script
    assert "apt_retry_chroot apt-get update" in script
    assert "apt_retry_chroot apt-get install -y --fix-missing debconf-utils" in script
    assert "apt_retry_chroot apt-get install -y --fix-missing \\" in script
    assert "run_in_chroot apt-get install -y \\" not in script


def test_release_installimage_dependency_step_uses_apt_retries() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    block = workflow.split("name: Build server installimage tarball", 1)[1]
    block = block.split("name: Build server installer ISO", 1)[0]

    assert "sudo apt-get update -qq -o Acquire::Retries=5" in block
    assert "sudo apt-get install -y --fix-missing --no-install-recommends" in block
    assert "-o Acquire::Retries=5" in block


def test_build_iso_installimage_dependency_step_uses_apt_retries() -> None:
    workflow = BUILD_ISO_WORKFLOW.read_text(encoding="utf-8")
    block = workflow.split("name: Build server installimage tarball", 1)[1]
    block = block.split("name: Build server installer ISO", 1)[0]

    assert "sudo apt-get update -qq -o Acquire::Retries=5" in block
    assert "sudo apt-get install -y --fix-missing --no-install-recommends" in block
    assert "-o Acquire::Retries=5" in block
