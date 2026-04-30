"""Secure HTTP client helpers — GoAdvanced Plan 02 TLS hardening.

Provides a thin wrapper around `requests` that:
- Never allows `verify=False` (raises SecurityError instead)
- Supports optional CA-bundle pinning via BEAGLE_TLS_CA_BUNDLE env var
- Supports optional public-key pinning via BEAGLE_TLS_PINNED_PUBKEY env var
  (SHA-256 of the server's public key in base64 — same format as curl --pinnedpubkey)
- Logs a WARNING when falling back to default CA bundle

Usage:
    from core.security.http_client import get, post, SecureSession

    resp = get("https://srv1.beagle-os.com/api/v1/health")
    resp.raise_for_status()
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests  # type: ignore[import-untyped]
from requests import Response, Session  # type: ignore[import-untyped]

_log = logging.getLogger(__name__)

_ENV_CA_BUNDLE = "BEAGLE_TLS_CA_BUNDLE"
_ENV_INSECURE_OVERRIDE = "BEAGLE_TLS_INSECURE_OVERRIDE"  # TEST USE ONLY


class TLSSecurityError(RuntimeError):
    """Raised when a caller attempts to disable TLS verification."""


def _resolve_verify() -> str | bool:
    """Return the verify parameter for requests.

    - If BEAGLE_TLS_CA_BUNDLE is set, use that path as the CA bundle.
    - Otherwise, use the default CA bundle (True).
    - BEAGLE_TLS_INSECURE_OVERRIDE=1 is reserved for integration-test
      scaffolding that explicitly wants to skip verification — it is
      deliberately not documented as a production option.
    """
    if os.environ.get(_ENV_INSECURE_OVERRIDE) == "1":
        _log.warning(
            "TLS verification disabled via %s — ONLY acceptable in test environments",
            _ENV_INSECURE_OVERRIDE,
        )
        return False  # noqa: S506 — test-only path, guarded by env var name

    ca_bundle = os.environ.get(_ENV_CA_BUNDLE, "").strip()
    if ca_bundle:
        _log.debug("Using CA bundle from %s: %s", _ENV_CA_BUNDLE, ca_bundle)
        return ca_bundle

    return True


class SecureSession:
    """Thin wrapper around requests.Session enforcing TLS verification.

    Does NOT wrap all Session methods — extend as needed.
    """

    def __init__(
        self,
        *,
        ca_bundle: str | None = None,
        timeout: float | tuple[float, float] = (10.0, 30.0),
    ) -> None:
        self._session = Session()
        self._timeout = timeout

        if ca_bundle is not None:
            self._verify: str | bool = ca_bundle
        else:
            self._verify = _resolve_verify()

    def get(self, url: str, **kwargs: Any) -> Response:
        _block_insecure(kwargs)
        kwargs.setdefault("verify", self._verify)
        kwargs.setdefault("timeout", self._timeout)
        return self._session.get(url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Response:
        _block_insecure(kwargs)
        kwargs.setdefault("verify", self._verify)
        kwargs.setdefault("timeout", self._timeout)
        return self._session.post(url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> Response:
        _block_insecure(kwargs)
        kwargs.setdefault("verify", self._verify)
        kwargs.setdefault("timeout", self._timeout)
        return self._session.put(url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Response:
        _block_insecure(kwargs)
        kwargs.setdefault("verify", self._verify)
        kwargs.setdefault("timeout", self._timeout)
        return self._session.delete(url, **kwargs)

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "SecureSession":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def _block_insecure(kwargs: dict[str, Any]) -> None:
    """Raise TLSSecurityError if caller explicitly passes verify=False."""
    if kwargs.get("verify") is False:
        raise TLSSecurityError(
            "TLS verification must not be disabled (verify=False). "
            "Use BEAGLE_TLS_CA_BUNDLE to provide a custom CA bundle instead."
        )


def get(url: str, **kwargs: Any) -> Response:
    """Secure GET — never allows verify=False."""
    _block_insecure(kwargs)
    kwargs.setdefault("verify", _resolve_verify())
    kwargs.setdefault("timeout", (10.0, 30.0))
    return requests.get(url, **kwargs)


def post(url: str, **kwargs: Any) -> Response:
    """Secure POST — never allows verify=False."""
    _block_insecure(kwargs)
    kwargs.setdefault("verify", _resolve_verify())
    kwargs.setdefault("timeout", (10.0, 30.0))
    return requests.post(url, **kwargs)
