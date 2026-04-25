"""recording_http_surface.py — HTTP surface for session recording endpoints.

Handles:
  GET  /api/v1/sessions/{session_id}/recording         (download)
  POST /api/v1/sessions/{session_id}/recording/start
  POST /api/v1/sessions/{session_id}/recording/stop

Extracted from beagle-control-plane.py inline handlers.
Auth/authz is performed by the caller before routing here.
"""
from __future__ import annotations

import re
from http import HTTPStatus
from typing import Any, Callable

_RECORDING_GET_RE = re.compile(
    r"^/api/v1/sessions/(?P<session_id>[A-Za-z0-9._:-]+)/recording$"
)
_RECORDING_START_RE = re.compile(
    r"^/api/v1/sessions/(?P<session_id>[A-Za-z0-9._:-]+)/recording/start$"
)
_RECORDING_STOP_RE = re.compile(
    r"^/api/v1/sessions/(?P<session_id>[A-Za-z0-9._:-]+)/recording/stop$"
)


class RecordingHttpSurfaceService:
    """HTTP surface for session recording download, start, and stop."""

    def __init__(
        self,
        *,
        recording_service: Any,
        audit_event: Callable[..., None],
        requester_identity: Callable[[], str],
        remote_addr: Callable[[], str],
        active_session_by_id: Callable[[str], dict[str, Any] | None],
        pool_recording_watermark: Callable[[str], dict[str, Any]],
        read_json_body: Callable[[], dict[str, Any]],
        has_body: Callable[[], bool],
    ) -> None:
        self._recording_service = recording_service
        self._audit_event = audit_event
        self._requester_identity = requester_identity
        self._remote_addr = remote_addr
        self._active_session_by_id = active_session_by_id
        self._pool_recording_watermark = pool_recording_watermark
        self._read_json_body = read_json_body
        self._has_body = has_body

    @staticmethod
    def handles_get(path: str) -> bool:
        return bool(_RECORDING_GET_RE.match(path))

    @staticmethod
    def handles_post(path: str) -> bool:
        return bool(_RECORDING_START_RE.match(path) or _RECORDING_STOP_RE.match(path))

    def route_get(self, path: str, **_: Any) -> dict[str, Any]:
        m = _RECORDING_GET_RE.match(path)
        if m:
            return self._handle_download(str(m.group("session_id")).strip())
        raise ValueError(f"Unhandled recording GET path: {path}")

    def route_post(self, path: str) -> dict[str, Any]:
        m_start = _RECORDING_START_RE.match(path)
        if m_start:
            return self._handle_start(str(m_start.group("session_id")).strip())
        m_stop = _RECORDING_STOP_RE.match(path)
        if m_stop:
            return self._handle_stop(str(m_stop.group("session_id")).strip())
        raise ValueError(f"Unhandled recording POST path: {path}")

    # ------------------------------------------------------------------ #
    # GET — download recording                                             #
    # ------------------------------------------------------------------ #

    def _handle_download(self, session_id: str) -> dict[str, Any]:
        file_payload = self._recording_service.read_recording_bytes(session_id=session_id)
        if file_payload is None:
            return {"kind": "json", "status": HTTPStatus.NOT_FOUND, "payload": {"ok": False, "error": "recording not found"}}
        body, filename = file_payload
        self._audit_event(
            "session.recording.download",
            "success",
            session_id=session_id,
            downloader=self._requester_identity(),
            remote_addr=self._remote_addr(),
        )
        return {
            "kind": "bytes",
            "status": HTTPStatus.OK,
            "body": body,
            "content_type": "video/mp4",
            "filename": filename,
        }

    # ------------------------------------------------------------------ #
    # POST — start                                                          #
    # ------------------------------------------------------------------ #

    def _handle_start(self, session_id: str) -> dict[str, Any]:
        try:
            payload: dict[str, Any] = self._read_json_body() if self._has_body() else {}
        except Exception as exc:
            return {"kind": "json", "status": HTTPStatus.BAD_REQUEST, "payload": {"ok": False, "error": f"invalid payload: {exc}"}}

        active_session = self._active_session_by_id(session_id)
        pool_id = str((active_session or {}).get("pool_id") or "").strip()
        user_id = str((active_session or {}).get("user_id") or self._requester_identity()).strip()
        watermark = self._pool_recording_watermark(pool_id) if pool_id else {"enabled": False, "custom_text": ""}

        response = self._recording_service.start_recording(
            session_id=session_id,
            input_url=str(payload.get("input_url") or "").strip(),
            codec=str(payload.get("codec") or "h264").strip(),
            test_source=bool(payload.get("test_source", False)),
            watermark_enabled=bool(payload.get("watermark_enabled", watermark.get("enabled", False))),
            watermark_username=str(payload.get("watermark_username") or user_id).strip(),
            watermark_custom_text=str(payload.get("watermark_custom_text") or watermark.get("custom_text", "")).strip(),
            watermark_show_timestamp=bool(payload.get("watermark_show_timestamp", True)),
        )
        self._audit_event(
            "session.recording.start",
            "success",
            session_id=session_id,
            requested_by=self._requester_identity(),
            remote_addr=self._remote_addr(),
        )
        return {"kind": "json", "status": HTTPStatus.OK, "payload": response}

    # ------------------------------------------------------------------ #
    # POST — stop                                                           #
    # ------------------------------------------------------------------ #

    def _handle_stop(self, session_id: str) -> dict[str, Any]:
        response = self._recording_service.stop_recording(session_id=session_id)
        if not bool(response.get("ok")):
            return {"kind": "json", "status": HTTPStatus.NOT_FOUND, "payload": response}
        self._audit_event(
            "session.recording.stop",
            "success",
            session_id=session_id,
            requested_by=self._requester_identity(),
            remote_addr=self._remote_addr(),
        )
        return {"kind": "json", "status": HTTPStatus.OK, "payload": response}
