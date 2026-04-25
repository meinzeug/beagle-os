"""Atomic, locked JSON state persistence helper.

Replaces direct ``path.write_text(json.dumps(...))`` calls across the codebase
with a single implementation that provides:

* **Atomic writes** — write to a sibling temp-file then ``os.replace()`` so a
  crash mid-write never leaves a half-written JSON file.
* **fsync** before rename — guarantees the data hits the storage device.
* **fcntl advisory lock** — prevents concurrent writers from interleaving.
* **Permission enforcement** — ``mode`` is applied after every save (default
  ``0o600`` so state files are not world-readable by accident).
* **default_factory** — if the file doesn't exist yet the factory is called
  to produce the initial state.

Usage::

    store = JsonStateStore(
        Path("/var/lib/beagle/device-registry.json"),
        default_factory=lambda: {"devices": {}},
    )
    data = store.load()
    data["devices"]["x1"] = {...}
    store.save(data)

    # or atomic read-modify-write:
    store.update(lambda d: d["devices"].update({"x1": {...}}))
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable


class JsonStateStore:
    """Thread- and multi-process-safe atomic JSON file store.

    Parameters
    ----------
    path:
        Absolute path to the JSON state file.  The parent directory is
        created automatically on first save.
    default_factory:
        Callable that returns the default state dict when the file does not
        exist yet.  Called with no arguments.
    mode:
        Unix permission bits applied to the file after every save.
        Defaults to ``0o600`` (owner read/write only).
    """

    def __init__(
        self,
        path: Path | str,
        default_factory: Callable[[], Any],
        *,
        mode: int = 0o600,
    ) -> None:
        self._path = Path(path)
        self._default_factory = default_factory
        self._mode = mode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> Any:
        """Load and return the current state.

        Acquires a shared (read) lock while the file is read.  Returns the
        default value if the file does not exist.  Raises ``json.JSONDecodeError``
        if the file exists but contains invalid JSON.
        """
        if not self._path.exists():
            return self._default_factory()
        with open(self._path, "r", encoding="utf-8") as fh:
            fcntl.flock(fh, fcntl.LOCK_SH)
            try:
                return json.load(fh)
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def save(self, data: Any) -> None:
        """Atomically persist *data* to disk.

        Acquires an exclusive lock on the *lock file* (``<path>.lock``) for
        the duration of the write so concurrent callers serialise correctly
        even across processes.  Uses a sibling temp-file + ``os.replace()``
        for atomicity.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        with open(lock_path, "a", encoding="utf-8") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            try:
                self._atomic_write(data)
            finally:
                fcntl.flock(lock_fh, fcntl.LOCK_UN)

    def update(self, mutator: Callable[[Any], None]) -> Any:
        """Read-modify-write under an exclusive lock.

        *mutator* receives the current state dict and may modify it in-place.
        The (possibly mutated) state is then persisted atomically.  Returns
        the final state.

        Example::

            store.update(lambda d: d["devices"].update({"id1": {...}}))
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        with open(lock_path, "a", encoding="utf-8") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            try:
                data = self._read_locked()
                mutator(data)
                self._atomic_write(data)
                return data
            finally:
                fcntl.flock(lock_fh, fcntl.LOCK_UN)

    def exists(self) -> bool:
        """Return True if the backing file exists."""
        return self._path.exists()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_locked(self) -> Any:
        """Read state without acquiring a new lock (caller holds EX lock)."""
        if not self._path.exists():
            return self._default_factory()
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _atomic_write(self, data: Any) -> None:
        """Write *data* to a temp-file then rename into place (no lock acquired)."""
        parent = self._path.parent
        fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=".tmp-" + self._path.name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp_path, self._mode)
            os.replace(tmp_path, self._path)
        except Exception:
            # Clean up temp file if anything goes wrong
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
