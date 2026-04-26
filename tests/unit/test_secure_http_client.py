"""Tests for core.security.http_client — GoAdvanced Plan 02 Schritt 2.

Verifies that verify=False is NEVER allowed by the secure HTTP client helpers.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from core.security.http_client import (
    SecureSession,
    TLSSecurityError,
    _resolve_verify,
    get,
    post,
)


# ---------------------------------------------------------------------------
# _resolve_verify
# ---------------------------------------------------------------------------


class TestResolveVerify:
    def test_defaults_to_true(self, monkeypatch):
        monkeypatch.delenv("BEAGLE_TLS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("BEAGLE_TLS_INSECURE_OVERRIDE", raising=False)
        assert _resolve_verify() is True

    def test_uses_ca_bundle_from_env(self, monkeypatch):
        monkeypatch.setenv("BEAGLE_TLS_CA_BUNDLE", "/tmp/my-ca.pem")
        monkeypatch.delenv("BEAGLE_TLS_INSECURE_OVERRIDE", raising=False)
        result = _resolve_verify()
        assert result == "/tmp/my-ca.pem"

    def test_insecure_override_returns_false(self, monkeypatch):
        monkeypatch.setenv("BEAGLE_TLS_INSECURE_OVERRIDE", "1")
        result = _resolve_verify()
        assert result is False

    def test_insecure_override_only_triggers_on_exact_1(self, monkeypatch):
        for val in ("true", "yes", "0", ""):
            monkeypatch.setenv("BEAGLE_TLS_INSECURE_OVERRIDE", val)
            monkeypatch.delenv("BEAGLE_TLS_CA_BUNDLE", raising=False)
            assert _resolve_verify() is True


# ---------------------------------------------------------------------------
# Module-level get() / post() helpers
# ---------------------------------------------------------------------------


class TestModuleLevelHelpers:
    def test_get_blocks_verify_false(self):
        with pytest.raises(TLSSecurityError):
            get("https://example.com", verify=False)

    def test_post_blocks_verify_false(self):
        with pytest.raises(TLSSecurityError):
            post("https://example.com", verify=False)

    def test_get_passes_verify_true(self, monkeypatch):
        monkeypatch.delenv("BEAGLE_TLS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("BEAGLE_TLS_INSECURE_OVERRIDE", raising=False)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("requests.get", return_value=mock_resp) as mock_get:
            resp = get("https://example.com")
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs.get("verify") is True
            assert resp is mock_resp

    def test_get_passes_ca_bundle_when_env_set(self, monkeypatch):
        monkeypatch.setenv("BEAGLE_TLS_CA_BUNDLE", "/tmp/custom-ca.pem")
        monkeypatch.delenv("BEAGLE_TLS_INSECURE_OVERRIDE", raising=False)
        mock_resp = MagicMock()
        with patch("requests.get", return_value=mock_resp) as mock_get:
            get("https://example.com")
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs["verify"] == "/tmp/custom-ca.pem"

    def test_get_sets_default_timeout(self, monkeypatch):
        monkeypatch.delenv("BEAGLE_TLS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("BEAGLE_TLS_INSECURE_OVERRIDE", raising=False)
        mock_resp = MagicMock()
        with patch("requests.get", return_value=mock_resp) as mock_get:
            get("https://example.com")
            call_kwargs = mock_get.call_args[1]
            assert "timeout" in call_kwargs

    def test_get_caller_can_override_timeout(self, monkeypatch):
        monkeypatch.delenv("BEAGLE_TLS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("BEAGLE_TLS_INSECURE_OVERRIDE", raising=False)
        mock_resp = MagicMock()
        with patch("requests.get", return_value=mock_resp) as mock_get:
            get("https://example.com", timeout=5)
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs["timeout"] == 5


# ---------------------------------------------------------------------------
# SecureSession
# ---------------------------------------------------------------------------


class TestSecureSession:
    def test_get_blocks_verify_false(self, monkeypatch):
        monkeypatch.delenv("BEAGLE_TLS_INSECURE_OVERRIDE", raising=False)
        sess = SecureSession()
        with pytest.raises(TLSSecurityError):
            sess.get("https://example.com", verify=False)

    def test_post_blocks_verify_false(self, monkeypatch):
        monkeypatch.delenv("BEAGLE_TLS_INSECURE_OVERRIDE", raising=False)
        sess = SecureSession()
        with pytest.raises(TLSSecurityError):
            sess.post("https://example.com", verify=False)

    def test_ca_bundle_kwarg_overrides_env(self, monkeypatch):
        monkeypatch.delenv("BEAGLE_TLS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("BEAGLE_TLS_INSECURE_OVERRIDE", raising=False)
        sess = SecureSession(ca_bundle="/custom/ca.pem")
        mock_resp = MagicMock()
        with patch.object(sess._session, "get", return_value=mock_resp) as mock_get:
            sess.get("https://example.com")
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs["verify"] == "/custom/ca.pem"

    def test_context_manager(self, monkeypatch):
        monkeypatch.delenv("BEAGLE_TLS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("BEAGLE_TLS_INSECURE_OVERRIDE", raising=False)
        with SecureSession() as sess:
            assert isinstance(sess, SecureSession)

    def test_delete_blocks_verify_false(self, monkeypatch):
        monkeypatch.delenv("BEAGLE_TLS_INSECURE_OVERRIDE", raising=False)
        sess = SecureSession()
        with pytest.raises(TLSSecurityError):
            sess.delete("https://example.com", verify=False)
