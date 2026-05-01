from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "package.sh"


def test_package_sh_keeps_published_downloads_visible_during_rebuild() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "Keep the currently published download set in place until replacements are" in script
    assert "temporary 404s on" in script
    assert '"$DIST_DIR/beagle-downloads-status.json"' not in script.split("if [[ \"$SKIP_THIN_CLIENT_BUILD\" != \"1\" ]]; then", 1)[0]
    assert '"$DIST_DIR/pve-thin-client-usb-installer-host-latest.sh"' not in script.split("if [[ \"$SKIP_THIN_CLIENT_BUILD\" != \"1\" ]]; then", 1)[0]


def test_package_sh_can_skip_server_release_artifacts_for_host_local_refreshes() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS="${BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS:-1}"' in script
    assert 'if [[ "$BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS" == "1" ]]; then' in script
    assert 'BEAGLE_VERIFY_SERVER_INSTALLER_DIR="$DIST_DIR" \\' in script
    assert 'checksum_targets+=(' in script
