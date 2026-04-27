from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable


class VmMutationSurfaceService:
    def __init__(
        self,
        *,
        attach_usb_to_guest: Callable[[Any, str], dict[str, Any]],
        build_vm_usb_state: Callable[[Any], dict[str, Any]],
        find_vm: Callable[[int], Any | None],
        invalidate_vm_cache: Callable[[int | None, str], None],
        issue_sunshine_access_token: Callable[[Any], tuple[str, dict[str, Any]]],
        migrate_vm: Callable[[int, str, bool, bool, str], dict[str, Any]],
        queue_vm_action: Callable[[Any, str, str, dict[str, Any] | None], dict[str, Any]],
        reboot_vm: Callable[[int], str],
        service_name: str,
        start_vm: Callable[[int], str],
        start_installer_prep: Callable[[Any], dict[str, Any]],
        stop_vm: Callable[[int], str],
        summarize_action_result: Callable[[dict[str, Any] | None], dict[str, Any]],
        sunshine_proxy_ticket_url: Callable[[str], str],
        usb_action_wait_seconds: float,
        utcnow: Callable[[], str],
        version: str,
        wait_for_action_result: Callable[[str, int, str], dict[str, Any] | None],
        detach_usb_from_guest: Callable[[Any, int | None, str], dict[str, Any]],
        enqueue_job: Callable[..., Any] | None = None,
        delete_vm_snapshot: Callable[[int, str], str] | None = None,
        reset_vm_to_snapshot: Callable[[int, str], str] | None = None,
        clone_vm: Callable[[int, int, str], str] | None = None,
    ) -> None:
        self._attach_usb_to_guest = attach_usb_to_guest
        self._build_vm_usb_state = build_vm_usb_state
        self._find_vm = find_vm
        self._invalidate_vm_cache = invalidate_vm_cache
        self._issue_sunshine_access_token = issue_sunshine_access_token
        self._migrate_vm = migrate_vm
        self._queue_vm_action = queue_vm_action
        self._reboot_vm = reboot_vm
        self._service_name = str(service_name or "beagle-control-plane")
        self._start_vm = start_vm
        self._start_installer_prep = start_installer_prep
        self._stop_vm = stop_vm
        self._summarize_action_result = summarize_action_result
        self._sunshine_proxy_ticket_url = sunshine_proxy_ticket_url
        self._usb_action_wait_seconds = float(usb_action_wait_seconds)
        self._utcnow = utcnow
        self._version = str(version or "")
        self._wait_for_action_result = wait_for_action_result
        self._detach_usb_from_guest = detach_usb_from_guest
        self._enqueue_job = enqueue_job
        self._delete_vm_snapshot = delete_vm_snapshot
        self._reset_vm_to_snapshot = reset_vm_to_snapshot
        self._clone_vm = clone_vm

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
    def _update_match(path: str) -> re.Match[str] | None:
        return re.match(r"^/api/v1/vms/(?P<vmid>\d+)/update/(?P<operation>scan|download|apply|rollback)$", path)

    @staticmethod
    def handles_path(path: str) -> bool:
        return bool(
            VmMutationSurfaceService._update_match(path)
            or (path.startswith("/api/v1/vms/") and path.endswith("/installer-prep"))
            or (path.startswith("/api/v1/vms/") and path.endswith("/actions"))
            or (path.startswith("/api/v1/vms/") and path.endswith("/usb/refresh"))
            or (path.startswith("/api/v1/vms/") and path.endswith("/usb/attach"))
            or (path.startswith("/api/v1/vms/") and path.endswith("/usb/detach"))
            or (path.startswith("/api/v1/vms/") and path.endswith("/migrate"))
            or (path.startswith("/api/v1/vms/") and path.endswith("/clone"))
            or (path.startswith("/api/v1/vms/") and path.endswith("/snapshot"))
            or (path.startswith("/api/v1/vms/") and path.endswith("/snapshot/revert"))
            or (path.startswith("/api/v1/vms/") and path.endswith("/sunshine-access"))
            or (path.startswith("/api/v1/virtualization/vms/") and path.endswith("/power"))
        )

    @staticmethod
    def handles_delete(path: str) -> bool:
        return bool(path.startswith("/api/v1/vms/") and path.endswith("/snapshot"))

    @staticmethod
    def requires_json_body(path: str) -> bool:
        return (
            (path.startswith("/api/v1/vms/") and path.endswith("/actions"))
            or (path.startswith("/api/v1/vms/") and path.endswith("/usb/attach"))
            or (path.startswith("/api/v1/vms/") and path.endswith("/usb/detach"))
            or (path.startswith("/api/v1/vms/") and path.endswith("/migrate"))
            or (path.startswith("/api/v1/vms/") and path.endswith("/clone"))
            or (path.startswith("/api/v1/vms/") and path.endswith("/snapshot/revert"))
            or (path.startswith("/api/v1/virtualization/vms/") and path.endswith("/power"))
        )

    @staticmethod
    def accepts_optional_json_body(path: str) -> bool:
        return VmMutationSurfaceService._update_match(path) is not None

    def _vm_from_segment(self, path: str, index_from_end: int) -> tuple[Any | None, str | None]:
        vmid_text = path.split("/")[index_from_end]
        if not vmid_text.isdigit():
            return None, "invalid vmid"
        vm = self._find_vm(int(vmid_text))
        if vm is None:
            return None, "vm not found"
        return vm, None

    def route_post(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None,
        requester_identity: str,
        client_idempotency_key: str = "",
    ) -> dict[str, Any]:
        if path.startswith("/api/v1/vms/") and path.endswith("/snapshot"):
            vm, error = self._vm_from_segment(path, -2)
            if vm is None:
                status = HTTPStatus.BAD_REQUEST if error == "invalid vmid" else HTTPStatus.NOT_FOUND
                return self._json_response(status, {"ok": False, "error": error})
            payload = json_payload if isinstance(json_payload, dict) else {}
            snap_name = str(payload.get("name") or "").strip() or f"snap-{self._utcnow()[:10]}"
            if self._enqueue_job is not None:
                ikey = client_idempotency_key or f"vm.snapshot.{vm.vmid}.{snap_name}"
                try:
                    job = self._enqueue_job(
                        "vm.snapshot",
                        {"vmid": int(vm.vmid), "node": str(vm.node), "name": snap_name},
                        idempotency_key=ikey,
                        owner=requester_identity,
                    )
                    return self._json_response(
                        HTTPStatus.ACCEPTED,
                        {
                            "ok": True,
                            "job_id": str(job.job_id),
                            "vmid": int(vm.vmid),
                            "name": snap_name,
                        },
                    )
                except Exception as exc:
                    return self._json_response(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {"ok": False, "error": f"failed to enqueue snapshot job: {exc}"},
                    )
            # No job queue wired: reject with 503 to avoid silent data loss
            return self._json_response(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"ok": False, "error": "job queue not available"},
            )

        if path.startswith("/api/v1/vms/") and path.endswith("/snapshot/revert"):
            vm, error = self._vm_from_segment(path, -3)
            if vm is None:
                status = HTTPStatus.BAD_REQUEST if error == "invalid vmid" else HTTPStatus.NOT_FOUND
                return self._json_response(status, {"ok": False, "error": error})
            if self._reset_vm_to_snapshot is None:
                return self._json_response(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"ok": False, "error": "snapshot revert not available"},
                )
            payload = json_payload if isinstance(json_payload, dict) else {}
            snap_name = str(payload.get("snapshot_name") or payload.get("name") or "").strip()
            if not snap_name:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "invalid payload: missing snapshot_name"},
                )
            try:
                provider_result = self._reset_vm_to_snapshot(int(vm.vmid), snap_name)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.CONFLICT,
                    {
                        "ok": False,
                        "error": f"snapshot revert failed: {exc}",
                        "vmid": int(vm.vmid),
                        "snapshot_name": snap_name,
                    },
                )
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        snapshot_revert={
                            "vmid": int(vm.vmid),
                            "node": str(vm.node),
                            "snapshot_name": snap_name,
                            "requested_by": requester_identity,
                            "provider_result": str(provider_result or ""),
                        }
                    ),
                },
            )

        if path.startswith("/api/v1/vms/") and path.endswith("/clone"):
            vm, error = self._vm_from_segment(path, -2)
            if vm is None:
                status = HTTPStatus.BAD_REQUEST if error == "invalid vmid" else HTTPStatus.NOT_FOUND
                return self._json_response(status, {"ok": False, "error": error})
            if self._clone_vm is None:
                return self._json_response(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"ok": False, "error": "vm clone not available"},
                )
            payload = json_payload if isinstance(json_payload, dict) else {}
            target_vmid_text = str(payload.get("target_vmid") or payload.get("newid") or "").strip()
            if not target_vmid_text.isdigit() or int(target_vmid_text) <= 0:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "invalid payload: missing target_vmid"},
                )
            target_vmid = int(target_vmid_text)
            clone_name = str(payload.get("name") or "").strip()
            try:
                provider_result = self._clone_vm(int(vm.vmid), target_vmid, clone_name)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.CONFLICT,
                    {
                        "ok": False,
                        "error": f"vm clone failed: {exc}",
                        "vmid": int(vm.vmid),
                        "target_vmid": target_vmid,
                    },
                )
            return self._json_response(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    **self._envelope(
                        vm_clone={
                            "source_vmid": int(vm.vmid),
                            "target_vmid": target_vmid,
                            "node": str(vm.node),
                            "name": clone_name,
                            "requested_by": requester_identity,
                            "provider_result": str(provider_result or ""),
                        }
                    ),
                },
            )

        if path.startswith("/api/v1/vms/") and path.endswith("/migrate"):
            vm, error = self._vm_from_segment(path, -2)
            if vm is None:
                status = HTTPStatus.BAD_REQUEST if error == "invalid vmid" else HTTPStatus.NOT_FOUND
                return self._json_response(status, {"ok": False, "error": error})
            payload = json_payload if isinstance(json_payload, dict) else {}
            target_node = str(payload.get("target_node", "")).strip()
            live = payload.get("live", True) is not False
            copy_storage = payload.get("copy_storage", False) is True
            if not target_node:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid payload: missing target_node"})
            try:
                migration = self._migrate_vm(int(vm.vmid), target_node, bool(live), bool(copy_storage), requester_identity)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.CONFLICT,
                    {
                        "ok": False,
                        "error": f"vm migration failed: {exc}",
                        "vmid": int(vm.vmid),
                        "target_node": target_node,
                    },
                )
            return self._json_response(HTTPStatus.ACCEPTED, {"ok": True, **migration})

        if path.startswith("/api/v1/virtualization/vms/") and path.endswith("/power"):
            payload = json_payload if isinstance(json_payload, dict) else {}
            action_name = str(payload.get("action", "")).strip().lower()
            vmid_text = path.split("/")[-2]
            vmid_hint = int(vmid_text) if vmid_text.isdigit() else 0
            vm, error = self._vm_from_segment(path, -2)
            if vm is None:
                status = HTTPStatus.BAD_REQUEST if error == "invalid vmid" else HTTPStatus.NOT_FOUND
                response_payload: dict[str, Any] = {"ok": False, "error": error}
                if action_name in {"start", "stop", "reboot"}:
                    response_payload.update(
                        self._envelope(
                            vm_power={
                                "vmid": vmid_hint,
                                "node": "",
                                "action": action_name,
                                "requested_by": requester_identity,
                                "provider_result": "",
                            }
                        )
                    )
                return self._json_response(status, response_payload)
            if action_name not in {"start", "stop", "reboot"}:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "invalid payload: unsupported power action"},
                )
            try:
                if action_name == "start":
                    provider_result = self._start_vm(vm.vmid)
                elif action_name == "stop":
                    provider_result = self._stop_vm(vm.vmid)
                else:
                    provider_result = self._reboot_vm(vm.vmid)
                self._invalidate_vm_cache(vm.vmid, vm.node)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "error": f"vm power action failed: {exc}",
                        "vmid": int(vm.vmid),
                        "action": action_name,
                    },
                )
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        vm_power={
                            "vmid": int(vm.vmid),
                            "node": str(vm.node),
                            "action": action_name,
                            "requested_by": requester_identity,
                            "provider_result": str(provider_result or ""),
                        }
                    ),
                },
            )

        if path.startswith("/api/v1/vms/") and path.endswith("/installer-prep"):
            vm, error = self._vm_from_segment(path, -2)
            if vm is None:
                status = HTTPStatus.BAD_REQUEST if error == "invalid vmid" else HTTPStatus.NOT_FOUND
                return self._json_response(status, {"ok": False, "error": error})
            try:
                state = self._start_installer_prep(vm)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": f"failed to start installer prep: {exc}"},
                )
            status = HTTPStatus.ACCEPTED if str(state.get("status", "")).lower() == "running" else HTTPStatus.OK
            return self._json_response(
                status,
                {
                    "ok": True,
                    **self._envelope(installer_prep=state),
                },
            )

        match = self._update_match(path)
        if match:
            vm = self._find_vm(int(match.group("vmid")))
            if vm is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            payload = json_payload if isinstance(json_payload, dict) else {}
            params = payload.get("params", {}) if isinstance(payload.get("params"), dict) else {}
            operation = match.group("operation")
            action_name = {
                "scan": "os-update-scan",
                "download": "os-update-download",
                "apply": "os-update-apply",
                "rollback": "os-update-rollback",
            }[operation]
            params = dict(params)
            if operation == "download":
                params["force"] = True
            if operation in {"apply", "rollback"} and "reboot" not in params:
                params["reboot"] = True
            queued = self._queue_vm_action(vm, action_name, requester_identity, params)
            return self._json_response(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    **self._envelope(queued_action=queued),
                },
            )

        if path.startswith("/api/v1/vms/") and path.endswith("/actions"):
            vm, error = self._vm_from_segment(path, -2)
            if vm is None:
                status = HTTPStatus.BAD_REQUEST if error == "invalid vmid" else HTTPStatus.NOT_FOUND
                return self._json_response(status, {"ok": False, "error": error})
            payload = json_payload if isinstance(json_payload, dict) else {}
            action_name = str(payload.get("action", "")).strip().lower()
            action_params = payload.get("params", {}) if isinstance(payload.get("params"), dict) else {}
            if action_name not in {
                "healthcheck",
                "recheckin",
                "restart-session",
                "restart-runtime",
                "support-bundle",
                "os-update-scan",
                "os-update-download",
                "os-update-apply",
                "os-update-rollback",
            }:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid payload: unsupported action"})
            queued = self._queue_vm_action(vm, action_name, requester_identity, action_params)
            return self._json_response(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    **self._envelope(queued_action=queued),
                },
            )

        if path.startswith("/api/v1/vms/") and path.endswith("/usb/refresh"):
            vm, error = self._vm_from_segment(path, -3)
            if vm is None:
                status = HTTPStatus.BAD_REQUEST if error == "invalid vmid" else HTTPStatus.NOT_FOUND
                return self._json_response(status, {"ok": False, "error": error})
            queued = self._queue_vm_action(vm, "usb-refresh", requester_identity)
            return self._json_response(
                HTTPStatus.ACCEPTED,
                {
                    "ok": True,
                    **self._envelope(queued_action=queued),
                },
            )

        if path.startswith("/api/v1/vms/") and path.endswith("/usb/attach"):
            vm, error = self._vm_from_segment(path, -3)
            if vm is None:
                status = HTTPStatus.BAD_REQUEST if error == "invalid vmid" else HTTPStatus.NOT_FOUND
                return self._json_response(status, {"ok": False, "error": error})
            payload = json_payload if isinstance(json_payload, dict) else {}
            busid = str(payload.get("busid", "")).strip()
            if not busid:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid payload: missing busid"})
            queued = self._queue_vm_action(vm, "usb-bind", requester_identity, {"busid": busid})
            result = self._wait_for_action_result(vm.node, vm.vmid, queued["action_id"])
            if result is None:
                return self._json_response(
                    HTTPStatus.ACCEPTED,
                    {
                        "ok": True,
                        **self._envelope(
                            queued_action=queued,
                            message="USB export queued on endpoint; refresh in a few seconds.",
                        ),
                    },
                )
            if not bool(result.get("ok")):
                return self._json_response(
                    HTTPStatus.CONFLICT,
                    {
                        "ok": False,
                        "error": str(result.get("message", "") or "endpoint usb export failed"),
                        "queued_action": queued,
                        "endpoint_result": self._summarize_action_result(result),
                    },
                )
            try:
                attach_result = self._attach_usb_to_guest(vm, busid)
            except Exception as exc:
                message = str(exc)
                if "Device busy (exported)" in message:
                    retry = self._queue_vm_action(vm, "usb-bind", requester_identity, {"busid": busid})
                    retry_result = self._wait_for_action_result(vm.node, vm.vmid, retry["action_id"])
                    if retry_result is not None and bool(retry_result.get("ok")):
                        try:
                            attach_result = self._attach_usb_to_guest(vm, busid)
                        except Exception as retry_exc:
                            message = str(retry_exc)
                        else:
                            return self._json_response(
                                HTTPStatus.OK,
                                {
                                    "ok": True,
                                    **self._envelope(
                                        queued_action=queued,
                                        endpoint_result=self._summarize_action_result(result),
                                        retry_action=retry,
                                        retry_endpoint_result=self._summarize_action_result(retry_result),
                                        attach_result=attach_result,
                                    ),
                                },
                            )
                return self._json_response(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "error": f"guest usb attach failed: {message}",
                        "queued_action": queued,
                        "endpoint_result": self._summarize_action_result(result),
                    },
                )
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        queued_action=queued,
                        endpoint_result=self._summarize_action_result(result),
                        guest_attach=attach_result,
                        usb=self._build_vm_usb_state(vm),
                    ),
                },
            )

        if path.startswith("/api/v1/vms/") and path.endswith("/usb/detach"):
            vm, error = self._vm_from_segment(path, -3)
            if vm is None:
                status = HTTPStatus.BAD_REQUEST if error == "invalid vmid" else HTTPStatus.NOT_FOUND
                return self._json_response(status, {"ok": False, "error": error})
            payload = json_payload if isinstance(json_payload, dict) else {}
            busid = str(payload.get("busid", "")).strip()
            port_value = payload.get("port")
            try:
                port = int(port_value) if port_value is not None and str(port_value).strip() else None
            except Exception as exc:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
            try:
                detach_result = self._detach_usb_from_guest(vm, port, busid)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.BAD_GATEWAY,
                    {"ok": False, "error": f"guest usb detach failed: {exc}"},
                )
            queued = None
            endpoint_result = None
            if busid:
                queued = self._queue_vm_action(vm, "usb-unbind", requester_identity, {"busid": busid})
                endpoint_result = self._wait_for_action_result(vm.node, vm.vmid, queued["action_id"])
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        guest_detach=detach_result,
                        queued_action=queued,
                        endpoint_result=self._summarize_action_result(endpoint_result),
                        usb=self._build_vm_usb_state(vm),
                    ),
                },
            )

        if path.startswith("/api/v1/vms/") and path.endswith("/sunshine-access"):
            vm, error = self._vm_from_segment(path, -2)
            if vm is None:
                status = HTTPStatus.BAD_REQUEST if error == "invalid vmid" else HTTPStatus.NOT_FOUND
                return self._json_response(status, {"ok": False, "error": error})
            token, payload = self._issue_sunshine_access_token(vm)
            return self._json_response(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    **self._envelope(
                        sunshine_access={
                            **payload,
                            "url": self._sunshine_proxy_ticket_url(token),
                        }
                    ),
                },
            )

        return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def route_delete(
        self,
        path: str,
        *,
        query: dict[str, list[str]] | None = None,
        requester_identity: str,
    ) -> dict[str, Any] | None:
        if path.startswith("/api/v1/vms/") and path.endswith("/snapshot"):
            vm, error = self._vm_from_segment(path, -2)
            if vm is None:
                status = HTTPStatus.BAD_REQUEST if error == "invalid vmid" else HTTPStatus.NOT_FOUND
                return self._json_response(status, {"ok": False, "error": error})
            if self._delete_vm_snapshot is None:
                return self._json_response(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"ok": False, "error": "snapshot delete not available"},
                )
            q = query or {}
            snap_name = str(q.get("name", [""])[0] or q.get("snapshot_name", [""])[0] or "").strip()
            if not snap_name:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "invalid payload: missing snapshot_name"},
                )
            try:
                provider_result = self._delete_vm_snapshot(int(vm.vmid), snap_name)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.CONFLICT,
                    {
                        "ok": False,
                        "error": f"snapshot delete failed: {exc}",
                        "vmid": int(vm.vmid),
                        "snapshot_name": snap_name,
                    },
                )
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        snapshot_delete={
                            "vmid": int(vm.vmid),
                            "node": str(vm.node),
                            "snapshot_name": snap_name,
                            "requested_by": requester_identity,
                            "provider_result": str(provider_result or ""),
                        }
                    ),
                },
            )
        return None
