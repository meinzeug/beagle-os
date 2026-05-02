"""Tests for StructuredLogger.

GoAdvanced Plan 08 Schritt 3+4.
"""
from __future__ import annotations

import io
import json
import os
import sys
import threading

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "beagle-host", "services"))

from structured_logger import StructuredLogger  # noqa: E402


def _records(buf: io.StringIO) -> list[dict]:
    lines = [l for l in buf.getvalue().splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


def _make(level: str = "debug") -> tuple[StructuredLogger, io.StringIO]:
    buf = io.StringIO()
    log = StructuredLogger(
        service="test",
        stream=buf,
        utcnow=lambda: "2026-04-26T00:00:00.000000Z",
        min_level=level,
    )
    return log, buf


def test_basic_info():
    log, buf = _make()
    log.info("hello", count=3)
    [rec] = _records(buf)
    assert rec == {
        "timestamp": "2026-04-26T00:00:00.000000Z",
        "level": "info",
        "service": "test",
        "event": "hello",
        "count": 3,
    }


def test_all_levels_emit():
    log, buf = _make()
    log.debug("d")
    log.info("i")
    log.warn("w")
    log.error("e")
    levels = [r["level"] for r in _records(buf)]
    assert levels == ["debug", "info", "warn", "error"]


def test_min_level_filters():
    log, buf = _make(level="warn")
    log.debug("d")
    log.info("i")
    log.warn("w")
    log.error("e")
    levels = [r["level"] for r in _records(buf)]
    assert levels == ["warn", "error"]


def test_invalid_level_at_init():
    with pytest.raises(ValueError):
        StructuredLogger(service="t", min_level="trace")


def test_service_required():
    with pytest.raises(ValueError):
        StructuredLogger(service="")


def test_context_merges_fields():
    log, buf = _make()
    with log.context(request_id="abc", user="dennis"):
        log.info("vm.start", vm_id=42)
    [rec] = _records(buf)
    assert rec["request_id"] == "abc"
    assert rec["user"] == "dennis"
    assert rec["vm_id"] == 42


def test_context_nested():
    log, buf = _make()
    with log.context(request_id="abc"):
        with log.context(user="dennis"):
            log.info("inner")
        log.info("outer")
    recs = _records(buf)
    assert recs[0]["request_id"] == "abc"
    assert recs[0]["user"] == "dennis"
    assert recs[1]["request_id"] == "abc"
    assert "user" not in recs[1]


def test_context_isolated_between_threads():
    log, buf = _make()
    barrier = threading.Barrier(2)

    def worker(rid: str):
        with log.context(request_id=rid):
            barrier.wait()
            log.info("evt")

    t1 = threading.Thread(target=worker, args=("one",))
    t2 = threading.Thread(target=worker, args=("two",))
    t1.start(); t2.start(); t1.join(); t2.join()
    recs = _records(buf)
    rids = sorted(r["request_id"] for r in recs)
    assert rids == ["one", "two"]


def test_explicit_field_overrides_context():
    log, buf = _make()
    with log.context(user="dennis"):
        log.info("evt", user="override")
    [rec] = _records(buf)
    assert rec["user"] == "override"


def test_log_message_compat():
    log, buf = _make()
    log.log_message('"%s" %s', "GET /api/v1/health", "200")
    [rec] = _records(buf)
    assert rec["event"] == "http.access"
    assert "GET /api/v1/health" in rec["message"]
    assert "200" in rec["message"]


def test_log_message_handles_format_error():
    log, buf = _make()
    log.log_message("missing %s args")  # no args provided
    [rec] = _records(buf)
    assert rec["event"] == "http.access"


def test_unjsonable_value_falls_back():
    log, buf = _make()

    class Weird:
        def __repr__(self) -> str:
            return "<weird>"

    log.info("evt", obj=Weird(), tup=(1, 2), s={1, 2}, b=b"hi")
    [rec] = _records(buf)
    assert rec["obj"] == "<weird>"
    assert rec["tup"] == [1, 2]
    assert sorted(rec["s"]) == [1, 2]
    assert rec["b"] == "hi"


def test_clear_resets_context():
    log, buf = _make()
    log.bind(request_id="abc")
    log.clear()
    log.info("evt")
    [rec] = _records(buf)
    assert "request_id" not in rec


def test_concurrent_writes_no_interleave():
    log, buf = _make()
    n = 200

    def worker(prefix: str):
        for i in range(n):
            log.info("evt", k=f"{prefix}-{i}")

    threads = [threading.Thread(target=worker, args=(p,)) for p in ("a", "b", "c", "d")]
    for t in threads: t.start()
    for t in threads: t.join()
    recs = _records(buf)
    assert len(recs) == 4 * n
    # all parsable -> no interleaved bytes
    for r in recs:
        assert "k" in r


def test_event_coerced_to_string():
    log, buf = _make()
    log.info(123)
    [rec] = _records(buf)
    assert rec["event"] == "123"


def test_sinks_receive_structured_records():
    received = []

    class Sink:
        def emit(self, record):
            received.append(record)

    buf = io.StringIO()
    log = StructuredLogger(
        service="test",
        stream=buf,
        utcnow=lambda: "2026-04-26T00:00:00.000000Z",
        sinks=[Sink()],
    )

    log.info("vm.start", vmid=100)

    assert received == [_records(buf)[0]]


def test_sink_failures_do_not_break_logging():
    class BrokenSink:
        def emit(self, _record):
            raise RuntimeError("down")

    buf = io.StringIO()
    log = StructuredLogger(service="test", stream=buf, sinks=[BrokenSink()])

    log.info("still.logged")

    [rec] = _records(buf)
    assert rec["event"] == "still.logged"
