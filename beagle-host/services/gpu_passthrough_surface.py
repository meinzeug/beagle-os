from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable

_ROUTE_RE = re.compile(
    r"^/api/v1/virtualization/gpus/(?P<pci>[^/]+)/(?P<action>assign|release)$"
)


class GpuPassthroughSurfaceService:
    """HTTP surface for GPU passthrough operations.

    Handles:
      POST /api/v1/virtualization/gpus/<pci_address>/assign
      POST /api/v1/virtualization/gpus/<pci_address>/release
    Both require JSON body {"vmid": <int>}.
    """

    def __init__(
        self,
        *,
        assign_gpu: Callable[[str, int], dict[str, Any]],
        release_gpu: Callable[[str, int], dict[str, Any]],
        service_name: str,
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._assign_gpu = assign_gpu
        self._release_gpu = release_gpu
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

    @staticmethod
    def handles_path(path: str) -> bool:
        return bool(_ROUTE_RE.match(path))

    def route_post(
        self,
        path: str,
        json_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        m = _ROUTE_RE.match(path)
        if not m:
            return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

        pci_addr = str(m.group("pci") or "").strip()
        action = str(m.group("action") or "").strip()

        body = json_payload if isinstance(json_payload, dict) else {}
        raw_vmid = body.get("vmid")
        if raw_vmid is None or not str(int(raw_vmid if str(raw_vmid).lstrip("-").isdigit() else -1)).lstrip("-").isdigit():
            return self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "missing or invalid 'vmid' in request body"},
            )

        try:
            vmid = int(raw_vmid)
        except (TypeError, ValueError):
            return self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "vmid must be an integer"},
            )

        if vmid <= 0:
            return self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "vmid must be a positive integer"},
            )

        if action == "assign":
            result = self._assign_gpu(pci_addr, vmid)
        elif action == "release":
            result = self._release_gpu(pci_addr, vmid)
        else:
            return self._json_response(
                HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown action"}
            )

        http_status = HTTPStatus.OK if result.get("ok") else HTTPStatus.UNPROCESSABLE_ENTITY
        return self._json_response(http_status, self._envelope(**result))
