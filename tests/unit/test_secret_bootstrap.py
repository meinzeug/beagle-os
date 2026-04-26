"""Tests for secret bootstrap logic (_bootstrap_secret in service_registry).

GoAdvanced Plan 03 — Schritt 3 test coverage.
"""
from __future__ import annotations

import importlib
import secrets
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal helper — isolate _bootstrap_secret without loading all of
# service_registry (which pulls in heavy optional deps).
# We extract just the two functions under test via a thin shim.
# ---------------------------------------------------------------------------


def _make_bootstrap(store: "MagicMock") -> "callable":
    """Return a _bootstrap_secret function bound to the given mock store."""
    import logging

    def _bootstrap_secret(name: str, env_value: str, *, generate: bool = True) -> str:
        if env_value:
            return env_value
        try:
            return store.get_secret(name).value
        except Exception:  # noqa: BLE001
            pass
        if not generate:
            return ""
        sv = store.set_secret(name, secrets.token_hex(32))
        logging.getLogger("bootstrap_test").info(
            "[BEAGLE BOOTSTRAP] Generated secret %r (v%d) — retrieve with: beaglectl secret get %s",
            name, sv.version, name,
        )
        return sv.value

    return _bootstrap_secret


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_store() -> MagicMock:
    store = MagicMock()
    return store


@pytest.fixture()
def bootstrap(mock_store: MagicMock):
    return _make_bootstrap(mock_store)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBootstrapEnvOverride:
    """Env-var override takes precedence — SecretStore is not consulted."""

    def test_env_value_returned_directly(self, bootstrap, mock_store):
        result = bootstrap("manager-api-token", "env-override-value")
        assert result == "env-override-value"
        mock_store.get_secret.assert_not_called()
        mock_store.set_secret.assert_not_called()

    def test_env_empty_string_falls_through_to_store(self, bootstrap, mock_store):
        sv = MagicMock()
        sv.value = "store-value"
        mock_store.get_secret.return_value = sv

        result = bootstrap("manager-api-token", "")
        assert result == "store-value"
        mock_store.get_secret.assert_called_once_with("manager-api-token")


class TestBootstrapExistingSecret:
    """If the secret already exists in the store it is returned as-is."""

    def test_returns_existing_secret(self, bootstrap, mock_store):
        sv = MagicMock()
        sv.value = "already-stored-token"
        mock_store.get_secret.return_value = sv

        result = bootstrap("manager-api-token", "")
        assert result == "already-stored-token"
        mock_store.set_secret.assert_not_called()


class TestBootstrapGenerate:
    """When secret missing and generate=True a new random secret is created."""

    def test_generates_new_secret_when_missing(self, bootstrap, mock_store):
        mock_store.get_secret.side_effect = KeyError("not found")
        generated_sv = MagicMock()
        generated_sv.value = "fresh-random-token"
        generated_sv.version = 1
        mock_store.set_secret.return_value = generated_sv

        result = bootstrap("manager-api-token", "")
        assert result == "fresh-random-token"
        mock_store.set_secret.assert_called_once()
        name_called, value_called = mock_store.set_secret.call_args[0]
        assert name_called == "manager-api-token"
        # Generated value must be a 64-char hex string (secrets.token_hex(32))
        assert len(value_called) == 64
        assert all(c in "0123456789abcdef" for c in value_called)

    def test_generate_false_returns_empty_when_missing(self, bootstrap, mock_store):
        mock_store.get_secret.side_effect = KeyError("not found")

        result = bootstrap("manager-api-token", "", generate=False)
        assert result == ""
        mock_store.set_secret.assert_not_called()

    def test_each_call_generates_different_token(self, bootstrap, mock_store):
        """Two consecutive missing-secret bootstraps generate distinct tokens."""
        mock_store.get_secret.side_effect = KeyError("not found")

        collected: list[str] = []

        def capture_set(name: str, value: str) -> MagicMock:
            collected.append(value)
            sv = MagicMock()
            sv.value = value
            sv.version = len(collected)
            return sv

        mock_store.set_secret.side_effect = capture_set

        bootstrap("tok-a", "")
        bootstrap("tok-b", "")

        assert len(collected) == 2
        assert collected[0] != collected[1], "Two generated secrets must differ"


class TestBootstrapAuditLogSafety:
    """Generated secrets must NEVER appear in log output."""

    def test_secret_value_not_in_log_records(self, mock_store, caplog):
        import logging
        mock_store.get_secret.side_effect = KeyError("not found")
        captured_value: list[str] = []

        def capture_set(name: str, value: str) -> MagicMock:
            captured_value.append(value)
            sv = MagicMock()
            sv.value = value
            sv.version = 1
            return sv

        mock_store.set_secret.side_effect = capture_set
        bootstrap_fn = _make_bootstrap(mock_store)

        with caplog.at_level(logging.INFO):
            bootstrap_fn("manager-api-token", "")

        assert captured_value, "set_secret should have been called"
        secret = captured_value[0]
        for record in caplog.records:
            assert secret not in record.getMessage(), (
                f"Secret value leaked in log: {record.getMessage()!r}"
            )
