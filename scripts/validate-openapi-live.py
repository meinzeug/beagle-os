#!/usr/bin/env python3
"""Validate generated OpenAPI v1 paths against a live API endpoint.

Validation rule: every documented path must not return HTTP 404.
Auth-required endpoints can return 401/403 and still count as present.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


VALID_STATUS = {200, 201, 202, 204, 400, 401, 403, 405, 409, 422}


def load_paths(coverage_file: Path) -> list[str]:
    paths: list[str] = []
    pattern = re.compile(r"^- `(/api/v1/[^`]+)`")
    for raw in coverage_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = pattern.match(raw.strip())
        if match:
            paths.append(match.group(1))
    return sorted(set(paths))


def check_path(base_url: str, path: str, token: str = "") -> tuple[int, str]:
    target_path = re.sub(r"\{[A-Za-z0-9_]+\}", "sample", path)
    target = f"{base_url.rstrip('/')}{target_path}"
    req = urllib.request.Request(target, method="GET")
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            return int(response.status), ""
    except urllib.error.HTTPError as exc:
        return int(exc.code), ""
    except urllib.error.URLError as exc:
        return 0, str(exc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate generated OpenAPI v1 paths against live API")
    parser.add_argument("--base-url", default="http://127.0.0.1:9088", help="Control-plane base URL")
    parser.add_argument(
        "--coverage-file",
        default="docs/api/openapi-v1-coverage.md",
        help="Path to generated coverage markdown",
    )
    parser.add_argument("--token", default="", help="Optional bearer token")
    args = parser.parse_args(argv)

    coverage_file = Path(args.coverage_file)
    if not coverage_file.exists():
        print(f"coverage file not found: {coverage_file}", file=sys.stderr)
        return 2

    paths = load_paths(coverage_file)
    if not paths:
        print("no API paths found in coverage file", file=sys.stderr)
        return 2

    failures: list[tuple[str, int, str]] = []
    checked = 0
    for path in paths:
        status, err = check_path(args.base_url, path, token=args.token)
        checked += 1
        if status in VALID_STATUS:
            continue
        failures.append((path, status, err))

    print(f"checked_paths={checked}")
    if failures:
        for path, status, err in failures:
            suffix = f" error={err}" if err else ""
            print(f"FAIL {path} status={status}{suffix}")
        return 1

    print("openapi-live-validation=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
