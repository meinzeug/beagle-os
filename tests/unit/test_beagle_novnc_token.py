"""Unit tests for the BeagleTokenFile websockify token plugin."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Make the bin directory importable (plugin lives there for deployment)
_BIN_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "bin"
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))

import beagle_novnc_token as module  # noqa: E402

BeagleTokenFile = module.BeagleTokenFile


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
    store_path.write_text(json.dumps(store))
    os.chmod(store_path, 0o600)


class TestBeagleTokenFileLookup(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store_path = Path(self._tmp.name) / "console-tokens.json"
        self.plugin = BeagleTokenFile(str(self.store_path))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_valid_token_returns_host_port(self) -> None:
        _write_entry(self.store_path, "abc123", "127.0.0.1", 5901)
        result = self.plugin.lookup("abc123")
        self.assertEqual(result, ["127.0.0.1", "5901"])

    def test_unknown_token_returns_none(self) -> None:
        self.assertIsNone(self.plugin.lookup("does-not-exist"))

    def test_expired_token_returns_none(self) -> None:
        old_ts = time.time() - 60  # 60 seconds ago, TTL is 30s
        _write_entry(self.store_path, "expired_tok", "127.0.0.1", 5901, created_at=old_ts)
        self.assertIsNone(self.plugin.lookup("expired_tok"))

    def test_used_token_returns_none(self) -> None:
        _write_entry(self.store_path, "used_tok", "127.0.0.1", 5901, used=True)
        self.assertIsNone(self.plugin.lookup("used_tok"))

    def test_token_marked_used_after_first_lookup(self) -> None:
        _write_entry(self.store_path, "single_use", "127.0.0.1", 5902)
        result = self.plugin.lookup("single_use")
        self.assertEqual(result, ["127.0.0.1", "5902"])
        result2 = self.plugin.lookup("single_use")
        self.assertIsNone(result2)

    def test_expired_entries_pruned_from_store(self) -> None:
        old_ts = time.time() - 60
        _write_entry(self.store_path, "stale", "127.0.0.1", 5901, created_at=old_ts)
        self.plugin.lookup("stale")  # triggers pruning
        store = json.loads(self.store_path.read_text())
        self.assertNotIn("stale", store)

    def test_missing_store_file_returns_none(self) -> None:
        self.assertIsNone(self.plugin.lookup("anything"))

    def test_returns_correct_host_and_port(self) -> None:
        _write_entry(self.store_path, "tok2", "192.168.1.50", 5999)
        result = self.plugin.lookup("tok2")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "192.168.1.50")
        self.assertEqual(result[1], "5999")


if __name__ == "__main__":
    unittest.main()
