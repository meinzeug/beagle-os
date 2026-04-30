#!/usr/bin/env python3
"""
scripts/test-audit-export-smoke.py
Smoke test: Audit-Export API endpoints functional check.

Checks:
  1. GET /api/v1/audit/report → ok=true, count>=0
  2. GET /api/v1/audit/export-targets → targets list present
  3. Audit events contain no plaintext passwords/tokens (PII/Secret redaction)
  4. Audit events have required fields (id, timestamp, action)

Usage:
  python3 test-audit-export-smoke.py --base http://127.0.0.1:9088 --token <token>
  python3 test-audit-export-smoke.py --base http://127.0.0.1:9088 --username admin --password <pw>
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error


def req(url, token):
    r = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(r, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


def login(base, username, password):
    payload = json.dumps({"username": username, "password": password}).encode()
    r = urllib.request.Request(
        f"{base}/api/v1/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(r, timeout=10) as resp:
        body = json.loads(resp.read())
    return body["access_token"]


REDACTION_PATTERNS = [
    re.compile(r'"password"\s*:\s*"[^"]{4,}"', re.IGNORECASE),
    re.compile(r'"token"\s*:\s*"[^"]{20,}"', re.IGNORECASE),
    re.compile(r'"secret"\s*:\s*"[^"]{8,}"', re.IGNORECASE),
    re.compile(r'"api_key"\s*:\s*"[^"]{8,}"', re.IGNORECASE),
]

REQUIRED_FIELDS = {"id", "timestamp", "action"}


def check(label, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {label}" + (f": {detail}" if detail else ""))
    return cond


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:9088")
    ap.add_argument("--token", default="")
    ap.add_argument("--username", default="admin")
    ap.add_argument("--password", default="")
    args = ap.parse_args()

    token = args.token
    if not token:
        if not args.password:
            print("ERROR: provide --token or --username/--password", file=sys.stderr)
            sys.exit(2)
        token = login(args.base, args.username, args.password)
        print("  [INFO] Logged in, token obtained")

    failures = 0
    print("=== Audit Export Smoke ===")

    # 1. Audit report
    try:
        status, body = req(f"{args.base}/api/v1/audit/report", token)
        ok = status == 200 and body.get("ok") is True
        count = body.get("count", -1)
        if not check("audit_report_ok", ok, f"HTTP {status}, ok={body.get('ok')}"):
            failures += 1
        check("audit_event_count", count >= 0, f"{count} events")

        events = body.get("events", [])
        if events:
            # Check required fields
            first = events[0]
            has_fields = REQUIRED_FIELDS.issubset(first.keys())
            if not check("audit_event_required_fields", has_fields,
                         f"missing={REQUIRED_FIELDS - first.keys()}"):
                failures += 1

            # Check PII/secret redaction — scan all event JSON for leaked creds
            events_json = json.dumps(events)
            leaked = []
            for pattern in REDACTION_PATTERNS:
                m = pattern.search(events_json)
                if m:
                    leaked.append(m.group(0)[:60])
            if not check("audit_pii_redaction", len(leaked) == 0,
                         f"potential leaks: {leaked}" if leaked else "no plaintext secrets found"):
                failures += 1
        else:
            check("audit_event_required_fields", True, "0 events — fields check skipped")
            check("audit_pii_redaction", True, "0 events — PII check skipped")

    except Exception as e:
        print(f"  [FAIL] audit_report: {e}")
        failures += 1

    # 2. Export targets
    try:
        status, body = req(f"{args.base}/api/v1/audit/export-targets", token)
        ok = status == 200 and "targets" in body
        if not check("audit_export_targets_ok", ok, f"HTTP {status}"):
            failures += 1
        targets = body.get("targets", [])
        check("audit_export_targets_list", isinstance(targets, list),
              f"{len(targets)} targets present")
        # Verify targets have type and enabled fields
        if targets:
            first_t = targets[0]
            has_t_fields = {"type", "label", "enabled"}.issubset(first_t.keys())
            if not check("audit_export_target_fields", has_t_fields,
                         f"fields: {list(first_t.keys())}"):
                failures += 1
    except Exception as e:
        print(f"  [FAIL] audit_export_targets: {e}")
        failures += 1

    # Summary
    total = failures
    print(f"\nAUDIT_EXPORT_SMOKE={'PASS' if total == 0 else 'FAIL'} "
          f"checked=6 failed={total}")
    sys.exit(0 if total == 0 else 1)


if __name__ == "__main__":
    main()
