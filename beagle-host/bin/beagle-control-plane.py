#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
PROVIDERS_DIR = Path(__file__).resolve().parents[1] / "providers"
SERVICES_DIR = Path(__file__).resolve().parents[1] / "services"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(PROVIDERS_DIR) not in sys.path:
    sys.path.insert(0, str(PROVIDERS_DIR))
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from service_registry import *  # noqa: F401,F403
from service_registry import (  # private helpers used in main()
    _bootstrap_secret,
    _secret_store,
    _start_recording_retention_thread,
    _start_backup_scheduler_thread,
)
import service_registry as _svc_registry  # needed to update module-level secrets in main()
from request_handler_mixin import HandlerMixin

class Handler(HandlerMixin, BaseHTTPRequestHandler):
    server_version = f"BeagleControlPlane/{VERSION}"

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._write_common_security_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Beagle-Api-Token, X-Beagle-Endpoint-Token, X-Beagle-Refresh-Token")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if not self._enforce_api_rate_limit(urlparse(self.path).path.rstrip("/") or "/"):
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query_text = parsed.query
        query = parse_qs(parsed.query or "")

        response = public_sunshine_surface_service().route_request(
            parsed.path,
            query=query_text,
            method="GET",
            body=None,
            request_headers={"Accept": self.headers.get("Accept", "")},
        )
        if response is not None:
            if response["kind"] == "proxy":
                self._write_proxy_response(response["status"], response["headers"], response["body"])
            else:
                self._write_json(response["status"], response["payload"])
            return

        response = public_http_surface_service().route_get(path)
        if response is not None:
            self._write_json(response["status"], response["payload"])
            return

        if path == "/api/v1/endpoints/update-feed":
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            response = public_http_surface_service().endpoint_update_feed(
                query_text=query_text,
                endpoint_identity=self._endpoint_identity(),
            )
            self._write_json(response["status"], response["payload"])
            return

        if self._auth_session_surface().handles_get(path):
            response = self._auth_session_surface().route_get(path, query=query)
            if response["kind"] == "redirect":
                self._write_redirect(response["location"])
            elif response["kind"] == "bytes":
                self._write_bytes(response["status"], response["body"], content_type=response["content_type"])
            else:
                self._write_json(
                    response["status"],
                    response["payload"],
                    extra_headers=response.get("extra_headers"),
                )
            return

        if path == "/api/v1/events/stream":
            principal = self._stream_principal(parsed)
            if principal is None:
                self._stream_auth_error(HTTPStatus.UNAUTHORIZED, code="unauthorized", message="unauthorized")
                return
            self._stream_live_events(principal)
            return

        if AuditReportHttpSurfaceService.handles_get(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("GET", path):
                return
            response = self._audit_report_surface().route_get(path, query=query)
            if response["kind"] == "bytes":
                self._write_bytes(response["status"], response["body"], content_type=response["content_type"], filename=response.get("filename", ""))
            else:
                self._write_json(response["status"], response["payload"])
            return

        if scim_service().handles_path(path):
            if not SCIM_BEARER_TOKEN:
                self._write_json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": "scim disabled"})
                return
            if not self._is_scim_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            response = scim_service().route_get(path)
            self._write_json(response["status"], response["payload"])
            return

        if API_V2_PREPARATION_ENABLED and path in {"/api/v2", "/api/v2/health"}:
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "beagle-control-plane",
                    "version": VERSION,
                    "api": {
                        "current": "v1",
                        "next": "v2",
                        "status": "preparation",
                        "deprecated_v1_endpoints": sorted(API_V1_DEPRECATED_ENDPOINTS),
                        "deprecation_doc": API_V1_DEPRECATION_DOC_URL,
                        "sunset": API_V1_DEPRECATION_SUNSET,
                    },
                },
            )
            return

        if auth_http_surface_service().handles_get(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("GET", path):
                return
            principal = self._auth_principal()
            requester_tenant = (principal or {}).get("tenant_id") or None
            response = auth_http_surface_service().route_get(
                path, requester_tenant_id=requester_tenant
            )
            self._write_json(response["status"], response["payload"])
            return

        if self._recording_surface().handles_get(path):
            if not self._authorize_or_respond("GET", path):
                return
            response = self._recording_surface().route_get(path)
            if response["kind"] == "bytes":
                self._write_bytes(response["status"], response["body"], content_type=response["content_type"], filename=response.get("filename", ""))
            else:
                self._write_json(response["status"], response["payload"])
            return

        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return

        if self._backups_surface().handles_get(path):
            if not self._authorize_or_respond("GET", path):
                return
            response = self._backups_surface().route_get(path, query=query)
            if response is not None:
                if response.get("kind") == "bytes":
                    self._write_bytes(response["status"], response["body"], content_type=response["content_type"], filename=response.get("filename", ""))
                else:
                    self._write_json(response["status"], response["payload"])
            return

        if self._pools_surface().handles_get(path):
            if not self._authorize_or_respond("GET", path):
                return
            response = self._pools_surface().route_get(path)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        if path == "/healthz":
            self._write_json(HTTPStatus.OK, {"ok": True, "service": "beagle-control-plane", "version": VERSION})
            return
        response = control_plane_read_surface_service().route_get(path)
        if response is not None:
            if response["kind"] == "bytes":
                self._write_bytes(
                    response["status"],
                    response["body"],
                    content_type=response["content_type"],
                    filename=response["filename"],
                )
            else:
                self._write_json(response["status"], response["payload"])
            return
        response = virtualization_read_surface_service().route_get(path)
        if response is not None:
            self._write_json(response["status"], response["payload"])
            return
        if vgpu_surface_service().handles_path_get(path):
            if not self._authorize_or_respond("GET", path):
                return
            response = vgpu_surface_service().route_get(path)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return
        if path == "/api/v1/health":
            self._write_json(HTTPStatus.OK, build_health_payload())
            return
        if path == "/api/v1/vms":
            self._write_json(HTTPStatus.OK, build_vm_inventory())
            return
        if self._cluster_surface().handles_get(path):
            if not self._authorize_or_respond("GET", path):
                return
            response = self._cluster_surface().route_get(path)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return
        if path.startswith("/api/v1/vms/"):
            response = vm_http_surface_service().route_get(path)
            if response["kind"] == "bytes":
                self._write_bytes(
                    response["status"],
                    response["body"],
                    content_type=response["content_type"],
                    filename=response["filename"],
                )
            else:
                self._write_json(response["status"], response["payload"])
            return

        if path.startswith("/api/v1/settings/"):
            if not self._authorize_or_respond("GET", path):
                return
            response = server_settings_service().route_get(path)
            if response is not None:
                self._write_json(response["status"], response["payload"])
                return

        if network_http_surface_service().handles_get(path):
            if not self._authorize_or_respond("GET", path):
                return
            response = network_http_surface_service().route_get(path)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._enforce_api_rate_limit(urlparse(self.path).path.rstrip("/") or "/"):
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query or "")

        if self._backups_surface().handles_post(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            if path == "/api/v1/backups/ingest":
                content_length = int(self.headers.get("Content-Length") or 0)
                if content_length <= 0 or content_length > 10 * 1024 * 1024 * 1024:  # max 10 GB
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid Content-Length"})
                    return
                raw_body = self.rfile.read(content_length)
                raw_headers = {"X-Beagle-Backup-Meta": str(self.headers.get("X-Beagle-Backup-Meta") or "{}")}
                response = self._backups_surface().route_post(path, raw_body=raw_body, raw_headers=raw_headers)
            else:
                try:
                    json_payload = self._read_json_body() if int(self.headers.get("Content-Length", "0") or "0") > 0 else {}
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
                response = self._backups_surface().route_post(path, json_payload=json_payload)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        if self._cluster_surface().handles_post(path):
            if path != "/api/v1/cluster/join":
                if not self._is_authenticated():
                    self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                    return
                if not self._authorize_or_respond("POST", path):
                    return
            try:
                json_payload = self._read_json_body() if int(self.headers.get("Content-Length", "0") or "0") > 0 else {}
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = self._cluster_surface().route_post(path, json_payload=json_payload)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        if self._auth_session_surface().handles_post(path):
            response = self._auth_session_surface().route_post(path)
            if response["kind"] == "redirect":
                self._write_redirect(response["location"])
            elif response["kind"] == "bytes":
                self._write_bytes(response["status"], response["body"], content_type=response["content_type"])
            else:
                self._write_json(
                    response["status"],
                    response["payload"],
                    extra_headers=response.get("extra_headers"),
                )
            return

        if scim_service().handles_path(path):
            if not SCIM_BEARER_TOKEN:
                self._write_json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": "scim disabled"})
                return
            if not self._is_scim_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = scim_service().route_post(path, json_payload)
            self._write_json(response["status"], response["payload"])
            return

        if auth_http_surface_service().handles_post(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            json_payload: dict[str, Any] | None = None
            if auth_http_surface_service().requires_json_body(path):
                try:
                    json_payload = self._read_json_body()
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
            principal = self._auth_principal()
            requester_tenant = (principal or {}).get("tenant_id") or None
            response = auth_http_surface_service().route_post(
                path, json_payload=json_payload, requester_tenant_id=requester_tenant
            )
            self._audit_auth_surface_response("POST", path, response)
            self._write_json(response["status"], response["payload"])
            return

        if self._recording_surface().handles_post(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            response = self._recording_surface().route_post(path)
            if response["kind"] == "bytes":
                self._write_bytes(response["status"], response["body"], content_type=response["content_type"])
            else:
                self._write_json(response["status"], response["payload"])
            return

        sunshine_body: bytes | None = None
        if path.startswith("/api/v1/public/sunshine/"):
            try:
                sunshine_body = self._read_binary_body(max_bytes=16 * 1024 * 1024)
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid content length: {exc}"})
                return
            response = public_sunshine_surface_service().route_request(
                parsed.path,
                query=parsed.query,
                method="POST",
                body=sunshine_body,
                request_headers={
                    "Content-Type": self.headers.get("Content-Type", ""),
                    "Accept": self.headers.get("Accept", ""),
                },
            )
            if response is not None:
                if response["kind"] == "proxy":
                    self._write_proxy_response(response["status"], response["headers"], response["body"])
                else:
                    self._write_json(response["status"], response["payload"])
                return
            return

        public_install_payload: dict[str, Any] | None = None
        if path.endswith("/failed") and int(self.headers.get("Content-Length", "0") or "0") > 0:
            try:
                public_install_payload = self._read_json_body()
            except Exception:
                public_install_payload = {}
        response = public_ubuntu_install_surface_service().route_post(
            path,
            query=query,
            payload=public_install_payload,
        )
        if response is not None:
            self._write_json(response["status"], response["payload"])
            return

        if endpoint_http_surface_service().handles_path(path):
            if not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            json_payload: dict[str, Any] | None = None
            binary_payload: bytes | None = None
            if endpoint_http_surface_service().requires_json_body(path):
                try:
                    json_payload = self._read_json_body()
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
            if endpoint_http_surface_service().requires_binary_body(path):
                try:
                    binary_payload = self._read_binary_body(max_bytes=128 * 1024 * 1024)
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid upload: {exc}"})
                    return
            response = endpoint_http_surface_service().route_post(
                path,
                endpoint_identity=self._endpoint_identity(),
                query=query,
                json_payload=json_payload,
                binary_payload=binary_payload,
            )
            self._write_json(response["status"], response["payload"])
            return

        if endpoint_lifecycle_surface_service().handles_post(path):
            if endpoint_lifecycle_surface_service().requires_endpoint_auth(path) and not self._is_endpoint_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = endpoint_lifecycle_surface_service().route_post(
                path,
                endpoint_identity=self._endpoint_identity(),
                json_payload=json_payload,
                remote_addr=self.client_address[0],
            )
            self._audit_event(
                "endpoint.lifecycle",
                "success" if int(response["status"]) < 400 else "error",
                method="POST",
                path=path,
                status=int(response["status"]),
            )
            self._write_json(response["status"], response["payload"])
            return

        if vm_mutation_surface_service().handles_path(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            json_payload: dict[str, Any] | None = None
            if vm_mutation_surface_service().requires_json_body(path):
                try:
                    json_payload = self._read_json_body()
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
            elif vm_mutation_surface_service().accepts_optional_json_body(path) and int(self.headers.get("Content-Length", "0") or "0") > 0:
                try:
                    json_payload = self._read_json_body()
                except Exception as exc:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                    return
            response = vm_mutation_surface_service().route_post(
                path,
                json_payload=json_payload,
                requester_identity=self._requester_identity(),
            )
            self._audit_event(
                "mutation.request",
                "success" if int(response["status"]) < 400 else "error",
                method="POST",
                path=path,
                permission=authz_policy_service().required_permission("POST", path),
                username=self._requester_identity(),
                status=int(response["status"]),
            )
            vm_power_event = build_vm_power_audit_event(response, requester_identity=self._requester_identity())
            if isinstance(vm_power_event, dict):
                self._audit_event(
                    str(vm_power_event.get("event_type") or "vm.unknown"),
                    str(vm_power_event.get("outcome") or "unknown"),
                    **(vm_power_event.get("details") if isinstance(vm_power_event.get("details"), dict) else {}),
                )
                if str(vm_power_event.get("outcome") or "") == "success":
                    event_type = str(vm_power_event.get("event_type") or "")
                    event_details = vm_power_event.get("details") if isinstance(vm_power_event.get("details"), dict) else {}
                    try:
                        webhook_service().dispatch_event(
                            event_type=event_type,
                            event_payload={
                                "vm": event_details,
                                "requested_by": self._requester_identity(),
                            },
                        )
                    except Exception:
                        pass
            self._write_json(response["status"], response["payload"])
            return

        if gpu_passthrough_surface_service().handles_path(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = gpu_passthrough_surface_service().route_post(
                path,
                json_payload=json_payload,
            )
            self._audit_event(
                "gpu.passthrough.request",
                "success" if int(response["status"]) < 400 else "error",
                method="POST",
                path=path,
                username=self._requester_identity(),
                status=int(response["status"]),
            )
            self._write_json(response["status"], response["payload"])
            return

        if vgpu_surface_service().handles_path_post(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = vgpu_surface_service().route_post(path, json_payload=json_payload)
            self._audit_event(
                "gpu.vgpu.request",
                "success" if int(response["status"]) < 400 else "error",
                method="POST",
                path=path,
                username=self._requester_identity(),
                status=int(response["status"]),
            )
            self._write_json(response["status"], response["payload"])
            return

        if self._pools_surface().handles_post(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            try:
                json_payload = self._read_json_body() if int(self.headers.get("Content-Length", "0") or "0") > 0 else {}
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = self._pools_surface().route_post(path, json_payload=json_payload)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        admin_post_path = "/api/v1/provisioning/vms" if path == "/api/v1/vms" else path
        if admin_http_surface_service().handles_post(admin_post_path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", admin_post_path):
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                response = admin_http_surface_service().read_error_response("POST", admin_post_path, exc)
                self._write_json(response["status"], response["payload"])
                return
            response = admin_http_surface_service().route_post(
                admin_post_path,
                json_payload=json_payload,
                requester_identity=self._requester_identity(),
            )
            self._audit_event(
                "mutation.request",
                "success" if int(response["status"]) < 400 else "error",
                method="POST",
                path=path,
                effective_path=admin_post_path,
                permission=authz_policy_service().required_permission("POST", admin_post_path),
                username=self._requester_identity(),
                status=int(response["status"]),
            )
            self._write_json(response["status"], response["payload"])
            return

        if path.startswith("/api/v1/settings/"):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = server_settings_service().route_post(path, json_payload or {})
            if response is not None:
                self._audit_event(
                    "settings.mutation",
                    "success" if int(response["status"]) < 400 else "error",
                    method="POST",
                    path=path,
                    username=self._requester_identity(),
                )
                self._write_json(response["status"], response["payload"])
                return

        if network_http_surface_service().handles_post(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("POST", path):
                return
            try:
                json_payload = self._read_json_body() if int(self.headers.get("Content-Length", "0") or "0") > 0 else {}
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = network_http_surface_service().route_post(path, json_payload=json_payload)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_PUT(self) -> None:  # noqa: N802
        if not self._enforce_api_rate_limit(urlparse(self.path).path.rstrip("/") or "/"):
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if scim_service().handles_path(path):
            if not SCIM_BEARER_TOKEN:
                self._write_json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": "scim disabled"})
                return
            if not self._is_scim_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            try:
                payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = scim_service().route_put(path, payload)
            self._write_json(response["status"], response["payload"])
            return

        if auth_http_surface_service().handles_put(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("PUT", path):
                return
            try:
                payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            principal = self._auth_principal()
            requester_tenant = (principal or {}).get("tenant_id") or None
            response = auth_http_surface_service().route_put(
                path, json_payload=payload, requester_tenant_id=requester_tenant
            )
            self._audit_auth_surface_response("PUT", path, response)
            self._write_json(response["status"], response["payload"])
            return

        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        if not self._authorize_or_respond("PUT", path):
            return

        if self._backups_surface().handles_put(path):
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = self._backups_surface().route_put(path, json_payload=json_payload)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        if self._pools_surface().handles_put(path):
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = self._pools_surface().route_put(path, json_payload=json_payload)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        if path.startswith("/api/v1/settings/"):
            try:
                json_payload = self._read_json_body()
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid payload: {exc}"})
                return
            response = server_settings_service().route_put(path, json_payload or {})
            if response is not None:
                self._audit_event(
                    "settings.mutation",
                    "success" if int(response["status"]) < 400 else "error",
                    method="PUT",
                    path=path,
                    username=self._requester_identity(),
                )
                self._write_json(response["status"], response["payload"])
                return

        if not admin_http_surface_service().handles_put(path):
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        try:
            json_payload = self._read_json_body()
        except Exception as exc:
            response = admin_http_surface_service().read_error_response("PUT", path, exc)
            self._write_json(response["status"], response["payload"])
            return
        response = admin_http_surface_service().route_put(path, json_payload=json_payload)
        self._audit_event(
            "mutation.request",
            "success" if int(response["status"]) < 400 else "error",
            method="PUT",
            path=path,
            permission=authz_policy_service().required_permission("PUT", path),
            username=self._requester_identity(),
            status=int(response["status"]),
        )
        self._write_json(response["status"], response["payload"])

    def do_DELETE(self) -> None:  # noqa: N802
        if not self._enforce_api_rate_limit(urlparse(self.path).path.rstrip("/") or "/"):
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if scim_service().handles_path(path):
            if not SCIM_BEARER_TOKEN:
                self._write_json(HTTPStatus.NOT_IMPLEMENTED, {"ok": False, "error": "scim disabled"})
                return
            if not self._is_scim_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            response = scim_service().route_delete(path)
            if int(response["status"]) == int(HTTPStatus.NO_CONTENT):
                self.send_response(HTTPStatus.NO_CONTENT)
                self._write_common_security_headers()
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._write_json(response["status"], response["payload"])
            return

        if auth_http_surface_service().handles_delete(path):
            if not self._is_authenticated():
                self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                return
            if not self._authorize_or_respond("DELETE", path):
                return
            principal = self._auth_principal()
            requester_tenant = (principal or {}).get("tenant_id") or None
            response = auth_http_surface_service().route_delete(
                path, requester_tenant_id=requester_tenant
            )
            self._audit_auth_surface_response("DELETE", path, response)
            self._write_json(response["status"], response["payload"])
            return

        if not self._is_authenticated():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
            return
        if not self._authorize_or_respond("DELETE", path):
            return
        if self._pools_surface().handles_delete(path):
            response = self._pools_surface().route_delete(path)
            if response is not None:
                self._write_json(response["status"], response["payload"])
            return

        if not admin_http_surface_service().handles_delete(path):
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return
        response = admin_http_surface_service().route_delete(path)
        self._audit_event(
            "mutation.request",
            "success" if int(response["status"]) < 400 else "error",
            method="DELETE",
            path=path,
            permission=authz_policy_service().required_permission("DELETE", path),
            username=self._requester_identity(),
            status=int(response["status"]),
        )
        self._write_json(response["status"], response["payload"])

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{utcnow()}] {self.address_string()} {fmt % args}", flush=True)

    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        except Exception as error:
            self._handle_unexpected_error(error)


def main() -> int:
    global API_TOKEN, SCIM_BEARER_TOKEN, PAIRING_TOKEN_SECRET  # noqa: PLW0603
    # Auto-bootstrap: if secrets not set via env, load or generate from SecretStore.
    # Must update BOTH service_registry module globals (used by factory functions)
    # and control-plane.py module globals (used by Handler class at request time).
    _svc_registry.API_TOKEN = _bootstrap_secret("manager-api-token", _svc_registry.API_TOKEN, generate=True)
    _svc_registry.SCIM_BEARER_TOKEN = _bootstrap_secret("scim-bearer-token", _svc_registry.SCIM_BEARER_TOKEN, generate=False)
    _svc_registry.PAIRING_TOKEN_SECRET = _bootstrap_secret("pairing-token-secret", _svc_registry.PAIRING_TOKEN_SECRET, generate=True)
    API_TOKEN = _svc_registry.API_TOKEN
    SCIM_BEARER_TOKEN = _svc_registry.SCIM_BEARER_TOKEN
    PAIRING_TOKEN_SECRET = _svc_registry.PAIRING_TOKEN_SECRET
    # Wire AuditLogService into SecretStoreService (audit fn must be set after audit log is ready)
    def _audit_secret_event(event: str, details: dict) -> None:
        # Never include secret values in audit events
        safe_details = {k: v for k, v in details.items() if k != "value"}
        audit_log_service().write_event(event, "ok", details=safe_details)
    _secret_store()._audit_fn = _audit_secret_event
    effective_data_dir = ensure_data_dir()
    ensure_cluster_rpc_listener()
    _start_recording_retention_thread()
    _start_backup_scheduler_thread()
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    print(
        json.dumps(
            {
                "service": "beagle-control-plane",
                "version": VERSION,
                "listen_host": LISTEN_HOST,
                "listen_port": LISTEN_PORT,
                "allow_localhost_noauth": ALLOW_LOCALHOST_NOAUTH,
                "data_dir": str(effective_data_dir),
            }
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if _svc_registry.RECORDING_RETENTION_STOP_EVENT is not None:
            _svc_registry.RECORDING_RETENTION_STOP_EVENT.set()
        if _svc_registry.RECORDING_RETENTION_THREAD is not None:
            _svc_registry.RECORDING_RETENTION_THREAD.join(timeout=5)
        if _svc_registry.BACKUP_SCHEDULER_STOP_EVENT is not None:
            _svc_registry.BACKUP_SCHEDULER_STOP_EVENT.set()
        if _svc_registry.BACKUP_SCHEDULER_THREAD is not None:
            _svc_registry.BACKUP_SCHEDULER_THREAD.join(timeout=5)
        if _svc_registry.CLUSTER_RPC_SERVER is not None:
            _svc_registry.CLUSTER_RPC_SERVER.shutdown()
            _svc_registry.CLUSTER_RPC_SERVER.server_close()
        if _svc_registry.CLUSTER_RPC_THREAD is not None:
            _svc_registry.CLUSTER_RPC_THREAD.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
