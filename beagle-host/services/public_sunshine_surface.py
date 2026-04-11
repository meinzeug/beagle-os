from __future__ import annotations

from http import HTTPStatus
from typing import Any, Callable


class PublicSunshineSurfaceService:
    def __init__(
        self,
        *,
        proxy_sunshine_request: Callable[..., tuple[int, dict[str, str], bytes]],
        resolve_ticket_vm: Callable[[str], tuple[Any | None, str]],
    ) -> None:
        self._proxy_sunshine_request = proxy_sunshine_request
        self._resolve_ticket_vm = resolve_ticket_vm

    @staticmethod
    def _json_response(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    @staticmethod
    def _proxy_response(status: int, headers: dict[str, str], body: bytes) -> dict[str, Any]:
        return {
            "kind": "proxy",
            "status": int(status),
            "headers": dict(headers),
            "body": body,
        }

    def route_request(
        self,
        path: str,
        *,
        query: str,
        method: str,
        body: bytes | None,
        request_headers: dict[str, str],
    ) -> dict[str, Any] | None:
        if not str(path).startswith("/api/v1/public/sunshine/"):
            return None
        vm, relative = self._resolve_ticket_vm(path)
        if vm is None:
            return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "sunshine ticket not found"})
        try:
            status_code, headers, response_body = self._proxy_sunshine_request(
                vm,
                request_path=relative,
                query=query,
                method=method,
                body=body,
                request_headers=request_headers,
            )
        except Exception as exc:
            return self._json_response(HTTPStatus.BAD_GATEWAY, {"ok": False, "error": f"sunshine proxy failed: {exc}"})
        return self._proxy_response(status_code, headers, response_body)
