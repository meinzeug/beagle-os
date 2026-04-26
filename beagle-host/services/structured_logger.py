"""Structured logging helper.

GoAdvanced Plan 08 Schritt 3+4.

Emits one JSON object per line on stdout (or any writable stream). Required
fields are ``timestamp``, ``level``, ``service``, ``event``. Arbitrary
key/value pairs may be added per call.

A per-thread context allows callers to set request-scoped fields once
(e.g. ``request_id``, ``user_id``) and have them merged into every log
emitted while handling that request::

    log = StructuredLogger(service="control_plane")
    with log.context(request_id="abc-123", user="dennis"):
        log.info("vm.start", vm_id=42)
    # => {"timestamp":"...","level":"info","service":"control_plane",
    #     "event":"vm.start","request_id":"abc-123","user":"dennis","vm_id":42}

Design notes:

- Stdlib only; no logging.* dependency to keep this trivially testable
  and to avoid surprises with third-party log handlers.
- Atomic write: a single ``stream.write(line)`` per emit. Most stdio
  streams in CPython hold the GIL during a write, so concurrent writers
  do not interleave bytes within one line. A lock is taken regardless
  for safety on non-stdout streams.
- Back-compat: the ``log_message`` helper accepts an arbitrary string
  (mirroring ``BaseHTTPRequestHandler.log_message``) so we can swap the
  built-in HTTP server logger without rewriting call sites.
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import io
import json
import sys
import threading
from typing import Any, Iterator


_VALID_LEVELS = ("debug", "info", "warn", "error")


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class StructuredLogger:
    """JSON-line logger with thread-local context."""

    def __init__(
        self,
        *,
        service: str,
        stream: io.TextIOBase | None = None,
        utcnow: callable = _utcnow_iso,
        min_level: str = "debug",
    ) -> None:
        if not service:
            raise ValueError("service is required")
        if min_level not in _VALID_LEVELS:
            raise ValueError(f"min_level must be one of {_VALID_LEVELS}")
        self._service = service
        self._stream = stream if stream is not None else sys.stdout
        self._utcnow = utcnow
        self._min_level_idx = _VALID_LEVELS.index(min_level)
        self._lock = threading.Lock()
        self._tls = threading.local()

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    def _ctx(self) -> dict[str, Any]:
        if not hasattr(self._tls, "stack"):
            self._tls.stack = [{}]
        return self._tls.stack[-1]

    @contextlib.contextmanager
    def context(self, **fields: Any) -> Iterator[dict[str, Any]]:
        if not hasattr(self._tls, "stack"):
            self._tls.stack = [{}]
        merged = {**self._ctx(), **fields}
        self._tls.stack.append(merged)
        try:
            yield merged
        finally:
            self._tls.stack.pop()

    def bind(self, **fields: Any) -> None:
        """Permanently merge fields into the current context (no scope)."""
        if not hasattr(self._tls, "stack"):
            self._tls.stack = [{}]
        self._tls.stack[-1] = {**self._ctx(), **fields}

    def clear(self) -> None:
        """Reset the per-thread context."""
        self._tls.stack = [{}]

    # ------------------------------------------------------------------
    # Emit
    # ------------------------------------------------------------------

    def _emit(self, level: str, event: str, fields: dict[str, Any]) -> None:
        if _VALID_LEVELS.index(level) < self._min_level_idx:
            return
        record = {
            "timestamp": self._utcnow(),
            "level": level,
            "service": self._service,
            "event": str(event),
        }
        ctx = self._ctx()
        if ctx:
            record.update(ctx)
        if fields:
            record.update(fields)
        try:
            line = json.dumps(record, default=_json_default, ensure_ascii=False)
        except Exception as exc:  # pragma: no cover - dump failure path
            line = json.dumps({
                "timestamp": self._utcnow(),
                "level": "error",
                "service": self._service,
                "event": "log.encode_failed",
                "error": str(exc),
                "original_event": str(event),
            })
        with self._lock:
            self._stream.write(line + "\n")
            try:
                self._stream.flush()
            except Exception:
                pass

    def debug(self, event: str, **fields: Any) -> None:
        self._emit("debug", event, fields)

    def info(self, event: str, **fields: Any) -> None:
        self._emit("info", event, fields)

    def warn(self, event: str, **fields: Any) -> None:
        self._emit("warn", event, fields)

    def error(self, event: str, **fields: Any) -> None:
        self._emit("error", event, fields)

    # ------------------------------------------------------------------
    # Compat shim for BaseHTTPRequestHandler.log_message
    # ------------------------------------------------------------------

    def log_message(self, fmt: str, *args: Any) -> None:
        """Drop-in replacement for stdlib HTTP server access logs.

        Encodes the rendered message as a single field so existing greps
        (``journalctl | grep " 200 "``) keep working.
        """
        try:
            message = fmt % args if args else fmt
        except Exception:
            message = fmt
        self.info("http.access", message=message)


def _json_default(value: Any) -> Any:
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.hex()
    return repr(value)
