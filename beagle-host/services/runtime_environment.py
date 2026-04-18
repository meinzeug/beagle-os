"""Runtime environment helper utilities.

This service owns runtime host resolution and manager certificate pinning
helpers used across multiple host-side services. The control plane keeps thin
wrappers so existing helper signatures stay stable while environment-specific
logic leaves the entrypoint.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import socket
import subprocess
from pathlib import Path
from typing import Any, Callable


class RuntimeEnvironmentService:
    def __init__(
        self,
        *,
        manager_cert_file: Path,
        public_stream_host_raw: str,
        getaddrinfo: Callable[..., Any] | None = None,
        run_subprocess: Callable[..., Any] | None = None,
    ) -> None:
        self._manager_cert_file = Path(manager_cert_file)
        self._public_stream_host_raw = str(public_stream_host_raw or "")
        self._getaddrinfo = getaddrinfo or socket.getaddrinfo
        self._run_subprocess = run_subprocess or subprocess.run
        self._manager_pinned_pubkey_cache: str | None = None

    def resolve_public_stream_host(self, host: str) -> str:
        candidate = str(host or "").strip()
        if not candidate:
            return ""
        # Already an IP literal – return as-is.
        try:
            ipaddress.ip_address(candidate)
            return candidate
        except ValueError:
            pass
        # FQDN with dots (e.g. "myserver.example.com") – keep the name so that
        # public TLS certs (Let's Encrypt) remain valid for clients.
        if "." in candidate:
            return candidate
        # Bare hostname (e.g. "beagleserver") – resolve to IP so that thin
        # clients without a matching DNS entry can still connect.
        try:
            infos = self._getaddrinfo(
                candidate,
                None,
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror:
            return candidate
        for item in infos:
            ip = str(item[4][0]).strip()
            try:
                if ip and not ipaddress.ip_address(ip).is_loopback:
                    return ip
            except ValueError:
                pass
        return candidate

    def current_public_stream_host(self) -> str:
        return self.resolve_public_stream_host(self._public_stream_host_raw)

    def manager_pinned_pubkey(self) -> str:
        if self._manager_pinned_pubkey_cache is not None:
            return self._manager_pinned_pubkey_cache
        if not self._manager_cert_file.is_file():
            self._manager_pinned_pubkey_cache = ""
            return ""
        try:
            pubkey = self._run_subprocess(
                ["openssl", "x509", "-in", str(self._manager_cert_file), "-pubkey", "-noout"],
                check=True,
                capture_output=True,
                text=False,
            ).stdout
            der = self._run_subprocess(
                ["openssl", "pkey", "-pubin", "-outform", "der"],
                check=True,
                input=pubkey,
                capture_output=True,
                text=False,
            ).stdout
        except (FileNotFoundError, subprocess.CalledProcessError):
            self._manager_pinned_pubkey_cache = ""
            return ""
        digest = hashlib.sha256(der).digest()
        self._manager_pinned_pubkey_cache = "sha256//" + base64.b64encode(digest).decode("ascii")
        return self._manager_pinned_pubkey_cache
