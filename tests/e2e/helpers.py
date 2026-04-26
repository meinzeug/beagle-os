"""Shared helpers for E2E tests.

Import this module (not conftest) from test files.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.request
import urllib.error
from typing import Any

import pytest

_TOKEN = os.environ.get("BEAGLE_E2E_TOKEN", "")
_BASE_URL = os.environ.get("BEAGLE_E2E_URL", "https://srv1.beagle-os.com:8443").rstrip("/")

requires_e2e = pytest.mark.skipif(
    not _TOKEN,
    reason="BEAGLE_E2E_TOKEN not set — skipping live E2E tests",
)


class E2EHttpClient:
    """Thin HTTPS client for the Beagle control-plane API (stdlib only)."""

    def __init__(self, base_url: str, token: str, timeout: float = 15.0):
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._ctx = ssl.create_default_context()
        if os.environ.get("BEAGLE_E2E_INSECURE", "").strip() == "1":
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl.CERT_NONE

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        url = f"{self._base_url}{path}"
        data: bytes | None = None
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(data))

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=self._timeout) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw) if raw else {}
            except Exception:
                return exc.code, {"error": raw.decode(errors="replace")}

    def get(self, path: str) -> tuple[int, dict[str, Any]]:
        return self._request("GET", path)

    def post(self, path: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        return self._request("POST", path, body)

    def delete(self, path: str) -> tuple[int, dict[str, Any]]:
        return self._request("DELETE", path)
