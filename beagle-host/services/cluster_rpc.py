from __future__ import annotations

import json
import ssl
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib import error, request


class ClusterRpcError(RuntimeError):
    pass


@dataclass
class ClusterRpcPeer:
    common_name: str
    certificate: dict[str, Any]


def _peer_common_name(cert: dict[str, Any]) -> str:
    for part in cert.get("subject", []):
        for key, value in part:
            if key == "commonName":
                return str(value or "")
    return ""


def build_server_ssl_context(*, ca_cert_path: Path, cert_path: Path, key_path: Path) -> ssl.SSLContext:
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = False
    context.load_verify_locations(cafile=str(ca_cert_path))
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    context.set_alpn_protocols(["h2", "http/1.1"])
    return context


def build_client_ssl_context(
    *,
    ca_cert_path: Path,
    cert_path: Path | None = None,
    key_path: Path | None = None,
    check_hostname: bool = True,
) -> ssl.SSLContext:
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca_cert_path))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = bool(check_hostname)
    if cert_path and key_path:
        context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    context.set_alpn_protocols(["h2", "http/1.1"])
    return context


class ClusterRpcService:
    def __init__(
        self,
        *,
        node_name: str,
        methods: dict[str, Callable[[dict[str, Any], ClusterRpcPeer], Any]] | None = None,
    ) -> None:
        self._node_name = str(node_name or "cluster-node")
        self._methods = dict(methods or {})

    def register_method(self, name: str, handler: Callable[[dict[str, Any], ClusterRpcPeer], Any]) -> None:
        method_name = str(name or "").strip()
        if not method_name:
            raise ValueError("cluster rpc method name is required")
        self._methods[method_name] = handler

    def create_server(
        self,
        *,
        host: str,
        port: int,
        ca_cert_path: Path,
        cert_path: Path,
        key_path: Path,
    ) -> ThreadingHTTPServer:
        service = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "BeagleClusterRpc/0.1"

            def log_message(self, _format: str, *args: Any) -> None:
                return None

            def _write_json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:
                if self.path != "/rpc":
                    self._write_json(404, {"error": "not_found"})
                    return
                try:
                    content_length = int(self.headers.get("Content-Length") or "0")
                except ValueError:
                    content_length = 0
                raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
                try:
                    payload = json.loads(raw_body.decode("utf-8"))
                except json.JSONDecodeError:
                    self._write_json(400, {"error": "invalid_json"})
                    return
                method_name = str(payload.get("method") or "").strip()
                params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
                request_id = payload.get("request_id")
                handler = service._methods.get(method_name)
                if handler is None:
                    self._write_json(404, {"error": "unknown_method", "request_id": request_id})
                    return
                connection = getattr(self, "connection", None)
                cert = connection.getpeercert() if connection is not None else {}
                peer = ClusterRpcPeer(common_name=_peer_common_name(cert or {}), certificate=cert or {})
                try:
                    result = handler(params, peer)
                except Exception as exc:
                    self._write_json(
                        500,
                        {
                            "ok": False,
                            "error": str(exc),
                            "request_id": request_id,
                            "served_by": service._node_name,
                        },
                    )
                    return
                self._write_json(
                    200,
                    {
                        "ok": True,
                        "result": result,
                        "request_id": request_id,
                        "served_by": service._node_name,
                        "peer_common_name": peer.common_name,
                    },
                )

        server = ThreadingHTTPServer((host, int(port)), Handler)
        server.socket = build_server_ssl_context(
            ca_cert_path=ca_cert_path,
            cert_path=cert_path,
            key_path=key_path,
        ).wrap_socket(server.socket, server_side=True)
        return server

    def serve_in_thread(
        self,
        *,
        host: str,
        port: int,
        ca_cert_path: Path,
        cert_path: Path,
        key_path: Path,
    ) -> tuple[ThreadingHTTPServer, threading.Thread]:
        server = self.create_server(
            host=host,
            port=port,
            ca_cert_path=ca_cert_path,
            cert_path=cert_path,
            key_path=key_path,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    @staticmethod
    def request_json(
        *,
        url: str,
        ca_cert_path: Path,
        cert_path: Path | None = None,
        key_path: Path | None = None,
        method: str,
        params: dict[str, Any] | None = None,
        request_id: str | None = None,
        timeout: int = 5,
        check_hostname: bool = True,
    ) -> dict[str, Any]:
        body = json.dumps(
            {
                "method": str(method or "").strip(),
                "params": params or {},
                "request_id": request_id,
            }
        ).encode("utf-8")
        req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        context = build_client_ssl_context(
            ca_cert_path=ca_cert_path,
            cert_path=cert_path,
            key_path=key_path,
            check_hostname=check_hostname,
        )
        try:
            with request.urlopen(req, timeout=timeout, context=context) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise ClusterRpcError(f"cluster rpc http error {exc.code}: {body_text}") from exc
        except Exception as exc:
            raise ClusterRpcError(str(exc)) from exc
