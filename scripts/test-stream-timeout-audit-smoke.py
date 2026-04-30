#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any


def request_json(base: str, token: str, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + path,
        method=method,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
            return int(resp.status), data if isinstance(data, dict) else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"ok": False, "error": raw}
        return int(exc.code), data if isinstance(data, dict) else {"ok": False, "error": "invalid error payload"}


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate stream timeout event -> audit trail on /api/v1/streams/{vmid}/events")
    parser.add_argument("--base", default=os.environ.get("BEAGLE_API_BASE", "http://127.0.0.1:9088"))
    parser.add_argument("--token", default=os.environ.get("BEAGLE_MANAGER_API_TOKEN", ""))
    parser.add_argument("--vmid", type=int, default=int(os.environ.get("BEAGLE_SMOKE_VMID", "100")))
    parser.add_argument("--stream-server-id", default="timeout-audit-smoke")
    args = parser.parse_args()

    token = str(args.token or "").strip()
    if not token:
        print("STREAM_TIMEOUT_AUDIT_SMOKE=FAIL")
        print("error=missing token")
        return 2

    vmid = int(args.vmid)
    suffix = int(time.time())

    register_payload = {
        "vm_id": vmid,
        "stream_server_id": f"{args.stream_server_id}-{suffix}",
        "host": "127.0.0.1",
        "port": 47984,
        "wireguard_active": True,
    }
    register_status, register_data = request_json(str(args.base), token, "POST", "/api/v1/streams/register", register_payload)
    ensure(register_status in {201, 403}, f"register unexpected status: {register_status} {register_data}")
    if register_status == 403:
        print("STREAM_TIMEOUT_AUDIT_SMOKE=FAIL")
        print("error=stream register forbidden for vm policy/runtime")
        return 3

    timeout_payload = {
        "event_type": "session.timeout",
        "outcome": "error",
        "details": {
            "source": "stream-timeout-audit-smoke",
            "reason": "simulated timeout for audit proof",
            "timestamp": suffix,
        },
    }
    event_status, event_data = request_json(str(args.base), token, "POST", f"/api/v1/streams/{vmid}/events", timeout_payload)
    ensure(event_status == 200 and bool(event_data.get("ok")), f"timeout event post failed: {event_status} {event_data}")

    config_status, config_data = request_json(str(args.base), token, "GET", f"/api/v1/streams/{vmid}/config?wireguard_active=true")
    ensure(config_status == 200 and bool(config_data.get("ok")), f"stream config fetch failed: {config_status} {config_data}")
    last_event = (((config_data.get("config") or {}).get("registration") or {}).get("last_event") or {})
    ensure(str(last_event.get("event_type") or "") == "session.timeout", f"last_event mismatch: {last_event}")

    report_status, report_data = request_json(str(args.base), token, "GET", "/api/v1/audit/report?limit=50")
    ensure(report_status == 200, f"audit report failed: {report_status} {report_data}")
    events = report_data.get("events") if isinstance(report_data.get("events"), list) else []
    matches = [
        item
        for item in events
        if isinstance(item, dict)
        and str(item.get("action") or "") == "stream.session.timeout"
        and str(item.get("result") or "") in {"failure", "error"}
    ]
    ensure(matches, "stream.session.timeout audit event with result=failure|error not found")

    print("STREAM_TIMEOUT_AUDIT_SMOKE=PASS")
    print("STREAM_TIMEOUT_AUDIT_EVENT_COUNT=" + str(len(matches)))
    print("STREAM_TIMEOUT_AUDIT_EVENT_LATEST=" + json.dumps(matches[0], separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
