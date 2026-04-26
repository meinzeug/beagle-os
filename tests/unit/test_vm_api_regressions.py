from __future__ import annotations

import importlib.util
import tempfile
import threading
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


admin_module = load_module("admin_http_surface_regression", "beagle-host/services/admin_http_surface.py")
vm_module = load_module("vm_http_surface_regression", "beagle-host/services/vm_http_surface.py")
auth_module = load_module("auth_session_regression", "beagle-host/services/auth_session.py")

AdminHttpSurfaceService = admin_module.AdminHttpSurfaceService
VmHttpSurfaceService = vm_module.VmHttpSurfaceService
AuthSessionService = auth_module.AuthSessionService


@dataclass
class Vm:
    vmid: int
    node: str = "beagle-0"
    name: str = "beagle-test"
    status: str = "running"


def test_delete_provisioned_vm_returns_deleted_payload() -> None:
    deleted: list[int] = []

    surface = AdminHttpSurfaceService(
        create_provisioned_vm=lambda _payload: {},
        create_ubuntu_beagle_vm=lambda _payload: {},
        delete_provisioned_vm=lambda vmid: deleted.append(vmid) or {"vmid": vmid, "deleted": True},
        delete_policy=lambda _name: False,
        queue_bulk_actions=lambda _vmids, _action, _requester: [],
        save_policy=lambda *_args, **_kwargs: {},
        service_name="beagle-control-plane",
        update_ubuntu_beagle_vm=lambda _vmid, _payload: {},
        utcnow=lambda: "2026-04-26T00:00:00Z",
        version="test",
    )

    response = surface.route_delete("/api/v1/provisioning/vms/101")

    assert response["status"] == HTTPStatus.OK
    assert response["payload"]["ok"] is True
    assert response["payload"]["provisioned_vm"] == {"vmid": 101, "deleted": True}
    assert deleted == [101]


def test_delete_provisioned_vm_maps_missing_vm_to_404() -> None:
    surface = AdminHttpSurfaceService(
        create_provisioned_vm=lambda _payload: {},
        create_ubuntu_beagle_vm=lambda _payload: {},
        delete_provisioned_vm=lambda _vmid: (_ for _ in ()).throw(ValueError("vm not found: 404")),
        delete_policy=lambda _name: False,
        queue_bulk_actions=lambda _vmids, _action, _requester: [],
        save_policy=lambda *_args, **_kwargs: {},
        service_name="beagle-control-plane",
        update_ubuntu_beagle_vm=lambda _vmid, _payload: {},
        utcnow=lambda: "2026-04-26T00:00:00Z",
        version="test",
    )

    response = surface.route_delete("/api/v1/provisioning/vms/404")

    assert response["status"] == HTTPStatus.NOT_FOUND
    assert response["payload"] == {"ok": False, "error": "vm not found: 404"}


def make_vm_surface(vm: Vm | None, novnc_payload: dict) -> VmHttpSurfaceService:
    return VmHttpSurfaceService(
        build_profile=lambda _vm: {},
        build_novnc_access=lambda _vm: novnc_payload,
        build_vm_state=lambda _vm: {},
        build_vm_usb_state=lambda _vm, _report: {},
        downloads_status_file=Path("/nonexistent/status.json"),
        ensure_vm_secret=lambda _vm: {},
        find_vm=lambda vmid: vm if vm is not None and vm.vmid == vmid else None,
        list_support_bundle_metadata=lambda **_kwargs: [],
        load_action_queue=lambda _node, _vmid: [],
        load_endpoint_report=lambda _node, _vmid: None,
        load_installer_prep_state=lambda _node, _vmid: None,
        load_json_file=lambda _path, default: default,
        public_manager_url="https://example.invalid",
        public_server_name="example.invalid",
        render_vm_installer_script=lambda _vm: (b"", "installer.sh"),
        render_vm_live_usb_script=lambda _vm: (b"", "live-usb.sh"),
        render_vm_windows_installer_script=lambda _vm: (b"", "installer.ps1"),
        render_vm_windows_live_usb_script=lambda _vm: (b"", "live-usb.ps1"),
        service_name="beagle-control-plane",
        summarize_endpoint_report=lambda _report: {},
        summarize_installer_prep_state=lambda _vm, _state: {},
        usb_tunnel_ssh_user="beagle-tunnel",
        utcnow=lambda: "2026-04-26T00:00:00Z",
        version="test",
    )


def test_novnc_access_returns_success_payload_for_existing_vm() -> None:
    novnc_payload = {"url": "https://example.invalid/novnc/?path=beagle-novnc/websockify", "token_ttl_seconds": 30}
    surface = make_vm_surface(Vm(vmid=101), novnc_payload)

    response = surface.route_get("/api/v1/vms/101/novnc-access")

    assert response["status"] == HTTPStatus.OK
    assert response["payload"]["novnc_access"] == novnc_payload


def test_novnc_access_returns_404_for_missing_vm() -> None:
    surface = make_vm_surface(None, {})

    response = surface.route_get("/api/v1/vms/101/novnc-access")

    assert response["status"] == HTTPStatus.NOT_FOUND
    assert response["payload"] == {"ok": False, "error": "vm not found"}


def test_windows_live_usb_download_route_returns_script() -> None:
    surface = make_vm_surface(Vm(vmid=101), {})

    response = surface.route_get("/api/v1/vms/101/live-usb.ps1")

    assert response["status"] == HTTPStatus.OK
    assert response["filename"] == "live-usb.ps1"


def test_concurrent_refreshes_do_not_corrupt_session_state() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        counter = {"value": 0}

        def token_urlsafe(_length: int) -> str:
            counter["value"] += 1
            return f"token-{counter['value']}"

        service = AuthSessionService(
            data_dir=root,
            load_json_file=lambda path, default: __import__("json").loads(path.read_text()) if path.exists() else default,
            write_json_file=lambda path, payload: (path.parent.mkdir(parents=True, exist_ok=True), path.write_text(__import__("json").dumps(payload))),
            now=lambda: 1_700_000_000,
            token_urlsafe=token_urlsafe,
            access_ttl_seconds=900,
        )
        service.create_user(username="admin", password="secret123", role="superadmin", enabled=True)
        session = service.login(username="admin", password="secret123")
        assert session is not None
        refresh_token = session["refresh_token"]

        results: list[dict | None] = []
        threads = [threading.Thread(target=lambda: results.append(service.refresh(refresh_token))) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(results) == 10
        assert all(item is not None and item["ok"] is True for item in results)
        sessions_doc = __import__("json").loads((root / "auth" / "sessions.json").read_text())
        assert len(sessions_doc["sessions"]) == 1
        assert sessions_doc["sessions"][0]["refresh_token"] == refresh_token
        assert sessions_doc["sessions"][0]["access_token"].startswith("token-")
