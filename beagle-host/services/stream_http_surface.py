from __future__ import annotations

import json
import re
import threading
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable


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
        try:
            payload = dict(details)
            payload.setdefault("username", self._requester_identity())
            self._audit_event(event_type, outcome, **payload)
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
            if self._state_file.exists():
                try:
                    payload = json.loads(self._state_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    payload = {}
            else:
                payload = {}
            registrations = payload.get("registrations")
            if not isinstance(registrations, dict):
                registrations = {}
            return {"registrations": registrations}

    def _save_state(self, state: dict[str, Any]) -> None:
        with self._lock:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

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
            "port": int(payload.get("port") or existing.get("port") or vm_profile.get("moonlight_port") or 47984),
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

    def route_post(self, path: str, *, json_payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
        payload = json_payload or {}
        if path == self._ALLOCATE_ROUTE:
            pool_id = str(payload.get("pool_id") or "").strip()
            user_id = str(payload.get("user_id") or "").strip()
            device_id = str(payload.get("device_id") or "").strip() or "unknown-device"
            if not pool_id or not user_id:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "pool_id and user_id required"})

            try:
                lease = self._pool_manager.allocate_desktop(pool_id, user_id)
            except Exception as exc:
                return self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc) or "allocation failed"})

            vm_id = int(getattr(lease, "vm_id", 0) or 0)
            vm = self._find_vm(vm_id)
            if vm is None:
                return self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "allocated vm not found"})

            policy = self._stream_policy.resolve_policy(pool_id)
            network_mode = str(getattr(policy, "network_mode", "vpn_preferred") or "vpn_preferred")
            wg_peer_config = payload.get("wg_peer_config") if isinstance(payload.get("wg_peer_config"), dict) else {}
            if not wg_peer_config and self._build_wireguard_peer_config is not None:
                try:
                    wg_peer_config = self._build_wireguard_peer_config(device_id, pool_id, user_id) or {}
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
                    pairing_token = str(self._issue_pairing_token(vm_id, user_id, device_id) or "").strip()
                except Exception:
                    pairing_token = ""

            vm_profile = self._build_vm_profile(vm)
            allocation = {
                "pool_id": pool_id,
                "user_id": user_id,
                "device_id": device_id,
                "vm_id": vm_id,
                "session_id": str(getattr(lease, "session_id", "") or ""),
                "host_ip": str(vm_profile.get("stream_host") or "").strip(),
                "port": int(vm_profile.get("moonlight_port") or 47984),
                "token": pairing_token,
                "network_mode": network_mode,
                "wg_peer_config": wg_peer_config if isinstance(wg_peer_config, dict) else {},
                "links": self._config_links(vm_id),
            }
            self._safe_audit(
                "stream.client.allocate",
                "success",
                vm_id=vm_id,
                pool_id=pool_id,
                user_id=user_id,
                device_id=device_id,
                network_mode=network_mode,
                wireguard_profile=bool(allocation["wg_peer_config"]),
            )
            return self._json(HTTPStatus.OK, {"ok": True, **self._envelope(allocation=allocation)})

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

    def route_get(self, path: str, *, query: dict[str, list[str]] | None = None) -> dict[str, Any] | None:
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
            "port": int(vm_profile.get("moonlight_port") or registration.get("port") if isinstance(registration, dict) else 47984),
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
