import socket
import sys
import tempfile
import unittest
from pathlib import Path

SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from ca_manager import ClusterCaService
from cluster_rpc import ClusterRpcError, ClusterRpcService


def free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


class ClusterRpcServiceTests(unittest.TestCase):
    def make_certs(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        ca_service = ClusterCaService(data_dir=Path(temp_dir.name))
        server_bundle = ca_service.issue_node_certificate(
            node_name="node-server",
            subject_alt_names=["DNS:localhost", "IP:127.0.0.1"],
        )
        client_bundle = ca_service.issue_node_certificate(node_name="node-client")
        return ca_service, server_bundle, client_bundle

    def test_rpc_request_requires_valid_client_certificate(self):
        _ca_service, server_bundle, _client_bundle = self.make_certs()
        rpc = ClusterRpcService(node_name="node-server", methods={"ping": lambda params, peer: {"pong": params.get("value")}})
        port = free_port()
        server, thread = rpc.serve_in_thread(
            host="127.0.0.1",
            port=port,
            ca_cert_path=Path(server_bundle["ca_cert_path"]),
            cert_path=Path(server_bundle["cert_path"]),
            key_path=Path(server_bundle["key_path"]),
        )
        try:
            with self.assertRaises(ClusterRpcError):
                ClusterRpcService.request_json(
                    url=f"https://127.0.0.1:{port}/rpc",
                    ca_cert_path=Path(server_bundle["ca_cert_path"]),
                    method="ping",
                    params={"value": "missing-client-cert"},
                    request_id="no-client-cert",
                    timeout=5,
                )
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_rpc_request_succeeds_with_mutual_tls(self):
        _ca_service, server_bundle, client_bundle = self.make_certs()
        rpc = ClusterRpcService(
            node_name="node-server",
            methods={
                "ping": lambda params, peer: {
                    "pong": params.get("value"),
                    "peer_seen": peer.common_name,
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
                params={"value": "hello-cluster"},
                request_id="with-client-cert",
                timeout=5,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["peer_common_name"], "node-client")
        self.assertEqual(payload["served_by"], "node-server")
        self.assertEqual(payload["result"]["pong"], "hello-cluster")
        self.assertEqual(payload["result"]["peer_seen"], "node-client")


if __name__ == "__main__":
    unittest.main()
