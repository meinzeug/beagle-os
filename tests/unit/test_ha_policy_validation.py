import unittest

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from ubuntu_beagle_provisioning import UbuntuBeagleProvisioningService


class HaPolicyValidationTests(unittest.TestCase):
    def test_normalize_ha_policy_accepts_known_values(self) -> None:
        self.assertEqual(UbuntuBeagleProvisioningService._normalize_ha_policy("restart"), "restart")
        self.assertEqual(UbuntuBeagleProvisioningService._normalize_ha_policy("fail-over"), "fail_over")
        self.assertEqual(UbuntuBeagleProvisioningService._normalize_ha_policy(""), "")

    def test_normalize_ha_policy_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            UbuntuBeagleProvisioningService._normalize_ha_policy("wrong")


if __name__ == "__main__":
    unittest.main()
