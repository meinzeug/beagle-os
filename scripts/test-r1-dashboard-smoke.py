#!/usr/bin/env python3
"""R1 dashboard/API smoke test for Beagle OS.

Checks that core dashboard endpoints load without 500 errors.
Usage:
  python3 scripts/test-r1-dashboard-smoke.py \
    --base-url https://srv1.beagle-os.com/beagle-api \
    --username admin --password '...'
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Iterable

import requests


@dataclass
class CheckResult:
    endpoint: str
    status: int
    ok: bool
    detail: str


ENDPOINTS = [
    "/api/v1/health",
    "/api/v1/vms",
    "/api/v1/pools",
    "/api/v1/policies",
    "/api/v1/audit/report",
    "/api/v1/audit/export-targets",
    "/api/v1/cluster/nodes",
    "/api/v1/virtualization/nodes",
]


def login(base_url: str, username: str, password: str, timeout: float) -> str:
    resp = requests.post(
        f"{base_url}/api/v1/auth/login",
        json={"username": username, "password": password},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    token = str(data.get("access_token") or "")
    if not token:
        raise RuntimeError(f"login failed: {data}")
    return token


def run_checks(base_url: str, token: str, timeout: float, endpoints: Iterable[str]) -> list[CheckResult]:
    out: list[CheckResult] = []
    headers = {"Authorization": f"Bearer {token}"}
    for ep in endpoints:
        url = f"{base_url}{ep}"
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            ok = resp.status_code < 500
            detail = "ok" if ok else (resp.text[:200].replace("\n", " "))
            out.append(CheckResult(endpoint=ep, status=resp.status_code, ok=ok, detail=detail))
        except Exception as exc:  # pragma: no cover
            out.append(CheckResult(endpoint=ep, status=0, ok=False, detail=str(exc)))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    token = login(base_url, args.username, args.password, args.timeout)
    checks = run_checks(base_url, token, args.timeout, ENDPOINTS)

    failed = [c for c in checks if not c.ok]
    summary = {
        "ok": len(failed) == 0,
        "checked": len(checks),
        "failed": len(failed),
        "results": [c.__dict__ for c in checks],
    }
    print(json.dumps(summary, indent=2))

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
