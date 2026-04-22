import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "beagle-host" / "services") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "beagle-host" / "services"))

from ubuntu_beagle_provisioning import UbuntuBeagleProvisioningService


class _ProviderStub:
    def __init__(self, inventory):
        self._inventory = list(inventory)

    def list_storage_inventory(self):
        return list(self._inventory)


class UbuntuBeagleProvisioningQuotaTests(unittest.TestCase):
    def _build_service(self, *, inventory, quota_bytes):
        service = UbuntuBeagleProvisioningService.__new__(UbuntuBeagleProvisioningService)
        service._provider = _ProviderStub(inventory)
        service._get_storage_quota = lambda _pool: {"quota_bytes": quota_bytes}
        return service

    def test_enforce_storage_quota_allows_when_quota_unlimited(self):
        service = self._build_service(
            inventory=[{"storage": "local", "used": 900 * 1024 * 1024 * 1024}],
            quota_bytes=0,
        )
        service.enforce_storage_quota("local", 300 * 1024 * 1024 * 1024)

    def test_enforce_storage_quota_rejects_when_limit_exceeded(self):
        service = self._build_service(
            inventory=[{"storage": "local", "used": 80 * 1024 * 1024 * 1024}],
            quota_bytes=100 * 1024 * 1024 * 1024,
        )
        with self.assertRaisesRegex(ValueError, "quota_exceeded"):
            service.enforce_storage_quota("local", 30 * 1024 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
