from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from installer_script import InstallerScriptService
from installer_template_patch import InstallerTemplatePatchService


class InstallerScriptServiceTests(unittest.TestCase):
    def test_shell_downloads_fall_back_to_raw_template_when_dist_templates_are_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_shell = root / "pve-thin-client-usb-installer.sh"
            raw_windows = root / "pve-thin-client-usb-installer.ps1"
            missing_hosted = root / "missing-hosted.sh"
            missing_live = root / "missing-live.sh"
            missing_iso = root / "missing.iso"

            raw_shell.write_text(
                '\n'.join([
                    'USB_WRITER_VARIANT="${PVE_THIN_CLIENT_USB_WRITER_VARIANT:-installer}"',
                    'PVE_THIN_CLIENT_PRESET_NAME="${PVE_THIN_CLIENT_PRESET_NAME:-}"',
                    'PVE_THIN_CLIENT_PRESET_B64="${PVE_THIN_CLIENT_PRESET_B64:-}"',
                    'RELEASE_ISO_URL="${RELEASE_ISO_URL:-}"',
                    'RELEASE_BOOTSTRAP_URL="${RELEASE_BOOTSTRAP_URL:-}"',
                    'RELEASE_PAYLOAD_URL="${RELEASE_PAYLOAD_URL:-}"',
                    'INSTALL_PAYLOAD_URL="${INSTALL_PAYLOAD_URL:-}"',
                    'BOOTSTRAP_DISABLE_CACHE="${PVE_DCV_BOOTSTRAP_DISABLE_CACHE:-0}"',
                    '',
                ]),
                encoding="utf-8",
            )
            raw_windows.write_text(
                'iso=__BEAGLE_DEFAULT_RELEASE_ISO_URL__\nname=__BEAGLE_DEFAULT_PRESET_NAME__\npreset=__BEAGLE_DEFAULT_PRESET_B64__\n',
                encoding="utf-8",
            )

            service = InstallerScriptService(
                build_profile=lambda vm: {
                    "stream_host": "stream.example",
                    "sunshine_api_url": "https://stream.example/api",
                },
                ensure_vm_secret=lambda vm: {
                    "sunshine_username": "sun-user",
                    "sunshine_password": "sun-pass",
                    "sunshine_pin": "1234",
                },
                fetch_sunshine_server_identity=lambda vm, guest_user: {},
                get_vm_config=lambda node, vmid: {"name": f"vm-{vmid}", "description": ""},
                hosted_installer_iso_file=missing_iso,
                hosted_installer_template_file=missing_hosted,
                hosted_live_usb_template_file=missing_live,
                issue_enrollment_token=lambda vm: (
                    "token-123",
                    {"thinclient_password": "thin-pass"},
                ),
                manager_pinned_pubkey="manager-pubkey",
                parse_description_meta=lambda text: {},
                patch_installer_defaults=InstallerTemplatePatchService().patch_installer_defaults,
                patch_windows_installer_defaults=InstallerTemplatePatchService().patch_windows_installer_defaults,
                public_bootstrap_latest_download_url=lambda: "https://downloads.example/bootstrap.tar.gz",
                public_installer_iso_url=lambda: "https://downloads.example/beagle-os-installer-amd64.iso",
                public_manager_url="https://manager.example/beagle-api",
                public_payload_latest_download_url=lambda: "https://downloads.example/payload.tar.gz",
                public_server_name="srv1.beagle-os.com",
                raw_shell_installer_template_file=raw_shell,
                raw_windows_installer_template_file=raw_windows,
                safe_hostname=lambda name, vmid: f"vm-{vmid}",
                sunshine_guest_user=lambda vm, config: "beagle",
            )
            vm = SimpleNamespace(vmid=100, node="srv1", name="VM 100", status="running")

            installer_body, installer_name = service.render_installer_script(vm)
            live_body, live_name = service.render_live_usb_script(vm)
            windows_body, windows_name = service.render_windows_installer_script(vm)

            installer_text = installer_body.decode("utf-8")
            live_text = live_body.decode("utf-8")
            windows_text = windows_body.decode("utf-8")

            self.assertEqual(installer_name, "pve-thin-client-usb-installer-vm-100.sh")
            self.assertEqual(live_name, "pve-thin-client-live-usb-vm-100.sh")
            self.assertEqual(windows_name, "pve-thin-client-usb-installer-vm-100.ps1")
            self.assertIn('USB_WRITER_VARIANT="${PVE_THIN_CLIENT_USB_WRITER_VARIANT:-installer}"', installer_text)
            self.assertIn('USB_WRITER_VARIANT="${PVE_THIN_CLIENT_USB_WRITER_VARIANT:-live}"', live_text)
            self.assertIn('RELEASE_ISO_URL="${RELEASE_ISO_URL:-https://downloads.example/beagle-os-installer-amd64.iso}"', installer_text)
            self.assertIn('RELEASE_BOOTSTRAP_URL="${RELEASE_BOOTSTRAP_URL:-https://downloads.example/bootstrap.tar.gz}"', installer_text)
            self.assertIn('INSTALL_PAYLOAD_URL="${INSTALL_PAYLOAD_URL:-https://downloads.example/payload.tar.gz}"', live_text)
            self.assertIn('iso=https://downloads.example/beagle-os-installer-amd64.iso', windows_text)


if __name__ == "__main__":
    unittest.main()