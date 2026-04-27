from __future__ import annotations

from http import HTTPStatus
from typing import Any, Callable


class EndpointHttpSurfaceService:
    def __init__(
        self,
        *,
        build_vm_profile: Callable[[Any], dict[str, Any]],
        dequeue_vm_actions: Callable[[str, int], list[dict[str, Any]]],
        exchange_moonlight_pairing_token: Callable[[Any, dict[str, Any], str], dict[str, Any]],
        fetch_sunshine_server_identity: Callable[[Any, str], dict[str, Any]],
        find_vm: Callable[[int], Any | None],
        issue_moonlight_pairing_token: Callable[[Any, dict[str, Any], str], dict[str, Any]],
        register_moonlight_certificate_on_vm: Callable[[Any, str], dict[str, Any]],
        service_name: str,
        prepare_virtual_display_on_vm: Callable[[Any, str], dict[str, Any]],
        session_manager_service: Any,
        store_action_result: Callable[[str, int, dict[str, Any]], None],
        store_support_bundle: Callable[[str, int, str, str, bytes], dict[str, Any]],
        summarize_action_result: Callable[[dict[str, Any] | None], dict[str, Any]],
        utcnow: Callable[[], str],
        version: str,
    ) -> None:
        self._build_vm_profile = build_vm_profile
        self._dequeue_vm_actions = dequeue_vm_actions
        self._exchange_moonlight_pairing_token = exchange_moonlight_pairing_token
        self._fetch_sunshine_server_identity = fetch_sunshine_server_identity
        self._find_vm = find_vm
        self._issue_moonlight_pairing_token = issue_moonlight_pairing_token
        self._register_moonlight_certificate_on_vm = register_moonlight_certificate_on_vm
        self._prepare_virtual_display_on_vm = prepare_virtual_display_on_vm
        self._session_manager = session_manager_service
        self._service_name = str(service_name or "beagle-control-plane")
        self._store_action_result = store_action_result
        self._store_support_bundle = store_support_bundle
        self._summarize_action_result = summarize_action_result
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
    def _scope_matches(identity: dict[str, Any], vmid: int, node: str) -> bool:
        if not identity:
            return True
        return int(identity.get("vmid", -1)) == int(vmid) and str(identity.get("node", "")).strip() == str(node).strip()

    @staticmethod
    def handles_path(path: str) -> bool:
        return path in {
            "/api/v1/session/current",
            "/api/v1/endpoints/moonlight/register",
            "/api/v1/endpoints/moonlight/prepare-stream",
            "/api/v1/endpoints/moonlight/pair-token",
            "/api/v1/endpoints/moonlight/pair-exchange",
            "/api/v1/endpoints/actions/pull",
            "/api/v1/endpoints/actions/result",
            "/api/v1/endpoints/support-bundles/upload",
        }

    @staticmethod
    def requires_json_body(path: str) -> bool:
        return path in {
            "/api/v1/endpoints/moonlight/register",
            "/api/v1/endpoints/moonlight/prepare-stream",
            "/api/v1/endpoints/moonlight/pair-token",
            "/api/v1/endpoints/moonlight/pair-exchange",
            "/api/v1/endpoints/actions/pull",
            "/api/v1/endpoints/actions/result",
        }

    @staticmethod
    def requires_binary_body(path: str) -> bool:
        return path == "/api/v1/endpoints/support-bundles/upload"

    def route_get(
        self,
        path: str,
        *,
        endpoint_identity: dict[str, Any] | None,
        query: dict[str, list[str]],
    ) -> dict[str, Any]:
        identity = endpoint_identity or {}

        if path == "/api/v1/session/current":
            session_id = str((query.get("session_id") or [""])[0] or "").strip()
            vmid_text = str((query.get("vmid") or [""])[0] or "").strip()
            try:
                vmid = int(vmid_text or identity.get("vmid") or 0)
            except (TypeError, ValueError):
                vmid = 0
            if not session_id and vmid <= 0:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "session_id or vmid is required"})

            session = self._session_manager.find_active_session(session_id=session_id, vm_id=vmid)
            if session is None and vmid > 0:
                vm = self._find_vm(vmid)
                if vm is None:
                    return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "session not found"})
                session = {
                    "session_id": session_id or f"vm:{vmid}",
                    "pool_id": "",
                    "vm_id": vmid,
                    "user_id": str(identity.get("hostname", "") or ""),
                    "current_node": str(vm.node or ""),
                    "status": "active",
                }
            elif session is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "session not found"})

            session_vmid = int(session.get("vm_id") or vmid or 0)
            vm = self._find_vm(session_vmid) if session_vmid > 0 else None
            if vm is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})

            profile = self._build_vm_profile(vm) if callable(self._build_vm_profile) else {}
            stream_host = str(profile.get("stream_host", "") or "").strip()
            moonlight_port = str(profile.get("moonlight_port", "") or "").strip()
            current_node = str(session.get("current_node") or vm.node or "").strip()
            reconnect_required = bool(current_node and str(identity.get("node", "")).strip() and current_node != str(identity.get("node", "")).strip())
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(
                        session_id=str(session.get("session_id") or session_id or ""),
                        pool_id=str(session.get("pool_id") or ""),
                        vmid=session_vmid,
                        current_node=current_node,
                        stream_host=stream_host,
                        moonlight_port=moonlight_port,
                        reconnect_required=reconnect_required,
                    ),
                },
            )

        return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def route_post(
        self,
        path: str,
        *,
        endpoint_identity: dict[str, Any] | None,
        query: dict[str, list[str]],
        json_payload: dict[str, Any] | None = None,
        binary_payload: bytes | None = None,
    ) -> dict[str, Any]:
        identity = endpoint_identity or {}

        if path == "/api/v1/endpoints/moonlight/register":
            vmid = int(identity.get("vmid", 0) or 0)
            vm = self._find_vm(vmid)
            if vm is None or str(identity.get("node", "")).strip() != vm.node:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})
            payload = json_payload if isinstance(json_payload, dict) else {}
            client_cert_pem = str(payload.get("client_cert_pem", "")).strip()
            device_name = (
                str(payload.get("device_name", "")).strip()
                or str(identity.get("hostname", "")).strip()
                or f"beagle-vm{vmid}-client"
            )
            if not client_cert_pem or "BEGIN CERTIFICATE" not in client_cert_pem:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid payload: missing client certificate"})
            result = self._register_moonlight_certificate_on_vm(vm, client_cert_pem, device_name=device_name)
            guest_user = str(result.get("guest_user", "") or "").strip()
            sunshine_server: dict[str, Any] = {
                "ok": False,
                "uniqueid": "",
                "server_cert_pem": "",
                "sunshine_name": "",
                "stream_port": "",
                "stdout": "",
                "stderr": "",
            }
            if bool(result.get("ok")) and guest_user:
                sunshine_server = self._fetch_sunshine_server_identity(vm, guest_user)
            overall_ok = bool(result.get("ok")) and bool(sunshine_server.get("ok")) and bool(
                sunshine_server.get("uniqueid")
            ) and bool(sunshine_server.get("server_cert_pem"))
            return self._json_response(
                HTTPStatus.CREATED if overall_ok else HTTPStatus.BAD_GATEWAY,
                {
                    "ok": overall_ok,
                    **self._envelope(
                        vmid=vm.vmid,
                        node=vm.node,
                        device_name=device_name,
                        guest_user=result.get("guest_user", ""),
                        stdout=result.get("stdout", ""),
                        stderr=result.get("stderr", ""),
                        sunshine_server={
                            "ok": bool(sunshine_server.get("ok")),
                            "uniqueid": sunshine_server.get("uniqueid", ""),
                            "server_cert_pem": sunshine_server.get("server_cert_pem", ""),
                            "sunshine_name": sunshine_server.get("sunshine_name", ""),
                            "stream_port": sunshine_server.get("stream_port", ""),
                            "stdout": sunshine_server.get("stdout", ""),
                            "stderr": sunshine_server.get("stderr", ""),
                        },
                    ),
                },
            )

        if path == "/api/v1/endpoints/moonlight/prepare-stream":
            vmid = int(identity.get("vmid", 0) or 0)
            vm = self._find_vm(vmid)
            if vm is None or str(identity.get("node", "")).strip() != vm.node:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})

            payload = json_payload if isinstance(json_payload, dict) else {}
            resolution = str(payload.get("resolution", "")).strip()
            if not resolution:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid payload: missing resolution"})

            result = self._prepare_virtual_display_on_vm(vm, resolution)
            return self._json_response(
                HTTPStatus.OK if bool(result.get("ok")) else HTTPStatus.BAD_GATEWAY,
                {
                    "ok": bool(result.get("ok")),
                    **self._envelope(
                        vmid=vm.vmid,
                        node=vm.node,
                        resolution=resolution,
                        result=result,
                    ),
                },
            )

        if path == "/api/v1/endpoints/moonlight/pair-token":
            vmid = int(identity.get("vmid", 0) or 0)
            vm = self._find_vm(vmid)
            if vm is None or str(identity.get("node", "")).strip() != vm.node:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})

            payload = json_payload if isinstance(json_payload, dict) else {}
            device_name = (
                str(payload.get("device_name", "")).strip()
                or str(identity.get("hostname", "")).strip()
                or f"beagle-vm{vmid}-client"
            )
            try:
                issued = self._issue_moonlight_pairing_token(vm, identity, device_name)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "error": f"pair token issue failed: {exc}",
                        **self._envelope(vmid=vm.vmid, node=vm.node, device_name=device_name),
                    },
                )
            if not bool(issued.get("ok")):
                return self._json_response(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "error": str(issued.get("error", "pair token issue failed") or "pair token issue failed"),
                        **self._envelope(vmid=vm.vmid, node=vm.node, device_name=device_name),
                    },
                )
            return self._json_response(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    **self._envelope(
                        vmid=vm.vmid,
                        node=vm.node,
                        device_name=device_name,
                        pairing={
                            "token": str(issued.get("token", "") or ""),
                            "pin": str(issued.get("pin", "") or ""),
                            "expires_at": str(issued.get("expires_at", "") or ""),
                        },
                    ),
                },
            )

        if path == "/api/v1/endpoints/moonlight/pair-exchange":
            vmid = int(identity.get("vmid", 0) or 0)
            vm = self._find_vm(vmid)
            if vm is None or str(identity.get("node", "")).strip() != vm.node:
                return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "vm not found"})

            payload = json_payload if isinstance(json_payload, dict) else {}
            token = str(payload.get("pairing_token", "")).strip()
            if not token:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid payload: missing pairing_token"})

            try:
                exchanged = self._exchange_moonlight_pairing_token(vm, identity, token)
            except Exception as exc:
                return self._json_response(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "error": f"pair exchange failed: {exc}",
                        **self._envelope(vmid=vm.vmid, node=vm.node),
                    },
                )
            if not bool(exchanged.get("ok")):
                return self._json_response(
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "ok": False,
                        "error": str(exchanged.get("error", "pair exchange failed") or "pair exchange failed"),
                        **self._envelope(vmid=vm.vmid, node=vm.node),
                    },
                )
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(vmid=vm.vmid, node=vm.node, paired=True),
                },
            )

        if path == "/api/v1/endpoints/actions/pull":
            payload = json_payload if isinstance(json_payload, dict) else {}
            try:
                vmid = int(payload.get("vmid"))
                node = str(payload.get("node", "")).strip()
            except Exception as exc:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
            if not node:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid payload: missing node"})
            if not self._scope_matches(identity, vmid, node):
                return self._json_response(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(actions=self._dequeue_vm_actions(node, vmid)),
                },
            )

        if path == "/api/v1/endpoints/actions/result":
            payload = dict(json_payload) if isinstance(json_payload, dict) else {}
            try:
                vmid = int(payload.get("vmid"))
                node = str(payload.get("node", "")).strip()
                action_name = str(payload.get("action", "")).strip()
                action_id = str(payload.get("action_id", "")).strip()
            except Exception as exc:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
            if not node or not action_name or not action_id:
                return self._json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "invalid payload: missing action result fields"},
                )
            if not self._scope_matches(identity, vmid, node):
                return self._json_response(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})
            payload["vmid"] = vmid
            payload["node"] = node
            payload["received_at"] = self._utcnow()
            self._store_action_result(node, vmid, payload)
            return self._json_response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    **self._envelope(last_action=self._summarize_action_result(payload)),
                },
            )

        if path == "/api/v1/endpoints/support-bundles/upload":
            try:
                vmid = int((query.get("vmid") or [""])[0])
                node = str((query.get("node") or [""])[0]).strip()
                action_id = str((query.get("action_id") or [""])[0]).strip()
                filename = str((query.get("filename") or [""])[0]).strip() or "support-bundle.tar.gz"
            except Exception as exc:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid upload: {exc}"})
            if not node or not action_id:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid upload: missing upload fields"})
            if binary_payload is None:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid upload: missing payload"})
            if not self._scope_matches(identity, vmid, node):
                return self._json_response(HTTPStatus.FORBIDDEN, {"ok": False, "error": "endpoint scope mismatch"})
            bundle = self._store_support_bundle(node, vmid, action_id, filename, binary_payload)
            return self._json_response(
                HTTPStatus.CREATED,
                {
                    "ok": True,
                    **self._envelope(support_bundle=bundle),
                },
            )

        return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
