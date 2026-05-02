"""Minimal OpenTelemetry OTLP/HTTP log adapter.

The control plane intentionally avoids a hard runtime dependency on the
OpenTelemetry SDK. This adapter translates existing structured log records into
OTLP JSON and posts them to an OTLP/HTTP endpoint when configured.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


_SEVERITY_NUMBER = {
    "debug": 5,
    "info": 9,
    "warn": 13,
    "warning": 13,
    "error": 17,
}

_SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "cookie",
    "password",
    "refresh_token",
    "secret",
    "token",
)


def _any_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"intValue": value}
    if isinstance(value, float):
        return {"doubleValue": value}
    if value is None:
        return {"stringValue": ""}
    if isinstance(value, (list, tuple)):
        return {"arrayValue": {"values": [_any_value(item) for item in value]}}
    if isinstance(value, dict):
        return {
            "kvlistValue": {
                "values": [
                    {"key": str(key), "value": _any_value(item)}
                    for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
                ]
            }
        }
    return {"stringValue": str(value)}


def _attributes(record: dict[str, Any]) -> list[dict[str, Any]]:
    skip = {"timestamp", "level", "service", "event", "message"}
    return [
        {"key": str(key), "value": _any_value(_redact_if_sensitive(str(key), value))}
        for key, value in sorted(record.items(), key=lambda pair: str(pair[0]))
        if key not in skip
    ]


def _redact_if_sensitive(key: str, value: Any) -> Any:
    normalized = key.replace("-", "_").lower()
    if any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS):
        return "[redacted]"
    return value


@dataclass(frozen=True)
class OTelHttpLogAdapter:
    endpoint: str
    service_name: str = "beagle-control-plane"
    timeout_seconds: float = 1.0
    opener: Callable[[urllib.request.Request, float], Any] | None = None

    def emit(self, record: dict[str, Any]) -> bool:
        """Export one structured log record as OTLP JSON.

        Returns ``True`` if the request was accepted locally by the HTTP layer,
        ``False`` for disabled/misconfigured endpoints or export failures.
        """
        endpoint = self.endpoint.strip()
        if not endpoint:
            return False
        payload = self.to_otlp_payload(record)
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            opener = self.opener or urllib.request.urlopen
            response = opener(request, timeout=self.timeout_seconds)
            close = getattr(response, "close", None)
            if callable(close):
                close()
            return True
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            return False

    def to_otlp_payload(self, record: dict[str, Any]) -> dict[str, Any]:
        level = str(record.get("level") or "info").lower()
        body_text = str(record.get("message") or record.get("event") or "")
        observed_time_unix_nano = int(time.time() * 1_000_000_000)
        return {
            "resourceLogs": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": self.service_name}},
                        ]
                    },
                    "scopeLogs": [
                        {
                            "scope": {"name": "beagle.structured_logger"},
                            "logRecords": [
                                {
                                    "observedTimeUnixNano": str(observed_time_unix_nano),
                                    "severityText": level.upper(),
                                    "severityNumber": _SEVERITY_NUMBER.get(level, 9),
                                    "body": {"stringValue": body_text},
                                    "attributes": _attributes(record),
                                }
                            ],
                        }
                    ],
                }
            ]
        }
