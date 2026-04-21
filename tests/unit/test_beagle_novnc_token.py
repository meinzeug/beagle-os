"""Unit tests for the BeagleTokenFile websockify token plugin."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

# Make the bin directory importable (plugin lives there for deployment)
_BIN_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "bin"
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))

import beagle_novnc_token as module  # noqa: E402

BeagleTokenFile = module.BeagleTokenFile


@pytest.fixture()
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "console-tokens.json"


@pytest.fixture()
def plugin(store_path: Path) -> BeagleTokenFile:
    return BeagleTokenFile(str(store_path))


def _write_entry(store_path: Path, token: str, host: str, port: int, *, created_at: float | None = None, used: bool = False) -> None:
    store: dict = {}
    if store_path.exists():
        store = json.loads(store_path.read_text())
    store[token] = {
        "host": host,
        "port": port,
        "created_at": created_at if created_at is not None else time.time(),
        "used": used,
    }
    import os
    store_path.write_text(json.dumps(store))
    os.chmod(store_path, 0o600)


class TestBeagleTokenFileLookup:
    def test_valid_token_returns_host_port(self, plugin: BeagleTokenFile, store_path: Path) -> None:
        _write_entry(store_path, "abc123", "127.0.0.1", 5901)
        result = plugin.lookup("abc123")
        assert result == ["127.0.0.1", "5901"]

    def test_unknown_token_returns_none(self, plugin: BeagleTokenFile, store_path: Path) -> None:
        assert plugin.lookup("does-not-exist") is None

    def test_expired_token_returns_none(self, plugin: BeagleTokenFile, store_path: Path) -> None:
        old_ts = time.time() - 60  # 60 seconds ago, TTL is 30s
        _write_entry(store_path, "expired_tok", "127.0.0.1", 5901, created_at=old_ts)
        assert plugin.lookup("expired_tok") is None

    def test_used_token_returns_none(self, plugin: BeagleTokenFile, store_path: Path) -> None:
        _write_entry(store_path, "used_tok", "127.0.0.1", 5901, used=True)
        assert plugin.lookup("used_tok") is None

    def test_token_marked_used_after_first_lookup(self, plugin: BeagleTokenFile, store_path: Path) -> None:
        _write_entry(store_path, "single_use", "127.0.0.1", 5902)
        # First lookup succeeds
        result = plugin.lookup("single_use")
        assert result == ["127.0.0.1", "5902"]
        # Second lookup must fail (token is now marked used)
        result2 = plugin.lookup("single_use")
        assert result2 is None

    def test_expired_entries_pruned_from_store(self, plugin: BeagleTokenFile, store_path: Path) -> None:
        old_ts = time.time() - 60
        _write_entry(store_path, "stale", "127.0.0.1", 5901, created_at=old_ts)
        plugin.lookup("stale")  # triggers pruning
        store = json.loads(store_path.read_text())
        assert "stale" not in store

    def test_missing_store_file_returns_none(self, plugin: BeagleTokenFile) -> None:
        assert plugin.lookup("anything") is None

    def test_returns_correct_host_and_port(self, plugin: BeagleTokenFile, store_path: Path) -> None:
        _write_entry(store_path, "tok2", "192.168.1.50", 5999)
        result = plugin.lookup("tok2")
        assert result is not None
        assert result[0] == "192.168.1.50"
        assert result[1] == "5999"
