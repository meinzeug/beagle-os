import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from ca_manager import ClusterCaService


class ClusterCaServiceTests(unittest.TestCase):
    def make_service(self) -> tuple[tempfile.TemporaryDirectory, ClusterCaService]:
        temp_dir = tempfile.TemporaryDirectory()
        service = ClusterCaService(data_dir=Path(temp_dir.name))
        return temp_dir, service

    def test_ensure_ca_creates_ca_key_and_cert(self):
        temp_dir, service = self.make_service()
        self.addCleanup(temp_dir.cleanup)

        payload = service.ensure_ca()

        self.assertTrue(Path(payload["ca_key_path"]).is_file())
        self.assertTrue(Path(payload["ca_cert_path"]).is_file())

    def test_issue_node_certificate_signs_join_certificate(self):
        temp_dir, service = self.make_service()
        self.addCleanup(temp_dir.cleanup)

        bundle = service.issue_node_certificate(
            node_name="node-a",
            subject_alt_names=["DNS:localhost", "IP:127.0.0.1"],
        )

        self.assertTrue(Path(bundle["key_path"]).is_file())
        self.assertTrue(Path(bundle["csr_path"]).is_file())
        self.assertTrue(Path(bundle["cert_path"]).is_file())
        self.assertIn("OK", service.verify_certificate(cert_path=Path(bundle["cert_path"])))

        cert_text = subprocess.run(
            ["openssl", "x509", "-in", bundle["cert_path"], "-noout", "-text"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertIn("DNS:node-a", cert_text)
        self.assertIn("DNS:localhost", cert_text)
        self.assertIn("IP Address:127.0.0.1", cert_text)

    def test_issue_node_certificate_rejects_invalid_node_name(self):
        temp_dir, service = self.make_service()
        self.addCleanup(temp_dir.cleanup)

        with self.assertRaises(ValueError):
            service.issue_node_certificate(node_name="bad node")


if __name__ == "__main__":
    unittest.main()
