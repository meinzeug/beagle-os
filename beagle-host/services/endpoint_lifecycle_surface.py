from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable


class EndpointLifecycleSurfaceService:
    def __init__(
        self,
        *,
        enroll_endpoint: Callable[[dict[str, Any]], dict[str, Any]],
        register_wireguard_peer: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        service_name: str,
        store_endpoint_report: Callable[[str, int, dict[str, Any]], Path],
        summarize_endpoint_report: Callable[[dict[str, Any]], dict[str, Any]],
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._enroll_endpoint = enroll_endpoint
        self._register_wireguard_peer = register_wireguard_peer
        self._service_name = str(service_name or "beagle-control-plane")
        self._store_endpoint_report = store_endpoint_report
        self._summarize_endpoint_report = summarize_endpoint_report
        self._utcnow = utcnow
        self._version = str(version or "")

    @staticmethod
    def _json_response(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    @staticmethod
    def handles_post(path: str) -> bool:
        return path in {
            "/api/v1/endpoints/enroll",
            "/api/v1/endpoints/check-in",
            "/api/v1/vpn/register",
        }

    @staticmethod
    def requires_endpoint_auth(path: str) -> bool:
        return path in {"/api/v1/endpoints/check-in", "/api/v1/vpn/register"}

    @staticmethod
    def requires_json_body(_path: str) -> bool:
        return True

    def route_post(
        self,
        path: str,
        *,
        endpoint_identity: dict[str, Any] | None,
        json_payload: dict[str, Any] | None,
        remote_addr: str,
    ) -> dict[str, Any]:
        payload = dict(json_payload) if isinstance(json_payload, dict) else {}

        if path == "/api/v1/endpoints/enroll":
            try:
                response_payload = self._enroll_endpoint(payload)
            except Exception as exc:
                if isinstance(exc, ValueError):
                    return self._json_response(
                        HTTPStatus.BAD_REQUEST,
                        {"ok": False, "error": f"invalid payload: {exc}"},
                    )
                if isinstance(exc, PermissionError):
                    return self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": str(exc)})
                if isinstance(exc, LookupError):
                    return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": str(exc)})
                raise
            return self._json_response(HTTPStatus.CREATED, response_payload)

        if path == "/api/v1/endpoints/check-in":
            identity = endpoint_identity or {}
            try:
                vmid = int(payload.get("vmid"))
                node = str(payload.get("node", "")).strip()
                if not node:
                    raise ValueError("missing node")
            except Exception as exc:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
            if identity and (int(identity.get("vmid", -1)) != vmid or str(identity.get("node", "")).strip() != node):
                return self._json_response(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})

            payload["vmid"] = vmid
            payload["node"] = node
            payload["received_at"] = self._utcnow()
            payload["remote_addr"] = remote_addr
            path_obj = self._store_endpoint_report(node, vmid, payload)
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": self._service_name,
                    "version": self._version,
                    "stored_at": str(path_obj),
                    "endpoint": self._summarize_endpoint_report(payload),
                },
            )

        if path == "/api/v1/vpn/register":
            identity = endpoint_identity or {}
            try:
                response_payload = self._register_wireguard_peer(identity, payload)
            except Exception as exc:
                if isinstance(exc, ValueError):
                    return self._json_response(
                        HTTPStatus.BAD_REQUEST,
                        {"ok": False, "error": f"invalid payload: {exc}"},
                    )
                if isinstance(exc, PermissionError):
                    return self._json_response(HTTPStatus.FORBIDDEN, {"ok": False, "error": str(exc)})
                raise
            return self._json_response(HTTPStatus.OK, response_payload)

        return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
