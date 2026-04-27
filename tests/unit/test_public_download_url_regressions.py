from __future__ import annotations

from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from download_metadata import DownloadMetadataService


def make_service(*, port: int) -> DownloadMetadataService:
    return DownloadMetadataService(
        cache_get=None,
        cache_put=None,
        dist_sha256sums_file=ROOT_DIR / "dist" / "SHA256SUMS",
        downloads_status_file=ROOT_DIR / "dist" / "beagle-downloads-status.json",
        load_json_file=lambda _path, default: default,
        manager_pinned_pubkey="",
        public_downloads_path="/beagle-downloads",
        public_downloads_port=port,
        public_manager_url="https://srv1.beagle-os.com/beagle-api",
        public_server_name="srv1.beagle-os.com",
        public_update_base_url="https://srv1.beagle-os.com/beagle-updates",
        version="test",
    )


def test_download_metadata_omits_default_https_port_from_hosted_urls() -> None:
    service = make_service(port=443)

    assert service.public_installer_iso_url() == "https://srv1.beagle-os.com/beagle-downloads/beagle-os-installer-amd64.iso"
    assert service.public_payload_latest_download_url() == "https://srv1.beagle-os.com/beagle-downloads/pve-thin-client-usb-payload-latest.tar.gz"


def test_download_metadata_keeps_non_default_https_port_in_hosted_urls() -> None:
    service = make_service(port=9443)

    assert service.public_installer_iso_url() == "https://srv1.beagle-os.com:9443/beagle-downloads/beagle-os-installer-amd64.iso"
