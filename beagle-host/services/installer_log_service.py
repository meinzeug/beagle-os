from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable


class InstallerLogService:
    """Scoped append-only log intake for generated USB installer scripts."""

    _SESSION_RE = re.compile(r"^[A-Za-z0-9._-]{8,96}$")

    def __init__(
        self,
        *,
        log_dir: Path,
        signing_secret: str,
        token_ttl_seconds: int,
        utcnow: Callable[[], str],
    ) -> None:
        secret = str(signing_secret or "").encode("utf-8")
        if not secret:
            raise ValueError("installer log signing secret is required")
        self._log_dir = Path(log_dir)
        self._events_dir = self._log_dir / "events"
        self._sessions_file = self._log_dir / "sessions.json"
        self._secret = secret
        self._token_ttl_seconds = max(300, int(token_ttl_seconds))
        self._utcnow = utcnow
        self._lock = threading.RLock()

    @staticmethod
    def _json_response(status: HTTPStatus, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": "json", "status": status, "payload": payload}

    @staticmethod
    def _b64url_encode(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _b64url_decode(value: str) -> bytes:
        text = str(value or "").strip()
        if not text:
            raise ValueError("empty base64url value")
        padding = "=" * ((4 - len(text) % 4) % 4)
        return base64.urlsafe_b64decode((text + padding).encode("ascii"))

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        text = str(value or "").strip()
        if not text:
            raise ValueError("missing timestamp")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _now(self) -> datetime:
        return self._parse_timestamp(self._utcnow())

    def _issue_token(self, payload: dict[str, Any]) -> str:
        now = self._now()
        body = dict(payload)
        body.setdefault("issued_at", now.isoformat())
        body.setdefault("expires_at", (now + timedelta(seconds=self._token_ttl_seconds)).isoformat())
        header_json = json.dumps({"alg": "HS256", "typ": "beagle.installer-log.v1"}, separators=(",", ":"), ensure_ascii=True)
        payload_json = json.dumps(body, separators=(",", ":"), ensure_ascii=True)
        header_part = self._b64url_encode(header_json.encode("utf-8"))
        payload_part = self._b64url_encode(payload_json.encode("utf-8"))
        signing_input = f"{header_part}.{payload_part}".encode("ascii")
        signature = hmac.new(self._secret, signing_input, hashlib.sha256).digest()
        return f"{header_part}.{payload_part}.{self._b64url_encode(signature)}"

    def validate_token(self, token: str) -> dict[str, Any] | None:
        try:
            parts = str(token or "").strip().split(".")
            if len(parts) != 3:
                return None
            header_part, payload_part, signature_part = parts
            signing_input = f"{header_part}.{payload_part}".encode("ascii")
            expected_sig = hmac.new(self._secret, signing_input, hashlib.sha256).digest()
            provided_sig = self._b64url_decode(signature_part)
            if not hmac.compare_digest(expected_sig, provided_sig):
                return None

            header = json.loads(self._b64url_decode(header_part).decode("utf-8"))
            if str((header or {}).get("typ") or "") != "beagle.installer-log.v1":
                return None

            payload = json.loads(self._b64url_decode(payload_part).decode("utf-8"))
            if not isinstance(payload, dict) or payload.get("scope") != "installer-log:write":
                return None
            expires_at = self._parse_timestamp(str(payload.get("expires_at") or ""))
            if expires_at <= self._now():
                return None
            session_id = str(payload.get("session_id") or "")
            if not self._SESSION_RE.fullmatch(session_id):
                return None
            return payload
        except Exception:
            return None

    def issue_log_context(self, *, vmid: int, node: str, script_kind: str, script_name: str) -> dict[str, str]:
        session_id = f"inst-{uuid.uuid4().hex}"
        token = self._issue_token(
            {
                "scope": "installer-log:write",
                "session_id": session_id,
                "vmid": int(vmid),
                "node": str(node or ""),
                "script_kind": str(script_kind or ""),
                "script_name": str(script_name or ""),
            }
        )
        return {
            "session_id": session_id,
            "token": token,
            "expires_at": str((self.validate_token(token) or {}).get("expires_at") or ""),
        }

    @staticmethod
    def _token_from_authorization(value: str) -> str:
        text = str(value or "").strip()
        if text.lower().startswith("bearer "):
            return text[7:].strip()
        return ""

    @staticmethod
    def _safe_text(value: Any, *, max_len: int = 512) -> str:
        text = str(value or "").replace("\x00", "").strip()
        if len(text) > max_len:
            return text[:max_len] + "...[truncated]"
        return text

    @classmethod
    def _safe_symbol(cls, value: Any, *, fallback: str = "unknown") -> str:
        text = cls._safe_text(value, max_len=96).lower()
        text = re.sub(r"[^a-z0-9._:-]+", "_", text).strip("._:-")
        return text or fallback

    @classmethod
    def _redact_payload(cls, value: Any, *, depth: int = 0) -> Any:
        if depth > 4:
            return "[truncated]"
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for key, item in value.items():
                key_text = cls._safe_text(key, max_len=80)
                if re.search(r"(token|secret|password|credential|key)", key_text, re.IGNORECASE):
                    out[key_text] = "[redacted]"
                else:
                    out[key_text] = cls._redact_payload(item, depth=depth + 1)
            return out
        if isinstance(value, list):
            return [cls._redact_payload(item, depth=depth + 1) for item in value[:25]]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return cls._safe_text(value, max_len=1024) if isinstance(value, str) else value
        return cls._safe_text(value, max_len=256)

    def _events_file(self, session_id: str) -> Path:
        if not self._SESSION_RE.fullmatch(session_id):
            raise ValueError("invalid session id")
        return self._events_dir / f"{session_id}.jsonl"

    def _load_sessions_locked(self) -> dict[str, Any]:
        if not self._sessions_file.is_file():
            return {"sessions": []}
        try:
            data = json.loads(self._sessions_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("sessions"), list):
                return data
        except Exception:
            pass
        return {"sessions": []}

    def _write_sessions_locked(self, data: dict[str, Any]) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = self._sessions_file.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp_file.replace(self._sessions_file)

    def _upsert_session_locked(self, token_payload: dict[str, Any], event: dict[str, Any]) -> None:
        data = self._load_sessions_locked()
        session_id = str(token_payload["session_id"])
        sessions = [item for item in data.get("sessions", []) if isinstance(item, dict)]
        existing = next((item for item in sessions if item.get("session_id") == session_id), None)
        if existing is None:
            existing = {
                "session_id": session_id,
                "vmid": int(token_payload.get("vmid") or 0),
                "node": str(token_payload.get("node") or ""),
                "script_kind": str(token_payload.get("script_kind") or ""),
                "script_name": str(token_payload.get("script_name") or ""),
                "issued_at": str(token_payload.get("issued_at") or ""),
                "expires_at": str(token_payload.get("expires_at") or ""),
                "event_count": 0,
            }
            sessions.append(existing)
        existing["last_seen_at"] = event["observed_at"]
        existing["last_event"] = event["event"]
        existing["last_status"] = event["status"]
        existing["event_count"] = int(existing.get("event_count") or 0) + 1
        sessions = sorted(sessions, key=lambda item: str(item.get("last_seen_at") or ""), reverse=True)[:500]
        data["sessions"] = sessions
        self._write_sessions_locked(data)

    def submit_event(
        self,
        *,
        payload: dict[str, Any],
        authorization_header: str,
        remote_addr: str,
        user_agent: str,
    ) -> dict[str, Any]:
        token_payload = self.validate_token(self._token_from_authorization(authorization_header))
        if token_payload is None:
            return self._json_response(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"})

        event = {
            "observed_at": self._now().isoformat(),
            "session_id": str(token_payload["session_id"]),
            "vmid": int(token_payload.get("vmid") or 0),
            "node": str(token_payload.get("node") or ""),
            "script_kind": str(token_payload.get("script_kind") or ""),
            "script_name": str(token_payload.get("script_name") or ""),
            "event": self._safe_symbol(payload.get("event")),
            "stage": self._safe_symbol(payload.get("stage")),
            "status": self._safe_symbol(payload.get("status"), fallback="info"),
            "message": self._safe_text(payload.get("message"), max_len=1024),
            "client": {
                "remote_addr": self._safe_text(remote_addr, max_len=128),
                "user_agent": self._safe_text(user_agent, max_len=256),
            },
            "details": self._redact_payload(payload.get("details") if isinstance(payload, dict) else {}),
        }

        with self._lock:
            self._events_dir.mkdir(parents=True, exist_ok=True)
            with self._events_file(event["session_id"]).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, separators=(",", ":"), ensure_ascii=True) + "\n")
            self._upsert_session_locked(token_payload, event)

        return self._json_response(
            HTTPStatus.ACCEPTED,
            {"ok": True, "session_id": event["session_id"], "accepted": True},
        )

    def handles_get(self, path: str) -> bool:
        return path == "/api/v1/installer-logs" or re.fullmatch(r"/api/v1/installer-logs/[A-Za-z0-9._-]{8,96}", path) is not None

    def route_get(self, path: str, *, query: dict[str, list[str]] | None = None) -> dict[str, Any]:
        query = query or {}
        if path == "/api/v1/installer-logs":
            try:
                limit = max(1, min(500, int((query.get("limit") or ["100"])[0])))
            except Exception:
                limit = 100
            with self._lock:
                sessions = self._load_sessions_locked().get("sessions", [])
            return self._json_response(HTTPStatus.OK, {"ok": True, "sessions": sessions[:limit]})

        session_id = path.rsplit("/", 1)[-1]
        if not self._SESSION_RE.fullmatch(session_id):
            return self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid session id"})
        events_file = self._events_file(session_id)
        if not events_file.is_file():
            return self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "session not found"})
        events: list[dict[str, Any]] = []
        with events_file.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        events.append(item)
                except Exception:
                    continue
        return self._json_response(HTTPStatus.OK, {"ok": True, "session_id": session_id, "events": events[-1000:]})
