#!/usr/bin/env python3
"""Smoke: Prometheus /metrics endpoint exposes expected metric families.

Validates that:
- GET /metrics returns HTTP 200 with Prometheus text format
- All expected core metric families are present:
  beagle_http_requests_total, beagle_http_request_duration_seconds,
  beagle_vm_count, beagle_session_count, beagle_auth_failures_total,
  beagle_rate_limit_drops_total, beagle_process_start_time_seconds

Run on srv1:
    source /etc/beagle/beagle-manager.env
    python3 /opt/beagle/scripts/test-metrics-families-smoke.py \
        --base http://127.0.0.1:9088 --token "$BEAGLE_MANAGER_API_TOKEN"

Expected output: METRICS_FAMILIES_SMOKE=PASS
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request


EXPECTED_FAMILIES = [
    "beagle_http_requests_total",
    "beagle_http_request_duration_seconds",
    "beagle_vm_count",
    "beagle_session_count",
    "beagle_auth_failures_total",
    "beagle_rate_limit_drops_total",
    "beagle_process_start_time_seconds",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Prometheus metrics families on /metrics")
    parser.add_argument("--base", default=os.environ.get("BEAGLE_API_BASE", "http://127.0.0.1:9088"))
    parser.add_argument("--token", default=os.environ.get("BEAGLE_MANAGER_API_TOKEN", ""))
    args = parser.parse_args()

    url = args.base.rstrip("/") + "/metrics"
    req = urllib.request.Request(url, method="GET")
    # Include token if available (some deployments gate /metrics behind bearer)
    token = str(args.token or "").strip()
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = int(resp.status)
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print("METRICS_FAMILIES_SMOKE=FAIL")
        print(f"error=HTTP {exc.code}: {body[:200]}")
        return 1
    except Exception as exc:
        print("METRICS_FAMILIES_SMOKE=FAIL")
        print(f"error={exc}")
        return 1

    if status != 200:
        print("METRICS_FAMILIES_SMOKE=FAIL")
        print(f"error=unexpected status {status}")
        return 1

    missing = [name for name in EXPECTED_FAMILIES if name not in body]
    if missing:
        print("METRICS_FAMILIES_SMOKE=FAIL")
        print(f"error=missing metric families: {missing}")
        return 1

    print("METRICS_FAMILIES_SMOKE=PASS")
    found = [name for name in EXPECTED_FAMILIES if name in body]
    print(f"families_found={len(found)} ({', '.join(found[:3])}...)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
