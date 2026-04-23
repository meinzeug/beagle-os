#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def request_json(base: str, token: str, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + path,
        method=method,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status = int(resp.status)
            raw = resp.read().decode("utf-8")
            data = json.loads(raw) if raw.strip() else {}
            return status, data if isinstance(data, dict) else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"ok": False, "error": raw}
        return int(exc.code), data if isinstance(data, dict) else {"ok": False, "error": "invalid error payload"}


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_smoke(*, base: str, token: str) -> dict[str, Any]:
    suffix = int(time.time())
    pool_id = f"stream-health-active-{suffix}"
    vmid = 98000 + (suffix % 1000)
    user_id = "stream-health-smoke-user"

    result: dict[str, Any] = {"pool_id": pool_id, "vmid": vmid, "steps": []}

    def step(name: str, status: int, payload: dict[str, Any]) -> None:
        result["steps"].append({"step": name, "status": status, "ok": bool(payload.get("ok"))})

    create_pool_payload = {
        "pool_id": pool_id,
        "template_id": "tpl-smoke",
        "mode": "floating_non_persistent",
        "min_pool_size": 1,
        "max_pool_size": 2,
        "warm_pool_size": 1,
        "cpu_cores": 2,
        "memory_mib": 4096,
        "storage_pool": "local",
    }
    register_payload = {"vmid": vmid}
    entitlement_payload = {"action": "set", "users": [user_id], "groups": []}
    allocate_payload = {"user_id": user_id}
    health_payload = {
        "pool_id": pool_id,
        "vmid": vmid,
        "stream_health": {
            "rtt_ms": 17,
            "fps": 60,
            "dropped_frames": 1,
            "encoder_load": 74,
            "updated_at": "2026-04-23T18:00:00Z",
        },
    }

    # Best-effort cleanup from previous interrupted runs with same id.
    request_json(base, token, "DELETE", f"/api/v1/pools/{pool_id}")

    create_status, create_data = request_json(base, token, "POST", "/api/v1/pools", create_pool_payload)
    step("create_pool", create_status, create_data)
    ensure(create_status == 201 and create_data.get("ok") is True, f"create_pool failed: {create_status} {create_data}")

    register_status, register_data = request_json(base, token, "POST", f"/api/v1/pools/{pool_id}/vms", register_payload)
    step("register_vm", register_status, register_data)
    ensure(register_status == 201 and register_data.get("ok") is True, f"register_vm failed: {register_status} {register_data}")

    entitlement_status, entitlement_data = request_json(
        base,
        token,
        "POST",
        f"/api/v1/pools/{pool_id}/entitlements",
        entitlement_payload,
    )
    step("set_entitlements", entitlement_status, entitlement_data)
    ensure(
        entitlement_status == 200 and entitlement_data.get("ok") is True,
        f"set_entitlements failed: {entitlement_status} {entitlement_data}",
    )

    allocate_status, allocate_data = request_json(base, token, "POST", f"/api/v1/pools/{pool_id}/allocate", allocate_payload)
    step("allocate_session", allocate_status, allocate_data)
    ensure(allocate_status == 200 and allocate_data.get("ok") is True, f"allocate failed: {allocate_status} {allocate_data}")
    ensure(int(allocate_data.get("vmid") or 0) == vmid, "allocated vmid mismatch")

    health_status, health_data = request_json(base, token, "POST", "/api/v1/sessions/stream-health", health_payload)
    step("post_stream_health", health_status, health_data)
    ensure(health_status == 200 and health_data.get("ok") is True, f"stream-health update failed: {health_status} {health_data}")

    sessions_status, sessions_data = request_json(base, token, "GET", "/api/v1/sessions")
    step("get_sessions", sessions_status, sessions_data)
    ensure(sessions_status == 200 and sessions_data.get("ok") is True, f"get_sessions failed: {sessions_status} {sessions_data}")
    sessions = sessions_data.get("sessions") if isinstance(sessions_data.get("sessions"), list) else []

    target = None
    for session in sessions:
        if not isinstance(session, dict):
            continue
        if str(session.get("pool_id") or "") == pool_id and int(session.get("vmid") or 0) == vmid:
            target = session
            break

    ensure(target is not None, "active session not found in /api/v1/sessions")
    ensure(str(target.get("state") or "") == "in_use", f"session state mismatch: {target}")
    health = target.get("stream_health") if isinstance(target.get("stream_health"), dict) else {}
    ensure(health.get("rtt_ms") == 17, f"rtt mismatch: {health}")
    ensure(health.get("fps") == 60, f"fps mismatch: {health}")
    ensure(health.get("dropped_frames") == 1, f"dropped_frames mismatch: {health}")
    ensure(health.get("encoder_load") == 74, f"encoder_load mismatch: {health}")

    release_status, release_data = request_json(
        base,
        token,
        "POST",
        f"/api/v1/pools/{pool_id}/release",
        {"vmid": vmid, "user_id": user_id},
    )
    step("release_session", release_status, release_data)
    ensure(release_status == 200 and release_data.get("ok") is True, f"release failed: {release_status} {release_data}")

    delete_status, delete_data = request_json(base, token, "DELETE", f"/api/v1/pools/{pool_id}")
    step("delete_pool", delete_status, delete_data)
    ensure(delete_status == 200 and delete_data.get("ok") is True, f"delete failed: {delete_status} {delete_data}")

    result["ok"] = True
    result["stream_health"] = health
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate stream-health visibility for active sessions via pool/session API.")
    parser.add_argument("--base", default=os.environ.get("BEAGLE_API_BASE", "http://127.0.0.1:9088"), help="Base URL to control plane API host")
    parser.add_argument("--token", default=os.environ.get("BEAGLE_MANAGER_API_TOKEN", ""), help="Bearer token")
    args = parser.parse_args()

    token = str(args.token or "").strip()
    if not token:
        print("STREAM_HEALTH_ACTIVE_RESULT=FAIL")
        print("error=missing token (use --token or BEAGLE_MANAGER_API_TOKEN)")
        return 1

    try:
        payload = run_smoke(base=str(args.base), token=token)
        print("STREAM_HEALTH_ACTIVE_RESULT=PASS")
        print("STREAM_HEALTH_ACTIVE_STEPS=" + json.dumps(payload.get("steps", []), separators=(",", ":")))
        print("STREAM_HEALTH_ACTIVE_VALUES=" + json.dumps(payload.get("stream_health", {}), separators=(",", ":")))
        return 0
    except Exception as exc:
        print("STREAM_HEALTH_ACTIVE_RESULT=FAIL")
        print("error=" + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
