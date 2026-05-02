from __future__ import annotations

import json
import os
import sys
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "beagle-host", "services"))

from otel_adapter import OTelHttpLogAdapter  # noqa: E402


class _Response:
    def close(self) -> None:
        pass


def test_to_otlp_payload_maps_record_fields() -> None:
    adapter = OTelHttpLogAdapter(endpoint="http://otel.example/v1/logs", service_name="beagle-test")

    payload = adapter.to_otlp_payload({
        "timestamp": "2026-05-02T00:00:00Z",
        "level": "warn",
        "service": "beagle-control-plane",
        "event": "vm.start",
        "request_id": "req-1",
        "api_token": "super-secret",
        "vmid": 100,
        "ok": True,
    })

    resource = payload["resourceLogs"][0]["resource"]
    record = payload["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]
    assert resource["attributes"][0] == {"key": "service.name", "value": {"stringValue": "beagle-test"}}
    assert record["severityText"] == "WARN"
    assert record["severityNumber"] == 13
    assert record["body"] == {"stringValue": "vm.start"}
    attrs = {item["key"]: item["value"] for item in record["attributes"]}
    assert attrs["request_id"] == {"stringValue": "req-1"}
    assert attrs["api_token"] == {"stringValue": "[redacted]"}
    assert attrs["vmid"] == {"intValue": 100}
    assert attrs["ok"] == {"boolValue": True}


def test_emit_posts_otlp_json_to_configured_endpoint() -> None:
    calls: list[dict[str, Any]] = []

    def opener(request, timeout):
        calls.append({
            "url": request.full_url,
            "timeout": timeout,
            "content_type": request.headers.get("Content-type"),
            "body": json.loads(request.data.decode("utf-8")),
        })
        return _Response()

    adapter = OTelHttpLogAdapter(
        endpoint="http://otel.example/v1/logs",
        service_name="beagle-test",
        timeout_seconds=2.5,
        opener=opener,
    )

    assert adapter.emit({"level": "info", "event": "health.ok"}) is True

    assert calls[0]["url"] == "http://otel.example/v1/logs"
    assert calls[0]["timeout"] == 2.5
    assert calls[0]["content_type"] == "application/json"
    record = calls[0]["body"]["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]
    assert record["body"] == {"stringValue": "health.ok"}


def test_emit_failures_are_non_fatal() -> None:
    def opener(_request, timeout):
        raise OSError("down")

    adapter = OTelHttpLogAdapter(endpoint="http://otel.example/v1/logs", opener=opener)

    assert adapter.emit({"level": "error", "event": "boom"}) is False

