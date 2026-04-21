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
            with mock.patch.object(MODULE, "_which", return_value="/usr/bin/certbot"), \
                 mock.patch.object(MODULE, "_ACME_WEBROOT", fake_webroot), \
                 mock.patch.object(MODULE, "_run_certbot_command", side_effect=fake_run_certbot), \
                 mock.patch.object(MODULE, "_switch_nginx_tls_to_letsencrypt", return_value=(True, "ok")):
                result = service.request_letsencrypt("srv1.beagle-os.com", "ops@beagle-os.com")

        self.assertTrue(result["ok"], result)
        self.assertIn("--webroot", captured[0])
        self.assertNotIn("--nginx", captured[0])


if __name__ == "__main__":
    unittest.main()
