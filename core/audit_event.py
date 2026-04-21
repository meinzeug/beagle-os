from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4


SERVICES_DIR = Path(__file__).resolve().parents[1] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from audit_pii_filter import redact_sensitive_fields


_RESULT_MAP = {
    "success": "success",
    "ok": "success",
    "allowed": "success",
    "error": "failure",
    "failed": "failure",
    "failure": "failure",
    "denied": "rejected",
    "rejected": "rejected",
    "forbidden": "rejected",
    "unauthorized": "rejected",
}


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clean_json_value(value: Any) -> Any:
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        return value
    return str(value)


@dataclass(frozen=True)
class AuditEvent:
    id: str
    timestamp: str
    tenant_id: str | None
    user_id: str | None
    session_id: str | None
    action: str
    resource_type: str
    resource_id: str
    old_value: Any
    new_value: Any
    result: str
    source_ip: str | None
    user_agent: str | None
    metadata: dict[str, Any]
    schema_version: str = "1"

    @classmethod
    def create(cls, *, timestamp: str, action: str, result: str, details: dict[str, Any] | None = None) -> "AuditEvent":
        raw_details = details if isinstance(details, dict) else {}
        details_copy = dict(raw_details)
        metadata = {
            str(key): _clean_json_value(value)
            for key, value in details_copy.items()
            if str(key)
            not in {
                "tenant_id",
                "user_id",
                "username",
                "requested_by",
                "session_id",
                "resource_type",
                "resource_id",
                "old_value",
                "new_value",
                "source_ip",
                "remote_addr",
                "user_agent",
            }
        }
        return cls(
            id=str(uuid4()),
            timestamp=str(timestamp or "").strip(),
            tenant_id=_clean_text(details_copy.get("tenant_id")),
            user_id=_clean_text(details_copy.get("user_id") or details_copy.get("username") or details_copy.get("requested_by")),
            session_id=_clean_text(details_copy.get("session_id")),
            action=str(action or "unknown").strip() or "unknown",
            resource_type=str(details_copy.get("resource_type") or "").strip(),
            resource_id=str(details_copy.get("resource_id") or "").strip(),
            old_value=redact_sensitive_fields(_clean_json_value(details_copy.get("old_value")), field_name="old_value"),
            new_value=redact_sensitive_fields(_clean_json_value(details_copy.get("new_value")), field_name="new_value"),
            result=_RESULT_MAP.get(str(result or "unknown").strip().lower(), "failure"),
            source_ip=_clean_text(details_copy.get("source_ip") or details_copy.get("remote_addr")),
            user_agent=_clean_text(details_copy.get("user_agent")),
            metadata=metadata,
        )

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "AuditEvent":
        if isinstance(record, dict) and record.get("schema_version"):
            metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
            return cls(
                id=str(record.get("id") or uuid4()),
                timestamp=str(record.get("timestamp") or "").strip(),
                tenant_id=_clean_text(record.get("tenant_id")),
                user_id=_clean_text(record.get("user_id")),
                session_id=_clean_text(record.get("session_id")),
                action=str(record.get("action") or "unknown").strip() or "unknown",
                resource_type=str(record.get("resource_type") or "").strip(),
                resource_id=str(record.get("resource_id") or "").strip(),
                old_value=redact_sensitive_fields(_clean_json_value(record.get("old_value")), field_name="old_value"),
                new_value=redact_sensitive_fields(_clean_json_value(record.get("new_value")), field_name="new_value"),
                result=_RESULT_MAP.get(str(record.get("result") or "failure").strip().lower(), "failure"),
                source_ip=_clean_text(record.get("source_ip")),
                user_agent=_clean_text(record.get("user_agent")),
                metadata={str(key): _clean_json_value(value) for key, value in metadata.items()},
                schema_version=str(record.get("schema_version") or "1"),
            )
        legacy_details = record.get("details") if isinstance(record, dict) else {}
        return cls.create(
            timestamp=str((record or {}).get("timestamp") or "").strip(),
            action=str((record or {}).get("event_type") or "unknown").strip() or "unknown",
            result=str((record or {}).get("outcome") or "failure").strip() or "failure",
            details=legacy_details if isinstance(legacy_details, dict) else {},
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "timestamp": self.timestamp,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "result": self.result,
            "source_ip": self.source_ip,
            "user_agent": self.user_agent,
            "metadata": self.metadata,
        }