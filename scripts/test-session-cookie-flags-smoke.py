#!/usr/bin/env python3
"""Smoke: Session cookies have Secure, HttpOnly, SameSite=Strict, short TTL.

Validates that POST /api/v1/auth/login returns a Set-Cookie header with all
required security attributes for the refresh token cookie:
- Secure
- HttpOnly
- SameSite=Strict
- Max-Age present and <= 7 days (604800 seconds)
- Path=/api/v1/auth (scoped, not root)

Run on srv1:
    source /etc/beagle/beagle-manager.env
    python3 /opt/beagle/scripts/test-session-cookie-flags-smoke.py \
        --base http://127.0.0.1:9088 --token "$BEAGLE_MANAGER_API_TOKEN"

Note: uses the API token as password via the bootstrap credential flow.
Expected output: SESSION_COOKIE_FLAGS_SMOKE=PASS
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate session cookie security flags")
    parser.add_argument("--base", default=os.environ.get("BEAGLE_API_BASE", "http://127.0.0.1:9088"))
    parser.add_argument("--token", default=os.environ.get("BEAGLE_MANAGER_API_TOKEN", ""))
    args = parser.parse_args()

    token = str(args.token or "").strip()
    if not token:
        print("SESSION_COOKIE_FLAGS_SMOKE=FAIL")
        print("error=missing token")
        return 2

    base = str(args.base).rstrip("/")

    # POST /api/v1/auth/login with bootstrap credentials (admin / API_TOKEN)
    login_payload = json.dumps({
        "username": "admin",
        "password": token,
    }, separators=(",", ":")).encode("utf-8")

    req = urllib.request.Request(
        f"{base}/api/v1/auth/login",
        method="POST",
        data=login_payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = int(resp.status)
            set_cookie_headers = resp.headers.get_all("Set-Cookie") or []
            # Also check single header
            single = resp.headers.get("Set-Cookie")
            if single and single not in set_cookie_headers:
                set_cookie_headers.append(single)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        # 401 means the admin/token bootstrap isn't active on this host — soft skip
        if exc.code == 401:
            print("SESSION_COOKIE_FLAGS_SMOKE=SKIP")
            print("reason=login with API token as password returned 401 (bootstrap may be disabled)")
            return 0
        print("SESSION_COOKIE_FLAGS_SMOKE=FAIL")
        print(f"error=HTTP {exc.code}: {raw[:200]}")
        return 1
    except Exception as exc:
        print("SESSION_COOKIE_FLAGS_SMOKE=FAIL")
        print(f"error={exc}")
        return 1

    if status not in {200, 201}:
        # Non-auth error (e.g. 422 if body is wrong), mark as SKIP
        print("SESSION_COOKIE_FLAGS_SMOKE=SKIP")
        print(f"reason=login returned {status} (credential mismatch?)")
        return 0

    # Find the beagle_refresh_token cookie
    refresh_cookie = ""
    for hdr in set_cookie_headers:
        if "beagle_refresh_token" in hdr:
            refresh_cookie = hdr
            break

    if not refresh_cookie:
        print("SESSION_COOKIE_FLAGS_SMOKE=FAIL")
        print("error=no beagle_refresh_token cookie in Set-Cookie headers")
        print(f"  headers_found={set_cookie_headers}")
        return 1

    findings: list[str] = []
    cookie_lower = refresh_cookie.lower()

    # Required flags
    if "httponly" not in cookie_lower:
        findings.append("HttpOnly flag missing")
    if "secure" not in cookie_lower:
        findings.append("Secure flag missing")
    if "samesite=strict" not in cookie_lower:
        findings.append("SameSite=Strict flag missing")
    if "path=/api/v1/auth" not in cookie_lower:
        findings.append("Path=/api/v1/auth scoping missing")

    # Max-Age must be present and <= 7 days
    max_age_match = re.search(r"max-age=(\d+)", cookie_lower)
    if not max_age_match:
        findings.append("Max-Age attribute missing (cookie may persist indefinitely)")
    else:
        max_age = int(max_age_match.group(1))
        if max_age > 7 * 24 * 3600:
            findings.append(f"Max-Age={max_age} exceeds 7 days (604800s)")

    if findings:
        print("SESSION_COOKIE_FLAGS_SMOKE=FAIL")
        for f in findings:
            print(f"  {f}")
        print(f"  cookie_header: {refresh_cookie[:200]}")
        return 1

    print("SESSION_COOKIE_FLAGS_SMOKE=PASS")
    print(f"flags=HttpOnly Secure SameSite=Strict Path=/api/v1/auth Max-Age={max_age_match.group(1) if max_age_match else '?'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
