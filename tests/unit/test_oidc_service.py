from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa


ROOT_DIR = Path(__file__).resolve().parents[2]
for _path in (str(ROOT_DIR), str(ROOT_DIR / "beagle-host" / "services")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from oidc_service import OidcService


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _jwt(private_key: rsa.RSAPrivateKey, claims: dict[str, Any], *, kid: str = "kid-1") -> str:
    header = {"alg": "RS256", "typ": "JWT", "kid": kid}
    parts = [
        _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url(json.dumps(claims, separators=(",", ":")).encode("utf-8")),
    ]
    signing_input = ".".join(parts).encode("ascii")
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    parts.append(_b64url(signature))
    return ".".join(parts)


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _service(tmp_path: Path, url_map: dict[str, dict[str, Any]], *, time_value: int = 1_700_000_000) -> OidcService:
    state: dict[str, Any] = {}

    def _load(path: Path, default: Any) -> Any:
        return state.get(str(path), default)

    def _write(path: Path, payload: Any) -> None:
        state[str(path)] = payload

    def _urlopen(req, timeout=12):  # noqa: ANN001, ARG001
        url = getattr(req, "full_url", str(req))
        if url not in url_map:
            raise AssertionError(f"unexpected url {url}")
        return _Response(url_map[url])

    return OidcService(
        data_dir=tmp_path,
        enabled=True,
        issuer="https://issuer.example.test",
        client_id="beagle-web",
        redirect_uri="https://mgr.example.test/api/v1/auth/oidc/callback",
        authorization_endpoint="https://issuer.example.test/auth",
        token_endpoint="https://issuer.example.test/token",
        userinfo_endpoint="",
        jwks_uri="https://issuer.example.test/jwks",
        scope="openid profile email",
        utcnow=lambda: "2026-05-02T00:00:00Z",
        load_json_file=_load,
        write_json_file=_write,
        urlopen_fn=_urlopen,
        time_fn=lambda: float(time_value),
    )


def test_finish_login_validates_signed_id_token(tmp_path: Path) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "kid": "kid-1",
                "use": "sig",
                "alg": "RS256",
                "n": _b64url(public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, "big")),
                "e": _b64url(public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, "big")),
            }
        ]
    }
    claims = {
        "iss": "https://issuer.example.test",
        "aud": "beagle-web",
        "sub": "user-1",
        "preferred_username": "dennis",
        "email": "dennis@example.test",
        "name": "Dennis",
        "nonce": "nonce-1",
        "exp": 1_800_000_000,
        "iat": 1_700_000_000,
    }
    id_token = _jwt(private_key, claims)
    service = _service(
        tmp_path,
        {
            "https://issuer.example.test/token": {
                "access_token": "access-1",
                "id_token": id_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "openid profile email",
            },
            "https://issuer.example.test/jwks": jwks,
        },
    )
    service._store_state(state="state-1", verifier="verifier-1", nonce="nonce-1")

    payload = service.finish_login(code="code-1", state="state-1")

    assert payload["ok"] is True
    assert payload["claims"]["sub"] == "user-1"
    assert payload["claims"]["preferred_username"] == "dennis"
    assert payload["claims"]["email"] == "dennis@example.test"


def test_finish_login_rejects_nonce_mismatch(tmp_path: Path) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "kid": "kid-1",
                "use": "sig",
                "alg": "RS256",
                "n": _b64url(public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, "big")),
                "e": _b64url(public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, "big")),
            }
        ]
    }
    id_token = _jwt(
        private_key,
        {
            "iss": "https://issuer.example.test",
            "aud": "beagle-web",
            "sub": "user-1",
            "nonce": "wrong-nonce",
            "exp": 1_800_000_000,
        },
    )
    service = _service(
        tmp_path,
        {
            "https://issuer.example.test/token": {
                "access_token": "access-1",
                "id_token": id_token,
            },
            "https://issuer.example.test/jwks": jwks,
        },
    )
    service._store_state(state="state-1", verifier="verifier-1", nonce="nonce-1")

    with pytest.raises(ValueError, match="nonce"):
        service.finish_login(code="code-1", state="state-1")


def test_finish_login_rejects_tampered_signature(tmp_path: Path) -> None:
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = wrong_key.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "kid": "kid-1",
                "use": "sig",
                "alg": "RS256",
                "n": _b64url(public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, "big")),
                "e": _b64url(public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, "big")),
            }
        ]
    }
    id_token = _jwt(
        signing_key,
        {
            "iss": "https://issuer.example.test",
            "aud": "beagle-web",
            "sub": "user-1",
            "nonce": "nonce-1",
            "exp": 1_800_000_000,
        },
    )
    service = _service(
        tmp_path,
        {
            "https://issuer.example.test/token": {
                "access_token": "access-1",
                "id_token": id_token,
            },
            "https://issuer.example.test/jwks": jwks,
        },
    )
    service._store_state(state="state-1", verifier="verifier-1", nonce="nonce-1")

    with pytest.raises(Exception):
        service.finish_login(code="code-1", state="state-1")
