import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

SERVER_SETTINGS_PATH = SERVICES_DIR / "server_settings.py"
SPEC = importlib.util.spec_from_file_location("beagle_server_settings", SERVER_SETTINGS_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
ServerSettingsService = MODULE.ServerSettingsService


class ServerSettingsLetsEncryptTests(unittest.TestCase):
    def make_service(self) -> ServerSettingsService:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return ServerSettingsService(data_dir=Path(temp_dir.name))

    def test_request_letsencrypt_requires_certbot(self):
        service = self.make_service()

        with mock.patch.object(MODULE, "_which", return_value=None):
            result = service.request_letsencrypt("srv1.beagle-os.com", "ops@beagle-os.com")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "certbot not installed on this server")

    def test_request_letsencrypt_uses_webroot_authenticator(self):
        service = self.make_service()

        captured = []

        def fake_run_certbot(cmd, *, timeout):
            captured.append(cmd)
            proc = mock.Mock()
            proc.returncode = 0
            proc.stdout = "Successfully received certificate."
            proc.stderr = ""
            return proc

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_webroot = Path(tmpdir) / "acme-webroot"
            fake_certbot_config = Path(tmpdir) / "certbot" / "config"
            fake_certbot_work = Path(tmpdir) / "certbot" / "work"
            fake_certbot_logs = Path(tmpdir) / "certbot" / "logs"
            with mock.patch.object(MODULE, "_which", return_value="/usr/bin/certbot"), \
                  mock.patch.object(MODULE, "_domain_has_ipv6_records", return_value=False), \
                  mock.patch.object(MODULE, "_host_has_global_ipv6", return_value=False), \
                 mock.patch.object(MODULE, "_ACME_WEBROOT", fake_webroot), \
                 mock.patch.object(MODULE, "_CERTBOT_CONFIG_DIR", fake_certbot_config), \
                 mock.patch.object(MODULE, "_CERTBOT_WORK_DIR", fake_certbot_work), \
                 mock.patch.object(MODULE, "_CERTBOT_LOGS_DIR", fake_certbot_logs), \
                 mock.patch.object(MODULE, "_run_certbot_command", side_effect=fake_run_certbot), \
                 mock.patch.object(MODULE, "_switch_nginx_tls_to_letsencrypt", return_value=(True, "ok")):
                result = service.request_letsencrypt("srv1.beagle-os.com", "ops@beagle-os.com")

        self.assertTrue(result["ok"], result)
        self.assertIn("--webroot", captured[0])
        self.assertNotIn("--nginx", captured[0])
        self.assertIn("--config-dir", captured[0])
        self.assertIn("--work-dir", captured[0])
        self.assertIn("--logs-dir", captured[0])

    def test_request_letsencrypt_rejects_aaaa_without_global_ipv6(self):
        service = self.make_service()

        with mock.patch.object(MODULE, "_which", return_value="/usr/bin/certbot"), \
             mock.patch.object(MODULE, "_domain_has_ipv6_records", return_value=True), \
             mock.patch.object(MODULE, "_host_has_global_ipv6", return_value=False):
            result = service.request_letsencrypt("srv1.beagle-os.com", "ops@beagle-os.com")

        self.assertFalse(result["ok"])
        self.assertIn("AAAA/IPv6 DNS record", result["error"])

    def test_get_artifacts_reports_missing_and_present_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install_dir = Path(tmpdir) / "beagle"
            dist = install_dir / "dist"
            dist.mkdir(parents=True)
            (dist / "beagle-downloads-status.json").write_text('{"version":"test"}\n', encoding="utf-8")
            (dist / "pve-thin-client-live-usb-latest.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            service = ServerSettingsService(data_dir=Path(tmpdir) / "data", install_dir=install_dir)

            with mock.patch.object(MODULE, "_run_cmd", return_value="active"):
                result = service.get_artifacts()

        self.assertFalse(result["ready"])
        self.assertIn("pve-thin-client-usb-installer-latest.sh", result["missing"])
        self.assertEqual(result["status"]["version"], "test")
        self.assertEqual(result["services"]["beagle-artifacts-refresh.service"], "active")

    def test_start_artifact_refresh_starts_systemd_service(self):
        service = self.make_service()
        proc = mock.Mock()
        proc.returncode = 0
        proc.stderr = ""
        with mock.patch.object(MODULE.subprocess, "run", return_value=proc) as run, \
             mock.patch.object(service, "get_artifacts", return_value={"ready": True}):
            result = service.start_artifact_refresh()

        self.assertTrue(result["ok"])
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], ["systemctl", "start", "beagle-artifacts-refresh.service"])


if __name__ == "__main__":
    unittest.main()
