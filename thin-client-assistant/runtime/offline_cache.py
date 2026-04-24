#!/usr/bin/env python3
"""
Beagle Endpoint OS — Offline Cache and Reconnect Module.

Stores the last successful cluster configuration locally (AES-256-GCM encrypted
using a per-device key derived from machine-id) so endpoints can start streaming
sessions even when the cluster is temporarily unreachable.

Features:
  - Cache last valid pool/streaming config after every successful cluster contact.
  - Retrieve cached config when cluster is unreachable.
  - Show Offline-UI status ("Cluster nicht erreichbar — Reconnect in Xs").
  - Auto-reconnect every 30 seconds.
  - Invalidate cache after configurable TTL (default: 7 days).

Environment variables:
  BEAGLE_OFFLINE_CACHE_FILE   — path to encrypted cache file (default: /var/lib/beagle/offline-cache.bin)
  BEAGLE_OFFLINE_CACHE_TTL    — TTL in seconds (default: 604800 = 7 days)
  BEAGLE_MACHINE_ID_FILE      — path to machine-id (default: /etc/machine-id)

Usage as library:
  from offline_cache import OfflineCache
  cache = OfflineCache()
  cache.store(config_dict)            # called after successful cluster contact
  config = cache.load()               # returns config dict or None if stale/missing
  cache.is_valid()                    # True if cache exists and within TTL

Usage as CLI for testing:
  python3 offline_cache.py --store '{"pools": []}' 
  python3 offline_cache.py --load
  python3 offline_cache.py --status
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import struct
import time
from pathlib import Path

_DEFAULT_CACHE_FILE = Path("/var/lib/beagle/offline-cache.bin")
_DEFAULT_TTL = 7 * 24 * 3600  # 7 days
_DEFAULT_MACHINE_ID_FILE = Path("/etc/machine-id")
_MAGIC = b"BGLCACHE"
_VERSION = 1


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

def _derive_key(machine_id: str) -> bytes:
    """Derive a 32-byte AES key from the machine-id using SHA-256."""
    return hashlib.sha256(f"beagle-offline-cache:{machine_id}".encode()).digest()


def _read_machine_id(path: Path | None = None) -> str:
    p = path or _DEFAULT_MACHINE_ID_FILE
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        # Fallback for environments without /etc/machine-id
        return "beagle-dev-machine-id"


# ---------------------------------------------------------------------------
# Encryption helpers (AES-256-GCM via cryptography package; fallback: XOR obfuscation)
# ---------------------------------------------------------------------------

def _encrypt(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt using AES-256-GCM if available, else simple XOR (dev fallback)."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = os.urandom(12)
        ct = AESGCM(key).encrypt(nonce, plaintext, None)
        return nonce + ct
    except ImportError:
        # XOR fallback — not secure for production, acceptable for dev environments
        import itertools
        xored = bytes(p ^ k for p, k in zip(plaintext, itertools.cycle(key)))
        return b"\x00" * 12 + xored  # 12-byte fake nonce placeholder


def _decrypt(ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt AES-256-GCM or XOR fallback."""
    if len(ciphertext) < 12:
        raise ValueError("ciphertext too short")
    nonce = ciphertext[:12]
    ct = ciphertext[12:]
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return AESGCM(key).decrypt(nonce, ct, None)
    except ImportError:
        import itertools
        return bytes(p ^ k for p, k in zip(ct, itertools.cycle(key)))


# ---------------------------------------------------------------------------
# Cache format: MAGIC(8) + VERSION(1) + TIMESTAMP(8, big-endian int64) + ENCRYPTED_JSON
# ---------------------------------------------------------------------------

def _pack(data: dict, key: bytes) -> bytes:
    payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
    encrypted = _encrypt(payload, key)
    ts = int(time.time())
    return _MAGIC + struct.pack("!BQ", _VERSION, ts) + encrypted


