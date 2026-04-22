from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable


class PairingService:
    def __init__(
        self,
        *,
        signing_secret: str,
        token_ttl_seconds: int,
        utcnow: Callable[[], str],
    ) -> None:
        secret = str(signing_secret or "").encode("utf-8")
        if not secret:
            raise ValueError("pairing signing secret is required")
        self._secret = secret
        self._token_ttl_seconds = max(15, int(token_ttl_seconds))
        self._utcnow = utcnow

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

    def issue_token(self, payload: dict[str, Any]) -> str:
        body = dict(payload)
        now = self._now()
        body.setdefault("issued_at", now.isoformat())
        body.setdefault("expires_at", (now + timedelta(seconds=self._token_ttl_seconds)).isoformat())

        header_json = json.dumps({"alg": "HS256", "typ": "beagle.pairing.v1"}, separators=(",", ":"), ensure_ascii=True)
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
            if str((header or {}).get("typ") or "") != "beagle.pairing.v1":
                return None

            payload = json.loads(self._b64url_decode(payload_part).decode("utf-8"))
            if not isinstance(payload, dict):
                return None

            expires_at = self._parse_timestamp(str(payload.get("expires_at") or ""))
            if expires_at <= self._now():
                return None
            return payload
        except Exception:
            return None
