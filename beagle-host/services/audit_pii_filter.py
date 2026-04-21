from __future__ import annotations

from typing import Any


REDACTED = "[REDACTED]"
_SENSITIVE_PARTS = ("password", "secret", "token", "key")


def _looks_sensitive(field_name: str) -> bool:
    name = str(field_name or "").strip().lower()
    return any(part in name for part in _SENSITIVE_PARTS)


def redact_sensitive_fields(value: Any, *, field_name: str = "") -> Any:
    if _looks_sensitive(field_name):
        return REDACTED
    if isinstance(value, dict):
        return {
            str(key): redact_sensitive_fields(item, field_name=str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_fields(item, field_name=field_name) for item in value]
    return value