def _unpack(raw: bytes, key: bytes) -> tuple[dict, int]:
    """Returns (config_dict, timestamp)."""
    if len(raw) < len(_MAGIC) + 9:
        raise ValueError("cache file too short")
    if raw[:8] != _MAGIC:
        raise ValueError("invalid magic bytes")
    version, ts = struct.unpack("!BQ", raw[8:17])
    if version != _VERSION:
        raise ValueError(f"unsupported cache version {version}")
    decrypted = _decrypt(raw[17:], key)
    return json.loads(decrypted.decode("utf-8")), ts


# ---------------------------------------------------------------------------
# OfflineCache class
# ---------------------------------------------------------------------------

class OfflineCache:
    def __init__(
        self,
        cache_file: Path | None = None,
        ttl: int | None = None,
        machine_id_file: Path | None = None,
    ) -> None:
        env_file = os.environ.get("BEAGLE_OFFLINE_CACHE_FILE", "")
        self._cache_file = Path(env_file) if env_file else (cache_file or _DEFAULT_CACHE_FILE)
        env_ttl = os.environ.get("BEAGLE_OFFLINE_CACHE_TTL", "")
        self._ttl = int(env_ttl) if env_ttl.isdigit() else (ttl or _DEFAULT_TTL)
        mid = _read_machine_id(machine_id_file)
        self._key = _derive_key(mid)

    def store(self, config: dict) -> None:
        """Persist config to encrypted cache file."""
        raw = _pack(config, self._key)
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._cache_file.write_bytes(raw)

    def load(self) -> dict | None:
        """Return cached config if valid (not expired), else None."""
        if not self._cache_file.exists():
            return None
        try:
            raw = self._cache_file.read_bytes()
            config, ts = _unpack(raw, self._key)
            if time.time() - ts > self._ttl:
                return None  # expired
            return config
        except Exception:
            return None

    def is_valid(self) -> bool:
        return self.load() is not None

    def invalidate(self) -> None:
        """Delete the cache file."""
        try:
            self._cache_file.unlink()
        except FileNotFoundError:
            pass

    def status(self) -> dict:
        if not self._cache_file.exists():
            return {"cached": False, "reason": "no cache file"}
        try:
            raw = self._cache_file.read_bytes()
            _, ts = _unpack(raw, self._key)
            age = int(time.time() - ts)
            expired = age > self._ttl
            return {
                "cached": True,
                "age_seconds": age,
                "ttl_seconds": self._ttl,
                "expired": expired,
                "cache_file": str(self._cache_file),
            }
        except Exception as exc:
            return {"cached": False, "reason": str(exc)}


# ---------------------------------------------------------------------------
# Reconnect loop (for use in endpoint runtime)
# ---------------------------------------------------------------------------

def reconnect_loop(
    check_fn,
    on_connected,
    on_disconnected,
    interval: int = 30,
) -> None:
    """
    Continuously poll cluster connectivity.

    Args:
        check_fn: callable() -> bool — returns True if cluster is reachable
        on_connected: callable(config) — called when connection restored
        on_disconnected: callable(remaining_ttl_s) — called when cluster unreachable
        interval: poll interval in seconds
    """
    cache = OfflineCache()
    while True:
        try:
            if check_fn():
                on_connected(None)
            else:
                status = cache.status()
                remaining = max(0, cache._ttl - status.get("age_seconds", cache._ttl + 1))
                on_disconnected(remaining)
        except Exception:
            pass
        time.sleep(interval)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Beagle Endpoint Offline Cache")
    parser.add_argument("--store", metavar="JSON", help="Store config JSON into cache")
    parser.add_argument("--load", action="store_true", help="Load and print cached config")
    parser.add_argument("--status", action="store_true", help="Show cache status")
    parser.add_argument("--invalidate", action="store_true", help="Delete cache file")
    args = parser.parse_args()

    cache = OfflineCache()

    if args.store:
        config = json.loads(args.store)
        cache.store(config)
        print("Cache stored.")
    elif args.load:
        config = cache.load()
        if config is None:
            print("No valid cache.")
        else:
            print(json.dumps(config, indent=2))
    elif args.status:
        print(json.dumps(cache.status(), indent=2))
    elif args.invalidate:
        cache.invalidate()
        print("Cache invalidated.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
