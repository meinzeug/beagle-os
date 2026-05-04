from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable


def _run_checked(command: list[str], *, timeout: int = 30) -> str:
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout


class ClusterCaService:
    def __init__(
        self,
        *,
        data_dir: Path,
        openssl_bin: str = "openssl",
        run_command=_run_checked,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._openssl_bin = str(openssl_bin or "openssl")
        self._run_command = run_command

    @staticmethod
    def _sanitize_node_name(value: str) -> str:
        node_name = str(value or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,62}", node_name):
            raise ValueError("invalid cluster node name")
        return node_name

    @staticmethod
    def _normalize_subject_alt_names(subject_alt_names: Iterable[str] | None) -> list[str]:
        normalized: list[str] = []
        for item in subject_alt_names or []:
            text = str(item or "").strip()
            if not text:
                continue
            if not re.fullmatch(r"(DNS|IP):[^,\s]+", text):
                raise ValueError("subjectAltName entries must look like DNS:name or IP:addr")
            normalized.append(text)
        return normalized

    def cluster_dir(self) -> Path:
        path = self._data_dir / "cluster"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ca_dir(self) -> Path:
        path = self.cluster_dir() / "ca"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def nodes_dir(self) -> Path:
        path = self.cluster_dir() / "nodes"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ca_key_path(self) -> Path:
        return self.ca_dir() / "cluster-ca.key"

    def ca_cert_path(self) -> Path:
        return self.ca_dir() / "cluster-ca.crt"

    def ca_serial_path(self) -> Path:
        return self.ca_dir() / "cluster-ca.srl"

    def ensure_ca(self, *, common_name: str = "Beagle Cluster CA", days: int = 3650) -> dict[str, str]:
        key_path = self.ca_key_path()
        cert_path = self.ca_cert_path()
        if key_path.is_file() and cert_path.is_file():
            return {
                "ca_key_path": str(key_path),
                "ca_cert_path": str(cert_path),
            }

        self.ca_dir()
        self._run_command(
            [
                self._openssl_bin,
                "req",
                "-x509",
                "-newkey",
                "rsa:4096",
                "-sha256",
                "-nodes",
                "-subj",
                f"/CN={common_name}",
                "-keyout",
                str(key_path),
                "-out",
                str(cert_path),
                "-days",
                str(int(days)),
                "-addext",
                "basicConstraints=critical,CA:TRUE",
                "-addext",
                "keyUsage=critical,keyCertSign,cRLSign",
            ]
        )
        os.chmod(key_path, 0o600)
        os.chmod(cert_path, 0o644)
        return {
            "ca_key_path": str(key_path),
            "ca_cert_path": str(cert_path),
        }

    def issue_node_certificate(
        self,
        *,
        node_name: str,
        subject_alt_names: Iterable[str] | None = None,
        days: int = 30,
    ) -> dict[str, str]:
        normalized_node_name = self._sanitize_node_name(node_name)
        sans = self._normalize_subject_alt_names(subject_alt_names)
        if f"DNS:{normalized_node_name}" not in sans:
            sans.insert(0, f"DNS:{normalized_node_name}")

        self.ensure_ca()
        node_dir = self.nodes_dir() / normalized_node_name
        node_dir.mkdir(parents=True, exist_ok=True)

        key_path = node_dir / "node.key"
        csr_path = node_dir / "node.csr"
        cert_path = node_dir / "node.crt"
        config_path = node_dir / "openssl-node.cnf"

        config_path.write_text(self._node_openssl_config(normalized_node_name, sans), encoding="utf-8")
        self._run_command(
            [
                self._openssl_bin,
                "req",
                "-new",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(key_path),
                "-out",
                str(csr_path),
                "-config",
                str(config_path),
            ]
        )

        sign_cmd = [
            self._openssl_bin,
            "x509",
            "-req",
            "-in",
            str(csr_path),
            "-CA",
            str(self.ca_cert_path()),
            "-CAkey",
            str(self.ca_key_path()),
            "-out",
            str(cert_path),
            "-days",
            str(int(days)),
            "-sha256",
            "-extfile",
            str(config_path),
            "-extensions",
            "req_ext",
        ]
        serial_path = self.ca_serial_path()
        if serial_path.exists():
            sign_cmd.extend(["-CAserial", str(serial_path)])
        else:
            sign_cmd.extend(["-CAcreateserial", "-CAserial", str(serial_path)])
        self._run_command(sign_cmd)

        os.chmod(key_path, 0o600)
        os.chmod(csr_path, 0o600)
        os.chmod(cert_path, 0o644)
        return {
            "node_name": normalized_node_name,
            "node_dir": str(node_dir),
            "key_path": str(key_path),
            "csr_path": str(csr_path),
            "cert_path": str(cert_path),
            "ca_cert_path": str(self.ca_cert_path()),
        }

    def verify_certificate(self, *, cert_path: Path) -> str:
        return self._run_command(
            [
                self._openssl_bin,
                "verify",
                "-CAfile",
                str(self.ca_cert_path()),
                str(cert_path),
            ]
        ).strip()

    @staticmethod
    def _node_openssl_config(node_name: str, subject_alt_names: list[str]) -> str:
        alt_lines = []
        for index, item in enumerate(subject_alt_names, start=1):
            san_type, san_value = item.split(":", 1)
            alt_lines.append(f"{san_type}.{index} = {san_value}")
        return "\n".join(
            [
                "[req]",
                "distinguished_name = req_distinguished_name",
                "prompt = no",
                "req_extensions = req_ext",
                "",
                "[req_distinguished_name]",
                f"CN = {node_name}",
                "",
                "[req_ext]",
                "basicConstraints = CA:FALSE",
                "keyUsage = digitalSignature, keyEncipherment",
                "extendedKeyUsage = serverAuth, clientAuth",
                "subjectAltName = @alt_names",
                "",
                "[alt_names]",
                *alt_lines,
                "",
            ]
        )


def create_temp_cluster_ca(*, prefix: str = "beagle-cluster-ca-") -> tuple[tempfile.TemporaryDirectory, ClusterCaService]:
    temp_dir = tempfile.TemporaryDirectory(prefix=prefix)
    return temp_dir, ClusterCaService(data_dir=Path(temp_dir.name))
