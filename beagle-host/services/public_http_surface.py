from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable
from urllib.parse import parse_qs


class PublicHttpSurfaceService:
    def __init__(
        self,
        *,
        build_profile: Callable[[Any], dict[str, Any]],
        build_update_feed: Callable[..., dict[str, Any]],
        build_vm_state: Callable[[Any], dict[str, Any]],
        find_vm: Callable[[int], Any | None],
        service_name: str,
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._build_profile = build_profile
        self._build_update_feed = build_update_feed
        self._build_vm_state = build_vm_state
        self._find_vm = find_vm
        self._service_name = str(service_name or "beagle-control-plane")
        self._utcnow = utcnow
        self._version = str(version or "")

    @staticmethod
    def _json_response(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    def _envelope(self, **payload: Any) -> dict[str, Any]:
        return {
            "service": self._service_name,
            "version": self._version,
            "generated_at": self._utcnow(),
            **payload,
        }

    def _public_vm_state_payload(self, vmid: int) -> dict[str, Any] | None:
        vm = self._find_vm(vmid)
        if vm is None:
            return None
        return self._envelope(**self._build_vm_state(vm))

    def _public_vm_endpoint_payload(self, vmid: int) -> dict[str, Any] | None:
        vm = self._find_vm(vmid)
        if vm is None:
            return None
        state = self._build_vm_state(vm)
        if not state["endpoint"].get("reported_at"):
            return None
        return self._envelope(**state)

    def route_get(self, path: str) -> dict[str, Any] | None:
        if path.startswith("/api/v1/public/vms/") and path.endswith("/state"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
            payload = self._public_vm_state_payload(int(vmid_text))
            if payload is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            return self._json_response(HTTPStatus.OK, payload)

        if path.startswith("/api/v1/public/vms/") and path.endswith("/endpoint"):
            vmid_text = path.split("/")[-2]
            if not vmid_text.isdigit():
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid vmid"})
            payload = self._public_vm_endpoint_payload(int(vmid_text))
            if payload is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "endpoint not found"})
            return self._json_response(HTTPStatus.OK, payload)

        if path.startswith("/api/v1/public/vms/") and path.endswith("/installer.sh"):
            return self._json_response(HTTPStatus.FORBIDDEN, {"ok": False, "error": "public installer download disabled"})
        if path.startswith("/api/v1/public/vms/") and path.endswith("/live-usb.sh"):
            return self._json_response(HTTPStatus.FORBIDDEN, {"ok": False, "error": "public live USB download disabled"})
        if path.startswith("/api/v1/public/vms/") and path.endswith("/installer.ps1"):
            return self._json_response(HTTPStatus.FORBIDDEN, {"ok": False, "error": "public installer download disabled"})
        return None

    def endpoint_update_feed(
        self,
        *,
        query_text: str,
        endpoint_identity: dict[str, Any] | None,
    ) -> dict[str, Any]:
        identity = endpoint_identity or {}
        vmid = int(identity.get("vmid", 0) or 0)
        vm = self._find_vm(vmid)
        if vm is None or str(identity.get("node", "")).strip() != vm.node:
            return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
        query = parse_qs(query_text or "")
        profile = self._build_profile(vm)
        update_feed = self._build_update_feed(
            profile,
            installed_version=str((query.get("installed_version") or [""])[0]).strip(),
            channel=str((query.get("channel") or [""])[0]).strip(),
            version_pin=str((query.get("version_pin") or [""])[0]).strip(),
        )
        return self._json_response(
            HTTPStatus.OK,
            {
                "ok": True,
                **self._envelope(update=update_feed),
            },
        )
