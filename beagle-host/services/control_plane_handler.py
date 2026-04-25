"""Control plane HTTP request Handler — extracted from beagle-control-plane.py.

GoAdvanced Plan 05 (Control-Plane Split). The 800+ line Handler class lives
here so the bin/ entry point can stay small (bootstrap + main()).

The Handler dispatches to specialized `*_http_surface` services for each
domain (auth, vms, pools, cluster, backups, etc.). It holds only the
boilerplate routing / auth / json-parse glue.
"""
from __future__ import annotations

import hmac

# Pull every symbol used below (BaseHTTPRequestHandler, HTTPStatus, urlparse,
# parse_qs, json, VERSION, all *_service() factories, …) from service_registry.
from service_registry import *  # noqa: F401,F403
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

        # Prometheus scrape endpoint (GoAdvanced Plan 08 Schritt 2).
        # Optional bearer token via BEAGLE_METRICS_BEARER_TOKEN. When unset
        # the endpoint is unauthenticated (suitable for localhost scrape or
        # behind a reverse proxy with network-level ACL).
        if path == "/metrics":
            if METRICS_BEARER_TOKEN:
                auth_header = self.headers.get("Authorization", "") or ""
                expected = f"Bearer {METRICS_BEARER_TOKEN}"
                if not hmac.compare_digest(auth_header, expected):
                    self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})
                    return
            body = prometheus_metrics_service().render_bytes()
            self._write_bytes(
                HTTPStatus.OK,
                body,
                content_type=prometheus_metrics_service().content_type,
            )
            return

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
            payload = build_health_payload()
            try:
                aggregated = health_aggregator_service().run()
            except Exception as exc:  # never fail the health endpoint itself
                aggregated = {
                    "status": "unhealthy",
                    "components": {},
                    "error": f"aggregator_unavailable:{exc}",
                }
            payload["status"] = aggregated.get("status", "healthy")
            payload["components"] = aggregated.get("components", {})
            if "error" in aggregated:
                payload.setdefault("warnings", []).append(aggregated["error"])
            status_code = HTTPStatus.OK
            if HEALTH_503_ON_UNHEALTHY and payload["status"] == "unhealthy":
                status_code = HTTPStatus.SERVICE_UNAVAILABLE
            self._write_json(status_code, payload)
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
