import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
PROVIDERS_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "providers"
BIN_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "bin"
for _d in (SERVICES_DIR, PROVIDERS_DIR, BIN_DIR):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

SERVICE_REGISTRY_PATH = SERVICES_DIR / "service_registry.py"
SPEC = importlib.util.spec_from_file_location("beagle_service_registry", SERVICE_REGISTRY_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
# Patch create_provider before exec_module so HOST_PROVIDER (created at module level in
# service_registry.py) does not attempt to create /var/lib/beagle/... directories, which
# are not writable in CI environments.
with mock.patch("registry.create_provider", return_value=mock.MagicMock()):
    SPEC.loader.exec_module(MODULE)


def _stale_state() -> dict:
    updated_at = (datetime.now(timezone.utc) - timedelta(seconds=1200)).isoformat()
    return {
        "vmid": 100,
        "token": "abc123",
        "status": "installing",
        "phase": "firstboot",
        "updated_at": updated_at,
    }


class UbuntuBeagleStaleRuntimeTests(unittest.TestCase):
    def test_stale_firstboot_does_not_complete_while_guest_service_is_active(self) -> None:
        latest = _stale_state()
        raw_state = dict(latest)
        fake_state_service = mock.Mock()
        fake_state_service.latest_for_vmid.side_effect = [dict(latest), dict(raw_state)]
        provisioner = mock.Mock()

        with mock.patch.object(MODULE, "ubuntu_beagle_state_service", return_value=fake_state_service), \
             mock.patch.object(MODULE, "find_vm", return_value=SimpleNamespace(vmid=100, status="running")), \
             mock.patch.object(MODULE, "load_ubuntu_beagle_state", return_value=raw_state), \
             mock.patch.object(MODULE, "_ubuntu_beagle_guest_firstboot_runtime", return_value="active"), \
             mock.patch.object(MODULE, "save_ubuntu_beagle_state") as save_state, \
             mock.patch.object(MODULE, "ubuntu_beagle_provisioning_service", return_value=provisioner):
            MODULE.latest_ubuntu_beagle_state_for_vmid(100)

        provisioner.finalize_ubuntu_beagle_install.assert_not_called()
        save_state.assert_called_once()
        saved_payload = save_state.call_args.args[1]
        self.assertEqual(saved_payload["status"], "installing")
        self.assertIn("laeuft weiterhin im Gast", saved_payload["message"])

    def test_stale_firstboot_completes_when_guest_service_is_no_longer_active(self) -> None:
        latest = _stale_state()
        raw_state = dict(latest)
        fake_state_service = mock.Mock()
        fake_state_service.latest_for_vmid.return_value = dict(raw_state)
        provisioner = mock.Mock()
        provisioner.finalize_ubuntu_beagle_install.return_value = {
            "vmid": 100,
            "cleanup": "ok",
            "restart": "guest-reboot",
        }

        with mock.patch.object(MODULE, "ubuntu_beagle_state_service", return_value=fake_state_service), \
             mock.patch.object(MODULE, "find_vm", return_value=SimpleNamespace(vmid=100, status="running")), \
             mock.patch.object(MODULE, "load_ubuntu_beagle_state", return_value=raw_state), \
             mock.patch.object(MODULE, "_ubuntu_beagle_guest_firstboot_runtime", return_value="inactive"), \
             mock.patch.object(MODULE, "cancel_scheduled_ubuntu_beagle_vm_restart", return_value=None), \
             mock.patch.object(MODULE, "save_ubuntu_beagle_state") as save_state, \
             mock.patch.object(MODULE, "ubuntu_beagle_provisioning_service", return_value=provisioner):
            MODULE.latest_ubuntu_beagle_state_for_vmid(100)

        provisioner.finalize_ubuntu_beagle_install.assert_called_once_with(raw_state, restart=False)
        save_state.assert_called_once()
        saved_payload = save_state.call_args.args[1]
        self.assertEqual(saved_payload["status"], "completed")
        self.assertEqual(saved_payload["phase"], "complete")


if __name__ == "__main__":
    unittest.main()
