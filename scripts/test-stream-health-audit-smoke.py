#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from typing import Any


def request_json(url: str, *, token: str, timeout: int = 25) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run stream-health smoke and verify audit trail.")
    parser.add_argument("--base", default=os.environ.get("BEAGLE_API_BASE", "http://127.0.0.1:9088"))
    parser.add_argument("--token", default=os.environ.get("BEAGLE_MANAGER_API_TOKEN", ""))
    parser.add_argument(
        "--smoke-script",
        default=os.environ.get("BEAGLE_STREAM_HEALTH_SMOKE_SCRIPT", "/opt/beagle/scripts/test-stream-health-active-session-smoke.py"),
    )
    args = parser.parse_args()

    token = str(args.token or "").strip()
    if not token:
        print("STREAM_HEALTH_AUDIT_SMOKE=FAIL")
        print("error=missing token")
        return 2

    smoke = subprocess.run(
        [sys.executable, str(args.smoke_script), "--base", str(args.base), "--token", token],
        check=False,
        capture_output=True,
        text=True,
    )
    if smoke.stdout:
        print(smoke.stdout.rstrip())
    if smoke.stderr:
        print(smoke.stderr.rstrip(), file=sys.stderr)
    if smoke.returncode != 0:
        print("STREAM_HEALTH_AUDIT_SMOKE=FAIL")
        print(f"error=stream health smoke returned {smoke.returncode}")
        return 3

    report = request_json(f"{str(args.base).rstrip('/')}/api/v1/audit/report?limit=20", token=token)
    events = report.get("events") if isinstance(report.get("events"), list) else []
    matches = [item for item in events if isinstance(item, dict) and str(item.get("action") or "") == "session.stream_health.update"]

    if not matches:
        print("STREAM_HEALTH_AUDIT_SMOKE=FAIL")
        print("error=session.stream_health.update audit event not found")
        return 4

    latest = matches[0]
    print("STREAM_HEALTH_AUDIT_SMOKE=PASS")
    print("STREAM_HEALTH_AUDIT_COUNT=" + str(len(matches)))
    print("STREAM_HEALTH_AUDIT_LATEST=" + json.dumps(latest, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())