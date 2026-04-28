"""Fleet / Thin-client Device Registry HTTP surface.

GoEnterprise Plan 02:
- device registry CRUD/read surface
- heartbeat / lock / wipe state transitions
"""
from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable


class FleetHttpSurfaceService:
    _DEVICE_DETAIL = re.compile(r"^/api/v1/fleet/devices/(?P<device_id>[A-Za-z0-9._:-]+)$")
    _DEVICE_EFFECTIVE_POLICY = re.compile(r"^/api/v1/fleet/devices/(?P<device_id>[A-Za-z0-9._:-]+)/effective-policy$")
    _DEVICE_ACTION = re.compile(r"^/api/v1/fleet/devices/(?P<device_id>[A-Za-z0-9._:-]+)/(?P<action>heartbeat|lock|unlock|wipe|confirm-wiped)$")

    def __init__(
        self,
        *,
        device_registry_service: Any,
        mdm_policy_service: Any | None = None,
        audit_event: Callable[..., None] | None = None,
        requester_identity: Callable[[], str] | None = None,
        service_name: str = "beagle-control-plane",
        utcnow: Callable[[], str],
        version: str = "",
    ) -> None:
        self._registry = device_registry_service
        self._mdm_policy = mdm_policy_service
        self._audit_event = audit_event
        self._requester_identity = requester_identity or (lambda: "")
        self._service_name = str(service_name or "beagle-control-plane")
        self._utcnow = utcnow
        self._version = str(version or "")

    @staticmethod
    def _json(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    def _envelope(self, **payload: Any) -> dict[str, Any]:
        return {
            "service": self._service_name,
            "version": self._version,
            "generated_at": self._utcnow(),
            **payload,
        }

    def _safe_audit_event(self, event_type: str, outcome: str, **details: Any) -> None:
        if self._audit_event is None:
            return
        try:
            payload = dict(details)
            payload.setdefault("username", self._requester_identity())
            self._audit_event(
                event_type,
                outcome,
                **payload,
            )
        except Exception:
            return

    @staticmethod
    def _hardware_to_dict(hardware: Any) -> dict[str, Any]:
        return {
            "cpu_model": str(getattr(hardware, "cpu_model", "") or ""),
            "cpu_cores": int(getattr(hardware, "cpu_cores", 0) or 0),
            "ram_gb": int(getattr(hardware, "ram_gb", 0) or 0),
            "gpu_model": str(getattr(hardware, "gpu_model", "") or ""),
            "network_interfaces": list(getattr(hardware, "network_interfaces", []) or []),
            "disk_gb": int(getattr(hardware, "disk_gb", 0) or 0),
        }

    @classmethod
    def _device_to_dict(cls, device: Any) -> dict[str, Any]:
        return {
            "device_id": str(getattr(device, "device_id", "") or ""),
            "hostname": str(getattr(device, "hostname", "") or ""),
            "hardware": cls._hardware_to_dict(getattr(device, "hardware", None)),
            "os_version": str(getattr(device, "os_version", "") or ""),
            "enrolled_at": str(getattr(device, "enrolled_at", "") or ""),
            "last_seen": str(getattr(device, "last_seen", "") or ""),
            "location": str(getattr(device, "location", "") or ""),
            "group": str(getattr(device, "group", "") or ""),
            "status": str(getattr(device, "status", "offline") or "offline"),
            "vpn_active": bool(getattr(device, "vpn_active", False)),
            "vpn_interface": str(getattr(device, "vpn_interface", "") or ""),
            "wg_public_key": str(getattr(device, "wg_public_key", "") or ""),
            "wg_assigned_ip": str(getattr(device, "wg_assigned_ip", "") or ""),
            "notes": str(getattr(device, "notes", "") or ""),
        }

    def handles_get(self, path: str) -> bool:
        if path == "/api/v1/fleet/devices":
            return True
        if path == "/api/v1/fleet/devices/groups":
            return True
        if self._DEVICE_EFFECTIVE_POLICY.match(path):
            return True
        return self._DEVICE_DETAIL.match(path) is not None

    def route_get(self, path: str, *, query: dict[str, list[str]] | None = None) -> dict[str, Any] | None:
        params = query or {}
        if path == "/api/v1/fleet/devices":
            location = str((params.get("location") or [""])[0] or "").strip() or None
            group = str((params.get("group") or [""])[0] or "").strip() or None
            status = str((params.get("status") or [""])[0] or "").strip() or None
            devices = self._registry.list_devices(location=location, group=group, status=status)
            payload = [self._device_to_dict(item) for item in devices]
            return self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        devices=payload,
                        groups=self._registry.list_groups(),
                        count=len(payload),
                    ),
                },
            )
        if path == "/api/v1/fleet/devices/groups":
            return self._json(
                HTTPStatus.OK,
                {"ok": True, **self._envelope(groups=self._registry.list_groups())},
            )

        match = self._DEVICE_EFFECTIVE_POLICY.match(path)
        if match is not None:
            device = self._registry.get_device(match.group("device_id"))
            if device is None:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "device not found"})
            if self._mdm_policy is None:
                return self._json(HTTPStatus.OK, {"ok": True, **self._envelope(policy=None, source_type="default", source_id="__default__")})
            policy, source_type, source_id = self._mdm_policy.resolve_policy_with_source(
                str(getattr(device, "device_id", "") or ""),
                group=str(getattr(device, "group", "") or ""),
            )
            return self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        device_id=str(getattr(device, "device_id", "") or ""),
                        group=str(getattr(device, "group", "") or ""),
                        source_type=source_type,
                        source_id=source_id,
                        conflicts=self._mdm_policy.describe_effective_policy_conflicts(
                            str(getattr(device, "device_id", "") or ""),
                            group=str(getattr(device, "group", "") or ""),
                        ),
                        policy={
                            "policy_id": str(getattr(policy, "policy_id", "") or ""),
                            "name": str(getattr(policy, "name", "") or ""),
                            "allowed_networks": list(getattr(policy, "allowed_networks", []) or []),
                            "allowed_pools": list(getattr(policy, "allowed_pools", []) or []),
                            "max_resolution": str(getattr(policy, "max_resolution", "") or ""),
                            "allowed_codecs": list(getattr(policy, "allowed_codecs", []) or []),
                            "auto_update": bool(getattr(policy, "auto_update", True)),
                            "update_window_start_hour": int(getattr(policy, "update_window_start_hour", 2) or 2),
                            "update_window_end_hour": int(getattr(policy, "update_window_end_hour", 4) or 4),
                            "screen_lock_timeout_seconds": int(getattr(policy, "screen_lock_timeout_seconds", 0) or 0),
                            "validation": self._mdm_policy.validate_policy(policy),
                        },
                    ),
                },
            )

        match = self._DEVICE_DETAIL.match(path)
        if match is None:
            return None
        device = self._registry.get_device(match.group("device_id"))
        if device is None:
            return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "device not found"})
        return self._json(
            HTTPStatus.OK,
            {"ok": True, **self._envelope(device=self._device_to_dict(device))},
        )

    def handles_post(self, path: str) -> bool:
        if path == "/api/v1/fleet/devices/register":
            return True
        return self._DEVICE_ACTION.match(path) is not None

    def route_post(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
        requester: str = "",
    ) -> dict[str, Any] | None:
        payload = json_payload or {}
        requester_name = str(requester or "").strip()
        if path == "/api/v1/fleet/devices/register":
            device_id = str(payload.get("device_id") or "").strip()
            hostname = str(payload.get("hostname") or "").strip()
            hardware = payload.get("hardware")
            if not device_id or not hostname or not isinstance(hardware, dict):
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "device_id, hostname, hardware required"})
            device = self._registry.register_device(
                device_id,
                hostname,
                hardware,
                os_version=str(payload.get("os_version") or "").strip(),
                vpn_active=bool(payload.get("vpn_active", False)),
                vpn_interface=str(payload.get("vpn_interface") or "").strip(),
                wg_public_key=str(payload.get("wg_public_key") or "").strip(),
                wg_assigned_ip=str(payload.get("wg_assigned_ip") or "").strip(),
            )
            self._safe_audit_event(
                "fleet.device.register",
                "success",
                username=requester_name or self._requester_identity(),
                device_id=device_id,
                hostname=hostname,
            )
            return self._json(
                HTTPStatus.CREATED,
                {"ok": True, **self._envelope(device=self._device_to_dict(device))},
            )

        match = self._DEVICE_ACTION.match(path)
        if match is None:
            return None
        device_id = match.group("device_id")
        action = match.group("action")
        try:
            if action == "heartbeat":
                device = self._registry.update_heartbeat(device_id, metrics=payload.get("metrics"))
            elif action == "lock":
                device = self._registry.lock_device(device_id)
            elif action == "unlock":
                device = self._registry.unlock_device(device_id)
            elif action == "wipe":
                device = self._registry.wipe_device(device_id)
            elif action == "confirm-wiped":
                device = self._registry.confirm_wiped(device_id)
            else:
                return None
        except KeyError:
            return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "device not found"})
        self._safe_audit_event(
            f"fleet.device.{action}",
            "success",
            username=requester_name or self._requester_identity(),
            device_id=device_id,
            status=str(getattr(device, "status", "") or ""),
        )
        return self._json(
            HTTPStatus.OK,
            {"ok": True, "action": action, **self._envelope(device=self._device_to_dict(device))},
        )

    def handles_put(self, path: str) -> bool:
        return self._DEVICE_DETAIL.match(path) is not None

    def route_put(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
        requester: str = "",
    ) -> dict[str, Any] | None:
        payload = json_payload or {}
        requester_name = str(requester or "").strip()
        match = self._DEVICE_DETAIL.match(path)
        if match is None:
            return None
        device_id = match.group("device_id")
        try:
            device = self._registry.get_device(device_id)
            if device is None:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "device not found"})
            if "location" in payload:
                device = self._registry.set_location(device_id, str(payload.get("location") or "").strip())
            if "group" in payload:
                device = self._registry.set_group(device_id, str(payload.get("group") or "").strip())
            if "notes" in payload:
                raw = self._registry._require(device_id)
                raw["notes"] = str(payload.get("notes") or "").strip()
                self._registry._save()
                device = self._registry.get_device(device_id)
            if device is None:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "device not found"})
        except KeyError:
            return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "device not found"})
        self._safe_audit_event(
            "fleet.device.update",
            "success",
            username=requester_name or self._requester_identity(),
            device_id=device_id,
            location=str(payload.get("location") or "").strip() if "location" in payload else None,
            group=str(payload.get("group") or "").strip() if "group" in payload else None,
            notes_updated="notes" in payload,
        )
        return self._json(
            HTTPStatus.OK,
            {"ok": True, **self._envelope(device=self._device_to_dict(device))},
        )
