#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request


def _request_json(url: str, *, method: str = "GET", data: dict | None = None, token: str | None = None, timeout: float = 15.0) -> tuple[int, dict]:
    payload = None
    headers = {"Accept": "application/json"}
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    ctx = ssl._create_unverified_context() if url.startswith("https://") else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return int(resp.status), json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return int(exc.code), parsed


def _virsh_qga(domain: str, payload: dict) -> dict:
    proc = subprocess.run(
        ["virsh", "qemu-agent-command", domain, json.dumps(payload)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "virsh qemu-agent-command failed")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid qga json: {proc.stdout!r}") from exc


def _guest_exec(domain: str, shell_command: str, timeout_seconds: float = 60.0) -> tuple[int, str, str]:
    start = _virsh_qga(
        domain,
        {
            "execute": "guest-exec",
            "arguments": {
                "path": "/bin/bash",
                "arg": ["-lc", shell_command],
                "capture-output": True,
            },
        },
    )
    pid = int(start.get("return", {}).get("pid") or 0)
    if pid <= 0:
        raise RuntimeError(f"guest-exec did not return pid: {start}")

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = _virsh_qga(
            domain,
            {"execute": "guest-exec-status", "arguments": {"pid": pid}},
        ).get("return", {})
        if status.get("exited"):
            exitcode = int(status.get("exitcode") or 0)
            out_data = status.get("out-data") or ""
            err_data = status.get("err-data") or ""
            stdout = base64.b64decode(out_data).decode("utf-8", errors="replace") if out_data else ""
            stderr = base64.b64decode(err_data).decode("utf-8", errors="replace") if err_data else ""
            return exitcode, stdout, stderr
        time.sleep(0.5)

    raise TimeoutError(f"guest-exec timeout after {timeout_seconds}s (pid={pid})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan 01 runtime smoke: VM-side stream-server register/config/events")
    parser.add_argument("--api-base", default=os.environ.get("BEAGLE_API_BASE", "https://srv1.beagle-os.com/beagle-api/api/v1"))
    parser.add_argument("--vmid", type=int, default=int(os.environ.get("BEAGLE_SMOKE_VMID", "100")))
    parser.add_argument("--domain", default=os.environ.get("BEAGLE_SMOKE_DOMAIN", ""))
    parser.add_argument("--username", default=os.environ.get("BEAGLE_SMOKE_USER", "admin"))
    parser.add_argument("--password", default=os.environ.get("BEAGLE_SMOKE_PASS", ""))
    args = parser.parse_args()

    if not args.password:
        print("ERROR: provide --password or BEAGLE_SMOKE_PASS", file=sys.stderr)
        return 2

    api_base = args.api_base.rstrip("/")
    domain = args.domain.strip() or f"beagle-{int(args.vmid)}"

    status, login = _request_json(
        f"{api_base}/auth/login",
        method="POST",
        data={"username": args.username, "password": args.password},
    )
    if status != 200 or not login.get("ok"):
        print(f"ERROR: auth/login failed status={status} payload={login}", file=sys.stderr)
        return 3

    token = str(login.get("access_token") or "").strip()
    if not token:
        print("ERROR: auth/login response missing access_token", file=sys.stderr)
        return 4

    # VM-side register/config/events flow executed through qemu guest agent.
    cmd = f"""
set -euo pipefail
API='{api_base}'
TOK='{token}'
VMID='{int(args.vmid)}'

code_reg=$(curl -k -sS -o /tmp/beagle-stream-register.json -w '%{{http_code}}' -X POST "$API/streams/register" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOK" --data '{{"vm_id":'"$VMID"',"stream_server_id":"vm-stream-smoke","host":"127.0.0.1","port":47984,"wireguard_active":true}}') # tls-bypass-allowlist: local guest loopback smoke against self-signed stream API

code_cfg=$(curl -k -sS -o /tmp/beagle-stream-config.json -w '%{{http_code}}' -H "Authorization: Bearer $TOK" "$API/streams/$VMID/config?wireguard_active=true") # tls-bypass-allowlist: local guest loopback smoke against self-signed stream API

code_evt=$(curl -k -sS -o /tmp/beagle-stream-event.json -w '%{{http_code}}' -X POST "$API/streams/$VMID/events" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOK" --data '{{"event_type":"session.start","details":{{"source":"vm-smoke","wireguard_active":true}}}}') # tls-bypass-allowlist: local guest loopback smoke against self-signed stream API

echo "register_http=$code_reg"
echo "config_http=$code_cfg"
echo "events_http=$code_evt"

[[ "$code_reg" == "201" ]]
[[ "$code_cfg" == "200" ]]
[[ "$code_evt" == "200" ]]

echo "PLAN01_STREAM_VM_REGISTER=PASS"
""".strip()

    try:
        exitcode, stdout, stderr = _guest_exec(domain, cmd, timeout_seconds=90.0)
    except Exception as exc:
        print(f"ERROR: guest-exec failed on domain={domain}: {exc}", file=sys.stderr)
        return 5

    if stdout:
        print(stdout.rstrip())
    if stderr:
        print(stderr.rstrip(), file=sys.stderr)

    if exitcode != 0:
        print(f"ERROR: VM smoke command failed with exitcode={exitcode}", file=sys.stderr)
        return 6

    if "PLAN01_STREAM_VM_REGISTER=PASS" not in stdout:
        print("ERROR: PASS marker missing", file=sys.stderr)
        return 7

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
