#!/usr/bin/env python3
"""
Plan 12 — GPU-Inventory smoke test.

Verifies that:
1. GET /api/v1/virtualization/gpus returns {"ok": true, "gpus": [...]} with valid structure.
2. GET /api/v1/virtualization/overview returns a "gpus" key with correct schema.

Usage:
  python3 scripts/test-gpu-inventory-smoke.py --host 127.0.0.1 --port 9088

Environment:
  BEAGLE_MANAGER_API_TOKEN  — required auth token
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request


def _token() -> str:
    tok = os.environ.get("BEAGLE_MANAGER_API_TOKEN", "")
    if not tok:
        sys.exit("ERROR: BEAGLE_MANAGER_API_TOKEN not set")
    return tok


def _get(base_url: str, path: str) -> dict:
    req = urllib.request.Request(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {_token()}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def check_gpu_list(base_url: str) -> None:
    data = _get(base_url, "/api/v1/virtualization/gpus")
    assert "gpus" in data, f"missing 'gpus' key: {data}"
    gpus = data["gpus"]
    assert isinstance(gpus, list), f"gpus must be list, got {type(gpus)}"
    for gpu in gpus:
        assert "pci_address" in gpu or "pci" in gpu, f"gpu entry missing pci key: {gpu}"
        assert "vendor" in gpu or "model" in gpu, f"gpu entry missing vendor/model: {gpu}"
    print(f"  gpu_list: ok ({len(gpus)} GPU(s) found)")


def check_overview_gpus(base_url: str) -> None:
    data = _get(base_url, "/api/v1/virtualization/overview")
    assert "gpus" in data, f"missing 'gpus' key in overview: {data}"
    assert isinstance(data["gpus"], list), f"gpus must be list: {data['gpus']}"
    assert "gpu_count" in data, f"missing gpu_count in overview: {data}"
    assert isinstance(data["gpu_count"], int), f"gpu_count must be int: {data['gpu_count']}"
    print(f"  overview_gpus: ok (gpu_count={data['gpu_count']})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9088)
    args = parser.parse_args()
    base_url = f"http://{args.host}:{args.port}"

    results: dict[str, str] = {}
    failures: list[str] = []

    for name, fn in [
        ("gpu_list", lambda: check_gpu_list(base_url)),
        ("overview_gpus", lambda: check_overview_gpus(base_url)),
    ]:
        try:
            fn()
            results[name] = "ok"
        except Exception as exc:
            results[name] = f"FAIL: {exc}"
            failures.append(name)

    print()
    for k, v in results.items():
        print(f"  {k}: {v}")

    if failures:
        print(f"\nPLAN12_GPU_SMOKE=FAIL ({', '.join(failures)})")
        sys.exit(1)
    print("\nPLAN12_GPU_SMOKE=PASS")


if __name__ == "__main__":
    main()
