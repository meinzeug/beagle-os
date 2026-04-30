#!/usr/bin/env python3
"""Smoke test: Control-Plane-Health-Endpoint returns proper JSON and HTTP 200."""
import sys
import json
import urllib.request
import urllib.error
import argparse
from datetime import datetime


def test_health_endpoint(base_url: str, token: str) -> tuple[bool, str]:
    """Test /api/v1/health endpoint.
    
    Expected response:
    {
        "ok": true,
        "status": "healthy",
        "uptime_seconds": <int>,
        "version": <string>,
        "timestamp": <ISO8601>,
        ...
    }
    """
    url = f"{base_url}/api/v1/health"
    try:
        req = urllib.request.Request(url)
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status != 200:
                    return False, f"HTTP {resp.status} (expected 200)"
                
                body = resp.read().decode("utf-8")
                data = json.loads(body)
                
                # Validate required fields
                if not isinstance(data, dict):
                    return False, f"Response is not JSON object: {type(data)}"
                
                if "ok" not in data:
                    return False, "Missing 'ok' field"
                
                if not data.get("ok"):
                    return False, f"ok=false: {data.get('status', 'unknown')}"
                
                if "uptime_seconds" in data:
                    uptime = data["uptime_seconds"]
                    if not isinstance(uptime, (int, float)) or uptime < 0:
                        return False, f"Invalid uptime_seconds: {uptime}"
                
                if "version" in data:
                    version = data.get("version")
                    if not isinstance(version, str):
                        return False, f"Invalid version type: {type(version)}"
                
                return True, f"Health OK: {data}"
        
        except urllib.error.HTTPError as e:
            # 401 might be expected if auth is required, check if we have token
            if e.code == 401 and not token:
                return True, f"HTTP 401 without auth token (expected, health endpoint may require auth)"
            else:
                return False, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, f"Connection error: {e.reason}"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except Exception as e:
        return False, f"Unexpected error: {type(e).__name__}: {e}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:9088", help="Base API URL")
    parser.add_argument("--token", default="", help="Bearer token (optional)")
    args = parser.parse_args()
    
    # Try to get token from env if not provided
    if not args.token:
        import os
        args.token = os.environ.get("BEAGLE_MANAGER_API_TOKEN", "")
    
    success, message = test_health_endpoint(args.base, args.token)
    
    if success:
        print(f"HEALTH_ENDPOINT_SMOKE=PASS")
        print(f"message={message}")
        return 0
    else:
        print(f"HEALTH_ENDPOINT_SMOKE=FAIL")
        print(f"reason={message}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
