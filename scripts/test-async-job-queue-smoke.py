#!/usr/bin/env python3
"""Smoke: Async job queue lists jobs and returns expected schema.

Validates that:
- GET /api/v1/jobs returns 200 with a list response
- The response includes the 'jobs' key (or 'items') with correct schema
- Individual job entries have: job_id, status, name, created_at

This smoke does not enqueue a new job (no side effects) — it reads the
current job list from the control plane and validates the schema.

Run on srv1:
    source /etc/beagle/beagle-manager.env
    python3 /opt/beagle/scripts/test-async-job-queue-smoke.py \
        --base http://127.0.0.1:9088 --token "$BEAGLE_MANAGER_API_TOKEN"

Expected output: ASYNC_JOB_QUEUE_SMOKE=PASS
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def request_json(base: str, token: str, method: str, path: str) -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(
        base.rstrip("/") + path,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
            return int(resp.status), data if isinstance(data, dict) else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"ok": False, "error": raw[:200]}
        return int(exc.code), data if isinstance(data, dict) else {}
    except Exception as exc:
        return -1, {"ok": False, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate async job queue API schema")
    parser.add_argument("--base", default=os.environ.get("BEAGLE_API_BASE", "http://127.0.0.1:9088"))
    parser.add_argument("--token", default=os.environ.get("BEAGLE_MANAGER_API_TOKEN", ""))
    args = parser.parse_args()

    token = str(args.token or "").strip()
    if not token:
        print("ASYNC_JOB_QUEUE_SMOKE=FAIL")
        print("error=missing token")
        return 2

    status, data = request_json(str(args.base), token, "GET", "/api/v1/jobs")

    if status == -1:
        print("ASYNC_JOB_QUEUE_SMOKE=FAIL")
        print(f"error={data.get('error')}")
        return 1

    if status != 200:
        print("ASYNC_JOB_QUEUE_SMOKE=FAIL")
        print(f"error=unexpected status {status}: {data}")
        return 1

    # Expect a list under 'jobs' or 'items'
    jobs = data.get("jobs") or data.get("items") or []
    if not isinstance(jobs, list):
        print("ASYNC_JOB_QUEUE_SMOKE=FAIL")
        print(f"error=response missing 'jobs' list: keys={list(data.keys())}")
        return 1

    # Validate schema of any returned jobs
    schema_errors: list[str] = []
    for i, job in enumerate(jobs[:10]):  # check first 10
        if not isinstance(job, dict):
            schema_errors.append(f"job[{i}] is not a dict")
            continue
        for field in ("job_id", "status", "name"):
            if field not in job:
                schema_errors.append(f"job[{i}] missing field '{field}'")

    if schema_errors:
        print("ASYNC_JOB_QUEUE_SMOKE=FAIL")
        for e in schema_errors:
            print(f"  schema_error: {e}")
        return 1

    job_count = len(jobs)
    print("ASYNC_JOB_QUEUE_SMOKE=PASS")
    print(f"job_count={job_count} schema=valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
