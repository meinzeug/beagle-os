"""HTTP surface for NVIDIA vGPU (mdev) and Intel SR-IOV operations.

Routes handled (all require authentication):
  GET  /api/v1/virtualization/mdev/types           – list mdev types
  GET  /api/v1/virtualization/mdev/instances       – list active mdev instances
  POST /api/v1/virtualization/mdev/create          – create mdev instance
       body: {gpu_pci, type_id}
  POST /api/v1/virtualization/mdev/<uuid>/delete   – delete mdev instance
  POST /api/v1/virtualization/mdev/<uuid>/assign   – assign mdev to VM
       body: {vmid}
  POST /api/v1/virtualization/mdev/<uuid>/release  – release mdev from VM
       body: {vmid}

  GET  /api/v1/virtualization/sriov                – list SR-IOV devices
  POST /api/v1/virtualization/sriov/<pci>/set-vfs  – set VF count
       body: {count}
  GET  /api/v1/virtualization/sriov/<pci>/vfs      – list VFs for a device
"""
from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable

_UUID_RE_STR = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_MDEV_ASSIGN_RE = re.compile(
    r"^/api/v1/virtualization/mdev/(?P<uuid>" + _UUID_RE_STR + r")/(?P<action>assign|release|delete)$",
    re.IGNORECASE,
)
_SRIOV_VFS_RE = re.compile(
    r"^/api/v1/virtualization/sriov/(?P<pci>[^/]+)/vfs$"
)
_SRIOV_SET_RE = re.compile(
    r"^/api/v1/virtualization/sriov/(?P<pci>[^/]+)/set-vfs$"
)


class VgpuSurfaceService:
    def __init__(
        self,
        *,
        list_mdev_types: Callable[[str | None], list[dict[str, Any]]],
        list_mdev_instances: Callable[[], list[dict[str, Any]]],
        create_mdev_instance: Callable[[str, str], dict[str, Any]],
        delete_mdev_instance: Callable[[str], dict[str, Any]],
        assign_mdev_to_vm: Callable[[str, int], dict[str, Any]],
        release_mdev_from_vm: Callable[[str, int], dict[str, Any]],
        list_sriov_devices: Callable[[], list[dict[str, Any]]],
        set_vf_count: Callable[[str, int], dict[str, Any]],
        list_vfs: Callable[[str], list[dict[str, Any]]],
        service_name: str,
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._list_mdev_types = list_mdev_types
        self._list_mdev_instances = list_mdev_instances
        self._create_mdev_instance = create_mdev_instance
        self._delete_mdev_instance = delete_mdev_instance
        self._assign_mdev_to_vm = assign_mdev_to_vm
        self._release_mdev_from_vm = release_mdev_from_vm
        self._list_sriov_devices = list_sriov_devices
        self._set_vf_count = set_vf_count
        self._list_vfs = list_vfs
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
    def handles_path_get(path: str) -> bool:
        return path in (
            "/api/v1/virtualization/mdev/types",
            "/api/v1/virtualization/mdev/instances",
            "/api/v1/virtualization/sriov",
        ) or bool(_SRIOV_VFS_RE.match(path))

    @staticmethod
    def handles_path_post(path: str) -> bool:
        return path == "/api/v1/virtualization/mdev/create" or bool(
            _MDEV_ASSIGN_RE.match(path)
        ) or bool(_SRIOV_SET_RE.match(path))

    # ------------------------------------------------------------------
    # GET routes
    # ------------------------------------------------------------------

    def route_get(self, path: str) -> dict[str, Any] | None:
        if path == "/api/v1/virtualization/mdev/types":
            try:
                types = self._list_mdev_types(None)
            except Exception as exc:
                types = []
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(ok=True, mdev_types=types, count=len(types)),
            )

        if path == "/api/v1/virtualization/mdev/instances":
            try:
                instances = self._list_mdev_instances()
            except Exception:
                instances = []
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(ok=True, mdev_instances=instances, count=len(instances)),
            )

        if path == "/api/v1/virtualization/sriov":
            try:
                devices = self._list_sriov_devices()
            except Exception:
                devices = []
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(ok=True, sriov_devices=devices, count=len(devices)),
            )

        m = _SRIOV_VFS_RE.match(path)
        if m:
            pci = str(m.group("pci") or "")
            try:
                vfs = self._list_vfs(pci)
            except Exception:
                vfs = []
            return self._json_response(
                HTTPStatus.OK,
                self._envelope(ok=True, pci=pci, vfs=vfs, count=len(vfs)),
            )

        return None

    # ------------------------------------------------------------------
    # POST routes
    # ------------------------------------------------------------------

    def route_post(self, path: str, json_payload: dict[str, Any] | None) -> dict[str, Any]:
        body = json_payload if isinstance(json_payload, dict) else {}

        if path == "/api/v1/virtualization/mdev/create":
            gpu_pci = str(body.get("gpu_pci") or "").strip()
            type_id = str(body.get("type_id") or "").strip()
            if not gpu_pci or not type_id:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "gpu_pci and type_id are required"},
                )
            result = self._create_mdev_instance(gpu_pci, type_id)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.UNPROCESSABLE_ENTITY
            return self._json_response(status, self._envelope(**result))

        m = _MDEV_ASSIGN_RE.match(path)
        if m:
            uid = str(m.group("uuid") or "").lower()
            action = str(m.group("action") or "")

            if action == "delete":
                result = self._delete_mdev_instance(uid)
                status = HTTPStatus.OK if result.get("ok") else HTTPStatus.UNPROCESSABLE_ENTITY
                return self._json_response(status, self._envelope(**result))

            raw_vmid = body.get("vmid")
            if raw_vmid is None:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "vmid is required"},
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
                result = self._assign_mdev_to_vm(uid, vmid)
            elif action == "release":
                result = self._release_mdev_from_vm(uid, vmid)
            else:
                return self._json_response(
                    HTTPStatus.NOT_FOUND, {"ok": False, "error": "unknown action"}
                )
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.UNPROCESSABLE_ENTITY
            return self._json_response(status, self._envelope(**result))

        m = _SRIOV_SET_RE.match(path)
        if m:
            pci = str(m.group("pci") or "").strip()
            raw_count = body.get("count")
            if raw_count is None:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "count is required"},
                )
            try:
                count = int(raw_count)
            except (TypeError, ValueError):
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "count must be an integer"},
                )
            result = self._set_vf_count(pci, count)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.UNPROCESSABLE_ENTITY
            return self._json_response(status, self._envelope(**result))

        return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
