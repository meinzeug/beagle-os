from __future__ import annotations

import sys
import json
from pathlib import Path
from types import SimpleNamespace


ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from beagle_stream_server_integration import BeagleStreamServerIntegrationService


def _service(*, guest_exec_result: tuple[int, str, str], default_guest_user: str = "beagle") -> BeagleStreamServerIntegrationService:
    return BeagleStreamServerIntegrationService(
        build_profile=lambda *_args, **_kwargs: {},
        ensure_vm_secret=lambda _vm: {},
        find_vm=lambda _vmid: None,
        get_vm_config=lambda _node, _vmid: {"description": ""},
        guest_exec_script_text=lambda *_args, **_kwargs: guest_exec_result,
        load_beagle_stream_server_access_token=lambda _token: None,
        parse_description_meta=lambda _text: {},
        public_manager_url="https://srv1.beagle-os.com/beagle-api",
        ubuntu_beagle_default_guest_user=default_guest_user,
    )


def test_running_vm_guest_user_prefers_detected_state_owner() -> None:
    vm = SimpleNamespace(vmid=100, node="beagle-0", status="running")
    service = _service(guest_exec_result=(0, "dennis\n", ""))

    assert service.beagle_stream_server_guest_user(vm) == "dennis"


def test_guest_user_falls_back_to_default_when_detection_fails() -> None:
    vm = SimpleNamespace(vmid=100, node="beagle-0", status="running")
    service = _service(guest_exec_result=(1, "", "missing"), default_guest_user="beagle")

    assert service.beagle_stream_server_guest_user(vm) == "beagle"


def test_stopped_vm_does_not_require_guest_detection() -> None:
    vm = SimpleNamespace(vmid=100, node="beagle-0", status="stopped")
    service = _service(guest_exec_result=(0, "dennis\n", ""), default_guest_user="beagle")

    assert service.beagle_stream_server_guest_user(vm) == "beagle"


def test_guest_user_uses_latest_install_state_before_default() -> None:
    vm = SimpleNamespace(vmid=100, node="beagle-0", status="stopped")
    service = _service(guest_exec_result=(1, "", "missing"), default_guest_user="beagle")
    state_dir = service._ubuntu_beagle_install_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "vm100.json"
    original = state_file.read_text(encoding="utf-8") if state_file.exists() else None
    try:
        state_file.write_text(
            json.dumps(
                {
                    "vmid": 100,
                    "guest_user": "dennis",
                    "created_at": "2026-05-03T13:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        assert service.beagle_stream_server_guest_user(vm) == "dennis"
    finally:
        if original is None:
            state_file.unlink(missing_ok=True)
        else:
            state_file.write_text(original, encoding="utf-8")


def test_guest_user_detection_script_accepts_legacy_sunshine_paths() -> None:
    vm = SimpleNamespace(vmid=100, node="beagle-0", status="running")
    captured: dict[str, str] = {}

    def _guest_exec(_vmid: int, script: str, **_kwargs):
        captured["script"] = script
        return (0, "dennis\n", "")

    service = BeagleStreamServerIntegrationService(
        build_profile=lambda *_args, **_kwargs: {},
        ensure_vm_secret=lambda _vm: {},
        find_vm=lambda _vmid: None,
        get_vm_config=lambda _node, _vmid: {"description": ""},
        guest_exec_script_text=_guest_exec,
        load_beagle_stream_server_access_token=lambda _token: None,
        parse_description_meta=lambda _text: {},
        public_manager_url="https://srv1.beagle-os.com/beagle-api",
        ubuntu_beagle_default_guest_user="beagle",
    )

    assert service.beagle_stream_server_guest_user(vm) == "dennis"
    assert "sunshine_state.json" in captured["script"]
    assert "sunshine.conf" in captured["script"]


def test_register_certificate_script_restores_guest_ownership_and_uniqueid() -> None:
    vm = SimpleNamespace(vmid=100, node="beagle-0", status="running")
    captured: dict[str, str] = {}

    def _guest_exec(_vmid: int, script: str, **_kwargs):
        captured["script"] = script
        if "candidates=(" in script:
            return (0, "dennis\n", "")
        return (0, "registered-new\n", "")

    service = BeagleStreamServerIntegrationService(
        build_profile=lambda *_args, **_kwargs: {},
        ensure_vm_secret=lambda _vm: {},
        find_vm=lambda _vmid: None,
        get_vm_config=lambda _node, _vmid: {"description": ""},
        guest_exec_script_text=_guest_exec,
        load_beagle_stream_server_access_token=lambda _token: None,
        parse_description_meta=lambda _text: {},
        public_manager_url="https://srv1.beagle-os.com/beagle-api",
        ubuntu_beagle_default_guest_user="beagle",
    )

    result = service.register_beagle_stream_client_certificate_on_vm(
        vm,
        "-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----\n",
        device_name="vm100-thinclient",
    )

    assert result["ok"] is True
    script = captured["script"]
    assert 'root["uniqueid"]' in script
    assert 'chown "$guest_user:$guest_user" "$state_file"' in script
    assert 'chmod 0600 "$state_file"' in script
