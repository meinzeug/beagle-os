from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import sys


ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from installer_prep import InstallerPrepService


def _service(tmp_path: Path, guest_json: str) -> InstallerPrepService:
    return InstallerPrepService(
        build_profile=lambda vm: {
            "installer_target_eligible": True,
            "stream_host": f"10.0.0.{vm.vmid}",
            "beagle_stream_client_port": "47984",
        },
        data_dir=lambda: tmp_path,
        ensure_vm_secret=lambda _vm: {
            "beagle_stream_server_username": "beagle-stream-server",
            "beagle_stream_server_password": "secret",
            "beagle_stream_server_pin": "1234",
        },
        guest_exec_out_data=lambda _vmid, _command: guest_json,
        installer_prep_script_file=tmp_path / "prep.sh",
        installer_profile_surface=lambda profile, vmid, installer_iso_url: {
            "contract_version": "test",
            "installer_url": f"/vm/{vmid}/installer.sh",
            "live_usb_url": f"/vm/{vmid}/live.sh",
            "installer_windows_url": f"/vm/{vmid}/installer.ps1",
            "live_usb_windows_url": f"/vm/{vmid}/live.ps1",
            "installer_iso_url": installer_iso_url,
            "stream_host": profile.get("stream_host", ""),
            "beagle_stream_client_port": profile.get("beagle_stream_client_port", ""),
            "beagle_stream_server_api_url": "",
            "installer_target_eligible": bool(profile.get("installer_target_eligible")),
            "installer_target_message": "",
        },
        load_json_file=lambda path, default: default,
        public_installer_iso_url=lambda: "https://example.invalid/installer.iso",
        root_dir=tmp_path,
        safe_slug=lambda value, default="unknown": str(value or default),
        timestamp_age_seconds=lambda _value: 0,
        utcnow=lambda: "2026-05-02T05:00:00Z",
        write_json_file=lambda *_args, **_kwargs: None,
    )


def test_quick_beagle_stream_server_status_parses_stream_runtime_variant(tmp_path: Path) -> None:
    payload = json.dumps(
        {
            "binary": 1,
            "service": 1,
            "process": 1,
            "beagle_package": 1,
            "beagle_stream_server_package": 0,
            "variant": "beagle-stream-server",
            "package_url": "https://github.com/meinzeug/beagle-stream-server/releases/download/beagle-phase-a/beagle-stream-server-latest-ubuntu-24.04-amd64.deb",
        }
    )
    service = _service(tmp_path, payload)

    status = service.quick_beagle_stream_server_status(100)

    assert status["binary"] is True
    assert status["service"] is True
    assert status["process"] is True
    assert status["beagle_package"] is True
    assert status["beagle_stream_server_package"] is False
    assert status["variant"] == "beagle-stream-server"


def test_default_state_prefers_beaglestream_ready_message(tmp_path: Path) -> None:
    payload = json.dumps(
        {
            "binary": 1,
            "service": 1,
            "process": 1,
            "beagle_package": 1,
            "beagle_stream_server_package": 0,
            "variant": "beagle-stream-server",
            "package_url": "https://example.invalid/beagle-stream-server.deb",
        }
    )
    service = _service(tmp_path, payload)

    state = service.default_state(SimpleNamespace(vmid=100, node="srv1"))

    assert state["status"] == "ready"
    assert "BeagleStream Server ist aktiv" in state["message"]
    assert state["stream_runtime"]["variant"] == "beagle-stream-server"


def test_default_state_marks_compatibility_mode_when_only_server_runtime_is_present(tmp_path: Path) -> None:
    payload = json.dumps(
        {
            "binary": 1,
            "service": 1,
            "process": 1,
            "beagle_package": 0,
            "beagle_stream_server_package": 1,
            "variant": "beagle-stream-server-fallback",
            "package_url": "https://github.com/meinzeug/beagle-stream-server/releases/download/beagle-phase-a/beagle-stream-server-latest-ubuntu-24.04-amd64.deb",
        }
    )
    service = _service(tmp_path, payload)

    state = service.default_state(SimpleNamespace(vmid=101, node="srv1"))

    assert state["status"] == "ready"
    assert "Kompatibilitaetsmodus" in state["message"]
    assert state["stream_runtime"]["variant"] == "beagle-stream-server-fallback"
