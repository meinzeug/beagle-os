from __future__ import annotations

import base64
import hashlib
import json
import secrets
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


class OidcService:
    def __init__(
        self,
        *,
        data_dir: Path,
        enabled: bool,
        issuer: str,
        client_id: str,
        redirect_uri: str,
        authorization_endpoint: str,
        token_endpoint: str,
        userinfo_endpoint: str,
        scope: str,
        utcnow: Callable[[], str],
        load_json_file: Callable[[Path, Any], Any],
        write_json_file: Callable[[Path, Any], None],
    ) -> None:
        self._data_dir = Path(data_dir)
        self._enabled = bool(enabled)
        self._issuer = str(issuer or "").strip()
        self._client_id = str(client_id or "").strip()
        self._redirect_uri = str(redirect_uri or "").strip()
        self._authorization_endpoint = str(authorization_endpoint or "").strip()
        self._token_endpoint = str(token_endpoint or "").strip()
        self._userinfo_endpoint = str(userinfo_endpoint or "").strip()
        self._scope = str(scope or "openid profile email").strip() or "openid profile email"
        self._utcnow = utcnow
        self._load_json_file = load_json_file
        self._write_json_file = write_json_file

    @property
    def enabled(self) -> bool:
        return self._enabled

    def login_url(self) -> str:
        return "/api/v1/auth/oidc/login"

    def begin_login(self) -> str:
        if not self._enabled:
            raise RuntimeError("oidc disabled")
        if not self._authorization_endpoint or not self._client_id or not self._redirect_uri:
            raise ValueError("oidc not fully configured")
        if not self._is_safe_url(self._authorization_endpoint):
            raise ValueError("invalid oidc authorization endpoint")

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(64)
        challenge = self._code_challenge(verifier)
        self._store_state(state=state, verifier=verifier, nonce=nonce)

        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "scope": self._scope,
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self._authorization_endpoint}?{query}"

    def finish_login(self, *, code: str, state: str) -> dict[str, Any]:
        if not self._enabled:
            raise RuntimeError("oidc disabled")
        if not self._token_endpoint:
            raise ValueError("oidc token endpoint missing")

        state_record = self._consume_state(state)
        verifier = str(state_record.get("verifier") or "")
        if not verifier:
            raise PermissionError("invalid state")

        token_payload = self._exchange_code(code=code, code_verifier=verifier)
        claims = self._extract_claims(token_payload)
        return {
            "ok": True,
            "provider": "oidc",
            "issuer": self._issuer,
            "authenticated_at": self._utcnow(),
            "claims": claims,
            "token": {
                "token_type": str(token_payload.get("token_type") or "Bearer"),
                "expires_in": int(token_payload.get("expires_in") or 0),
                "scope": str(token_payload.get("scope") or self._scope),
            },
        }

    def _state_file(self) -> Path:
        path = self._data_dir / "auth" / "oidc-state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _store_state(self, *, state: str, verifier: str, nonce: str) -> None:
        doc = self._load_json_file(self._state_file(), {"states": {}})
        if not isinstance(doc, dict):
            doc = {"states": {}}
        states = doc.setdefault("states", {})
        if not isinstance(states, dict):
            states = {}
            doc["states"] = states
        states[state] = {
            "verifier": verifier,
            "nonce": nonce,
            "issued_at": self._utcnow(),
        }
        self._write_json_file(self._state_file(), doc)

    def _consume_state(self, state: str) -> dict[str, Any]:
        doc = self._load_json_file(self._state_file(), {"states": {}})
        if not isinstance(doc, dict):
            return {}
        states = doc.get("states")
        if not isinstance(states, dict):
            return {}
        record = states.pop(str(state or ""), None)
        self._write_json_file(self._state_file(), doc)
        if not isinstance(record, dict):
            return {}
        return record

    def _exchange_code(self, *, code: str, code_verifier: str) -> dict[str, Any]:
        body = urlencode(
            {
                "grant_type": "authorization_code",
                "code": str(code or "").strip(),
                "redirect_uri": self._redirect_uri,
                "client_id": self._client_id,
                "code_verifier": code_verifier,
            }
        ).encode("utf-8")
        req = Request(
            self._token_endpoint,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(req, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
        if not isinstance(payload, dict):
            raise ValueError("invalid token payload")
        return payload

    def _extract_claims(self, token_payload: dict[str, Any]) -> dict[str, Any]:
        claims: dict[str, Any] = {}

        id_token = str(token_payload.get("id_token") or "").strip()
        if id_token:
            claims.update(self._decode_jwt_payload(id_token))

        access_token = str(token_payload.get("access_token") or "").strip()
        if access_token and self._userinfo_endpoint and self._is_safe_url(self._userinfo_endpoint):
            req = Request(
                self._userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
                method="GET",
            )
            with urlopen(req, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
            if isinstance(payload, dict):
                claims.update(payload)

        return {
            "sub": str(claims.get("sub") or "").strip(),
            "preferred_username": str(claims.get("preferred_username") or claims.get("name") or "").strip(),
            "email": str(claims.get("email") or "").strip(),
            "name": str(claims.get("name") or "").strip(),
        }

    @staticmethod
    def _decode_jwt_payload(token: str) -> dict[str, Any]:
        parts = str(token or "").split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode((payload + padding).encode("ascii"))
        data = json.loads(decoded.decode("utf-8", "replace"))
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _code_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    @staticmethod
    def _is_safe_url(value: str) -> bool:
        parsed = urlparse(str(value or "").strip())
        return parsed.scheme in {"https", "http"} and bool(parsed.netloc) and not parsed.username and not parsed.password
