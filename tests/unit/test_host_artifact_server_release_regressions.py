from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PREPARE_SCRIPT = ROOT / "scripts" / "prepare-host-downloads.sh"
CHECK_SCRIPT = ROOT / "scripts" / "check-beagle-host.sh"
WATCHDOG_SCRIPT = ROOT / "scripts" / "artifact-watchdog.sh"
INSTALL_SCRIPT = ROOT / "scripts" / "install-beagle-host.sh"
SERVER_SETTINGS = ROOT / "beagle-host" / "services" / "server_settings.py"


def test_prepare_host_downloads_defaults_to_thin_client_only_host_artifacts() -> None:
    script = PREPARE_SCRIPT.read_text(encoding="utf-8")

    assert 'BEAGLE_HOST_BUILD_SERVER_RELEASE_ARTIFACTS="${BEAGLE_HOST_BUILD_SERVER_RELEASE_ARTIFACTS:-0}"' in script
    assert 'BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS="$BEAGLE_HOST_BUILD_SERVER_RELEASE_ARTIFACTS" \\' in script
    assert 'beagle-os-server-installer-amd64.iso' not in script.split('checksum_entries=(', 1)[1].split(')', 1)[0]
    assert 'Server ISO SHA256' not in script


def test_check_beagle_host_no_longer_requires_local_server_release_artifacts() -> None:
    script = CHECK_SCRIPT.read_text(encoding="utf-8")

    assert 'check_file "$INSTALL_DIR/dist/beagle-os-server-installer-amd64.iso"' not in script
    assert 'check_http "$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "beagle-os-server-installer-amd64.iso")"' not in script
    assert 'server_installer_iso_url mismatch' not in script


def test_artifact_watchdog_only_requires_host_local_endpoint_artifacts() -> None:
    script = WATCHDOG_SCRIPT.read_text(encoding="utf-8")

    assert '"beagle-os-server-installer-amd64.iso"' not in script
    assert '"Debian-1201-bookworm-amd64-beagle-server.tar.gz"' not in script


def test_install_beagle_host_no_longer_fetches_server_release_artifacts() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert 'curl -fsSLo "$dist_dir/beagle-os-server-installer-amd64.iso"' not in script
    assert 'BEAGLE_PACKAGE_INCLUDE_SERVER_RELEASE_ARTIFACTS=0 \\' in script
    assert 'BEAGLE_PACKAGE_INCLUDE_ENDPOINT_INSTALLER_ISO=0 \\' in script


def test_install_beagle_host_no_longer_fetches_host_local_endpoint_iso_or_bootstrap() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert 'pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz' not in script
    assert 'curl -fsSLo "$dist_dir/beagle-os-installer-amd64.iso"' not in script


def test_server_settings_required_artifacts_drop_server_release_files() -> None:
    script = SERVER_SETTINGS.read_text(encoding="utf-8")

    assert '"beagle-os-server-installer-amd64.iso"' not in script.split("_REQUIRED_ARTIFACTS = [", 1)[1].split("]", 1)[0]
    assert '"Debian-1201-bookworm-amd64-beagle-server.tar.gz"' not in script.split("_REQUIRED_ARTIFACTS = [", 1)[1].split("]", 1)[0]
