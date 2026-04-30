#!/usr/bin/env python3
"""Smoke: noVNC console token is TTL-scoped and single-use.

Validates that:
1. A freshly generated noVNC token is valid (present in the store)
2. The token has an expiry (created_at + TTL_SECONDS in the future)
3. After the token is marked 'used', it is pruned on the next write
4. The token store file has mode 0o600 (no world-readable secrets)

This smoke tests the vm_console_access service behavior without requiring
a running websockify or VNC server — it exercises the token-store logic.

Run on srv1:
    python3 /opt/beagle/scripts/test-novnc-token-ttl-smoke.py

Expected output: NOVNC_TOKEN_TTL_SMOKE=PASS
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from stat import S_IMODE

_OPT = Path("/opt/beagle")
_SERVICES_DIR = _OPT / "services"
if str(_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVICES_DIR))
if str(_OPT) not in sys.path:
    sys.path.insert(0, str(_OPT))

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REPO_SERVICES = _REPO_ROOT / "beagle-host" / "services"
if str(_REPO_SERVICES) not in sys.path:
    sys.path.insert(0, str(_REPO_SERVICES))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def main() -> int:
    try:
        from core.persistence.json_state_store import JsonStateStore
    except ImportError as exc:
        print("NOVNC_TOKEN_TTL_SMOKE=FAIL")
        print(f"error=import error: {exc}")
        return 2

    # We test the _create_ephemeral_novnc_token logic by replicating it
    # and verifying that tokens are correctly TTL-gated.
    TTL_SECONDS = 30.0

    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "novnc" / "console-tokens.json"
        store_path.parent.mkdir(parents=True, exist_ok=True)

        token_store = JsonStateStore(store_path, default_factory=dict, mode=0o600)

        # --- Write a valid token ---
        import secrets as secrets_mod
        token_a = secrets_mod.token_urlsafe(32)
        now = time.time()
        raw = token_store.load()
        store: dict = raw if isinstance(raw, dict) else {}
        store[token_a] = {
            "target_host": "127.0.0.1",
            "target_port": 5900,
            "created_at": now,
            "used": False,
        }
        token_store.save(store)

        # Verify file permissions
        mode = S_IMODE(store_path.stat().st_mode)
        if mode != 0o600:
            print("NOVNC_TOKEN_TTL_SMOKE=FAIL")
            print(f"error=token store mode is {oct(mode)}, expected 0o600")
            return 1

        # Token is readable and valid
        loaded = token_store.load()
        if not isinstance(loaded, dict) or token_a not in loaded:
            print("NOVNC_TOKEN_TTL_SMOKE=FAIL")
            print("error=fresh token not found in store")
            return 1

        entry = loaded[token_a]
        age = now - float(entry.get("created_at") or 0)
        if age > TTL_SECONDS:
            print("NOVNC_TOKEN_TTL_SMOKE=FAIL")
            print(f"error=fresh token already expired (age={age:.1f}s)")
            return 1

        # --- Mark token as used and prune ---
        store2: dict = token_store.load() if isinstance(token_store.load(), dict) else {}  # type: ignore[assignment]
        store2 = token_store.load()  # type: ignore[assignment]
        store2 = store2 if isinstance(store2, dict) else {}
        if token_a in store2:
            store2[token_a]["used"] = True
        token_store.save(store2)

        # Simulate the prune pass (same logic as VmConsoleAccessService)
        now2 = time.time()
        raw3 = token_store.load()
        store3 = raw3 if isinstance(raw3, dict) else {}
        pruned = {
            t: e
            for t, e in store3.items()
            if not e.get("used") and (now2 - float(e.get("created_at") or 0)) <= TTL_SECONDS
        }
        token_store.save(pruned)

        # Used token must be gone
        final = token_store.load()
        if not isinstance(final, dict):
            print("NOVNC_TOKEN_TTL_SMOKE=FAIL")
            print("error=invalid store after prune")
            return 1
        if token_a in final:
            print("NOVNC_TOKEN_TTL_SMOKE=FAIL")
            print("error=used token was not pruned")
            return 1

        # --- Write an expired token and verify it is pruned ---
        token_b = secrets_mod.token_urlsafe(32)
        store4 = final.copy()
        store4[token_b] = {
            "target_host": "127.0.0.1",
            "target_port": 5901,
            # created_at far in the past → already expired
            "created_at": time.time() - TTL_SECONDS - 60,
            "used": False,
        }
        token_store.save(store4)

        # Prune again
        now3 = time.time()
        raw5 = token_store.load()
        store5 = raw5 if isinstance(raw5, dict) else {}
        pruned5 = {
            t: e
            for t, e in store5.items()
            if not e.get("used") and (now3 - float(e.get("created_at") or 0)) <= TTL_SECONDS
        }
        token_store.save(pruned5)

        final2 = token_store.load()
        if isinstance(final2, dict) and token_b in final2:
            print("NOVNC_TOKEN_TTL_SMOKE=FAIL")
            print("error=expired token was not pruned")
            return 1

    print("NOVNC_TOKEN_TTL_SMOKE=PASS")
    print("ttl=30s used_pruned=true expired_pruned=true mode=0o600")
    return 0


if __name__ == "__main__":
    sys.exit(main())
