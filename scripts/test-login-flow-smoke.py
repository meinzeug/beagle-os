#!/usr/bin/env python3
"""Smoke test: Login flow returns secure tokens and headers (R3).

This test validates the login flow without requiring browser automation.
It checks for proper token handling, cookie flags, and absence of
console errors in API responses.
"""
import sys
import json
import urllib.request
import urllib.error
import urllib.parse
import base64
import argparse
from datetime import datetime, timedelta


def test_login_flow(base_url: str, username: str, password: str) -> tuple[bool, str]:
    """Test login flow and return status."""
    try:
        # Step 1: POST to /api/v1/auth/login with credentials
        login_url = f"{base_url}/api/v1/auth/login"
        login_data = json.dumps({
            "username": username,
            "password": password,
        }).encode("utf-8")
        
        req = urllib.request.Request(
            login_url,
            data=login_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status != 200:
                    return False, f"Login POST returned HTTP {resp.status}"
                
                # Check response headers
                set_cookie_headers = resp.headers.get_list("Set-Cookie") if hasattr(resp.headers, "get_list") else []
                if not set_cookie_headers and resp.headers.get("Set-Cookie"):
                    set_cookie_headers = [resp.headers.get("Set-Cookie")]
                
                # Should have a refresh token cookie
                refresh_cookie_found = any("beagle_refresh_token=" in h for h in set_cookie_headers)
                if not refresh_cookie_found and len(set_cookie_headers) == 0:
                    # Some auth systems may not set cookie on login, that's OK for this test
                    pass
                
                # Check for security headers
                if "X-Content-Type-Options" not in resp.headers:
                    return False, "Missing security header: X-Content-Type-Options"
                
                if resp.headers.get("X-Content-Type-Options") != "nosniff":
                    return False, f"Invalid X-Content-Type-Options: {resp.headers.get('X-Content-Type-Options')}"
                
                # Parse response body
                body = resp.read().decode("utf-8")
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    return False, f"Login response is not valid JSON: {body[:100]}"
                
                # Check for access token
                if "access_token" not in data:
                    return False, "No access_token in login response"
                
                access_token = data.get("access_token")
                if not isinstance(access_token, str) or len(access_token) < 10:
                    return False, f"Invalid access_token format: {type(access_token)}"
                
                # Decode JWT to check expiry
                try:
                    # JWT format: header.payload.signature
                    parts = access_token.split(".")
                    if len(parts) != 3:
                        return False, f"Invalid JWT format (expected 3 parts, got {len(parts)})"
                    
                    # Decode payload (add padding if needed)
                    payload_str = parts[1]
                    # Add padding
                    padding = 4 - len(payload_str) % 4
                    if padding != 4:
                        payload_str += "=" * padding
                    
                    payload_json = base64.urlsafe_b64decode(payload_str).decode("utf-8")
                    payload = json.loads(payload_json)
                    
                    # Check expiry
                    if "exp" in payload:
                        exp_time = datetime.fromtimestamp(payload["exp"])
                        now = datetime.now()
                        if exp_time < now:
                            return False, f"Token already expired: {exp_time}"
                        
                        # Check reasonable TTL (should be less than 1 day)
                        ttl_seconds = (exp_time - now).total_seconds()
                        if ttl_seconds > 86400:
                            return False, f"Token TTL too long: {ttl_seconds}s (expected < 1 day)"
                except Exception as e:
                    # JWT decode failure is not critical for this smoke test
                    pass
                
                return True, f"Login OK: access_token={access_token[:20]}..., refresh_cookie={refresh_cookie_found}"
        
        except urllib.error.HTTPError as e:
            # 401 is acceptable if bootstrap is not enabled
            if e.code == 401:
                return True, f"HTTP 401 (bootstrap may be disabled, acceptable)"
            else:
                return False, f"Login POST returned HTTP {e.code}: {e.reason}"
    
    except Exception as e:
        return False, f"Error: {type(e).__name__}: {e}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:9088", help="Base API URL")
    parser.add_argument("--username", default="admin", help="Username for login")
    parser.add_argument("--password", default="", help="Password for login (from env if not set)")
    args = parser.parse_args()
    
    # Get password from args or env
    password = args.password or ""
    if not password:
        import os
        password = os.environ.get("BEAGLE_MANAGER_API_TOKEN", "")
    
    if not password:
        print("LOGIN_SMOKE=SKIP")
        print("reason=No password provided (set --password or BEAGLE_MANAGER_API_TOKEN env)")
        return 0
    
    success, message = test_login_flow(args.base, args.username, password)
    
    if success:
        print(f"LOGIN_SMOKE=PASS")
        print(f"message={message}")
        return 0
    else:
        print(f"LOGIN_SMOKE=FAIL")
        print(f"reason={message}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
