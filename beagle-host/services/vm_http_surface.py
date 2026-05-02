from __future__ import annotations

import re
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable

from update_feed import _version_lt


class VmHttpSurfaceService:
    def __init__(
        self,
        *,
        build_profile: Callable[[Any], dict[str, Any]],
        build_novnc_access: Callable[[Any], dict[str, Any]],
        build_vm_state: Callable[[Any], dict[str, Any]],
        build_vm_usb_state: Callable[[Any, dict[str, Any] | None], dict[str, Any]],
        downloads_status_file: Path,
        ensure_vm_secret: Callable[[Any], dict[str, Any]],
        find_vm: Callable[[int], Any | None],
        list_support_bundle_metadata: Callable[..., list[dict[str, Any]]],
        load_action_queue: Callable[[str, int], list[dict[str, Any]]],
        load_endpoint_report: Callable[[str, int], dict[str, Any] | None],
        load_installer_prep_state: Callable[[str, int], dict[str, Any] | None],
        load_json_file: Callable[[Path, Any], Any],
        public_manager_url: str,
        public_server_name: str,
        render_vm_installer_script: Callable[[Any], tuple[bytes, str]],
        render_vm_live_usb_script: Callable[[Any], tuple[bytes, str]],
        render_vm_windows_installer_script: Callable[[Any], tuple[bytes, str]],
        render_vm_windows_live_usb_script: Callable[[Any], tuple[bytes, str]],
        service_name: str,
        summarize_endpoint_report: Callable[[dict[str, Any]], dict[str, Any]],
        summarize_installer_prep_state: Callable[[Any, dict[str, Any] | None], dict[str, Any]],
        usb_tunnel_ssh_user: str,
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._build_profile = build_profile
        self._build_novnc_access = build_novnc_access
        self._build_vm_state = build_vm_state
        self._build_vm_usb_state = build_vm_usb_state
        self._downloads_status_file = Path(downloads_status_file)
        self._ensure_vm_secret = ensure_vm_secret
        self._find_vm = find_vm
        self._list_support_bundle_metadata = list_support_bundle_metadata
        self._load_action_queue = load_action_queue
        self._load_endpoint_report = load_endpoint_report
        self._load_installer_prep_state = load_installer_prep_state
        self._load_json_file = load_json_file
        self._public_manager_url = str(public_manager_url or "")
        self._public_server_name = str(public_server_name or "")
        self._render_vm_installer_script = render_vm_installer_script
        self._render_vm_live_usb_script = render_vm_live_usb_script
        self._render_vm_windows_installer_script = render_vm_windows_installer_script
        self._render_vm_windows_live_usb_script = render_vm_windows_live_usb_script
        self._service_name = str(service_name or "beagle-control-plane")
        self._summarize_endpoint_report = summarize_endpoint_report
        self._summarize_installer_prep_state = summarize_installer_prep_state
        self._usb_tunnel_ssh_user = str(usb_tunnel_ssh_user or "")
        self._utcnow = utcnow
        self._version = str(version or "")

    @staticmethod
    def _json_response(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    @staticmethod
    def _bytes_response(status: HTTPStatus, body: bytes, *, content_type: str, filename: str) -> dict[str, Any]:
        return {
            "kind": "bytes",
            "status": status,
            "body": body,
            "content_type": content_type,
            "filename": filename,
        }

    def _envelope(self, **payload: Any) -> dict[str, Any]:
        return {
            "service": self._service_name,
            "version": self._version,
            "generated_at": self._utcnow(),
            **payload,
        }

    def _render_script_download(
        self,
        vm: Any,
        *,
        render: Callable[[Any], tuple[bytes, str]],
        content_type: str,
    ) -> dict[str, Any]:
        try:
            body, filename = render(vm)
        except FileNotFoundError as exc:
            return self._json_response(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": str(exc)})
        except ValueError as exc:
            return self._json_response(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
        return self._bytes_response(HTTPStatus.OK, body, content_type=content_type, filename=filename)

    def _credentials_payload(self, vm: Any) -> dict[str, Any]:
        secret = self._ensure_vm_secret(vm)
        return self._envelope(
            credentials={
                "vmid": vm.vmid,
                "node": vm.node,
                "thinclient_username": "thinclient",
                "thinclient_password": str(secret.get("thinclient_password", "")),
                "guest_password": str(secret.get("guest_password") or secret.get("password") or ""),
                "beagle_stream_server_username": str(secret.get("beagle_stream_server_username", "")),
                "beagle_stream_server_password": str(secret.get("beagle_stream_server_password", "")),
                "beagle_stream_server_pin": str(secret.get("beagle_stream_server_pin", "")),
                "usb_tunnel_host": self._public_server_name,
                "usb_tunnel_user": self._usb_tunnel_ssh_user,
                "usb_tunnel_port": int(secret.get("usb_tunnel_port", 0) or 0),
            }
        )

    def _installer_prep_payload(self, vm: Any) -> dict[str, Any]:
        return self._envelope(
            installer_prep=self._summarize_installer_prep_state(
                vm,
                self._load_installer_prep_state(vm.node, vm.vmid),
            )
        )

    def _policy_payload(self, vm: Any) -> dict[str, Any]:
        profile = self._build_profile(vm)
        return self._envelope(
            applied_policy=profile.get("applied_policy"),
            assignment_source=profile.get("assignment_source", ""),
        )

    def _novnc_access_payload(self, vm: Any) -> dict[str, Any]:
        return self._envelope(novnc_access=self._build_novnc_access(vm))

    def _support_bundles_payload(self, vm: Any) -> dict[str, Any]:
        return self._envelope(
            support_bundles=self._list_support_bundle_metadata(node=vm.node, vmid=vm.vmid)
        )

    def _usb_payload(self, vm: Any) -> dict[str, Any]:
        report = self._load_endpoint_report(vm.node, vm.vmid)
        return self._envelope(usb=self._build_vm_usb_state(vm, report))

    def _update_payload(self, vm: Any) -> dict[str, Any]:
        profile = self._build_profile(vm)
        endpoint = self._summarize_endpoint_report(self._load_endpoint_report(vm.node, vm.vmid) or {})
        downloads_status = self._load_json_file(self._downloads_status_file, {})
        if not isinstance(downloads_status, dict):
            downloads_status = {}
        published_latest_version = str(downloads_status.get("version", "")).strip()
        endpoint_compatibility = (
            downloads_status.get("endpoint_compatibility")
            if isinstance(downloads_status.get("endpoint_compatibility"), dict)
            else {}
        )
        current_version = str(endpoint.get("update_current_version", "") or "").strip()
        minimum_self_update_version = str(
            endpoint_compatibility.get("minimum_self_update_version")
            or downloads_status.get("minimum_self_update_version")
            or "8.0"
        ).strip()
        reinstall_required = bool(endpoint_compatibility.get("reinstall_required", False))
        migration_required = bool(endpoint_compatibility.get("migration_required", False))
        reinstall_reasons = endpoint_compatibility.get("reinstall_reasons", [])
        if not isinstance(reinstall_reasons, list):
            reinstall_reasons = []
        migration_reasons = endpoint_compatibility.get("migration_reasons", [])
        if not isinstance(migration_reasons, list):
            migration_reasons = []
        if current_version and minimum_self_update_version and _version_lt(current_version, minimum_self_update_version):
            reinstall_required = True
            reinstall_reasons = [
                *[str(item) for item in reinstall_reasons],
                f"Installierte Version ist aelter als die minimale Self-Update-Version {minimum_self_update_version}.",
            ]
        update_path = "reinstall_required" if reinstall_required else ("migration_required" if migration_required else "self_update")
        return self._envelope(
            update={
                "policy": {
                    "enabled": bool(profile.get("update_enabled", True)),
                    "channel": str(profile.get("update_channel", "stable") or "stable"),
                    "behavior": str(profile.get("update_behavior", "prompt") or "prompt"),
                    "feed_url": str(
                        profile.get("update_feed_url", f"{self._public_manager_url}/api/v1/endpoints/update-feed")
                        or ""
                    ),
                    "version_pin": str(profile.get("update_version_pin", "") or ""),
                },
                "endpoint": {
                    "state": endpoint.get("update_state", ""),
                    "current_version": current_version,
                    "latest_version": endpoint.get("update_latest_version", ""),
                    "staged_version": endpoint.get("update_staged_version", ""),
                    "current_slot": endpoint.get("update_current_slot", ""),
                    "next_slot": endpoint.get("update_next_slot", ""),
                    "available": endpoint.get("update_available", False),
                    "pending_reboot": endpoint.get("update_pending_reboot", False),
                    "last_scan_at": endpoint.get("update_last_scan_at", ""),
                    "last_error": endpoint.get("update_last_error", ""),
                    "health_failure": endpoint.get("update_health_failure", False),
                    "rollback_recommended": endpoint.get("update_rollback_recommended", False),
                    "last_health_failure_at": endpoint.get("update_last_health_failure_at", ""),
                },
                "published_latest_version": published_latest_version,
                "compatibility": {
                    "update_path": update_path,
                    "self_update_supported": update_path == "self_update",
                    "migration_required": update_path == "migration_required",
                    "reinstall_required": update_path == "reinstall_required",
                    "rebuild_recommended": update_path != "self_update",
                    "minimum_self_update_version": minimum_self_update_version,
                    "reinstall_reasons": [str(item) for item in reinstall_reasons],
                    "migration_reasons": [str(item) for item in migration_reasons],
                    "foundation_generation": str(
                        endpoint_compatibility.get("foundation_generation")
                        or downloads_status.get("foundation_generation")
                        or "1"
                    ),
                },
            }
        )

    def _state_payload(self, vmid: int) -> dict[str, Any] | None:
        vm = self._find_vm(vmid)
        if vm is None:
            return None
        return self._envelope(**self._build_vm_state(vm))

    def _actions_payload(self, vmid: int) -> dict[str, Any] | None:
        vm = self._find_vm(vmid)
        if vm is None:
            return None
        state = self._build_vm_state(vm)
        return self._envelope(
            pending_actions=self._load_action_queue(vm.node, vm.vmid),
            last_action=state["last_action"],
        )

    def _endpoint_payload(self, vmid: int) -> dict[str, Any] | None:
        vm = self._find_vm(vmid)
        if vm is None:
            return None
        state = self._build_vm_state(vm)
        if not state["endpoint"].get("reported_at"):
            return None
        return self._envelope(**state)

    def _profile_payload(self, vmid: int) -> dict[str, Any] | None:
        vm = self._find_vm(vmid)
        if vm is None:
            return None
        return self._envelope(profile=self._build_profile(vm))

    def route_get(self, path: str) -> dict[str, Any]:
        match = re.match(r"^/api/v1/vms/(?P<vmid>\d+)/installer\.sh$", path)
        if match:
            vm = self._find_vm(int(match.group("vmid")))
            if vm is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._render_script_download(
                vm,
                render=self._render_vm_installer_script,
                content_type="text/x-shellscript; charset=utf-8",
            )
        if path.endswith("/installer.sh"):
            return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})

        match = re.match(r"^/api/v1/vms/(?P<vmid>\d+)/live-usb\.sh$", path)
        if match:
            vm = self._find_vm(int(match.group("vmid")))
            if vm is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._render_script_download(
                vm,
                render=self._render_vm_live_usb_script,
                content_type="text/x-shellscript; charset=utf-8",
            )
        if path.endswith("/live-usb.sh"):
            return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})

        match = re.match(r"^/api/v1/vms/(?P<vmid>\d+)/installer\.ps1$", path)
        if match:
            vm = self._find_vm(int(match.group("vmid")))
            if vm is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._render_script_download(
                vm,
                render=self._render_vm_windows_installer_script,
                content_type="text/plain; charset=utf-8",
            )
        if path.endswith("/installer.ps1"):
            return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})

        match = re.match(r"^/api/v1/vms/(?P<vmid>\d+)/live-usb\.ps1$", path)
        if match:
            vm = self._find_vm(int(match.group("vmid")))
            if vm is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._render_script_download(
                vm,
                render=self._render_vm_windows_live_usb_script,
                content_type="text/plain; charset=utf-8",
            )
        if path.endswith("/live-usb.ps1"):
            return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})

        if path.endswith("/credentials"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
            vm = self._find_vm(int(vmid_text))
            if vm is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._json_response(HTTPStatus.OK, self._credentials_payload(vm))

        if path.endswith("/installer-prep"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
            vm = self._find_vm(int(vmid_text))
            if vm is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._json_response(HTTPStatus.OK, self._installer_prep_payload(vm))

        if path.endswith("/policy"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
            vm = self._find_vm(int(vmid_text))
            if vm is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._json_response(HTTPStatus.OK, self._policy_payload(vm))

        if path.endswith("/novnc-access"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
            vm = self._find_vm(int(vmid_text))
            if vm is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._json_response(HTTPStatus.OK, self._novnc_access_payload(vm))

        if path.endswith("/support-bundles"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
            vm = self._find_vm(int(vmid_text))
            if vm is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._json_response(HTTPStatus.OK, self._support_bundles_payload(vm))

        if path.endswith("/usb"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
            vm = self._find_vm(int(vmid_text))
            if vm is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._json_response(HTTPStatus.OK, self._usb_payload(vm))

        if path.endswith("/update"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
            vm = self._find_vm(int(vmid_text))
            if vm is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._json_response(HTTPStatus.OK, self._update_payload(vm))

        if path.endswith("/state"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
            payload = self._state_payload(int(vmid_text))
            if payload is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._json_response(HTTPStatus.OK, payload)

        if path.endswith("/actions"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
            payload = self._actions_payload(int(vmid_text))
            if payload is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._json_response(HTTPStatus.OK, payload)

        if path.endswith("/endpoint"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
            payload = self._endpoint_payload(int(vmid_text))
            if payload is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "endpoint not found"})
            return self._json_response(HTTPStatus.OK, payload)

        match = re.match(r"^/api/v1/vms/(?P<vmid>\d+)/?$", path)
        if not match:
            return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
        payload = self._profile_payload(int(match.group("vmid")))
        if payload is None:
            return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
        return self._json_response(HTTPStatus.OK, payload)
