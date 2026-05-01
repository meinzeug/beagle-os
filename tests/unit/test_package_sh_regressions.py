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


def test_package_sh_seeds_sha256sums_before_verifier() -> None:
    """Regression: verify-server-installer-artifacts.sh requires SHA256SUMS to exist.

    package.sh must create a temporary SHA256SUMS seeded with the server installer
    ISO checksums before invoking the verifier, otherwise the verifier exits with
    'Missing required file: .../dist/SHA256SUMS'.
    """
    script = SCRIPT.read_text(encoding="utf-8")

    server_block_marker = 'if [[ "$BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS" == "1" ]]; then'
    assert server_block_marker in script
    server_block = script.split(server_block_marker, 1)[1]

    sha256sum_pos = server_block.find('sha256sum \\\n      "$SERVER_INSTALLER_ISO_NAME"')
    verifier_pos = server_block.find('"$ROOT_DIR/scripts/verify-server-installer-artifacts.sh"')

    assert sha256sum_pos != -1, "SHA256SUMS seed creation not found in server artifacts block"
    assert verifier_pos != -1, "verify-server-installer-artifacts.sh call not found in server artifacts block"
    assert sha256sum_pos < verifier_pos, (
        "SHA256SUMS must be seeded before verify-server-installer-artifacts.sh is called; "
        "the verifier will fail with 'Missing required file: SHA256SUMS' otherwise"
    )
