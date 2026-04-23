#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shlex
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def request_json(base: str, method: str, path: str, *, token: str = "", payload: dict[str, Any] | None = None, timeout: int = 25) -> tuple[int, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(base.rstrip("/") + path, method=method, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = int(resp.status)
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw.strip() else {}
            return status, data if isinstance(data, dict) else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"ok": False, "error": raw}
        return int(exc.code), data if isinstance(data, dict) else {"ok": False, "error": "invalid error payload"}


def request_text(base: str, method: str, path: str, *, token: str = "", timeout: int = 25) -> tuple[int, str]:
    headers = {"Accept": "*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base.rstrip("/") + path, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def extract_preset_b64(installer_script: str) -> str:
    # Pattern in installer scripts:
    # PVE_THIN_CLIENT_PRESET_B64="${PVE_THIN_CLIENT_PRESET_B64:-<base64>}"
    match = re.search(r"PVE_THIN_CLIENT_PRESET_B64=\"\$\{PVE_THIN_CLIENT_PRESET_B64:-([^\"}]+)\}\"", installer_script)
    if not match:
        raise ValueError("preset base64 not found in installer script")
    return str(match.group(1) or "").strip()


def parse_shell_assignment(line: str) -> tuple[str, str]:
    key, sep, raw_value = line.partition("=")
    if not sep:
        return "", ""
    key = key.strip()
    raw_value = raw_value.strip()
    if not key:
        return "", ""
    try:
        tokens = shlex.split(raw_value)
        value = tokens[0] if tokens else ""
    except ValueError:
        value = raw_value.strip("\"'")
    return key, value


def extract_enrollment_token_from_installer(installer_script: str) -> str:
    preset_b64 = extract_preset_b64(installer_script)
    try:
        decoded = base64.b64decode(preset_b64).decode("utf-8", errors="replace")
    except Exception as exc:
        raise ValueError(f"failed to decode preset base64: {exc}")

    enrollment_token = ""
    for line in decoded.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = parse_shell_assignment(line)
        if key == "PVE_THIN_CLIENT_PRESET_BEAGLE_ENROLLMENT_TOKEN":
            enrollment_token = value.strip()
            break

    if not enrollment_token:
        raise ValueError("enrollment token not found in decoded preset")
    return enrollment_token


def select_running_vmid(vms_payload: dict[str, Any], preferred_vmid: int) -> int:
    if preferred_vmid > 0:
        return preferred_vmid

    vms = vms_payload.get("vms") if isinstance(vms_payload.get("vms"), list) else []
    for item in vms:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().lower()
        if status != "running":
            continue
        vmid = int(item.get("vmid") or 0)
        if vmid > 0:
            return vmid
    raise ValueError("no running vm found")


def run_smoke(*, base: str, manager_token: str, vmid: int) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []

    def step(name: str, status: int, ok: bool, details: str = "") -> None:
        payload = {"step": name, "status": status, "ok": ok}
        if details:
            payload["details"] = details
        steps.append(payload)

    list_status, list_data = request_json(base, "GET", "/api/v1/vms", token=manager_token)
    step("list_vms", list_status, list_status == 200 and bool(list_data.get("ok") is not False))
    ensure(list_status == 200, f"list vms failed: {list_status} {list_data}")

    chosen_vmid = select_running_vmid(list_data, vmid)

    installer_status, installer_script = request_text(base, "GET", f"/api/v1/vms/{chosen_vmid}/installer.sh", token=manager_token)
    step("get_installer_script", installer_status, installer_status == 200)
    ensure(installer_status == 200, f"installer script fetch failed: {installer_status}")

    enrollment_token = extract_enrollment_token_from_installer(installer_script)
    ensure(enrollment_token, "missing enrollment token")

    endpoint_id = f"smoke-auto-pair-{int(time.time())}"
    enroll_payload = {
        "enrollment_token": enrollment_token,
        "endpoint_id": endpoint_id,
        "hostname": endpoint_id,
    }
    enroll_status, enroll_data = request_json(base, "POST", "/api/v1/endpoints/enroll", payload=enroll_payload)
    step("endpoint_enroll", enroll_status, enroll_status == 201 and bool(enroll_data.get("ok")))
    ensure(enroll_status == 201 and bool(enroll_data.get("ok")), f"endpoint enroll failed: {enroll_status} {enroll_data}")

    config = enroll_data.get("config") if isinstance(enroll_data.get("config"), dict) else {}
    endpoint_token = str(config.get("beagle_manager_token") or "").strip()
    ensure(endpoint_token, f"missing endpoint token in enroll response: {enroll_data}")

    pair_token_status, pair_token_data = request_json(
        base,
        "POST",
        "/api/v1/endpoints/moonlight/pair-token",
        token=endpoint_token,
        payload={"device_name": endpoint_id},
    )
    step("issue_pair_token", pair_token_status, pair_token_status == 201 and bool(pair_token_data.get("ok")))
    ensure(
        pair_token_status == 201 and bool(pair_token_data.get("ok")),
        f"pair-token issue failed: {pair_token_status} {pair_token_data}",
    )

    pairing_obj = pair_token_data.get("pairing") if isinstance(pair_token_data.get("pairing"), dict) else {}
    pairing_token = str(pairing_obj.get("token") or "").strip()
    ensure(pairing_token, f"missing pairing token: {pair_token_data}")

    exchange_status, exchange_data = request_json(
        base,
        "POST",
        "/api/v1/endpoints/moonlight/pair-exchange",
        token=endpoint_token,
        payload={"pairing_token": pairing_token},
    )
    step("pair_exchange", exchange_status, exchange_status == 200 and bool(exchange_data.get("ok")))
    ensure(exchange_status == 200 and bool(exchange_data.get("ok")), f"pair-exchange failed: {exchange_status} {exchange_data}")

    return {
        "ok": True,
        "vmid": chosen_vmid,
        "endpoint_id": endpoint_id,
        "steps": steps,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test Moonlight auto-pairing flow without manual PIN.")
    parser.add_argument("--base", default=os.environ.get("BEAGLE_API_BASE", "http://127.0.0.1:9088"), help="Control-plane base URL")
    parser.add_argument("--token", default=os.environ.get("BEAGLE_MANAGER_API_TOKEN", ""), help="Manager bearer token")
    parser.add_argument("--vmid", type=int, default=0, help="Optional VMID override (must be running)")
    args = parser.parse_args()

    token = str(args.token or "").strip()
    if not token:
        print("MOONLIGHT_AUTO_PAIR_RESULT=FAIL")
        print("error=missing token (use --token or BEAGLE_MANAGER_API_TOKEN)")
        return 1

    try:
        result = run_smoke(base=str(args.base), manager_token=token, vmid=int(args.vmid or 0))
        print("MOONLIGHT_AUTO_PAIR_RESULT=PASS")
        print("MOONLIGHT_AUTO_PAIR_VMID=" + str(result.get("vmid")))
        print("MOONLIGHT_AUTO_PAIR_ENDPOINT_ID=" + str(result.get("endpoint_id")))
        print("MOONLIGHT_AUTO_PAIR_STEPS=" + json.dumps(result.get("steps", []), separators=(",", ":")))
        return 0
    except Exception as exc:
        print("MOONLIGHT_AUTO_PAIR_RESULT=FAIL")
        print("error=" + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
