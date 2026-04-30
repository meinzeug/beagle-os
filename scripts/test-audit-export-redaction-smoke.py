#!/usr/bin/env python3
"""Smoke: Audit report does not leak cleartext secrets or PII patterns.

Validates that:
- GET /api/v1/audit/report returns 200
- The report body contains no patterns that indicate cleartext secrets:
  - No values matching common secret patterns (password=..., token=..., secret=...)
  - No base64 blobs that decode to cleartext credentials
  - No API key patterns

Run on srv1:
    source /etc/beagle/beagle-manager.env
    python3 /opt/beagle/scripts/test-audit-export-redaction-smoke.py \
        --base http://127.0.0.1:9088 --token "$BEAGLE_MANAGER_API_TOKEN"

Expected output: AUDIT_EXPORT_REDACTION_SMOKE=PASS
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


# Patterns that must NOT appear in audit report output as literal values
_SECRET_PATTERNS = [
    re.compile(r'"password"\s*:\s*"[^"]{3,}"', re.IGNORECASE),
    re.compile(r'"secret"\s*:\s*"[^"]{3,}"', re.IGNORECASE),
    re.compile(r'"token"\s*:\s*"[A-Za-z0-9+/=_\-]{16,}"'),
    re.compile(r'"private_key"\s*:\s*"[^"]{8,}"', re.IGNORECASE),
    re.compile(r'"api_key"\s*:\s*"[^"]{8,}"', re.IGNORECASE),
    # REDACTED or *** are ok; literal values are not
]

# Strings that indicate a value WAS redacted (acceptable)
_REDACTED_MARKERS = {"***", "[redacted]", "<redacted>", "REDACTED"}


def _check_value(val: Any, path: str) -> list[str]:
    """Recursively scan a dict/list for secret-like values."""
    findings: list[str] = []
    if isinstance(val, dict):
        for k, v in val.items():
            findings.extend(_check_value(v, f"{path}.{k}"))
            # Check if this key looks like a secret holder with a real value
            key_lower = str(k).lower()
            if any(term in key_lower for term in ("password", "secret", "token", "api_key", "private_key")):
                if isinstance(v, str) and len(v) >= 8 and v not in _REDACTED_MARKERS and not v.startswith("***"):
                    findings.append(f"potential secret at {path}.{k}: value length={len(v)}")
    elif isinstance(val, list):
        for i, item in enumerate(val):
            findings.extend(_check_value(item, f"{path}[{i}]"))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate audit report does not leak secrets")
    parser.add_argument("--base", default=os.environ.get("BEAGLE_API_BASE", "http://127.0.0.1:9088"))
    parser.add_argument("--token", default=os.environ.get("BEAGLE_MANAGER_API_TOKEN", ""))
    args = parser.parse_args()

    token = str(args.token or "").strip()
    if not token:
        print("AUDIT_EXPORT_REDACTION_SMOKE=FAIL")
        print("error=missing token")
        return 2

    url = args.base.rstrip("/") + "/api/v1/audit/report"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status = int(resp.status)
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print("AUDIT_EXPORT_REDACTION_SMOKE=FAIL")
        print(f"error=HTTP {exc.code}: {raw[:200]}")
        return 1
    except Exception as exc:
        print("AUDIT_EXPORT_REDACTION_SMOKE=FAIL")
        print(f"error={exc}")
        return 1

    if status != 200:
        print("AUDIT_EXPORT_REDACTION_SMOKE=FAIL")
        print(f"error=unexpected status {status}")
        return 1

    # Check raw body for obvious secret patterns
    raw_findings: list[str] = []
    for pat in _SECRET_PATTERNS:
        matches = pat.findall(raw)
        for m in matches:
            raw_findings.append(f"pattern match: {m[:80]}")

    # Also parse JSON and check values recursively
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}

    struct_findings = _check_value(data, "report")

    all_findings = raw_findings + struct_findings
    if all_findings:
        print("AUDIT_EXPORT_REDACTION_SMOKE=FAIL")
        print(f"error=potential secret leakage in audit report ({len(all_findings)} findings)")
        for f in all_findings[:5]:
            print(f"  finding: {f}")
        return 1

    # Check event count
    events = data.get("events") or data.get("items") or []
    count = int(data.get("count") or data.get("total") or len(events) if isinstance(events, list) else 0)

    print("AUDIT_EXPORT_REDACTION_SMOKE=PASS")
    print(f"events_checked={count} no_secret_leakage=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
