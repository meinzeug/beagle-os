from __future__ import annotations

import json
import re
import threading
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable

from core.persistence.json_state_store import JsonStateStore


class StreamHttpSurfaceService:
    _REGISTER_ROUTE = "/api/v1/streams/register"
    _ALLOCATE_ROUTE = "/api/v1/streams/allocate"
    _CONFIG_ROUTE = re.compile(r"^/api/v1/streams/(?P<vm_id>\d+)/config$")
    _EVENTS_ROUTE = re.compile(r"^/api/v1/streams/(?P<vm_id>\d+)/events$")

    def __init__(
        self,
        *,
        state_file: Path,
        build_vm_profile: Callable[[Any], dict[str, Any]],
        find_vm: Callable[[int], Any | None],
        pool_manager_service: Any,
        stream_policy_service: Any,
        build_wireguard_peer_config: Callable[[str, str, str], dict[str, Any]] | None = None,
        issue_pairing_token: Callable[[int, str, str], str] | None = None,
        requester_identity: Callable[[], str] | None = None,
        audit_event: Callable[..., None] | None = None,
        service_name: str = "beagle-control-plane",
        utcnow: Callable[[], str],
        version: str = "",
    ) -> None:
        self._state_file = Path(state_file)
        self._build_vm_profile = build_vm_profile
        self._find_vm = find_vm
        self._pool_manager = pool_manager_service
        self._stream_policy = stream_policy_service
        self._build_wireguard_peer_config = build_wireguard_peer_config
        self._issue_pairing_token = issue_pairing_token
        self._requester_identity = requester_identity or (lambda: "")
        self._audit_event = audit_event
        self._service_name = str(service_name or "beagle-control-plane")
        self._utcnow = utcnow
        self._version = str(version or "")
        self._lock = threading.RLock()
        self._state_store = JsonStateStore(self._state_file, default_factory=lambda: {"registrations": {}})

    @classmethod
    def handles_get(cls, path: str) -> bool:
        return cls._CONFIG_ROUTE.match(str(path or "")) is not None

    @classmethod
    def handles_post(cls, path: str) -> bool:
        route = str(path or "")
        return route in {cls._REGISTER_ROUTE, cls._ALLOCATE_ROUTE} or cls._EVENTS_ROUTE.match(route) is not None

    @staticmethod
    def requires_json_body(path: str) -> bool:
        return StreamHttpSurfaceService.handles_post(path)

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

    def _safe_audit(self, event_type: str, outcome: str, **details: Any) -> None:
        if self._audit_event is None:
            return
        payload = dict(details)
        payload.setdefault("username", self._requester_identity())
        try:
            self._audit_event(event_type, outcome, **payload)
            return
        except TypeError:
            # Backward-compatibility for writers that expect a details dict as third arg.
            pass
        except Exception:
            return
        try:
            self._audit_event(event_type, outcome, payload)
        except Exception:
            return

    @staticmethod
    def _coerce_bool(value: Any, *, default: bool = False) -> bool:
        if value is None:
            return bool(default)
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
        return bool(default)

    def _load_state(self) -> dict[str, Any]:
        with self._lock:
            payload = self._state_store.load()
            registrations = payload.get("registrations")
            if not isinstance(registrations, dict):
                registrations = {}
            return {"registrations": registrations}

    def _save_state(self, state: dict[str, Any]) -> None:
        with self._lock:
            self._state_store.save(state)

    def _get_registration(self, vm_id: int) -> dict[str, Any] | None:
        state = self._load_state()
        registration = state["registrations"].get(str(int(vm_id)))
        return dict(registration) if isinstance(registration, dict) else None

    def _store_registration(self, vm_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        state = self._load_state()
        record = dict(payload)
        state["registrations"][str(int(vm_id))] = record
        self._save_state(state)
        return record

    def _find_active_session(self, vm_id: int) -> dict[str, Any] | None:
        for session in self._pool_manager.list_active_sessions():
            try:
                if int(session.get("vmid") or session.get("vm_id") or 0) == int(vm_id):
                    return dict(session)
            except (TypeError, ValueError):
                continue
        return None

    def _find_pool_id(self, vm_id: int) -> str:
        active_session = self._find_active_session(vm_id)
        if active_session is not None:
            return str(active_session.get("pool_id") or "").strip()
        for pool in self._pool_manager.list_pools():
            pool_id = str(getattr(pool, "pool_id", "") or "").strip()
            if not pool_id:
                continue
            try:
                desktops = self._pool_manager.list_desktops(pool_id)
            except Exception:
                continue
            for desktop in desktops:
                try:
                    if int(desktop.get("vmid") or 0) == int(vm_id):
                        return pool_id
                except (AttributeError, TypeError, ValueError):
                    continue
        return ""

    def _config_links(self, vm_id: int) -> dict[str, str]:
        return {
            "register": self._REGISTER_ROUTE,
            "config": f"/api/v1/streams/{int(vm_id)}/config",
            "events": f"/api/v1/streams/{int(vm_id)}/events",
        }

    def _build_registration_payload(self, vm_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        pool_id = self._find_pool_id(vm_id)
        vm = self._find_vm(int(vm_id))
        vm_profile = self._build_vm_profile(vm) if vm is not None else {}
        existing = self._get_registration(vm_id) or {}
        return {
            "vm_id": int(vm_id),
            "pool_id": pool_id,
            "registered_at": existing.get("registered_at") or self._utcnow(),
            "updated_at": self._utcnow(),
            "stream_server_id": str(payload.get("stream_server_id") or existing.get("stream_server_id") or f"vm-{int(vm_id)}").strip(),
            "host": str(payload.get("host") or existing.get("host") or vm_profile.get("stream_host") or "").strip(),
            "port": int(payload.get("port") or existing.get("port") or vm_profile.get("beagle_stream_client_port") or 47984),
            "wireguard_active": self._coerce_bool(payload.get("wireguard_active"), default=self._coerce_bool(existing.get("wireguard_active"))),
            "capabilities": payload.get("capabilities") if isinstance(payload.get("capabilities"), dict) else dict(existing.get("capabilities") or {}),
            "server_version": str(payload.get("server_version") or existing.get("server_version") or "").strip(),
            "last_event": dict(existing.get("last_event") or {}),
            "links": self._config_links(vm_id),
        }

    def _resolve_effective_wireguard_state(self, query: dict[str, list[str]] | None, registration: dict[str, Any] | None) -> bool:
        query_payload = query or {}
        if "wireguard_active" in query_payload and query_payload.get("wireguard_active"):
            return self._coerce_bool(query_payload["wireguard_active"][0])
        if isinstance(registration, dict):
            return self._coerce_bool(registration.get("wireguard_active"))
        return False

    def _resolve_policy_for_vm(self, vm_id: int, *, wireguard_active: bool) -> tuple[str, bool, str, str]:
        pool_id = self._find_pool_id(vm_id)
        policy_target = pool_id or str(int(vm_id))
        policy = self._stream_policy.resolve_policy(policy_target)
        network_mode = str(getattr(policy, "network_mode", "vpn_preferred") or "vpn_preferred")
        allowed, reason = self._stream_policy.check_connection_allowed(
            policy_target,
            wireguard_active=bool(wireguard_active),
        )
        return pool_id, allowed, reason, network_mode

    @staticmethod
    def _is_session_connect_event(event_type: str) -> bool:
        normalized = str(event_type or "").strip().lower()
        return normalized in {"session.start", "session.resume", "connection.start"}

    def _resolve_event_wireguard_state(self, payload: dict[str, Any], registration: dict[str, Any]) -> bool:
        if "wireguard_active" in payload:
            return self._coerce_bool(payload.get("wireguard_active"))
        details = payload.get("details")
        if isinstance(details, dict) and "wireguard_active" in details:
            return self._coerce_bool(details.get("wireguard_active"))
        return self._coerce_bool(registration.get("wireguard_active"))

    @staticmethod
    def _resolve_direct_vm_id(pool_id: str) -> int:
        match = re.match(r"^vm-(?P<vm_id>\d+)$", str(pool_id or "").strip().lower())
        if match is None:
            return 0
        try:
            return int(match.group("vm_id"))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _normalize_wireguard_compat_payload(wg_peer_config: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(wg_peer_config, dict) or not wg_peer_config:
            return {}
        allowed_ips_value = wg_peer_config.get("allowed_ips")
        if isinstance(allowed_ips_value, list):
            allowed_ips = [str(item or "").strip() for item in allowed_ips_value if str(item or "").strip()]
        else:
            allowed_ips = [str(allowed_ips_value or "").strip()] if str(allowed_ips_value or "").strip() else []
        return {
            "public_key": str(wg_peer_config.get("public_key") or wg_peer_config.get("server_public_key") or "").strip(),
            "endpoint": str(wg_peer_config.get("endpoint") or wg_peer_config.get("server_endpoint") or "").strip(),
            "allowed_ips": ", ".join(allowed_ips),
        }

    @staticmethod
    def _resolve_allocate_actor_ids(user_id: str, device_id: str) -> tuple[str, str]:
        requested_user_id = str(user_id or "").strip()
        resolved_device_id = str(device_id or "").strip()
        if requested_user_id:
            return requested_user_id, requested_user_id
        if not resolved_device_id:
            return "", ""
        return "", f"device:{resolved_device_id}"

    def route_post(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
        endpoint_identity: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        payload = json_payload or {}
        if path == self._ALLOCATE_ROUTE:
            pool_id = str(payload.get("pool_id") or "").strip()
            requested_user_id = str(payload.get("user_id") or "").strip()
            identity = endpoint_identity if isinstance(endpoint_identity, dict) else {}
            requested_device_id = str(payload.get("device_id") or identity.get("endpoint_id") or "").strip()
            user_id, lease_user_id = self._resolve_allocate_actor_ids(requested_user_id, requested_device_id)
            device_id = requested_device_id or "unknown-device"
            if not pool_id:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "pool_id required"})
            if not requested_user_id and not requested_device_id:
                return self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "device_id required when user_id is empty"},
                )

            direct_vm_id = self._resolve_direct_vm_id(pool_id)
            lease = None
            if direct_vm_id > 0:
                vm_id = int(direct_vm_id)
                vm = self._find_vm(vm_id)
                if vm is None:
                    return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "allocated vm not found"})
                session_id = f"{pool_id}:{lease_user_id or device_id or 'device'}"
            else:
                try:
                    lease = self._pool_manager.allocate_desktop(pool_id, lease_user_id or user_id)
                except Exception as exc:
                    return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc) or "allocation failed"})

                vm_id = int(getattr(lease, "vm_id", 0) or 0)
                vm = self._find_vm(vm_id)
                if vm is None:
                    return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "allocated vm not found"})
                session_id = str(getattr(lease, "session_id", "") or "")

            policy = self._stream_policy.resolve_policy(pool_id)
            network_mode = str(getattr(policy, "network_mode", "vpn_preferred") or "vpn_preferred")
            wg_peer_config = payload.get("wg_peer_config") if isinstance(payload.get("wg_peer_config"), dict) else {}
            if not wg_peer_config and self._build_wireguard_peer_config is not None:
                try:
                    wg_peer_config = self._build_wireguard_peer_config(
                        device_id,
                        pool_id,
                        lease_user_id or user_id,
                    ) or {}
                except Exception:
                    wg_peer_config = {}

            if network_mode == "vpn_required" and not isinstance(wg_peer_config, dict):
                wg_peer_config = {}
            if network_mode == "vpn_required" and not wg_peer_config:
                return self._json(
                    HTTPStatus.FORBIDDEN,
                    {"ok": False, "error": "vpn_required: wireguard peer config unavailable"},
                )

            pairing_token = ""
            if self._issue_pairing_token is not None:
                try:
                    pairing_token = str(
                        self._issue_pairing_token(vm_id, lease_user_id or user_id, device_id) or ""
                    ).strip()
                except Exception:
                    pairing_token = ""

            vm_profile = self._build_vm_profile(vm)
            local_stream_host = str(vm_profile.get("beagle_stream_client_local_host") or "").strip()
            public_stream_host = str(vm_profile.get("stream_host") or "").strip()
            allocation_host = local_stream_host if isinstance(wg_peer_config, dict) and wg_peer_config and local_stream_host else public_stream_host
            allocation = {
                "pool_id": pool_id,
                "user_id": user_id,
                "lease_user_id": lease_user_id or user_id,
                "device_id": device_id,
                "vm_id": vm_id,
                "session_id": session_id,
                "host_ip": allocation_host,
                "port": int(vm_profile.get("beagle_stream_client_port") or 47984),
                "token": pairing_token,
                "network_mode": network_mode,
                "wg_peer_config": wg_peer_config if isinstance(wg_peer_config, dict) else {},
                "links": self._config_links(vm_id),
            }
            compatibility_wg_peer_config = self._normalize_wireguard_compat_payload(allocation["wg_peer_config"])
            self._safe_audit(
                "stream.client.allocate",
                "success",
                vm_id=vm_id,
                pool_id=pool_id,
                user_id=user_id,
                lease_user_id=lease_user_id or user_id,
                device_id=device_id,
                network_mode=network_mode,
                wireguard_profile=bool(allocation["wg_peer_config"]),
            )
            response_payload = {"ok": True, **self._envelope(allocation=allocation)}
            response_payload.update(
                {
                    "host_ip": allocation["host_ip"],
                    "port": allocation["port"],
                    "token": allocation["token"],
                    "network_mode": allocation["network_mode"],
                    "wg_peer_config": compatibility_wg_peer_config,
                    "links": allocation["links"],
                }
            )
            return self._json(HTTPStatus.OK, response_payload)

        if path == self._REGISTER_ROUTE:
            try:
                vm_id = int(payload.get("vm_id") or 0)
            except (TypeError, ValueError):
                vm_id = 0
            if vm_id <= 0:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "vm_id required"})
            vm = self._find_vm(vm_id)
            if vm is None:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            registration = self._store_registration(vm_id, self._build_registration_payload(vm_id, payload))
            _pool_id, allowed, reason, network_mode = self._resolve_policy_for_vm(
                vm_id,
                wireguard_active=self._coerce_bool(registration.get("wireguard_active")),
            )
            if not allowed:
                self._safe_audit(
                    "stream.server.register",
                    "forbidden",
                    vm_id=vm_id,
                    pool_id=registration.get("pool_id", ""),
                    stream_server_id=registration.get("stream_server_id", ""),
                    wireguard_active=bool(registration.get("wireguard_active")),
                    network_mode=network_mode,
                    reason=reason,
                )
                return self._json(
                    HTTPStatus.FORBIDDEN,
                    {
                        "ok": False,
                        "error": reason,
                        **self._envelope(registration=registration),
                    },
                )
            self._safe_audit(
                "stream.server.register",
                "success",
                vm_id=vm_id,
                pool_id=registration.get("pool_id", ""),
                stream_server_id=registration.get("stream_server_id", ""),
                wireguard_active=bool(registration.get("wireguard_active")),
            )
            return self._json(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    **self._envelope(registration=registration),
                },
            )

        match = self._EVENTS_ROUTE.match(str(path or ""))
        if match is None:
            return None
        vm_id = int(match.group("vm_id"))
        vm = self._find_vm(vm_id)
        if vm is None:
            return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
        event_type = str(payload.get("event_type") or "").strip().lower()
        if not event_type:
            return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "event_type required"})
        registration = self._build_registration_payload(vm_id, {})
        if self._is_session_connect_event(event_type):
            wireguard_active = self._resolve_event_wireguard_state(payload, registration)
            _pool_id, allowed, reason, network_mode = self._resolve_policy_for_vm(
                vm_id,
                wireguard_active=wireguard_active,
            )
            if not allowed:
                self._safe_audit(
                    "stream.session.start",
                    "forbidden",
                    vm_id=vm_id,
                    pool_id=registration.get("pool_id", ""),
                    details=dict(payload.get("details") or {}),
                    stream_server_id=registration.get("stream_server_id", ""),
                    network_mode=network_mode,
                    wireguard_active=wireguard_active,
                    reason=reason,
                )
                return self._json(
                    HTTPStatus.FORBIDDEN,
                    {
                        "ok": False,
                        "error": reason,
                        **self._envelope(vm_id=vm_id),
                    },
                )
        registration["last_event"] = {
            "event_type": event_type,
            "recorded_at": self._utcnow(),
            "details": dict(payload.get("details") or {}),
        }
        self._store_registration(vm_id, registration)
        audit_name = f"stream.{event_type}" if re.match(r"^[a-z0-9_.-]+$", event_type) else "stream.session.event"
        self._safe_audit(
            audit_name,
            str(payload.get("outcome") or "success").strip() or "success",
            vm_id=vm_id,
            pool_id=registration.get("pool_id", ""),
            details=dict(payload.get("details") or {}),
            stream_server_id=registration.get("stream_server_id", ""),
        )
        return self._json(
            HTTPStatus.OK,
            {
                "ok": True,
                **self._envelope(vm_id=vm_id, event=registration["last_event"]),
            },
        )

    def route_get(
        self,
        path: str,
        *,
        query: dict[str, list[str]] | None = None,
        endpoint_identity: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        del endpoint_identity
        match = self._CONFIG_ROUTE.match(str(path or ""))
        if match is None:
            return None
        vm_id = int(match.group("vm_id"))
        vm = self._find_vm(vm_id)
        if vm is None:
            return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
        pool_id = self._find_pool_id(vm_id)
        policy_target = pool_id or str(vm_id)
        policy = self._stream_policy.resolve_policy(policy_target)
        registration = self._get_registration(vm_id)
        wireguard_active = self._resolve_effective_wireguard_state(query, registration)
        allowed, reason = self._stream_policy.check_connection_allowed(
            policy_target,
            wireguard_active=wireguard_active,
        )
        active_session = self._find_active_session(vm_id)
        vm_profile = self._build_vm_profile(vm)
        config_payload = {
            "vm_id": vm_id,
            "pool_id": pool_id,
            "current_node": str((active_session or {}).get("current_node") or getattr(vm, "node", "") or "").strip(),
            "stream_host": str(vm_profile.get("stream_host") or "").strip(),
            "port": int(vm_profile.get("beagle_stream_client_port") or registration.get("port") if isinstance(registration, dict) else 47984),
            "policy": {
                "policy_id": str(getattr(policy, "policy_id", "") or ""),
                "name": str(getattr(policy, "name", "") or ""),
                "max_fps": int(getattr(policy, "max_fps", 60) or 60),
                "max_bitrate_mbps": int(getattr(policy, "max_bitrate_mbps", 20) or 20),
                "resolution": str(getattr(policy, "resolution", "1920x1080") or "1920x1080"),
                "codec": str(getattr(policy, "codec", "h264") or "h264"),
                "clipboard_redirect": bool(getattr(policy, "clipboard_redirect", True)),
                "audio_redirect": bool(getattr(policy, "audio_redirect", True)),
                "gamepad_redirect": bool(getattr(policy, "gamepad_redirect", True)),
                "usb_redirect": bool(getattr(policy, "usb_redirect", False)),
                "network_mode": str(getattr(policy, "network_mode", "vpn_preferred") or "vpn_preferred"),
            },
            "wireguard_active": wireguard_active,
            "connection_allowed": bool(allowed),
            "connection_reason": reason,
            "registration": registration,
            "session": active_session,
            "links": self._config_links(vm_id),
        }
        if not allowed:
            return self._json(HTTPStatus.FORBIDDEN, {"ok": False, "error": reason, **self._envelope(config=config_payload)})
        return self._json(HTTPStatus.OK, {"ok": True, **self._envelope(config=config_payload)})
