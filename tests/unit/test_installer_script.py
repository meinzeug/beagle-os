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
    def test_patch_service_injects_log_defaults_into_stale_hosted_shell_template(self):
        stale_template = "\n".join(
            [
                'USB_WRITER_VARIANT="${PVE_THIN_CLIENT_USB_WRITER_VARIANT:-installer}"',
                'PVE_THIN_CLIENT_PRESET_NAME="${PVE_THIN_CLIENT_PRESET_NAME:-}"',
                'PVE_THIN_CLIENT_PRESET_B64="${PVE_THIN_CLIENT_PRESET_B64:-}"',
                'RELEASE_ISO_URL="${RELEASE_ISO_URL:-}"',
                'RELEASE_BOOTSTRAP_URL="${RELEASE_BOOTSTRAP_URL:-}"',
                'RELEASE_PAYLOAD_URL="${RELEASE_PAYLOAD_URL:-}"',
                'INSTALL_PAYLOAD_URL="${INSTALL_PAYLOAD_URL:-}"',
                'BOOTSTRAP_DISABLE_CACHE="${PVE_DCV_BOOTSTRAP_DISABLE_CACHE:-0}"',
                "",
            ]
        )

        patched = InstallerTemplatePatchService().patch_installer_defaults(
            stale_template,
            "vm100",
            "abc",
            "https://downloads.example/beagle.iso",
            "https://downloads.example/bootstrap.tar.gz",
            "https://downloads.example/payload.tar.gz",
            "installer",
            "https://manager.example/api/v1/public/installer-logs",
            "log-token",
            "log-session",
        )

        self.assertIn('INSTALLER_LOG_URL="${BEAGLE_INSTALLER_LOG_URL:-https://manager.example/api/v1/public/installer-logs}"', patched)
        self.assertIn('INSTALLER_LOG_TOKEN="${BEAGLE_INSTALLER_LOG_TOKEN:-log-token}"', patched)
        self.assertIn('INSTALLER_LOG_SESSION_ID="${BEAGLE_INSTALLER_LOG_SESSION_ID:-log-session}"', patched)

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
                    'INSTALLER_LOG_URL="${BEAGLE_INSTALLER_LOG_URL:-}"',
                    'INSTALLER_LOG_TOKEN="${BEAGLE_INSTALLER_LOG_TOKEN:-}"',
                    'INSTALLER_LOG_SESSION_ID="${BEAGLE_INSTALLER_LOG_SESSION_ID:-}"',
                    '',
                ]),
                encoding="utf-8",
            )
            raw_windows.write_text(
                'iso=__BEAGLE_DEFAULT_RELEASE_ISO_URL__\nvariant=__BEAGLE_DEFAULT_WRITER_VARIANT__\nname=__BEAGLE_DEFAULT_PRESET_NAME__\npreset=__BEAGLE_DEFAULT_PRESET_B64__\nlog_url=__BEAGLE_DEFAULT_INSTALLER_LOG_URL__\nlog_token=__BEAGLE_DEFAULT_INSTALLER_LOG_TOKEN__\nlog_session=__BEAGLE_DEFAULT_INSTALLER_LOG_SESSION_ID__\n',
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
                issue_installer_log_context=lambda **kwargs: {
                    "token": f"log-token-{kwargs['script_kind']}",
                    "session_id": f"log-session-{kwargs['script_kind']}",
                },
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
            windows_live_body, windows_live_name = service.render_windows_live_usb_script(vm)

            installer_text = installer_body.decode("utf-8")
            live_text = live_body.decode("utf-8")
            windows_text = windows_body.decode("utf-8")
            windows_live_text = windows_live_body.decode("utf-8")

            self.assertEqual(installer_name, "pve-thin-client-usb-installer-vm-100.sh")
            self.assertEqual(live_name, "pve-thin-client-live-usb-vm-100.sh")
            self.assertEqual(windows_name, "pve-thin-client-usb-installer-vm-100.ps1")
            self.assertEqual(windows_live_name, "pve-thin-client-live-usb-vm-100.ps1")
            self.assertIn('USB_WRITER_VARIANT="${PVE_THIN_CLIENT_USB_WRITER_VARIANT:-installer}"', installer_text)
            self.assertIn('USB_WRITER_VARIANT="${PVE_THIN_CLIENT_USB_WRITER_VARIANT:-live}"', live_text)
            self.assertIn('RELEASE_ISO_URL="${RELEASE_ISO_URL:-https://downloads.example/beagle-os-installer-amd64.iso}"', installer_text)
            self.assertIn('RELEASE_BOOTSTRAP_URL="${RELEASE_BOOTSTRAP_URL:-https://downloads.example/bootstrap.tar.gz}"', installer_text)
            self.assertIn('INSTALL_PAYLOAD_URL="${INSTALL_PAYLOAD_URL:-https://downloads.example/payload.tar.gz}"', live_text)
            self.assertIn('INSTALLER_LOG_URL="${BEAGLE_INSTALLER_LOG_URL:-https://manager.example/beagle-api/api/v1/public/installer-logs}"', installer_text)
            self.assertIn('INSTALLER_LOG_TOKEN="${BEAGLE_INSTALLER_LOG_TOKEN:-log-token-linux-installer-usb}"', installer_text)
            self.assertIn('INSTALLER_LOG_SESSION_ID="${BEAGLE_INSTALLER_LOG_SESSION_ID:-log-session-linux-live-usb}"', live_text)
            self.assertIn('iso=https://downloads.example/beagle-os-installer-amd64.iso', windows_text)
            self.assertIn('variant=installer', windows_text)
            self.assertIn('variant=live', windows_live_text)
            self.assertIn('log_url=https://manager.example/beagle-api/api/v1/public/installer-logs', windows_text)
            self.assertIn('log_token=log-token-windows-installer-usb', windows_text)
            self.assertIn('log_session=log-session-windows-live-usb', windows_live_text)


if __name__ == "__main__":
    unittest.main()
