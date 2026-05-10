from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from public_ubuntu_install_surface import PublicUbuntuInstallSurfaceService


def _service(
    *,
    state: dict,
    finalize_calls: list[tuple[dict, bool]],
    prepare_calls: list[dict],
    cancelled_restart: dict | None = None,
):
    state_store = {"payload": dict(state)}

    def load_state(_token: str) -> dict | None:
        payload = state_store.get("payload")
        return dict(payload) if isinstance(payload, dict) else None

    def save_state(_token: str, payload: dict) -> dict:
        state_store["payload"] = dict(payload)
        return payload

    def finalize(payload: dict, *, restart: bool):
        finalize_calls.append((dict(payload), bool(restart)))
        return {"vmid": int(payload.get("vmid", 0) or 0), "cleanup": "ok", "restart": "stop-start" if restart else "guest-reboot"}

    def prepare(payload: dict):
        prepare_calls.append(dict(payload))
        payload["status"] = "installing"
        payload["phase"] = "firstboot"
        payload["cleanup"] = {"vmid": int(payload.get("vmid", 0) or 0), "cleanup": "ok", "restart": "stop-start"}
        return payload["cleanup"]

    return PublicUbuntuInstallSurfaceService(
        cancel_scheduled_ubuntu_beagle_vm_restart=lambda _state: cancelled_restart,
        finalize_ubuntu_beagle_install=finalize,
        load_ubuntu_beagle_state=load_state,
        prepare_ubuntu_beagle_firstboot=prepare,
        save_ubuntu_beagle_state=save_state,
        service_name="beagle-control-plane",
        utcnow=lambda: "2026-05-10T00:00:00Z",
        version="test",
    )


class PublicUbuntuInstallSurfaceTests(unittest.TestCase):
    def test_complete_callback_is_idempotent_when_already_completed(self) -> None:
        finalize_calls: list[tuple[dict, bool]] = []
        prepare_calls: list[dict] = []
        service = _service(
            state={
                "token": "tok",
                "vmid": 100,
                "status": "completed",
                "phase": "complete",
                "cleanup": {"vmid": 100, "cleanup": "ok", "restart": "stop-start"},
            },
            finalize_calls=finalize_calls,
            prepare_calls=prepare_calls,
        )

        response = service.route_post(
            "/api/v1/public/ubuntu-install/tok/complete",
            query={"restart": ["1"]},
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response["status"].value, 200)
        self.assertTrue(response["payload"]["ok"])
        self.assertEqual(response["payload"]["ubuntu_beagle_install"]["status"], "completed")
        self.assertEqual(response["payload"]["ubuntu_beagle_install"]["phase"], "complete")
        self.assertEqual(finalize_calls, [])
        self.assertEqual(prepare_calls, [])

    def test_prepare_firstboot_callback_is_idempotent_when_firstboot_already_active(self) -> None:
        finalize_calls: list[tuple[dict, bool]] = []
        prepare_calls: list[dict] = []
        service = _service(
            state={
                "token": "tok",
                "vmid": 100,
                "status": "installing",
                "phase": "firstboot",
                "cleanup": {"vmid": 100, "cleanup": "ok", "restart": "stop-start"},
            },
            finalize_calls=finalize_calls,
            prepare_calls=prepare_calls,
        )

        response = service.route_post(
            "/api/v1/public/ubuntu-install/tok/prepare-firstboot",
            query={},
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response["status"].value, 200)
        self.assertTrue(response["payload"]["ok"])
        self.assertEqual(response["payload"]["ubuntu_beagle_install"]["status"], "installing")
        self.assertEqual(response["payload"]["ubuntu_beagle_install"]["phase"], "firstboot")
        self.assertEqual(response["payload"]["cleanup"], {"vmid": 100, "cleanup": "ok", "restart": "stop-start"})
        self.assertEqual(prepare_calls, [])
        self.assertEqual(finalize_calls, [])

    def test_prepare_firstboot_callback_is_idempotent_when_already_completed(self) -> None:
        finalize_calls: list[tuple[dict, bool]] = []
        prepare_calls: list[dict] = []
        service = _service(
            state={
                "token": "tok",
                "vmid": 100,
                "status": "completed",
                "phase": "complete",
                "cleanup": {"vmid": 100, "cleanup": "ok", "restart": "guest-reboot"},
            },
            finalize_calls=finalize_calls,
            prepare_calls=prepare_calls,
        )

        response = service.route_post(
            "/api/v1/public/ubuntu-install/tok/prepare-firstboot",
            query={},
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response["status"].value, 200)
        self.assertTrue(response["payload"]["ok"])
        self.assertEqual(response["payload"]["ubuntu_beagle_install"]["status"], "completed")
        self.assertEqual(response["payload"]["ubuntu_beagle_install"]["phase"], "complete")
        self.assertEqual(response["payload"]["cleanup"], {"vmid": 100, "cleanup": "ok", "restart": "guest-reboot"})
        self.assertEqual(prepare_calls, [])
        self.assertEqual(finalize_calls, [])

if __name__ == "__main__":
    unittest.main()
