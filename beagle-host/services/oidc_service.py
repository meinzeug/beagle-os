from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
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
        jwks_uri: str,
        scope: str,
        utcnow: Callable[[], str],
        load_json_file: Callable[[Path, Any], Any],
        write_json_file: Callable[[Path, Any], None],
        urlopen_fn: Callable[..., Any] = urlopen,
        time_fn: Callable[[], float] = time.time,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._enabled = bool(enabled)
        self._issuer = str(issuer or "").strip()
        self._client_id = str(client_id or "").strip()
        self._redirect_uri = str(redirect_uri or "").strip()
        self._authorization_endpoint = str(authorization_endpoint or "").strip()
        self._token_endpoint = str(token_endpoint or "").strip()
        self._userinfo_endpoint = str(userinfo_endpoint or "").strip()
        self._jwks_uri = str(jwks_uri or "").strip()
        self._scope = str(scope or "openid profile email").strip() or "openid profile email"
        self._utcnow = utcnow
        self._load_json_file = load_json_file
        self._write_json_file = write_json_file
        self._urlopen = urlopen_fn
        self._time = time_fn

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
        nonce = str(state_record.get("nonce") or "")
        if not verifier:
            raise PermissionError("invalid state")

        token_payload = self._exchange_code(code=code, code_verifier=verifier)
        claims = self._extract_claims(token_payload, expected_nonce=nonce)
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
        with self._urlopen(req, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
        if not isinstance(payload, dict):
            raise ValueError("invalid token payload")
        return payload

    def _extract_claims(self, token_payload: dict[str, Any], *, expected_nonce: str) -> dict[str, Any]:
        claims: dict[str, Any] = {}

        id_token = str(token_payload.get("id_token") or "").strip()
        if not id_token and "openid" in self._scope.split():
            raise ValueError("missing id_token")
        if id_token:
            claims.update(self._validate_id_token(id_token, expected_nonce=expected_nonce))

        access_token = str(token_payload.get("access_token") or "").strip()
        if access_token and self._userinfo_endpoint and self._is_safe_url(self._userinfo_endpoint):
            req = Request(
                self._userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
                method="GET",
            )
            with self._urlopen(req, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
            if isinstance(payload, dict):
                claims.update(payload)

        return {
            "sub": str(claims.get("sub") or "").strip(),
            "preferred_username": str(claims.get("preferred_username") or claims.get("name") or "").strip(),
            "email": str(claims.get("email") or "").strip(),
            "name": str(claims.get("name") or "").strip(),
        }

    def _validate_id_token(self, token: str, *, expected_nonce: str) -> dict[str, Any]:
        header, claims = self._decode_jwt(token)
        alg = str(header.get("alg") or "").strip()
        if not alg or alg.lower() == "none":
            raise ValueError("unsupported id_token algorithm")

        self._verify_jwt_signature(token, header)

        issuer = str(claims.get("iss") or "").strip()
        if self._issuer and issuer != self._issuer:
            raise ValueError("id_token issuer mismatch")

        audience = claims.get("aud")
        allowed_audience = self._client_id
        valid_audience = False
        if isinstance(audience, str):
            valid_audience = audience == allowed_audience
        elif isinstance(audience, list):
            valid_audience = allowed_audience in {str(item or "") for item in audience}
        if allowed_audience and not valid_audience:
            raise ValueError("id_token audience mismatch")

        if claims.get("exp") is not None and int(claims.get("exp") or 0) <= int(self._time()):
            raise ValueError("id_token expired")
        if claims.get("nbf") is not None and int(claims.get("nbf") or 0) > int(self._time()):
            raise ValueError("id_token not yet valid")
        if expected_nonce and not hmac.compare_digest(str(claims.get("nonce") or ""), expected_nonce):
            raise ValueError("id_token nonce mismatch")
        return claims

    def _verify_jwt_signature(self, token: str, header: dict[str, Any]) -> None:
        alg = str(header.get("alg") or "").strip().upper()
        if not alg.startswith("RS"):
            raise ValueError(f"unsupported id_token algorithm {alg or 'unknown'}")

        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"oidc signature verification unavailable: {exc}") from exc

        public_key = self._rsa_public_key_for_header(header)
        signing_input, signature = self._split_jwt_signature(token)
        hash_alg = {
            "RS256": hashes.SHA256,
            "RS384": hashes.SHA384,
            "RS512": hashes.SHA512,
        }.get(alg)
        if hash_alg is None:
            raise ValueError(f"unsupported id_token algorithm {alg}")

        public_key.verify(signature, signing_input, padding.PKCS1v15(), hash_alg())

    def _rsa_public_key_for_header(self, header: dict[str, Any]):
        kid = str(header.get("kid") or "").strip()
        jwks = self._load_jwks()
        for key in jwks.get("keys", []):
            if not isinstance(key, dict):
                continue
            if kid and str(key.get("kid") or "").strip() != kid:
                continue
            if str(key.get("kty") or "").strip().upper() != "RSA":
                continue
            if key.get("use") not in {None, "", "sig"}:
                continue
            n = self._decode_base64url_to_int(str(key.get("n") or ""))
            e = self._decode_base64url_to_int(str(key.get("e") or ""))
            if not n or not e:
                continue
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

            return RSAPublicNumbers(e, n).public_key()
        raise ValueError("no matching jwk for id_token")

    def _load_jwks(self) -> dict[str, Any]:
        jwks_uri = self._jwks_uri or self._discover_jwks_uri()
        if not self._is_safe_url(jwks_uri):
            raise ValueError("invalid oidc jwks uri")
        req = Request(jwks_uri, method="GET")
        with self._urlopen(req, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
        if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
            raise ValueError("invalid jwks payload")
        return payload

    def _discover_jwks_uri(self) -> str:
        if not self._issuer or not self._is_safe_url(self._issuer):
            raise ValueError("oidc jwks uri missing")
        well_known = self._issuer.rstrip("/") + "/.well-known/openid-configuration"
        req = Request(well_known, method="GET")
        with self._urlopen(req, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
        jwks_uri = str(payload.get("jwks_uri") or "").strip() if isinstance(payload, dict) else ""
        if not jwks_uri:
            raise ValueError("jwks_uri missing from oidc discovery")
        return jwks_uri

    @staticmethod
    def _decode_jwt(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
        parts = str(token or "").split(".")
        if len(parts) != 3:
            raise ValueError("invalid jwt")
        header = OidcService._decode_base64url_json(parts[0])
        payload = OidcService._decode_base64url_json(parts[1])
        return header, payload

    @staticmethod
    def _split_jwt_signature(token: str) -> tuple[bytes, bytes]:
        parts = str(token or "").split(".")
        if len(parts) != 3:
            raise ValueError("invalid jwt")
        signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
        return signing_input, OidcService._decode_base64url(parts[2])

    @staticmethod
    def _decode_base64url_json(value: str) -> dict[str, Any]:
        decoded = OidcService._decode_base64url(value)
        data = json.loads(decoded.decode("utf-8", "replace"))
        if not isinstance(data, dict):
            raise ValueError("invalid jwt json")
        return data

    @staticmethod
    def _decode_base64url(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode((str(value or "") + padding).encode("ascii"))

    @staticmethod
    def _decode_base64url_to_int(value: str) -> int:
        if not value:
            return 0
        return int.from_bytes(OidcService._decode_base64url(value), "big")

    @staticmethod
    def _code_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    @staticmethod
    def _is_safe_url(value: str) -> bool:
        parsed = urlparse(str(value or "").strip())
        return parsed.scheme in {"https", "http"} and bool(parsed.netloc) and not parsed.username and not parsed.password
