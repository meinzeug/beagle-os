from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from vm_http_surface import VmHttpSurfaceService


@dataclass
class _Vm:
    vmid: int = 100
    node: str = "beagle-0"
    name: str = "beagle-100"


def _surface(tmp_path: Path) -> VmHttpSurfaceService:
    vm = _Vm()
    return VmHttpSurfaceService(
        build_profile=lambda item: {"vmid": item.vmid, "name": item.name, "update_enabled": True},
        build_novnc_access=lambda item: {"url": f"/novnc/{item.vmid}", "token": "tok"},
        build_vm_state=lambda item: {
            "vm": {"vmid": item.vmid},
            "endpoint": {"reported_at": "2026-04-27T00:00:00Z"},
            "last_action": {"action": "start"},
        },
        build_vm_usb_state=lambda item, report: {"attached": [], "vmid": item.vmid},
        downloads_status_file=tmp_path / "downloads.json",
        ensure_vm_secret=lambda item: {
            "thinclient_password": "thin-secret",
            "guest_password": "guest-secret",
            "beagle_stream_server_username": "beagle-stream-server",
            "beagle_stream_server_password": "sun-secret",
            "beagle_stream_server_pin": "1234",
            "usb_tunnel_port": 2200,
        },
        find_vm=lambda vmid: vm if int(vmid) == vm.vmid else None,
        list_support_bundle_metadata=lambda **kwargs: [{"id": "bundle-1"}],
        load_action_queue=lambda node, vmid: [{"action": "restart"}],
        load_endpoint_report=lambda node, vmid: {"reported_at": "2026-04-27T00:00:00Z"},
        load_installer_prep_state=lambda node, vmid: {"phase": "ready"},
        load_json_file=lambda path, default: {"version": "6.7.0"},
        public_manager_url="https://srv1.beagle-os.com/beagle-api",
        public_server_name="srv1.beagle-os.com",
        render_vm_installer_script=lambda item: (b"#!/bin/sh\n", "installer.sh"),
        render_vm_live_usb_script=lambda item: (b"#!/bin/sh\n", "live-usb.sh"),
        render_vm_windows_installer_script=lambda item: (b"Write-Host install\n", "installer.ps1"),
        render_vm_windows_live_usb_script=lambda item: (b"Write-Host live\n", "live-usb.ps1"),
        service_name="beagle-control-plane",
        summarize_endpoint_report=lambda report: dict(report),
        summarize_installer_prep_state=lambda item, state: dict(state or {}),
        usb_tunnel_ssh_user="beagle-usb",
        utcnow=lambda: "2026-04-27T00:00:00Z",
        version="6.7.0",
    )


def test_vm_http_surface_returns_profile_and_downloads(tmp_path: Path) -> None:
    surface = _surface(tmp_path)

    profile = surface.route_get("/api/v1/vms/100")
    installer = surface.route_get("/api/v1/vms/100/installer.sh")
    live_usb_ps1 = surface.route_get("/api/v1/vms/100/live-usb.ps1")

    assert int(profile["status"]) == 200
    assert profile["payload"]["profile"]["vmid"] == 100
    assert int(installer["status"]) == 200
    assert installer["filename"] == "installer.sh"
    assert int(live_usb_ps1["status"]) == 200
    assert live_usb_ps1["filename"] == "live-usb.ps1"


def test_vm_http_surface_returns_state_actions_and_endpoint(tmp_path: Path) -> None:
    surface = _surface(tmp_path)

    state = surface.route_get("/api/v1/vms/100/state")
    actions = surface.route_get("/api/v1/vms/100/actions")
    endpoint = surface.route_get("/api/v1/vms/100/endpoint")

    assert int(state["status"]) == 200
    assert state["payload"]["vm"]["vmid"] == 100
    assert int(actions["status"]) == 200
    assert actions["payload"]["pending_actions"][0]["action"] == "restart"
    assert int(endpoint["status"]) == 200
    assert endpoint["payload"]["endpoint"]["reported_at"]


def test_vm_http_surface_maps_missing_or_invalid_vm(tmp_path: Path) -> None:
    surface = _surface(tmp_path)

    missing = surface.route_get("/api/v1/vms/999")
    invalid = surface.route_get("/api/v1/vms/not-a-number/installer.sh")

    assert int(missing["status"]) == 404
    assert missing["payload"]["error"] == "vm not found"
    assert int(invalid["status"]) == 400
    assert invalid["payload"]["error"] == "invalid vmid"
