import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from identity_provider_registry import IdentityProviderRegistryService


class IdentityProviderRegistryServiceTests(unittest.TestCase):
    def test_payload_falls_back_to_default_when_loader_raises(self):
        service = IdentityProviderRegistryService(
            load_json_file=lambda path, fallback: (_ for _ in ()).throw(IsADirectoryError("bad registry path")),
            registry_file=Path("/etc/beagle/identity-providers.json"),
            oidc_auth_url="",
            saml_login_url="",
            public_manager_url="https://srv1.beagle-os.com/beagle-api",
            oidc_enabled=False,
            saml_enabled=False,
        )

        payload = service.payload()

        self.assertTrue(payload["ok"])
        providers = payload["providers"]
        self.assertGreaterEqual(len(providers), 1)
        self.assertEqual(providers[0]["type"], "local")


if __name__ == "__main__":
    unittest.main()
