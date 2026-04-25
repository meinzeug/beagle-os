"""audit_report_http_surface.py — HTTP surface for GET /api/v1/audit/report.

Extracted from beagle-control-plane.py inline handler.
"""
from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable

_AUDIT_REPORT_PATH = "/api/v1/audit/report"
_GET_PATHS = frozenset({_AUDIT_REPORT_PATH})


class AuditReportHttpSurfaceService:
    """Handles the audit report download endpoint.

    Auth/authz is performed by the caller before routing here.
    """

    def __init__(
        self,
        *,
        audit_report_service: Any,
        audit_event: Callable[..., None],
        requester_identity: Callable[[], str],
        accept_header: Callable[[], str],
    ) -> None:
        self._audit_report_service = audit_report_service
        self._audit_event = audit_event
        self._requester_identity = requester_identity
        self._accept_header = accept_header

    @staticmethod
    def handles_get(path: str) -> bool:
        return path in _GET_PATHS

    def route_get(self, path: str, query: dict[str, list[str]] | None = None) -> dict[str, Any]:
        if path == _AUDIT_REPORT_PATH:
            return self._handle_audit_report(query or {})
        raise ValueError(f"Unhandled GET path: {path}")

    def _handle_audit_report(self, query: dict[str, list[str]]) -> dict[str, Any]:
        start = str((query.get("start") or [""])[0] or "").strip()
        end = str((query.get("end") or [""])[0] or "").strip()
        tenant_id = str((query.get("tenant") or query.get("tenant_id") or [""])[0] or "").strip()
        action = str((query.get("action") or [""])[0] or "").strip()
        resource_type = str((query.get("resource_type") or [""])[0] or "").strip()
        user_id = str((query.get("user") or query.get("user_id") or [""])[0] or "").strip()
        accept = self._accept_header().lower()

        self._audit_event(
            "audit.report.download",
            "success",
            requested_by=self._requester_identity(),
            resource_type="audit-report",
            resource_id="audit-report",
            start=start,
            end=end,
            tenant_id=tenant_id,
            action_filter=action,
            resource_filter=resource_type,
            user_filter=user_id,
            accept=accept,
        )

        if "text/csv" in accept:
            body = self._audit_report_service.build_csv_report(
                start=start,
                end=end,
                tenant_id=tenant_id,
                action=action,
                resource_type=resource_type,
                user_id=user_id,
            )
            return {
                "kind": "bytes",
                "status": HTTPStatus.OK,
                "body": body,
                "content_type": "text/csv; charset=utf-8",
                "filename": "audit-report.csv",
            }
        payload = self._audit_report_service.build_json_report(
            start=start,
            end=end,
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            user_id=user_id,
        )
        return {"kind": "json", "status": HTTPStatus.OK, "payload": payload}
