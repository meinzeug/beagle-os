#!/usr/bin/env python3
from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from ca_manager import create_temp_cluster_ca  # type: ignore
from cluster_rpc import ClusterRpcService  # type: ignore


def free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def main() -> int:
    temp_dir, ca_service = create_temp_cluster_ca()
    try:
        server_bundle = ca_service.issue_node_certificate(
            node_name="srv1-local",
            subject_alt_names=["DNS:localhost", "IP:127.0.0.1"],
        )
        client_bundle = ca_service.issue_node_certificate(node_name="node-client", subject_alt_names=["DNS:node-client"])

        rpc = ClusterRpcService(
            node_name="srv1-local",
            methods={
                "ping": lambda params, peer: {
                    "pong": params.get("value"),
                    "peer": peer.common_name,
                }
            },
        )
        port = free_port()
        server, thread = rpc.serve_in_thread(
            host="127.0.0.1",
            port=port,
            ca_cert_path=Path(server_bundle["ca_cert_path"]),
            cert_path=Path(server_bundle["cert_path"]),
            key_path=Path(server_bundle["key_path"]),
        )
        try:
            payload = ClusterRpcService.request_json(
                url=f"https://127.0.0.1:{port}/rpc",
                ca_cert_path=Path(server_bundle["ca_cert_path"]),
                cert_path=Path(client_bundle["cert_path"]),
                key_path=Path(client_bundle["key_path"]),
                method="ping",
                params={"value": "cluster-ok"},
                request_id="smoke-1",
                timeout=5,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            if payload.get("ok") is not True:
                return 1
            if payload.get("peer_common_name") != "node-client":
                return 1
            if (payload.get("result") or {}).get("pong") != "cluster-ok":
                return 1
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
    finally:
        temp_dir.cleanup()

    print("CLUSTER_RPC_SMOKE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
