from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable


class AdminHttpSurfaceService:
    def __init__(
        self,
        *,
        create_provisioned_vm: Callable[[dict[str, Any]], dict[str, Any]],
        create_ubuntu_beagle_vm: Callable[[dict[str, Any]], dict[str, Any]],
        delete_provisioned_vm: Callable[[int], dict[str, Any]],
        delete_policy: Callable[[str], bool],
        queue_bulk_actions: Callable[[list[int], str, str], list[dict[str, Any]]],
        save_policy: Callable[..., dict[str, Any]],
        service_name: str,
        update_ubuntu_beagle_vm: Callable[[int, dict[str, Any]], dict[str, Any]],
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._create_provisioned_vm = create_provisioned_vm
        self._create_ubuntu_beagle_vm = create_ubuntu_beagle_vm
        self._delete_provisioned_vm = delete_provisioned_vm
        self._delete_policy = delete_policy
        self._queue_bulk_actions = queue_bulk_actions
        self._save_policy = save_policy
        self._service_name = str(service_name or "beagle-control-plane")
        self._update_ubuntu_beagle_vm = update_ubuntu_beagle_vm
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
    def _provisioning_update_match(path: str) -> re.Match[str] | None:
        return re.match(r"^/api/v1/provisioning/vms/(?P<vmid>\d+)$", path)

    @staticmethod
    def handles_post(path: str) -> bool:
        return path in {
            "/api/v1/policies",
            "/api/v1/actions/bulk",
            "/api/v1/ubuntu-beagle-vms",
            "/api/v1/provisioning/vms",
        }

    @staticmethod
    def handles_put(path: str) -> bool:
        return AdminHttpSurfaceService._provisioning_update_match(path) is not None or path.startswith("/api/v1/policies/")

    @staticmethod
    def handles_delete(path: str) -> bool:
        return path.startswith("/api/v1/policies/") or AdminHttpSurfaceService._provisioning_update_match(path) is not None

    @staticmethod
    def requires_json_body(_path: str) -> bool:
        return True

    @staticmethod
    def read_error_response(method: str, path: str, exc: Exception) -> dict[str, Any]:
        if method == "POST" and path == "/api/v1/policies":
            error = f"invalid policy: {exc}"
        elif method == "POST" and path == "/api/v1/actions/bulk":
            error = f"invalid bulk action: {exc}"
        elif method == "POST" and path == "/api/v1/ubuntu-beagle-vms":
            error = f"failed to create ubuntu beagle vm: {exc}"
        elif method == "POST" and path == "/api/v1/provisioning/vms":
            error = f"failed to provision vm: {exc}"
        elif method == "PUT" and AdminHttpSurfaceService._provisioning_update_match(path) is not None:
            error = f"failed to update provisioned vm: {exc}"
        elif method == "PUT" and path.startswith("/api/v1/policies/"):
            error = f"invalid policy: {exc}"
        else:
            error = f"invalid payload: {exc}"
        return AdminHttpSurfaceService._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": error})

    def route_post(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None,
        requester_identity: str,
    ) -> dict[str, Any]:
        payload = json_payload if isinstance(json_payload, dict) else {}

        if path == "/api/v1/policies":
            try:
                policy = self._save_policy(payload, policy_name=None)
            except Exception as exc:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid policy: {exc}"})
            return self._json_response(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    **self._envelope(policy=policy),
                },
            )

        if path == "/api/v1/actions/bulk":
            try:
                action_name = str(payload.get("action", "")).strip().lower()
                vmid_values = payload.get("vmids", [])
                if action_name not in {
                    "healthcheck",
                    "recheckin",
                    "restart-session",
                    "restart-runtime",
                    "support-bundle",
                    "os-update-scan",
                    "os-update-download",
                }:
                    raise ValueError("unsupported action")
                if not isinstance(vmid_values, list) or not vmid_values:
                    raise ValueError("missing vmids")
                vmids = [int(item) for item in vmid_values]
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": f"invalid bulk action: {exc}"},
                )
            queued = self._queue_bulk_actions(vmids, action_name, requester_identity)
            return self._json_response(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    **self._envelope(
                        queued_actions=queued,
                        queued_count=len(queued),
                    ),
                },
            )

        if path == "/api/v1/ubuntu-beagle-vms":
            try:
                result = self._create_ubuntu_beagle_vm(payload)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": f"failed to create ubuntu beagle vm: {exc}"},
                )
            return self._json_response(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    **self._envelope(ubuntu_beagle_vm=result),
                },
            )

        if path == "/api/v1/provisioning/vms":
            try:
                result = self._create_provisioned_vm(payload)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": f"failed to provision vm: {exc}"},
                )
            return self._json_response(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    **self._envelope(provisioned_vm=result),
                },
            )

        return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def route_put(self, path: str, *, json_payload: dict[str, Any] | None) -> dict[str, Any]:
        payload = json_payload if isinstance(json_payload, dict) else {}

        match = self._provisioning_update_match(path)
        if match is not None:
            try:
                result = self._update_ubuntu_beagle_vm(int(match.group("vmid")), payload)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": f"failed to update provisioned vm: {exc}"},
                )
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(provisioned_vm=result),
                },
            )

        if path.startswith("/api/v1/policies/"):
            policy_name = path.rsplit("/", 1)[-1]
            try:
                policy = self._save_policy(payload, policy_name=policy_name)
            except Exception as exc:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid policy: {exc}"})
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(policy=policy),
                },
            )

        return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def route_delete(self, path: str) -> dict[str, Any]:
        match = self._provisioning_update_match(path)
        if match is not None:
            vmid = int(match.group("vmid"))
            try:
                result = self._delete_provisioned_vm(vmid)
            except ValueError as exc:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": str(exc)})
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": f"failed to delete provisioned vm: {exc}"},
                )
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(provisioned_vm=result),
                },
            )

        if not path.startswith("/api/v1/policies/"):
            return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
        policy_name = path.rsplit("/", 1)[-1]
        if not self._delete_policy(policy_name):
            return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "policy not found"})
        return self._json_response(
            HTTPStatus.OK,
            {
                "ok": True,
                **self._envelope(deleted=policy_name),
            },
        )
