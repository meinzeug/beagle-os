"""Custom websockify token plugin for Beagle noVNC console sessions.

Design:
  - Tokens are single-use and expire 30 seconds after creation.
  - The token store is a JSON file at the path passed as --token-source.
  - Format:
      { "<token>": {"host": "...", "port": N, "created_at": <unix_ts>, "used": false}, ... }
  - On lookup:  validates TTL, marks token used, returns [host, port_str].
  - Expired and used entries are cleaned up opportunistically on each load.

Usage in systemd unit:
    websockify --token-plugin beagle_novnc_token.BeagleTokenFile \
               --token-source /etc/beagle/novnc/console-tokens.json ...

The module must be importable – set PYTHONPATH to the directory containing this
file (renamed to beagle_novnc_token.py at deployment) in the systemd unit.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

TOKEN_TTL_SECONDS: float = 30.0


class BasePlugin:  # minimal shim so tests can import without websockify installed
    def __init__(self, src: str) -> None:
        self.source = src

    def lookup(self, token: str) -> list[str] | None:  # pragma: no cover
        return None


try:
    from websockify.token_plugins import BasePlugin  # type: ignore[no-redef]
except ImportError:
    pass  # BasePlugin shim above is used in unit tests / CI


class BeagleTokenFile(BasePlugin):
    """Single-use, TTL-based websockify token plugin for Beagle console sessions."""

    def __init__(self, src: str) -> None:
        super().__init__(src)
        self._store_path = Path(str(src or "").strip())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_store(self) -> dict[str, Any]:
        if not self._store_path.exists():
            return {}
        try:
            with self._store_path.open("r", encoding="utf-8", errors="ignore") as fh:
                fcntl.flock(fh, fcntl.LOCK_SH)
                try:
                    loaded = json.load(fh)
                finally:
                    fcntl.flock(fh, fcntl.LOCK_UN)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}

    def _save_store(self, store: dict[str, Any]) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        dir_fd = os.open(str(self._store_path.parent), os.O_RDONLY)
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=self._store_path.parent, suffix=".tmp"
            )
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as fh:
                    fcntl.flock(fh, fcntl.LOCK_EX)
                    try:
                        json.dump(store, fh, indent=2)
                        fh.flush()
                        os.fsync(fd)
                    finally:
                        fcntl.flock(fh, fcntl.LOCK_UN)
                os.close(fd)
                fd = -1
                os.replace(tmp_path, self._store_path)
                os.fsync(dir_fd)
            except Exception:
                if fd >= 0:
                    os.close(fd)
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        finally:
            os.close(dir_fd)

    @staticmethod
    def _is_expired(entry: dict[str, Any]) -> bool:
        created_at = float(entry.get("created_at") or 0.0)
        return (time.time() - created_at) > TOKEN_TTL_SECONDS

    @staticmethod
    def _is_used(entry: dict[str, Any]) -> bool:
        return bool(entry.get("used"))

    # ------------------------------------------------------------------
    # Public API (websockify calls this)
    # ------------------------------------------------------------------

    def lookup(self, token: str) -> list[str] | None:
        """Return [host, port_str] for a valid, unused, non-expired token.

        The token is atomically marked as used on first successful lookup.
        Expired and used entries are pruned from the store on each call.
        """
        store = self._load_store()
        now = time.time()

        # Prune stale entries
        store = {
            t: e
            for t, e in store.items()
            if not self._is_used(e) and not self._is_expired(e)
        }

        entry = store.get(str(token or "").strip())
        if entry is None:
            # Persist pruned store even if token not found
            self._save_store(store)
            return None

        host = str(entry.get("host") or "").strip()
        port = int(entry.get("port") or 0)
        if not host or port <= 0:
            self._save_store(store)
            return None

        # Mark as used (single-use enforcement)
        entry = dict(entry)
        entry["used"] = True
        store[str(token)] = entry
        self._save_store(store)

        return [host, str(port)]
