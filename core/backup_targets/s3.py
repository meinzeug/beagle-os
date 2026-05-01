"""S3BackupTarget — stores backup chunks in an S3-compatible object store.

Supports AWS S3, MinIO, Backblaze B2 and any S3-compatible API.
When encryption_key is provided, chunks are encrypted client-side with
AES-256-GCM before upload. Credentials are never logged.
"""
from __future__ import annotations

import secrets
from typing import Any, cast

_NONCE_SIZE = 12  # AES-GCM standard nonce length in bytes

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM

    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


def _safe_id(chunk_id: str) -> str:
    raw = str(chunk_id)
    if not raw or ".." in raw or "/" in raw or raw.startswith("."):
        raise ValueError(f"Invalid chunk_id: {chunk_id!r}")
    safe = "".join(c for c in raw if c.isalnum() or c in "-_.")
    if not safe:
        raise ValueError(f"Invalid chunk_id: {chunk_id!r}")
    return safe


class S3BackupTarget:
    """BackupTarget backed by an S3-compatible object store.

    Constructor parameters:
        bucket          — S3 bucket name (required).
        prefix          — Key prefix within the bucket (default: 'beagle-backup/').
        endpoint_url    — Custom endpoint URL (for MinIO / B2 / etc.).
        access_key      — AWS access key ID.
        secret_key      — AWS secret access key.
        encryption_key  — 64-char hex string (32 bytes) for AES-256-GCM
                          client-side encryption. If omitted, data is stored
                          unencrypted (not recommended for offsite targets).
    """

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "beagle-backup/",
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        encryption_key: str | None = None,
    ) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise ImportError(
                "S3BackupTarget requires 'boto3'. Install with: pip install boto3"
            ) from exc

        if not bucket:
            raise ValueError("S3BackupTarget: bucket is required")

        if encryption_key:
            if not _CRYPTO_AVAILABLE:
                raise ImportError(
                    "S3BackupTarget client-side encryption requires 'cryptography'. "
                    "Install with: pip install cryptography"
                )
            key_bytes = bytes.fromhex(str(encryption_key).strip())
            if len(key_bytes) != 32:
                raise ValueError(
                    "S3BackupTarget: encryption_key must be a 64-character hex string (32 bytes = 256 bits)"
                )
            self._enc_key: bytes | None = key_bytes
        else:
            self._enc_key = None

        client_kwargs: dict[str, Any] = {}
        if endpoint_url:
            client_kwargs["endpoint_url"] = str(endpoint_url)
        if access_key and secret_key:
            client_kwargs["aws_access_key_id"] = str(access_key)
            client_kwargs["aws_secret_access_key"] = str(secret_key)

        self._s3 = boto3.client("s3", **client_kwargs)
        self._bucket = str(bucket)
        self._prefix = str(prefix or "beagle-backup/")

    def _encrypt(self, data: bytes) -> bytes:
        if not self._enc_key:
            return data
        nonce = secrets.token_bytes(_NONCE_SIZE)
        ciphertext = cast(bytes, _AESGCM(self._enc_key).encrypt(nonce, data, None))
        return nonce + ciphertext

    def _decrypt(self, data: bytes) -> bytes:
        if not self._enc_key:
            return data
        if len(data) < _NONCE_SIZE:
            raise ValueError("Encrypted data is too short (missing AES-GCM nonce)")
        nonce, ciphertext = data[:_NONCE_SIZE], data[_NONCE_SIZE:]
        return cast(bytes, _AESGCM(self._enc_key).decrypt(nonce, ciphertext, None))

    def _object_key(self, chunk_id: str) -> str:
        return f"{self._prefix}{_safe_id(chunk_id)}"

    def write_chunk(self, chunk_id: str, data: bytes) -> None:
        self._s3.put_object(
            Bucket=self._bucket,
            Key=self._object_key(chunk_id),
            Body=self._encrypt(data),
        )

    def read_chunk(self, chunk_id: str) -> bytes:
        response = self._s3.get_object(Bucket=self._bucket, Key=self._object_key(chunk_id))
        raw: bytes = response["Body"].read()
        return self._decrypt(raw)

    def list_snapshots(self, *, prefix: str = "") -> list[dict[str, Any]]:
        full_prefix = self._prefix + (prefix or "")
        paginator = self._s3.get_paginator("list_objects_v2")
        results: list[dict[str, Any]] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=full_prefix):
            for obj in page.get("Contents", []):
                key = str(obj["Key"])
                snapshot_id = key[len(self._prefix):]
                last_mod = obj.get("LastModified")
                results.append(
                    {
                        "snapshot_id": snapshot_id,
                        "size": obj.get("Size", 0),
                        "modified": last_mod.isoformat() if hasattr(last_mod, "isoformat") else str(last_mod or ""),
                    }
                )
        return results

    def delete_snapshot(self, snapshot_id: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=self._object_key(snapshot_id))
