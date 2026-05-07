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


def _request_json(base: str, token: str, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
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
            payload_obj = json.loads(raw) if raw.strip() else {}
            return status, payload_obj if isinstance(payload_obj, dict) else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload_obj = json.loads(raw)
        except json.JSONDecodeError:
            payload_obj = {"ok": False, "error": raw}
        return int(exc.code), payload_obj if isinstance(payload_obj, dict) else {"ok": False, "error": "invalid error payload"}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_smoke(*, base: str, token: str) -> dict[str, Any]:
    suffix = int(time.time())
    pool_id = f"stream-input-matrix-{suffix}"
    template_id = "tpl-smoke"

    create_payload = {
        "pool_id": pool_id,
        "template_id": template_id,
        "mode": "floating_non_persistent",
        "min_pool_size": 1,
        "max_pool_size": 2,
        "warm_pool_size": 1,
        "cpu_cores": 2,
        "memory_mib": 4096,
        "storage_pool": "local",
        "streaming_profile": {
            "encoder": "auto",
            "color": "h265",
            "bitrate_kbps": 32000,
            "fps": 60,
            "resolution": "1920x1080",
            "hdr": False,
            "audio_input_enabled": True,
            "gamepad_redirect_enabled": True,
            "wacom_tablet_enabled": True,
            "usb_redirect_enabled": True,
        },
    }

    update_payload = {
        "streaming_profile": {
            "audio_input_enabled": False,
            "gamepad_redirect_enabled": False,
            "wacom_tablet_enabled": False,
            "usb_redirect_enabled": False,
        }
    }

    result: dict[str, Any] = {
        "pool_id": pool_id,
        "steps": [],
    }

    def step(name: str, status: int, payload: dict[str, Any]) -> None:
        result["steps"].append({"step": name, "status": status, "ok": bool(payload.get("ok"))})

    # cleanup best effort
    _request_json(base, token, "DELETE", f"/api/v1/pools/{pool_id}")

    create_status, create_data = _request_json(base, token, "POST", "/api/v1/pools", create_payload)
    step("create_pool", create_status, create_data)
    _assert(create_status == 201 and create_data.get("ok") is True, f"create failed: {create_status} {create_data}")

    get_status, get_data = _request_json(base, token, "GET", f"/api/v1/pools/{pool_id}")
    step("get_pool_after_create", get_status, get_data)
    _assert(get_status == 200 and get_data.get("ok") is True, f"get failed: {get_status} {get_data}")
    sp = get_data.get("streaming_profile") if isinstance(get_data.get("streaming_profile"), dict) else {}
    _assert(sp.get("audio_input_enabled") is True, "audio_input_enabled not true after create")
    _assert(sp.get("gamepad_redirect_enabled") is True, "gamepad_redirect_enabled not true after create")
    _assert(sp.get("wacom_tablet_enabled") is True, "wacom_tablet_enabled not true after create")
    _assert(sp.get("usb_redirect_enabled") is True, "usb_redirect_enabled not true after create")

    put_status, put_data = _request_json(base, token, "PUT", f"/api/v1/pools/{pool_id}", update_payload)
    step("update_pool_streaming_profile", put_status, put_data)
    _assert(put_status == 200 and put_data.get("ok") is True, f"update failed: {put_status} {put_data}")

    get2_status, get2_data = _request_json(base, token, "GET", f"/api/v1/pools/{pool_id}")
    step("get_pool_after_update", get2_status, get2_data)
    _assert(get2_status == 200 and get2_data.get("ok") is True, f"get2 failed: {get2_status} {get2_data}")
    sp2 = get2_data.get("streaming_profile") if isinstance(get2_data.get("streaming_profile"), dict) else {}
    _assert(sp2.get("audio_input_enabled") is False, "audio_input_enabled not false after update")
    _assert(sp2.get("gamepad_redirect_enabled") is False, "gamepad_redirect_enabled not false after update")
    _assert(sp2.get("wacom_tablet_enabled") is False, "wacom_tablet_enabled not false after update")
    _assert(sp2.get("usb_redirect_enabled") is False, "usb_redirect_enabled not false after update")

    del_status, del_data = _request_json(base, token, "DELETE", f"/api/v1/pools/{pool_id}")
    step("delete_pool", del_status, del_data)
    _assert(del_status == 200 and del_data.get("ok") is True, f"delete failed: {del_status} {del_data}")

    result["ok"] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate streaming input matrix flags roundtrip via Pool API.")
    parser.add_argument("--base", default=os.environ.get("BEAGLE_API_BASE", "http://127.0.0.1:9088"), help="Base URL to control plane API host")
    parser.add_argument("--token", default=os.environ.get("BEAGLE_MANAGER_API_TOKEN", ""), help="Bearer token")
    args = parser.parse_args()

    token = str(args.token or "").strip()
    if not token:
        print("STREAM_INPUT_MATRIX_RESULT=FAIL")
        print("error=missing token (use --token or BEAGLE_MANAGER_API_TOKEN)")
        return 1

    try:
        payload = run_smoke(base=str(args.base), token=token)
        print("STREAM_INPUT_MATRIX_RESULT=PASS")
        print("STREAM_INPUT_MATRIX_STEPS=" + json.dumps(payload.get("steps", []), separators=(",", ":")))
        return 0
    except Exception as exc:
        print("STREAM_INPUT_MATRIX_RESULT=FAIL")
        print("error=" + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
