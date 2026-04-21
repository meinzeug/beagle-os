import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SERVER_SETTINGS_PATH = Path(__file__).resolve().parents[2] / "beagle-host" / "services" / "server_settings.py"
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

    def test_request_letsencrypt_requires_nginx_plugin(self):
        service = self.make_service()

        with mock.patch.object(MODULE, "_which", return_value="/usr/bin/certbot"), \
             mock.patch.object(MODULE, "_certbot_has_plugin", return_value=False):
            result = service.request_letsencrypt("srv1.beagle-os.com", "ops@beagle-os.com")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "certbot nginx plugin not installed on this server")


if __name__ == "__main__":
    unittest.main()
