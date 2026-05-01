from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts" / "lib" / "prepare_host_downloads.py"
SPEC = importlib.util.spec_from_file_location("beagle_prepare_host_downloads", HELPER)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_write_download_status_omits_server_release_artifacts_when_not_hosted_locally() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        vm_installers = base / "beagle-vm-installers.json"
        status_path = base / "beagle-downloads-status.json"

        installer = base / "pve-thin-client-usb-installer-host-latest.sh"
        live_usb = base / "pve-thin-client-live-usb-host-latest.sh"
        installer_windows = base / "pve-thin-client-usb-installer-host-latest.ps1"
        live_usb_windows = base / "pve-thin-client-live-usb-host-latest.ps1"
        bootstrap = base / "pve-thin-client-usb-bootstrap-latest.tar.gz"
        payload = base / "pve-thin-client-usb-payload-latest.tar.gz"
        installer_iso = base / "beagle-os-installer-amd64.iso"

        for path in (
            installer,
            live_usb,
            installer_windows,
            live_usb_windows,
            bootstrap,
            payload,
            installer_iso,
        ):
            path.write_bytes(b"artifact")

        vm_installers.write_text("[]\n", encoding="utf-8")

        MODULE.write_download_status(
            status_path=status_path,
            version="8.0",
            server_name="srv1.beagle-os.com",
            listen_port=443,
            downloads_path="/beagle-downloads",
            installer_url="https://srv1/beagle-downloads/pve-thin-client-usb-installer-host-latest.sh",
            live_usb_url="https://srv1/beagle-downloads/pve-thin-client-live-usb-host-latest.sh",
            installer_windows_url="https://srv1/beagle-downloads/pve-thin-client-usb-installer-host-latest.ps1",
            live_usb_windows_url="https://srv1/beagle-downloads/pve-thin-client-live-usb-host-latest.ps1",
            bootstrap_url="https://srv1/beagle-downloads/pve-thin-client-usb-bootstrap-latest.tar.gz",
            payload_url="https://srv1/beagle-downloads/pve-thin-client-usb-payload-latest.tar.gz",
            installer_iso_url="https://srv1/beagle-downloads/beagle-os-installer-amd64.iso",
            status_url="https://srv1/beagle-downloads/beagle-downloads-status.json",
            sha256sums_url="https://srv1/beagle-downloads/SHA256SUMS",
            installer_path=installer,
            live_usb_path=live_usb,
            installer_windows_path=installer_windows,
            live_usb_windows_path=live_usb_windows,
            bootstrap_path=bootstrap,
            payload_path=payload,
            installer_iso_path=installer_iso,
            installer_sha256="sha-installer",
            bootstrap_sha256="sha-bootstrap",
            payload_sha256="sha-payload",
            installer_iso_sha256="sha-iso",
            vm_installer_url_template="https://srv1/beagle-api/api/v1/vms/{vmid}/installer.sh",
            vm_windows_installer_url_template="https://srv1/beagle-api/api/v1/vms/{vmid}/installer.ps1",
            vm_windows_live_usb_url_template="https://srv1/beagle-api/api/v1/vms/{vmid}/live-usb.ps1",
            vm_live_usb_url_template="https://srv1/beagle-api/api/v1/vms/{vmid}/live-usb.sh",
            vm_installers_path=vm_installers,
        )

        payload_json = json.loads(status_path.read_text(encoding="utf-8"))
        assert "server_installer_iso_url" not in payload_json
        assert "server_installimage_url" not in payload_json
        assert payload_json["installer_iso_url"].endswith("beagle-os-installer-amd64.iso")
